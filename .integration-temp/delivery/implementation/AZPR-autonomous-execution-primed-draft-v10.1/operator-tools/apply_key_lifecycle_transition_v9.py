#!/usr/bin/env python3
"""Atomically stage, anchor, activate, and recover a complete trust-store epoch.

All trust consumers select one immutable epoch through one atomic pointer. No
individual trust-store file is changed in place, preventing split-trust states.
"""
from __future__ import annotations
import argparse, base64, hashlib, json, os, shutil, stat, sys, tempfile
from pathlib import Path
from typing import Any, Callable
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'trusted-installation'))
from v9_transaction import AnchorClient, AnchorHead, InstallerGlobalLock, atomic_write, canonical, fsync_dir, sha_bytes

TRUST_STORES=(
 'approval_keyring','evidence_keyring','runtime_verification_key','installation_verification_key',
 'adapter_authorization_keyring','qualification_authorization_keyring','qualification_receipt_verification_key',
 'release_verification_key','phase_transition_keyring','bootstrap_root_manifest',
)
assert len(TRUST_STORES)==10
MAX_STORE_BYTES=4*1024*1024

def read_regular(path:Path)->bytes:
 path=Path(path).absolute(); fd=os.open(path,os.O_RDONLY|getattr(os,'O_NOFOLLOW',0))
 try:
  st=os.fstat(fd)
  if not stat.S_ISREG(st.st_mode) or st.st_nlink!=1 or st.st_size>MAX_STORE_BYTES or st.st_mode&0o022:raise SystemExit(f'unsafe trust-store input: {path}')
  data=os.read(fd,MAX_STORE_BYTES+1)
  if len(data)>MAX_STORE_BYTES:raise SystemExit('trust-store input too large')
  return data
 finally:os.close(fd)

def load_json(path:Path)->dict[str,Any]:
 try:v=json.loads(read_regular(path))
 except Exception as exc:raise SystemExit(f'invalid trust lifecycle JSON: {path}') from exc
 if not isinstance(v,dict):raise SystemExit('trust lifecycle JSON must be an object')
 return v

def load_keyring(path:Path)->dict[str,tuple[Ed25519PublicKey,set[str],str]]:
 v=load_json(path); out={}; fps=set(); signers=set()
 if v.get('format_version')!='1.0' or not isinstance(v.get('keys'),list):raise SystemExit('key-lifecycle keyring invalid')
 for row in v['keys']:
  try:
   kid=str(row['key_id']);sid=str(row['signer_id']);roles=set(row['roles']);key=serialization.load_pem_public_key(str(row['public_key_pem']).encode())
  except Exception as exc:raise SystemExit('key-lifecycle keyring entry invalid') from exc
  if not isinstance(key,Ed25519PublicKey):raise SystemExit('key-lifecycle key is not Ed25519')
  fp=sha_bytes(key.public_bytes(serialization.Encoding.Raw,serialization.PublicFormat.Raw))
  if kid in out or fp in fps or sid in signers:raise SystemExit('duplicate lifecycle signer/key')
  out[kid]=(key,roles,sid);fps.add(fp);signers.add(sid)
 return out

def verify_transition_signatures(doc:dict[str,Any],keyring_path:Path)->None:
 unsigned=dict(doc);sigs=unsigned.pop('signatures',None)
 if not isinstance(sigs,list):raise SystemExit('key-lifecycle signatures missing')
 keys=load_keyring(keyring_path); roles=set(); signers=set()
 for sig in sigs:
  if not isinstance(sig,dict) or set(sig)!={'key_id','signature'}:raise SystemExit('key-lifecycle signature row invalid')
  entry=keys.get(str(sig['key_id']))
  if not entry:raise SystemExit('unknown key-lifecycle signer')
  try:entry[0].verify(base64.b64decode(str(sig['signature']),validate=True),canonical(unsigned))
  except (InvalidSignature,ValueError,TypeError) as exc:raise SystemExit('key-lifecycle signature invalid') from exc
  roles|=entry[1];signers.add(entry[2])
 if not {'key-lifecycle-authorizer','security-approver'}<=roles or len(signers)<2:raise SystemExit('key-lifecycle transition lacks independent required roles')

