#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import stat
from pathlib import Path
from typing import Any

EXPECTED_NAME = "AZPR-autonomous-execution-primed-draft-v8-reports"
EXPECTED_TYPE = "reports"
MANIFEST_NAME = "SHA256SUMS.json"


def fail(message: str) -> None:
    raise SystemExit(f"REPORTS_BUNDLE_VERIFY_FAIL: {message}")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        fail(f"cannot parse {path.name}: {exc}")
    if not isinstance(value, dict):
        fail(f"{path.name} must be a JSON object")
    return value


def inventory(root: Path) -> dict[str, str]:
    result: dict[str, str] = {}
    for path in sorted(root.rglob("*")):
        rel = path.relative_to(root).as_posix()
        info = os.lstat(path)
        if stat.S_ISLNK(info.st_mode):
            fail(f"symlink member is forbidden: {rel}")
        if path.is_dir():
            continue
        if not stat.S_ISREG(info.st_mode):
            fail(f"non-regular member is forbidden: {rel}")
        if rel == MANIFEST_NAME:
            continue
        result[rel] = sha256(path)
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("root", nargs="?", default=str(Path(__file__).resolve().parent))
    args = parser.parse_args()
    root = Path(args.root).resolve()
    manifest_path = root / MANIFEST_NAME
    if not manifest_path.is_file():
        fail("missing SHA256SUMS.json")
    manifest = load_json(manifest_path)
    expected_metadata = {
        "format_version": "1.0",
        "algorithm": "SHA-256",
        "bundle_name": EXPECTED_NAME,
        "bundle_type": EXPECTED_TYPE,
        "excludes": [MANIFEST_NAME],
    }
    for key, value in expected_metadata.items():
        if manifest.get(key) != value:
            fail(f"manifest {key} mismatch")
    entries = manifest.get("entries")
    if not isinstance(entries, dict) or not all(isinstance(k, str) and isinstance(v, str) for k, v in entries.items()):
        fail("manifest entries must be a string-to-string object")
    if manifest.get("expected_inventory_count") != len(entries):
        fail("manifest inventory count does not match entry count")
    actual = inventory(root)
    if set(actual) != set(entries):
        missing = sorted(set(entries) - set(actual))
        extra = sorted(set(actual) - set(entries))
        fail(f"inventory mismatch; missing={missing}, extra={extra}")
    mismatches = [name for name, digest in actual.items() if entries.get(name) != digest]
    if mismatches:
        fail(f"hash mismatch: {mismatches}")
    print(json.dumps({
        "status": "PASS_REPORTS_BUNDLE",
        "bundle_name": EXPECTED_NAME,
        "bundle_type": EXPECTED_TYPE,
        "inventory_count": len(actual),
        "safe_for_unattended_execution_now": False,
    }, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
