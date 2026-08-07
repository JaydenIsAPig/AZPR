#!/usr/bin/env python3
"""Clean-room only adapter. It performs no external side effects."""
from __future__ import annotations
import hashlib,json,sys

def h(v):return hashlib.sha256(json.dumps(v,sort_keys=True,separators=(',',':')).encode()).hexdigest()
def main():
 mode=sys.argv[1] if len(sys.argv)>1 else ''
 req=json.load(sys.stdin)
 if mode=='probe':
  print(json.dumps({'target':req['target'],'drift_sha256':h({'cleanroom':True,'target':req['target']}),'safe_to_apply':True,'status':'NO_CHANGE'}));return 0
 if mode=='apply':
  print(json.dumps({'status':'NO_CHANGE','target':req['target'],'operation':req['operation'],'result_sha256':h(req)}));return 0
 print(json.dumps({'status':'FAILED','error':'unsupported mode'}));return 2
if __name__=='__main__':raise SystemExit(main())