class TrustEpochStore:
 def __init__(self,root:Path,anchor_command:str,journal_id:str='azpr-v9-trust-epochs',fault:Callable[[str],None]|None=None):
  self.root=Path(root);self.epochs=self.root/'epochs';self.active=self.root/'active-epoch.json';self.pending=self.root/'PENDING.json';self.head_path=self.root/'HEAD.json';self.anchor=AnchorClient(anchor_command,journal_id);self.journal_id=journal_id;self.fault=fault or (lambda _:None)
 def _head(self)->AnchorHead:
  if not self.head_path.exists():return AnchorHead.genesis(self.journal_id)
  v=load_json(self.head_path);return AnchorHead(str(v['journal_id']),int(v['ledger_sequence']),int(v['authorization_sequence']),str(v['head_sha256']))
 def _write_head(self,h:AnchorHead):atomic_write(self.head_path,(json.dumps(h.as_dict(),indent=2,sort_keys=True)+'\n').encode(),0o400)
 def _pointer(self)->dict[str,Any]|None:return load_json(self.active) if self.active.exists() else None
 def _audit_active(self,head:AnchorHead)->None:
  pointer=self._pointer()
  if head.authorization_sequence==0:
   if pointer is not None:raise SystemExit('active trust epoch exists at genesis')
   return
  if pointer is None or int(pointer.get('sequence',-1))!=head.authorization_sequence:raise SystemExit('active trust epoch pointer rollback detected')
  manifest_path=Path(str(pointer.get('epoch_manifest_path',''))).absolute()
  if not manifest_path.is_file() or sha_bytes(read_regular(manifest_path))!=pointer.get('epoch_manifest_sha256'):raise SystemExit('active trust epoch manifest mismatch')
  manifest=load_json(manifest_path)
  if manifest.get('epoch_id')!=pointer.get('epoch_id') or int(manifest.get('sequence',-1))!=head.authorization_sequence:raise SystemExit('active trust epoch identity mismatch')
 def recover(self)->str:
  local=self._head();remote=self.anchor.read_head()
  if not self.pending.exists():
   if local!=remote:raise SystemExit('trust epoch rollback/fork detected')
   self._audit_active(local)
   return 'NO_PENDING_TRANSACTION'
  p=load_json(self.pending);prev=AnchorHead(**p['previous_head']);new=AnchorHead(**p['new_head']);pointer=p['pointer'];epoch=Path(p['epoch_path'])
  if not epoch.is_dir():raise SystemExit('pending trust epoch directory missing')
  if local==prev and remote==prev:
   shutil.rmtree(epoch);self.pending.unlink();fsync_dir(self.root);return 'ROLLED_BACK_UNANCHORED_EPOCH'
  if local==prev and remote==new:
   atomic_write(self.active,(json.dumps(pointer,indent=2,sort_keys=True)+'\n').encode(),0o400);self._write_head(new);self.pending.unlink();fsync_dir(self.root);return 'ACTIVATED_ANCHORED_EPOCH'
  if local==new and remote==new:
   if self._pointer()!=pointer:atomic_write(self.active,(json.dumps(pointer,indent=2,sort_keys=True)+'\n').encode(),0o400)
   self.pending.unlink();fsync_dir(self.root);return 'CLEANED_COMPLETED_EPOCH'
  raise SystemExit('trust epoch pending state cannot reconcile')
 def apply(self,transition:dict[str,Any],keyring_path:Path)->dict[str,Any]:
  self.recover();verify_transition_signatures(transition,keyring_path)
  if transition.get('format_version')!='1.0' or transition.get('transition_kind')!='AZPR_V9_ATOMIC_TRUST_EPOCH_TRANSITION':raise SystemExit('trust transition identity invalid')
  stores=transition.get('stores')
  if not isinstance(stores,dict) or set(stores)!=set(TRUST_STORES):raise SystemExit('trust transition store set mismatch')
  local=self._head();remote=self.anchor.read_head()
  if local!=remote:raise SystemExit('trust epoch local/remote head mismatch')
  seq=int(transition['sequence'])
  if seq!=local.authorization_sequence+1:raise SystemExit('trust epoch sequence is not exact next value')
  prev_pointer=self._pointer();prev_epoch=prev_pointer.get('epoch_id') if prev_pointer else None
  if transition.get('previous_epoch_id')!=prev_epoch:raise SystemExit('trust transition previous epoch mismatch')
  epoch_id=str(transition['new_epoch_id']);final=self.epochs/epoch_id
  if final.exists():raise SystemExit('trust epoch collision')
  self.epochs.mkdir(parents=True,exist_ok=True,mode=0o700)
  staging=Path(tempfile.mkdtemp(prefix=f'.staging-{epoch_id}-',dir=self.epochs))
  try:
   manifest_stores={}
   for name in TRUST_STORES:
    row=stores[name]
    if not isinstance(row,dict) or set(row)!={'path','sha256'}:raise SystemExit(f'trust transition store row invalid: {name}')
    raw=read_regular(Path(str(row['path'])))
    if sha_bytes(raw)!=row['sha256']:raise SystemExit(f'trust transition source hash mismatch: {name}')
    dest=staging/f'{name}.bin';atomic_write(dest,raw,0o400);manifest_stores[name]={'path':str(final/dest.name),'sha256':row['sha256']}
   manifest={'format_version':'1.0','epoch_kind':'AZPR_V9_ATOMIC_TRUST_STORE_EPOCH','epoch_id':epoch_id,'sequence':seq,'previous_epoch_id':prev_epoch,'transition_sha256':sha_bytes(canonical(transition)),'stores':manifest_stores}
   manifest['epoch_sha256']=sha_bytes(canonical(manifest))
   atomic_write(staging/'epoch-manifest.json',(json.dumps(manifest,indent=2,sort_keys=True)+'\n').encode(),0o400)
   self.fault('after_stage')
   os.replace(staging,final);fsync_dir(self.epochs);staging=None
   pointer={'format_version':'1.0','epoch_id':epoch_id,'sequence':seq,'epoch_manifest_path':str(final/'epoch-manifest.json'),'epoch_manifest_sha256':sha_bytes((final/'epoch-manifest.json').read_bytes())}
   record_hash=sha_bytes(canonical({'transition_sha256':sha_bytes(canonical(transition)),'pointer':pointer,'previous_head':local.as_dict()}))
   new=AnchorHead(self.journal_id,local.ledger_sequence+1,seq,record_hash)
   pending={'format_version':'1.0','previous_head':local.as_dict(),'new_head':new.as_dict(),'pointer':pointer,'epoch_path':str(final)}
   self.root.mkdir(parents=True,exist_ok=True,mode=0o700);atomic_write(self.pending,(json.dumps(pending,indent=2,sort_keys=True)+'\n').encode(),0o600)
   self.fault('after_pending')
   self.anchor.compare_and_publish(local,new);self.fault('after_anchor')
   atomic_write(self.active,(json.dumps(pointer,indent=2,sort_keys=True)+'\n').encode(),0o400);self.fault('after_pointer')
   self._write_head(new);self.fault('after_head')
   self.pending.unlink();fsync_dir(self.root)
   return pointer
  finally:
   if staging is not None and staging.exists():shutil.rmtree(staging,ignore_errors=True)

