#!/usr/bin/env python3
"""Validate and dual-sign a fully bound AZPR v8 installation authorization.

This tool never installs anything. It signs only an operator-prepared unsigned
payload whose exact schema is shipped in the authenticated candidate bundle.
"""
from __future__ import annotations
import argparse,base64,json,os
from pathlib import Path
from typing import Any
import jsonschema
from referencing import Registry,Resource
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
ROOT=Path(__file__).resolve().parents[1];SCHEMAS=ROOT/'repository-overlay/automation/schemas'
def canonical(v:Any)->bytes:return json.dumps(v,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()
def load(path:Path)->dict[str,Any]:
 v=json.loads(path.read_bytes());
 if not isinstance(v,dict):raise SystemExit('authorization payload must be an object')
 return v
def registry():
 reg=Registry();schemas={}
 for p in SCHEMAS.glob('*.json'):
  v=load(p);r=Resource.from_contents(v);schemas[p.name]=v;reg=reg.with_resource(p.name,r)
  if isinstance(v.get('$id'),str):reg=reg.with_resource(v['$id'],r)
 return schemas,reg
def private(path:Path)->Ed25519PrivateKey:
 key=serialization.load_pem_private_key(path.read_bytes(),password=None)
 if not isinstance(key,Ed25519PrivateKey):raise SystemExit(f'not an Ed25519 private key: {path}')
 return key
def write_once(path:Path,data:bytes):
 path=path.absolute();path.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
 fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|getattr(os,'O_NOFOLLOW',0),0o600)
 try:os.write(fd,data);os.fsync(fd)
 finally:os.close(fd)
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--unsigned',required=True);ap.add_argument('--signer',action='append',required=True,help='KEY_ID=/absolute/private-key.pem; repeat for independent roles');ap.add_argument('--output',required=True);a=ap.parse_args()
 value=load(Path(a.unsigned));value.pop('signatures',None)
 signers=[];ids=set()
 for item in a.signer:
  if '=' not in item:raise SystemExit('--signer must be KEY_ID=PRIVATE_KEY')
  key_id,path=item.split('=',1)
  if key_id in ids:raise SystemExit('duplicate signer key ID')
  ids.add(key_id);signers.append((key_id,private(Path(path))))
 if len(signers)<2:raise SystemExit('at least two independent signers are required')
 value['signatures']=[{'key_id':key_id,'ed25519':base64.b64encode(key.sign(canonical(value))).decode()} for key_id,key in signers]
 schemas,reg=registry()
 try:jsonschema.Draft202012Validator(schemas['qualification-installation-authorization.schema.json'],registry=reg,format_checker=jsonschema.FormatChecker()).validate(value)
 except Exception as exc:raise SystemExit(f'authorization schema validation failed: {exc}') from exc
 write_once(Path(a.output),(json.dumps(value,indent=2,sort_keys=True)+'\n').encode());print(Path(a.output).absolute())
if __name__=='__main__':main()
