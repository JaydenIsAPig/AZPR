#!/usr/bin/env python3
"""Generate a bounded repository controller config after trusted installation."""
from __future__ import annotations
import argparse,hashlib,json,os,stat
from pathlib import Path

def read_once(path:Path,limit:int=4*1024*1024)->bytes:
 path=path.expanduser().absolute();fd=os.open(path,os.O_RDONLY|getattr(os,'O_NOFOLLOW',0))
 try:
  before=os.fstat(fd)
  if not stat.S_ISREG(before.st_mode) or before.st_nlink!=1 or before.st_size>limit:raise SystemExit(f'unsafe input: {path}')
  data=bytearray()
  while True:
   chunk=os.read(fd,65536)
   if not chunk:break
   data.extend(chunk)
   if len(data)>limit:raise SystemExit(f'input too large: {path}')
  after=os.fstat(fd)
  if (before.st_dev,before.st_ino,before.st_size,before.st_mtime_ns)!=(after.st_dev,after.st_ino,after.st_size,after.st_mtime_ns):raise SystemExit(f'input changed while reading: {path}')
  return bytes(data)
 finally:os.close(fd)
def sha(path):return hashlib.sha256(read_once(Path(path))).hexdigest()
def write_once(path:Path,data:bytes):
 path=path.expanduser().absolute();path.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
 for candidate in [path.parent,*path.parent.parents]:
  st=os.lstat(candidate)
  if stat.S_ISLNK(st.st_mode):raise SystemExit(f'symlinked output ancestor: {candidate}')
  if candidate==candidate.parent:break
 fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|getattr(os,'O_NOFOLLOW',0),0o600)
 try:os.write(fd,data);os.fsync(fd)
 finally:os.close(fd)
 dfd=os.open(path.parent,os.O_RDONLY|getattr(os,'O_DIRECTORY',0));os.fsync(dfd);os.close(dfd)
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--repository-id',required=True);ap.add_argument('--base-branch',default='main');ap.add_argument('--master-prompt-path',required=True);ap.add_argument('--validation-image-attestation',required=True);ap.add_argument('--output',required=True);ap.add_argument('--trusted-runner',default='/usr/local/libexec/azpr/validation/trusted_validation_runner.py');ap.add_argument('--container-engine',required=True);a=ap.parse_args()
 try:att=json.loads(read_once(Path(a.validation_image_attestation)))
 except Exception as exc:raise SystemExit('validation image attestation must be valid JSON') from exc
 image=att.get('image_reference');digest=att.get('image_digest')
 if not isinstance(image,str) or not isinstance(digest,str) or not image.endswith('@'+digest):raise SystemExit('validation image attestation does not contain a digest-pinned image')
 master=Path(a.master_prompt_path)
 if master.is_absolute() or '..' in master.parts:raise SystemExit('master prompt path must be repository-relative')
 value={'format_version':'4.0','repository_id':a.repository_id,'base_branch':a.base_branch,'master_prompt_path':str(master).replace('\\','/'),'approval_schema_path':'automation/schemas/approval.schema.json','capability_schema_path':'automation/schemas/capability-manifest.schema.json','evidence_schema_path':'automation/schemas/evidence.schema.json','security_policy_files':['automation/policy/canonical-policy-section-map.json'],'allowed_validation_executables':['python3','pytest','ruff','mypy','npm','npx','alembic'],'default_path_scope_budget':80,'default_max_changed_bytes':8388608,'required_evidence_signer_roles':['external-evidence'],'validation':{'trusted_runner_path':str(Path(a.trusted_runner).absolute()),'trusted_runner_sha256':sha(a.trusted_runner),'container_engine_path':str(Path(a.container_engine).absolute()),'container_engine_sha256':sha(a.container_engine),'image_reference':image,'image_digest':digest,'validation_image_attestation_sha256':sha(a.validation_image_attestation),'output_byte_limit':4194304,'file_count_limit':10000,'depth_limit':40,'file_size_limit_bytes':134217728,'cpus':'2','memory':'2g','pids_limit':256,'tmpfs_size':'512m'},'safe_for_unattended_execution_now':False}
 write_once(Path(a.output),(json.dumps(value,indent=2,sort_keys=True)+'\n').encode());print(Path(a.output).absolute())
if __name__=='__main__':main()
