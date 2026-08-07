#!/usr/bin/env python3
"""Create an unsigned validation-image attestation for independent signing."""
from __future__ import annotations
import argparse,hashlib,json,os,stat
from datetime import datetime,timezone
from pathlib import Path

def read(path:Path,limit=32*1024*1024):
 fd=os.open(path.absolute(),os.O_RDONLY|getattr(os,'O_NOFOLLOW',0))
 try:
  st=os.fstat(fd)
  if not stat.S_ISREG(st.st_mode) or st.st_nlink!=1 or st.st_size>limit:raise SystemExit(f'unsafe input: {path}')
  return os.read(fd,limit+1)
 finally:os.close(fd)
def sha(path):return hashlib.sha256(read(Path(path))).hexdigest()
def write_once(path:Path,data:bytes):
 path=path.absolute();path.parent.mkdir(parents=True,exist_ok=True,mode=0o700);fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|getattr(os,'O_NOFOLLOW',0),0o600)
 try:os.write(fd,data);os.fsync(fd)
 finally:os.close(fd)
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--image-reference',required=True);ap.add_argument('--image-digest',required=True);ap.add_argument('--dockerfile',required=True);ap.add_argument('--sbom',required=True);ap.add_argument('--build-provenance',required=True);ap.add_argument('--output',required=True);a=ap.parse_args()
 if not a.image_digest.startswith('sha256:') or len(a.image_digest)!=71:raise SystemExit('image digest must be sha256:<64 hex>')
 value={'format_version':'1.0','attestation_id':'validation-image-'+os.urandom(16).hex(),'image_reference':a.image_reference,'image_digest':a.image_digest,'dockerfile_sha256':sha(a.dockerfile),'sbom_sha256':sha(a.sbom),'build_provenance_sha256':sha(a.build_provenance),'created_at':datetime.now(timezone.utc).isoformat(),'signatures':[]}
 write_once(Path(a.output),(json.dumps(value,indent=2,sort_keys=True)+'\n').encode());print(Path(a.output).absolute())
if __name__=='__main__':main()
