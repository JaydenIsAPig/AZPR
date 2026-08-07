#!/usr/bin/env python3
"""Trusted AZPR execution gate.

Production use:
1. the root controller spawns this gate with a closed start barrier;
2. the controller attaches the gate PID to the dedicated run cgroup;
3. the controller releases the barrier;
4. the gate creates new mount, PID, and network namespaces;
5. the namespace-init child drops supplementary groups, GID, UID, capabilities,
   sets no-new-privileges and resource limits, then execs the untrusted target.

The outer controller still kills and proves the complete cgroup empty on every
completion path. Namespace isolation is defense in depth and prevents a normal
PID-namespace init exit from leaving descendants alive.
"""
from __future__ import annotations
import argparse,ctypes,os,resource,signal,sys
CLONE_NEWNS=0x00020000;CLONE_NEWPID=0x20000000;CLONE_NEWNET=0x40000000
MS_REC=16384;MS_PRIVATE=1<<18;PR_SET_NO_NEW_PRIVS=38
libc=ctypes.CDLL(None,use_errno=True)
def call_zero(name,*args):
 fn=getattr(libc,name);rc=fn(*args)
 if rc!=0:
  err=ctypes.get_errno();raise OSError(err,os.strerror(err),name)
def wait_status(pid:int)->int:
 while True:
  try:_p,status=os.waitpid(pid,0);break
  except InterruptedError:continue
 if os.WIFEXITED(status):return os.WEXITSTATUS(status)
 if os.WIFSIGNALED(status):return 128+os.WTERMSIG(status)
 return 125
def main()->int:
 ap=argparse.ArgumentParser();ap.add_argument('--barrier-fd',type=int,required=True);ap.add_argument('--production-isolation',action='store_true');ap.add_argument('--uid',type=int);ap.add_argument('--gid',type=int);ap.add_argument('command',nargs=argparse.REMAINDER);a=ap.parse_args()
 command=a.command[1:] if a.command[:1]==['--'] else a.command
 if not command:raise SystemExit('missing gated command')
 token=os.read(a.barrier_fd,1);os.close(a.barrier_fd)
 if token!=b'G':raise SystemExit('execution barrier was not released by trusted controller')
 os.umask(0o077)
 fsize=int(os.environ.get('AZPR_RLIMIT_FSIZE','8388608'));nofile=int(os.environ.get('AZPR_RLIMIT_NOFILE','1024'))
 resource.setrlimit(resource.RLIMIT_FSIZE,(fsize,fsize));resource.setrlimit(resource.RLIMIT_NOFILE,(nofile,nofile))
 if not a.production_isolation:
  os.execvpe(command[0],command,os.environ);return 127
 if os.geteuid()!=0 or not a.uid or not a.gid or a.uid<=0 or a.gid<=0:raise SystemExit('production namespace gate requires root and explicit non-root UID/GID')
 call_zero('unshare',CLONE_NEWNS|CLONE_NEWPID|CLONE_NEWNET)
 # Prevent mount propagation to the host before any target code runs.
 call_zero('mount',ctypes.c_void_p(),ctypes.c_char_p(b'/'),ctypes.c_void_p(),ctypes.c_ulong(MS_REC|MS_PRIVATE),ctypes.c_void_p())
 pid=os.fork()
 if pid:
  # The first child in the new PID namespace is namespace init. Kernel teardown
  # kills remaining namespace processes when it exits; the cgroup is still the
  # authoritative complete-tree boundary.
  return wait_status(pid)
 os.setgroups([]);os.setgid(a.gid);os.setuid(a.uid)
 call_zero('prctl',PR_SET_NO_NEW_PRIVS,1,0,0,0)
 os.execvpe(command[0],command,os.environ);return 127
if __name__=='__main__':raise SystemExit(main())
