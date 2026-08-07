#!/usr/bin/env python3
"""Create an Ed25519 keypair with create-once, no-follow semantics."""
from __future__ import annotations
import argparse, os, stat
from pathlib import Path
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

def ensure_parent(path:Path):
 path.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
 for candidate in [path.parent,*path.parent.parents]:
  st=os.lstat(candidate)
  if stat.S_ISLNK(st.st_mode): raise SystemExit(f'symlinked output ancestor: {candidate}')
  if candidate==candidate.parent:break

def write_once(path:Path,data:bytes,mode:int):
 path=path.expanduser().absolute(); ensure_parent(path)
 flags=os.O_WRONLY|os.O_CREAT|os.O_EXCL|getattr(os,'O_NOFOLLOW',0); fd=os.open(path,flags,mode)
 try:
  before=os.fstat(fd)
  if not stat.S_ISREG(before.st_mode) or before.st_nlink!=1: raise SystemExit(f'unsafe output leaf: {path}')
  view=memoryview(data)
  while view:
   n=os.write(fd,view); view=view[n:]
  os.fsync(fd); os.fchmod(fd,mode)
  after=os.fstat(fd)
  if (before.st_dev,before.st_ino)!=(after.st_dev,after.st_ino): raise SystemExit('output identity changed')
 finally:os.close(fd)
 dfd=os.open(path.parent,os.O_RDONLY|getattr(os,'O_DIRECTORY',0)); os.fsync(dfd); os.close(dfd)

def main():
 p=argparse.ArgumentParser();p.add_argument('--private-key',required=True);p.add_argument('--public-key',required=True);a=p.parse_args()
 priv=Path(a.private_key).absolute();pub=Path(a.public_key).absolute()
 if priv==pub:raise SystemExit('private and public outputs must differ')
 private=Ed25519PrivateKey.generate()
 write_once(priv,private.private_bytes(serialization.Encoding.PEM,serialization.PrivateFormat.PKCS8,serialization.NoEncryption()),0o600)
 try:write_once(pub,private.public_key().public_bytes(serialization.Encoding.PEM,serialization.PublicFormat.SubjectPublicKeyInfo),0o644)
 except Exception:
  try:priv.unlink()
  except OSError:pass
  raise
 print(f'Created private key {priv} and public key {pub}.')
if __name__=='__main__':main()
