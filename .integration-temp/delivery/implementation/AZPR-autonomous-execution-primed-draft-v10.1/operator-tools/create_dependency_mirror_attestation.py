#!/usr/bin/env python3
"""Sign a deterministic inventory of an immutable offline dependency mirror."""
from __future__ import annotations
import argparse,base64,hashlib,json,os,stat
from datetime import datetime,timezone
from pathlib import Path
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
def canonical(v):return json.dumps(v,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for c in iter(lambda:f.read(1024*1024),b''):h.update(c)
 return h.hexdigest()
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--mirror',required=True);ap.add_argument('--private-key',required=True);ap.add_argument('--key-id',required=True);ap.add_argument('--output',required=True);a=ap.parse_args();root=Path(a.mirror).absolute()
 files=[];total=0
 for p in sorted(root.rglob('*')):
  st=os.lstat(p)
  if stat.S_ISLNK(st.st_mode) or st.st_mode&0o022:raise SystemExit(f'unsafe mirror entry: {p}')
  if p.is_dir():continue
  if not stat.S_ISREG(st.st_mode) or st.st_nlink!=1:raise SystemExit(f'non-regular mirror entry: {p}')
  rel=str(p.relative_to(root)).replace(os.sep,'/');files.append({'path':rel,'sha256':sha(p),'size':st.st_size});total+=st.st_size
 if not files:raise SystemExit('mirror is empty')
 inventory=hashlib.sha256(canonical(files)).hexdigest();unsigned={'format_version':'1.0','mirror_name':root.name,'inventory_sha256':inventory,'file_count':len(files),'total_bytes':total,'created_at':datetime.now(timezone.utc).isoformat(),'signer_key_id':a.key_id}
 key=serialization.load_pem_private_key(Path(a.private_key).read_bytes(),password=None)
 if not isinstance(key,Ed25519PrivateKey):raise SystemExit('private key is not Ed25519')
 value=dict(unsigned,signature=base64.b64encode(key.sign(canonical(unsigned))).decode());out=Path(a.output).absolute();out.parent.mkdir(parents=True,exist_ok=True);fd=os.open(out,os.O_WRONLY|os.O_CREAT|os.O_EXCL|getattr(os,'O_NOFOLLOW',0),0o600)
 try:os.write(fd,(json.dumps(value,indent=2,sort_keys=True)+'\n').encode());os.fsync(fd)
 finally:os.close(fd)
 print(out)
if __name__=='__main__':main()