def resolve_active_store(root:Path,name:str)->Path:
 if name not in TRUST_STORES:raise SystemExit('unknown trust-store role')
 pointer=load_json(Path(root)/'active-epoch.json');manifest_path=Path(str(pointer['epoch_manifest_path'])).absolute();manifest=load_json(manifest_path)
 if sha_bytes(manifest_path.read_bytes())!=pointer['epoch_manifest_sha256'] or manifest.get('epoch_id')!=pointer.get('epoch_id'):raise SystemExit('active trust epoch pointer/manifest mismatch')
 row=manifest.get('stores',{}).get(name)
 if not isinstance(row,dict):raise SystemExit('active trust epoch lacks required store')
 path=Path(str(row['path'])).absolute()
 if sha_bytes(read_regular(path))!=row.get('sha256'):raise SystemExit('active trust-store hash mismatch')
 return path

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--transition',required=True);ap.add_argument('--authorization-keyring',required=True);ap.add_argument('--anchor-client',required=True);ap.add_argument('--state-root',default='/var/lib/azpr/trust-epochs');ap.add_argument('--global-lock',default='/run/lock/azpr/trusted-installer.global.lock');a=ap.parse_args()
 if os.geteuid()!=0:raise SystemExit('key lifecycle transition requires root')
 with InstallerGlobalLock(Path(a.global_lock)):
  pointer=TrustEpochStore(Path(a.state_root),a.anchor_client).apply(load_json(Path(a.transition)),Path(a.authorization_keyring))
 print(json.dumps({'status':'ATOMIC_TRUST_EPOCH_ACTIVATED','pointer':pointer,'safe_for_unattended_execution_now':False,'trusted_pre_autonomous_installation_ready':False},indent=2,sort_keys=True))
if __name__=='__main__':main()
