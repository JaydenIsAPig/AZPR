#!/usr/bin/env python3
"""Create an unsigned, create-once AZPR key lifecycle transition for later dual-control signing."""
from __future__ import annotations
import argparse,hashlib,json,os,re,stat
from datetime import datetime,timezone
from pathlib import Path
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

def fingerprint(path:Path)->str:
 data=path.read_bytes();key=serialization.load_pem_public_key(data)
 if not isinstance(key,Ed25519PublicKey):raise SystemExit('public keys must be Ed25519')
 return hashlib.sha256(key.public_bytes(serialization.Encoding.Raw,serialization.PublicFormat.Raw)).hexdigest()
def write_once(path:Path,data:bytes):
 path=path.absolute();path.parent.mkdir(parents=True,exist_ok=True,mode=0o700);fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|getattr(os,'O_NOFOLLOW',0),0o600)
 try:os.write(fd,data);os.fsync(fd)
 finally:os.close(fd)
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--type',choices=['ROTATE','REVOKE','EMERGENCY_DISABLE','CUSTODY_TRANSITION'],required=True);ap.add_argument('--key-role',required=True);ap.add_argument('--from-epoch',type=int,required=True);ap.add_argument('--old-key-id',required=True);ap.add_argument('--old-public-key',required=True);ap.add_argument('--new-key-id');ap.add_argument('--new-public-key');ap.add_argument('--effective-at');ap.add_argument('--output',required=True);a=ap.parse_args()
 if a.from_epoch<1:raise SystemExit('from epoch must be positive')
 needs=a.type in {'ROTATE','CUSTODY_TRANSITION'}
 if needs != bool(a.new_key_id and a.new_public_key):raise SystemExit('new key ID/public key are required only for rotation/custody transition')
 now=a.effective_at or datetime.now(timezone.utc).isoformat();value={'format_version':'1.0','transition_id':'key-transition-'+os.urandom(16).hex(),'transition_type':a.type,'key_role':a.key_role,'from_epoch':a.from_epoch,'to_epoch':a.from_epoch+1,'old_key_id':a.old_key_id,'old_key_fingerprint':fingerprint(Path(a.old_public_key)),'new_key_id':a.new_key_id,'new_key_fingerprint':fingerprint(Path(a.new_public_key)) if a.new_public_key else None,'effective_at':now,'emergency_disable':a.type=='EMERGENCY_DISABLE','historical_verification_policy':'OLD_KEY_MAY_VERIFY_PRE_EFFECTIVE_RECORDS_BUT_MAY_NOT_AUTHORIZE_NEW_RECORDS','required_approval_roles':['policy-owner','security-approver'],'signatures':[]}
 write_once(Path(a.output),(json.dumps(value,indent=2,sort_keys=True)+'\n').encode());print(Path(a.output).absolute())
if __name__=='__main__':main()
