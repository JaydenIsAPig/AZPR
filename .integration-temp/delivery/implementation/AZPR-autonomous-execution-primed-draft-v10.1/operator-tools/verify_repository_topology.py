#!/usr/bin/env python3
"""Black-box entrypoint for AZPR repository topology qualification."""
from __future__ import annotations
import argparse,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'trusted-controller'))
import secure_runtime as sr

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--repository',required=True);a=ap.parse_args()
 try:sr.repository_topology_preflight(Path(a.repository),[])
 except sr.SecurityError as exc:raise SystemExit(str(exc)) from exc
 print(json.dumps({'status':'PASS_SUPPORTED_STANDALONE_REPOSITORY','safe_for_unattended_execution_now':False},sort_keys=True))
if __name__=='__main__':main()
