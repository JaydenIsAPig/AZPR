#!/usr/bin/env python3
"""Synthetic reference anchor for tests only; production must use WORM/remote anchoring."""
from __future__ import annotations
import json, os, sys
from pathlib import Path

ROOT=Path(os.environ.get('AZPR_REFERENCE_ANCHOR_ROOT','/tmp/azpr-reference-anchor')).absolute()
ROOT.mkdir(parents=True,exist_ok=True,mode=0o700)
payload=json.loads(sys.stdin.buffer.read())
path=ROOT/f"{payload['journal_id']}.json"
if sys.argv[1]=='publish':
    previous=json.loads(path.read_text()) if path.exists() else {'sequence':0,'head_sha256':'0'*64}
    if payload['sequence'] < previous['sequence']:
        raise SystemExit(2)
    tmp=path.with_suffix('.tmp')
    tmp.write_text(json.dumps(payload,sort_keys=True))
    os.replace(tmp,path)
    print(json.dumps({'operation':'publish','journal_id':payload['journal_id'],'sequence':payload['sequence'],'head_sha256':payload['head_sha256']},sort_keys=True))
    raise SystemExit(0)
if sys.argv[1]=='verify':
    if not path.exists():
        raise SystemExit(2)
    anchored=json.loads(path.read_text())
    if anchored != payload:
        raise SystemExit(2)
    print(json.dumps({'operation':'verify','journal_id':payload['journal_id'],'sequence':payload['sequence'],'head_sha256':payload['head_sha256']},sort_keys=True))
    raise SystemExit(0)
raise SystemExit(2)
