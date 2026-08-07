#!/usr/bin/env python3
"""Review and sign one schema-valid AZPR JSON document.

This operator tool is intentionally separate from the controller and Codex. It
writes a new create-once output file and never edits the reviewed input in place.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import stat
from pathlib import Path
from typing import Any

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from jsonschema import Draft202012Validator
from referencing import Registry, Resource


def canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode("utf-8")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def strict_regular(path: Path, label: str, *, private: bool = False) -> bytes:
    path = path.expanduser().absolute()
    current = path
    for candidate in [current, *current.parents]:
        info = os.lstat(candidate)
        if stat.S_ISLNK(info.st_mode):
            raise SystemExit(f"{label} path is symlinked: {candidate}")
        if candidate == current and not stat.S_ISREG(info.st_mode):
            raise SystemExit(f"{label} must be a regular file.")
        if candidate == candidate.parent:
            break
    info = os.stat(path)
    if info.st_nlink != 1:
        raise SystemExit(f"{label} must have exactly one hard link.")
    if private and info.st_mode & 0o077:
        raise SystemExit(f"{label} must have mode 0600 or stricter.")
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(path, flags)
    try:
        return os.read(fd, info.st_size + 1)
    finally:
        os.close(fd)


def schema_registry(schema_dir: Path) -> Registry:
    registry = Registry()
    for path in sorted(schema_dir.glob("*.json")):
        value = json.loads(strict_regular(path, f"schema {path.name}").decode("utf-8"))
        registry = registry.with_resource(path.name, Resource.from_contents(value))
        registry = registry.with_resource(path.as_uri(), Resource.from_contents(value))
    return registry


def write_create_once(path: Path, payload: bytes) -> None:
    path = path.expanduser().absolute()
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    for candidate in [path.parent, *path.parent.parents]:
        info = os.lstat(candidate)
        if stat.S_ISLNK(info.st_mode):
            raise SystemExit(f"Output ancestor is symlinked: {candidate}")
        if candidate == candidate.parent:
            break
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(path, flags, 0o600)
    try:
        os.write(fd, payload)
        os.fsync(fd)
    finally:
        os.close(fd)
    directory_fd = os.open(path.parent, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
    try:
        os.fsync(directory_fd)
    finally:
        os.close(directory_fd)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("document")
    parser.add_argument("--output", required=True)
    parser.add_argument("--private-key", required=True)
    parser.add_argument("--key-id", required=True)
    parser.add_argument("--schema", required=True)
    parser.add_argument("--schema-dir", required=True)
    parser.add_argument("--confirm", help="Non-interactive exact confirmation phrase displayed by --review-only.")
    parser.add_argument("--review-only", action="store_true")
    args = parser.parse_args()

    document_path = Path(args.document).expanduser().absolute()
    schema_path = Path(args.schema).expanduser().absolute()
    schema_dir = Path(args.schema_dir).expanduser().absolute()
    payload = json.loads(strict_regular(document_path, "document").decode("utf-8"))
    if not isinstance(payload, dict):
        raise SystemExit("Document must be an object.")
    if payload.get("signatures") not in (None, []) and not isinstance(payload.get("signatures"), list):
        raise SystemExit("Document signatures must be an array.")

    unsigned = dict(payload)
    unsigned.pop("signatures", None)
    unsigned_hash = sha256_bytes(canonical(unsigned))
    schema_hash = sha256_bytes(strict_regular(schema_path, "schema"))
    phrase = f"SIGN {unsigned_hash} AS {args.key_id}"

    print(json.dumps({
        "document": str(document_path),
        "unsigned_sha256": unsigned_hash,
        "schema": str(schema_path),
        "schema_sha256": schema_hash,
        "key_id": args.key_id,
        "output": str(Path(args.output).expanduser().absolute()),
        "confirmation_phrase": phrase,
    }, indent=2))
    if args.review_only:
        return 0
    if args.confirm is None:
        supplied = input("Type the exact confirmation phrase: ")
    else:
        supplied = args.confirm
    if supplied != phrase:
        raise SystemExit("Confirmation phrase mismatch; nothing was signed.")

    key_bytes = strict_regular(Path(args.private_key), "private key", private=True)
    key = serialization.load_pem_private_key(key_bytes, password=None)
    if not isinstance(key, Ed25519PrivateKey):
        raise SystemExit("Private key must be Ed25519.")
    signature = base64.b64encode(key.sign(canonical(unsigned))).decode("ascii")
    signatures = [item for item in payload.get("signatures", []) if isinstance(item, dict) and item.get("key_id") != args.key_id]
    signatures.append({"key_id": args.key_id, "ed25519": signature})
    signed = dict(payload)
    signed["signatures"] = signatures

    schema = json.loads(strict_regular(schema_path, "schema").decode("utf-8"))
    Draft202012Validator.check_schema(schema)
    errors = sorted(Draft202012Validator(schema, registry=schema_registry(schema_dir)).iter_errors(signed), key=str)
    if errors:
        raise SystemExit("Signed document fails schema validation: " + "; ".join(error.message for error in errors[:5]))

    output = json.dumps(signed, indent=2, sort_keys=True, ensure_ascii=False).encode("utf-8") + b"\n"
    write_create_once(Path(args.output), output)
    print(f"Created signed document: {Path(args.output).expanduser().absolute()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
