#!/usr/bin/env python3
"""Apply a dual-authorized key transition to a create-once, anchored ledger."""
from __future__ import annotations
import argparse,base64,hashlib,json,os,subprocess,tempfile
from datetime import datetime,timezone
from pathlib import Path
from typing import Any
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from cryptography.exceptions import InvalidSignature
ROOT=Path(__file__).resolve().parents[1]
def canonical(v:Any)->bytes:return json.dumps(v,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()
def sha_bytes(v:bytes)->str:return hashlib.sha256(v).hexdigest()
def load(path:Path):
 v=json.loads(path.read_bytes());
 if not isinstance(v,dict):raise SystemExit(f'JSON object required: {path}')
 return v
def keyring(value):
 out={};fps=set();signers=set()
 for row in value.get('keys',[]):
  key_id=row.get('key_id');signer=row.get('signer_id');raw=base64.b64decode(row.get('public_key',''),validate=True);key=Ed25519PublicKey.from_public_bytes(raw);fp=sha_bytes(raw)
  if key_id in out or signer in signers or fp in fps:raise SystemExit('duplicate key ID, signer identity, or cryptographic material')
  out[key_id]=(key,set(row.get('roles',[])),signer);signers.add(signer);fps.add(fp)
 return out
def verify(transition,keys):
 unsigned=dict(transition);sigs=unsigned.pop('signatures',None);roles=set();signers=set()
 if not isinstance(sigs,list):raise SystemExit('transition signatures missing')
 for sig in sigs:
  key_id=sig.get('key_id');entry=keys.get(key_id)
  if not entry:raise SystemExit('unknown transition signer')
  key,keyroles,signer=entry
  try:key.verify(base64.b64decode(sig.get('ed25519',''),validate=True),canonical(unsigned))
  except (InvalidSignature,ValueError,TypeError) as exc:raise SystemExit('invalid transition signature') from exc
  roles.update(keyroles);signers.add(signer)
 required=set(transition.get('required_approval_roles',[]))
 if not required.issubset(roles) or len(signers)<len(required):raise SystemExit('transition lacks independent required-role quorum')
def write_once(path:Path,data:bytes,mode=0o400):
 path.parent.mkdir(parents=True,exist_ok=True,mode=0o700);fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|getattr(os,'O_NOFOLLOW',0),mode)
 try:os.write(fd,data);os.fsync(fd)
 finally:os.close(fd)
def atomic(path:Path,data:bytes):
 path.parent.mkdir(parents=True,exist_ok=True,mode=0o700);fd,tmp=tempfile.mkstemp(prefix='.'+path.name+'.',dir=path.parent)
 try:
  os.fchmod(fd,0o400);os.write(fd,data);os.fsync(fd);os.close(fd);os.replace(tmp,path);d=os.open(path.parent,os.O_RDONLY);os.fsync(d);os.close(d)
 finally:
  try:os.close(fd)
  except OSError:pass
  try:os.unlink(tmp)
  except FileNotFoundError:pass
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--state',required=True);ap.add_argument('--transition',required=True);ap.add_argument('--approval-keyring',required=True);ap.add_argument('--ledger',required=True);ap.add_argument('--anchor-command',required=True);a=ap.parse_args()
 state_path=Path(a.state).absolute();transition_path=Path(a.transition).absolute();ledger=Path(a.ledger).absolute();state=load(state_path);transition=load(transition_path);verify(transition,keyring(load(Path(a.approval_keyring))))
 role=transition['key_role'];receipt=ledger/(sha_bytes(transition['transition_id'].encode())+'.json')
 if receipt.exists():raise SystemExit('transition replay detected')
 current=state.get('roles',{}).get(role)
 if not isinstance(current,dict):raise SystemExit('transition role missing from current state')
 if transition['from_epoch']!=current['epoch'] or transition['to_epoch']!=current['epoch']+1 or transition['old_key_id']!=current['key_id'] or transition['old_key_fingerprint']!=current['fingerprint']:raise SystemExit('transition does not continue current key epoch')
 if state.get('sequence',0)+1!=transition['to_epoch'] and state.get('last_transition_id') is not None:raise SystemExit('global transition sequence discontinuity')
 old={'epoch':current['epoch'],'key_id':current['key_id'],'fingerprint':current['fingerprint'],'valid_until':transition['effective_at']};history=list(current.get('historical_keys',[]));history.append(old)
 typ=transition['transition_type']
 if typ in {'ROTATE','CUSTODY_TRANSITION'}:new={'epoch':transition['to_epoch'],'status':'ACTIVE','key_id':transition['new_key_id'],'fingerprint':transition['new_key_fingerprint'],'effective_at':transition['effective_at'],'historical_keys':history}
 else:new={'epoch':transition['to_epoch'],'status':'EMERGENCY_DISABLED' if typ=='EMERGENCY_DISABLE' else 'REVOKED','key_id':current['key_id'],'fingerprint':current['fingerprint'],'effective_at':transition['effective_at'],'historical_keys':history}
 new_state=dict(state);new_state['sequence']=int(state.get('sequence',0))+1;new_state['last_transition_id']=transition['transition_id'];new_state['roles']=dict(state['roles']);new_state['roles'][role]=new
 previous=state.get('transition_chain_sha256','0'*64);new_state['transition_chain_sha256']=sha_bytes((previous+sha_bytes(canonical(transition))).encode())
 challenge={'transition_id':transition['transition_id'],'state_sha256':sha_bytes(canonical(new_state)),'previous_chain_sha256':previous,'new_chain_sha256':new_state['transition_chain_sha256']}
 proc=subprocess.run([a.anchor_command,'publish'],input=json.dumps(challenge),text=True,capture_output=True,timeout=30)
 if proc.returncode:raise SystemExit('remote anchor rejected transition')
 try:anchor=json.loads(proc.stdout)
 except Exception as exc:raise SystemExit('invalid remote anchor receipt') from exc
 if anchor.get('accepted') is not True or anchor.get('new_chain_sha256')!=new_state['transition_chain_sha256']:raise SystemExit('remote anchor receipt mismatch')
 record={'format_version':'1.0','transition_id':transition['transition_id'],'transition_sha256':sha_bytes(canonical(transition)),'previous_state_sha256':sha_bytes(canonical(state)),'new_state_sha256':sha_bytes(canonical(new_state)),'anchor_receipt':anchor,'applied_at':datetime.now(timezone.utc).isoformat()}
 write_once(receipt,(json.dumps(record,indent=2,sort_keys=True)+'\n').encode());atomic(state_path,(json.dumps(new_state,indent=2,sort_keys=True)+'\n').encode());print(json.dumps(record,indent=2,sort_keys=True))
if __name__=='__main__':main()
