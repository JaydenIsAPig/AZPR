#!/usr/bin/env python3
"""Apply H0 preparation twice and emit non-authoritative idempotence evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import tempfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[3]
ANSIBLE_ROOT = ROOT / "infrastructure" / "ansible"
PREFLIGHT = ANSIBLE_ROOT / "playbooks" / "qualification-preflight.yml"
PREPARE = ANSIBLE_ROOT / "playbooks" / "qualification-prepare.yml"
CONFIRMATION = "APPLY H0 QUALIFICATION PREPARATION"
RECAP = re.compile(r"^\S+\s+:\s+ok=(\d+)\s+changed=(\d+)\s+unreachable=(\d+)\s+failed=(\d+)", re.MULTILINE)


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def run(command: list[str], env: dict[str, str]) -> dict[str, Any]:
    result = subprocess.run(
        command,
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    matches = RECAP.findall(result.stdout)
    recap = None
    if matches:
        ok, changed, unreachable, failed = matches[-1]
        recap = {
            "ok": int(ok),
            "changed": int(changed),
            "unreachable": int(unreachable),
            "failed": int(failed),
        }
    return {
        "command": [Path(command[0]).name, *command[1:]],
        "exit_code": result.returncode,
        "recap": recap,
        "stdout_sha256": sha256_text(result.stdout),
        "stderr_sha256": sha256_text(result.stderr),
    }


def atomic_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(value, handle, indent=2, sort_keys=True)
            handle.write("\n")
        os.replace(temporary, path)
    except BaseException:
        Path(temporary).unlink(missing_ok=True)
        raise


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inventory", type=Path, required=True)
    parser.add_argument("--ansible-playbook", type=Path, required=True)
    parser.add_argument("--environment-scope", choices=("DISPOSABLE_TEST", "HUMAN_APPROVED_QUALIFICATION"), required=True)
    parser.add_argument("--confirm", required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    if args.confirm != CONFIRMATION:
        raise SystemExit("explicit H0 preparation confirmation phrase is required")
    if not args.inventory.is_file() or not args.ansible_playbook.is_file():
        raise SystemExit("inventory and pinned ansible-playbook executable must exist")

    environment = dict(os.environ)
    environment.update(
        ANSIBLE_CONFIG=str(ANSIBLE_ROOT / "ansible.cfg"),
        ANSIBLE_NOCOLOR="1",
        PYTHONDONTWRITEBYTECODE="1",
    )
    base = [str(args.ansible_playbook), "-i", str(args.inventory.resolve())]
    preflight = run([*base, str(PREFLIGHT), "--diff"], environment)
    first = run([*base, str(PREPARE), "--diff"], environment) if preflight["exit_code"] == 0 else {}
    second = run([*base, str(PREPARE), "--diff"], environment) if first.get("exit_code") == 0 else {}
    second_recap = second.get("recap") or {}
    passed = (
        preflight["exit_code"] == 0
        and first.get("exit_code") == 0
        and second.get("exit_code") == 0
        and second_recap.get("changed") == 0
        and second_recap.get("unreachable") == 0
        and second_recap.get("failed") == 0
    )
    evidence = {
        "format_version": "1.0",
        "classification": "NON_AUTHORITATIVE_PROVISIONING_EVIDENCE",
        "status": "PASS" if passed else "FAIL",
        "environment_scope": args.environment_scope,
        "qualification_effect": false,
        "preflight": preflight,
        "first_apply": first,
        "second_apply": second,
        "idempotence_rule": "second apply changed=0, unreachable=0, failed=0",
    }
    if args.output:
        atomic_json(args.output, evidence)
    print(json.dumps(evidence, indent=2, sort_keys=True))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())

