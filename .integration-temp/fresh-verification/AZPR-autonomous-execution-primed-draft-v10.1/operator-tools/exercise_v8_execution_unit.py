#!/usr/bin/env python3
"""Black-box exerciser for the v8 duplex runner and complete execution unit."""
from __future__ import annotations
import argparse,json,os,sys,tempfile,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'trusted-controller'))
import secure_runtime as sr

def main():
 p=argparse.ArgumentParser();p.add_argument('--case',choices=['descendant','duplex','overflow'],required=True);p.add_argument('--marker');a=p.parse_args()
 os.environ['AZPR_EXPLICIT_TEST_MODE']='1';os.environ['AZPR_PRODUCTION_MODE']='0'
 target_uid,target_gid=(65534,65534) if os.geteuid()==0 else (os.geteuid(),os.getegid())
 with tempfile.TemporaryDirectory(dir='/tmp',prefix='azpr-v8-exec-') as td:
  root=Path(td);root.chmod(0o755);script=root/'child.py'
  if a.case=='descendant':
   marker=Path(a.marker).absolute();script.write_text("import os,subprocess,sys\nsubprocess.Popen([sys.executable,'-c',\"import time,pathlib;time.sleep(1);pathlib.Path(%r).write_text('survived')\"],start_new_session=True,stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,close_fds=True)\n"%str(marker))
   script.chmod(0o444)
   rc,out,err,d=sr.run_bounded_process([sys.executable,str(script)],cwd=root,timeout_seconds=5,env={**os.environ,'PATH':'/usr/bin:/bin'},run_as_uid=target_uid,run_as_gid=target_gid)
   time.sleep(1.4);ok=rc==0 and not marker.exists()
  elif a.case=='duplex':
   script.write_text("import os,sys\nos.write(1,b'x'*(2*1024*1024));data=sys.stdin.buffer.read();os.write(2,str(len(data)).encode())\n");script.chmod(0o444)
   rc,out,err,d=sr.run_bounded_process([sys.executable,str(script)],cwd=root,input_bytes=b'y'*(2*1024*1024),timeout_seconds=5,env={**os.environ,'PATH':'/usr/bin:/bin'},stdout_limit=3*1024*1024,stderr_limit=65536,run_as_uid=target_uid,run_as_gid=target_gid);ok=rc==0 and len(out)==2*1024*1024 and err==str(2*1024*1024).encode()
  else:
   script.write_text("import os\nwhile True:os.write(1,b'x'*65536)\n");script.chmod(0o444)
   try:sr.run_bounded_process([sys.executable,str(script)],cwd=root,timeout_seconds=5,env={**os.environ,'PATH':'/usr/bin:/bin'},stdout_limit=131072,stderr_limit=65536,run_as_uid=target_uid,run_as_gid=target_gid);ok=False
   except sr.SecurityError:ok=True;rc=-1;out=err=b'';d=0
 print(json.dumps({'case':a.case,'pass':ok,'safe_for_unattended_execution_now':False},sort_keys=True));return 0 if ok else 1
if __name__=='__main__':raise SystemExit(main())
