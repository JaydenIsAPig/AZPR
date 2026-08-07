#!/usr/bin/env python3
"""Exercise the source-level v7 per-run agent handoff under an exact UID/GID."""
from __future__ import annotations
import argparse, json, os, shutil, subprocess, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'trusted-controller'))
import secure_runtime as sr

CHILD = r'''
import json, os, sys
from pathlib import Path
home, tmp, output, protected = map(Path, sys.argv[1:5])
try:
    (home / "home-write").write_text("ok", encoding="utf-8")
    (tmp / "tmp-write").write_text("ok", encoding="utf-8")
    denied = False
    try:
        protected.read_bytes()
    except (PermissionError, OSError):
        denied = True
    output.write_text(json.dumps({"status":"PASS","protected_denied":denied}), encoding="utf-8")
    output.chmod(0o600)
    raise SystemExit(0 if denied else 2)
except BaseException as exc:
    print(f"agent child error: {type(exc).__name__}: {exc}", file=sys.stderr)
    raise
'''

def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument('--handoff-root', required=True)
    ap.add_argument('--agent-uid', type=int, required=True)
    ap.add_argument('--agent-gid', type=int, required=True)
    ap.add_argument('--protected-path', required=True)
    ap.add_argument('--controller-output', required=True)
    a = ap.parse_args()
    if os.geteuid() != 0:
        raise SystemExit('root is required for identity transition')
    setpriv = shutil.which('setpriv')
    if not setpriv:
        raise SystemExit('setpriv is required for exact identity transition')
    surface = sr.create_agent_run_surface(Path(a.handoff_root), agent_uid=a.agent_uid, agent_gid=a.agent_gid)
    try:
        env = {
            'PATH': '/usr/bin:/bin',
            'HOME': str(surface.home),
            'TMPDIR': str(surface.tmp),
            'PYTHONDONTWRITEBYTECODE': '1',
            'LANG': 'C.UTF-8',
            'LC_ALL': 'C.UTF-8',
        }
        command = [
            setpriv,
            '--reuid', str(a.agent_uid),
            '--regid', str(a.agent_gid),
            '--clear-groups',
            '--no-new-privs',
            sys.executable,
            '-c', CHILD,
            str(surface.home), str(surface.tmp), str(surface.output_path), str(Path(a.protected_path)),
        ]
        result = subprocess.run(command, env=env, capture_output=True, text=True, timeout=30)
        if result.returncode != 0:
            raise SystemExit(f'agent handoff child failed: {result.returncode}; stderr={result.stderr[-2000:]}')
        data = sr.import_agent_result(surface, Path(a.controller_output))
        value = json.loads(data)
        if value.get('protected_denied') is not True:
            raise SystemExit('agent read protected path')
    finally:
        sr.destroy_agent_run_surface(surface)
    print(json.dumps({
        'status': 'PASS_NONROOT_AGENT_HANDOFF_SOURCE_LEVEL',
        'safe_for_unattended_execution_now': False,
        'controller_output': str(Path(a.controller_output).absolute()),
    }, sort_keys=True))

if __name__ == '__main__':
    main()
