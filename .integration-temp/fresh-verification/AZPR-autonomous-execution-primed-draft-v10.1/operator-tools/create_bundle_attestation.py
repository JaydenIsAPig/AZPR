#!/usr/bin/env python3
"""Create a signed external attestation for an exact AZPR release directory.

Run only after SHA256SUMS.json is finalized. The attestation must remain outside
the attested bundle and be supplied separately to the root installer.
"""
from __future__ import annotations
import argparse,base64,hashlib,json,os,stat
from datetime import datetime,timezone
from pathlib import Path
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
def canonical(v):return json.dumps(v,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()
def read_once(path:Path,limit:int=32*1024*1024):
 fd=os.open(path,os.O_RDONLY|getattr(os,'O_NOFOLLOW',0))
 try:
  st=os.fstat(fd)
  if not stat.S_ISREG(st.st_mode) or st.st_nlink!=1 or st.st_size>limit:raise SystemExit(f'unsafe input: {path}')
  data=os.read(fd,limit+1)
  if len(data)>limit:raise SystemExit(f'oversized input: {path}')
  return data
 finally:os.close(fd)
def write_once(path:Path,data:bytes):
 path=path.absolute();path.parent.mkdir(parents=True,exist_ok=True,mode=0o700);fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|getattr(os,'O_NOFOLLOW',0),0o600)
 try:os.write(fd,data);os.fsync(fd)
 finally:os.close(fd)
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--bundle-root',required=True);ap.add_argument('--private-key',required=True);ap.add_argument('--key-id',required=True);ap.add_argument('--output',required=True);a=ap.parse_args()
 root=Path(a.bundle_root).absolute();manifest=root/'SHA256SUMS.json';raw=read_once(manifest)
 try:m=json.loads(raw)
 except Exception as exc:raise SystemExit('invalid bundle SHA256SUMS.json') from exc
 expected=set(m.get('entries',{}))|{'SHA256SUMS.json'};actual=[];total=0
 for p in sorted(root.rglob('*')):
  st=os.lstat(p)
  if stat.S_ISLNK(st.st_mode):raise SystemExit(f'symlinked bundle entry: {p}')
  if p.is_dir():continue
  if not stat.S_ISREG(st.st_mode) or st.st_nlink!=1:raise SystemExit(f'non-regular bundle entry: {p}')
  actual.append(str(p.relative_to(root)).replace(os.sep,'/'));total+=st.st_size
 if set(actual)!=expected:raise SystemExit('bundle inventory differs from SHA256SUMS.json')
 unsigned={'format_version':'1.0','bundle_name':root.name,'bundle_manifest_sha256':hashlib.sha256(raw).hexdigest(),'bundle_file_count':len(actual),'bundle_total_bytes':total,'issued_at':datetime.now(timezone.utc).isoformat(),'signer_key_id':a.key_id}
 key=serialization.load_pem_private_key(read_once(Path(a.private_key),64*1024),password=None)
 if not isinstance(key,Ed25519PrivateKey):raise SystemExit('private key is not Ed25519')
 value=dict(unsigned,signature=base64.b64encode(key.sign(canonical(unsigned))).decode());write_once(Path(a.output),(json.dumps(value,indent=2,sort_keys=True)+'\n').encode());print(Path(a.output).absolute())
if __name__=='__main__':main()
