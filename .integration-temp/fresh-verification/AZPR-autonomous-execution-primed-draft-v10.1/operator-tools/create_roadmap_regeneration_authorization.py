#!/usr/bin/env python3
"""Create an unsigned post-Prompt-004 roadmap-regeneration authorization."""
from __future__ import annotations
import argparse,hashlib,json,os,stat,subprocess
from datetime import datetime,timezone,timedelta
from pathlib import Path

def read_once(path:Path,limit=16*1024*1024):
 path=path.absolute();fd=os.open(path,os.O_RDONLY|getattr(os,'O_NOFOLLOW',0))
 try:
  st=os.fstat(fd)
  if not stat.S_ISREG(st.st_mode) or st.st_nlink!=1 or st.st_size>limit:raise SystemExit(f'unsafe input: {path}')
  data=os.read(fd,limit+1)
  if len(data)>limit:raise SystemExit(f'input too large: {path}')
  return data
 finally:os.close(fd)
def sha(path):return hashlib.sha256(read_once(Path(path))).hexdigest()
def git(repo,*args):return subprocess.run(['/usr/bin/git','-c','core.hooksPath=/dev/null','-c','core.fsmonitor=false','-c','commit.gpgSign=false',*args],cwd=repo,capture_output=True,text=True,check=True,env={'PATH':'/usr/bin:/bin','HOME':'/nonexistent','GIT_CONFIG_NOSYSTEM':'1','GIT_CONFIG_GLOBAL':'/dev/null'}).stdout.strip()
def write_once(path:Path,data:bytes):
 path=path.absolute();path.parent.mkdir(parents=True,exist_ok=True,mode=0o700);fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|getattr(os,'O_NOFOLLOW',0),0o600)
 try:os.write(fd,data);os.fsync(fd)
 finally:os.close(fd)
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--repository',required=True);ap.add_argument('--repository-id',required=True);ap.add_argument('--prompt-004-decision',required=True);ap.add_argument('--prompt-catalog-sha256',required=True);ap.add_argument('--canonical-policy-record',required=True);ap.add_argument('--installation-manifest',required=True);ap.add_argument('--security-test-report',required=True);ap.add_argument('--output',required=True);ap.add_argument('--valid-hours',type=int,default=24);a=ap.parse_args()
 repo=Path(a.repository).absolute();decision=Path(a.prompt_004_decision).absolute();decision_rel=str(decision.relative_to(repo)).replace('\\','/')
 now=datetime.now(timezone.utc);value={'format_version':'1.0','authorization_id':'roadmap-regeneration-'+os.urandom(16).hex(),'repository_id':a.repository_id,'target_commit':git(repo,'rev-parse','HEAD'),'target_tree':git(repo,'rev-parse','HEAD^{tree}'),'prompt_004_status':'COMPLETED_APPROVED_RECONCILED','prompt_004_decision_path':decision_rel,'prompt_004_decision_sha256':sha(decision),'prompt_catalog_sha256':a.prompt_catalog_sha256,'canonical_policy_record_sha256':sha(a.canonical_policy_record),'installation_manifest_sha256':sha(a.installation_manifest),'security_test_report_sha256':sha(a.security_test_report),'issued_at':now.isoformat(),'expires_at':(now+timedelta(hours=a.valid_hours)).isoformat(),'nonce':os.urandom(24).hex(),'signatures':[]}
 write_once(Path(a.output),(json.dumps(value,indent=2,sort_keys=True)+'\n').encode());print(Path(a.output).absolute())
if __name__=='__main__':main()
