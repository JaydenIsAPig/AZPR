#!/usr/bin/env python3
"""TEST-ONLY compare-and-publish anchor reference for v9 transaction tests."""
from __future__ import annotations
import json, os, sys, tempfile
from pathlib import Path

ZERO="0"*64
ROOT=(Path(__file__).resolve().parent/".v9-reference-anchor-state").absolute()
ROOT.mkdir(parents=True,exist_ok=True,mode=0o700)
try:payload=json.loads(sys.stdin.buffer.read() or b"{}")
except Exception:raise SystemExit(2)
if not isinstance(payload,dict):raise SystemExit(2)
journal=payload.get("journal_id")
if not isinstance(journal,str) or not journal or any(c not in "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789._:-" for c in journal):raise SystemExit(2)
path=ROOT/(journal+".json")
def genesis():return {"journal_id":journal,"ledger_sequence":0,"authorization_sequence":0,"head_sha256":ZERO}
def load():return json.loads(path.read_text()) if path.exists() else genesis()
def store(v):
 fd,tmp=tempfile.mkstemp(prefix=".anchor.",dir=ROOT)
 try:
  os.fchmod(fd,0o600);os.write(fd,(json.dumps(v,sort_keys=True)+"\n").encode());os.fsync(fd);os.close(fd);fd=-1;os.replace(tmp,path)
  d=os.open(ROOT,os.O_RDONLY);os.fsync(d);os.close(d)
 finally:
  if fd>=0:
   try:os.close(fd)
   except OSError:pass
  try:os.unlink(tmp)
  except FileNotFoundError:pass
op=sys.argv[1] if len(sys.argv)>1 else ""
if op=="read":
 print(json.dumps(load(),sort_keys=True));raise SystemExit(0)
if op=="compare-and-publish":
 previous=payload.get("expected_previous");new=payload.get("new_head");current=load()
 if previous!=current or not isinstance(new,dict):raise SystemExit(3)
 if new.get("journal_id")!=journal or int(new.get("ledger_sequence",-1))!=int(current["ledger_sequence"])+1:raise SystemExit(3)
 if int(new.get("authorization_sequence",-1))<int(current["authorization_sequence"]):raise SystemExit(3)
 store(new)
 print(json.dumps({"accepted":True,"journal_id":journal,"previous_head_sha256":current["head_sha256"],"new_head_sha256":new["head_sha256"],"ledger_sequence":new["ledger_sequence"]},sort_keys=True));raise SystemExit(0)
raise SystemExit(2)
