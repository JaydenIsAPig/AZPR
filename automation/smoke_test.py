#!/usr/bin/env python3
"""Read-only smoke tests for the autonomous-loop bundle."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def main() -> int:
    root = Path(
        subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
    )
    required = [
        "AGENTS.md",
        "automation/approval_manager.py",
        "automation/approvals/stage-manifests/AZPR-H0-TRANSPORT-20260807-001.json",
        "automation/approvals/tickets/AZPR-H0-TRANSPORT-20260807-001.json",
        "automation/approvals/reviews/AZPR-H0-TRANSPORT-20260807-001.md",
        "automation/controller.py",
        "automation/controller.config.json",
        "automation/result.schema.json",
        "automation/roadmap.schema.json",
        "automation/roadmap.example.json",
        "automation/roadmap-generator-prompt.md",
    ]
    missing = [value for value in required if not (root / value).is_file()]
    if missing:
        print(f"FAIL: missing files: {missing}", file=sys.stderr)
        return 1

    numbered = sorted((root / "automation" / "numbered").glob("*.md"))
    appendices = sorted((root / "automation" / "appendices").glob("*.md"))
    if len(numbered) != 38:
        print(f"FAIL: expected 38 numbered prompts, found {len(numbered)}", file=sys.stderr)
        return 1
    if len(appendices) != 3:
        print(f"FAIL: expected 3 appendices, found {len(appendices)}", file=sys.stderr)
        return 1

    for path in numbered + appendices:
        text = path.read_text(encoding="utf-8")
        if "BEGIN PROMPT" not in text or "END PROMPT" not in text:
            print(f"FAIL: prompt boundaries missing in {path}", file=sys.stderr)
            return 1

    roadmap = json.loads((root / "automation" / "roadmap.example.json").read_text())
    if len(roadmap["stages"]) != 38:
        print("FAIL: example roadmap does not contain 38 numbered stages", file=sys.stderr)
        return 1
    if roadmap["normal_execution"]["include_appendix_b"] is not False:
        print("FAIL: Appendix B is enabled in normal execution", file=sys.stderr)
        return 1
    if roadmap["normal_execution"]["include_appendix_c"] is not False:
        print("FAIL: Appendix C is enabled in normal execution", file=sys.stderr)
        return 1
    for letter in ("B", "C"):
        item = roadmap["appendices"][letter]
        if item["normal_execution_eligible"] is not False:
            print(f"FAIL: Appendix {letter} is normal-execution eligible", file=sys.stderr)
            return 1
        if item["hard_lock"]["enabled_by_default"] is not False:
            print(f"FAIL: Appendix {letter} hard lock is enabled by default", file=sys.stderr)
            return 1

    compile_result = subprocess.run(
        [sys.executable, "-m", "py_compile", "automation/controller.py"],
        cwd=root,
    )
    if compile_result.returncode != 0:
        return compile_result.returncode

    approval_compile_result = subprocess.run(
        [sys.executable, "-m", "py_compile", "automation/approval_manager.py"],
        cwd=root,
    )
    if approval_compile_result.returncode != 0:
        return approval_compile_result.returncode

    approval_check_result = subprocess.run(
        [
            sys.executable,
            "automation/approval_manager.py",
            "check",
            "--manifest",
            "automation/approvals/stage-manifests/AZPR-H0-TRANSPORT-20260807-001.json",
            "--ticket",
            "automation/approvals/tickets/AZPR-H0-TRANSPORT-20260807-001.json",
            "--review",
            "automation/approvals/reviews/AZPR-H0-TRANSPORT-20260807-001.md",
        ],
        cwd=root,
    )
    if approval_check_result.returncode != 0:
        return approval_check_result.returncode

    validate_result = subprocess.run(
        [sys.executable, "automation/controller.py", "validate-roadmap", "automation/roadmap.example.json"],
        cwd=root,
    )
    if validate_result.returncode != 0:
        return validate_result.returncode

    print("PASS: autonomous-loop bundle smoke test")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
