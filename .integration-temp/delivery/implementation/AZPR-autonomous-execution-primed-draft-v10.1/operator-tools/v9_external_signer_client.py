#!/usr/bin/env python3
"""Authenticated external qualification-receipt signing client.

The verifier supplies only an unsigned receipt and request metadata. This module
executes a separately qualified signer *client* command; it never accepts a
private-key path or key material. Production deployments must bind that client
to an organization-controlled remote/HSM-backed signing service.
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
import stat
import subprocess
from pathlib import Path
from typing import Any

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

MAX_RESPONSE = 2 * 1024 * 1024


def canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def sha_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def safe_executable(path: Path) -> Path:
    path = Path(path).absolute()
    for candidate in [path, *path.parents]:
        info = os.lstat(candidate)
        if stat.S_ISLNK(info.st_mode) or info.st_mode & 0o022:
            raise SystemExit(f"untrusted external signer client path: {candidate}")
        if candidate == candidate.parent:
            break
    info = os.stat(path)
    if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or not info.st_mode & 0o111:
        raise SystemExit("external signer client is not a single-link executable regular file")
    return path


def load_receipt_public_key(path: Path) -> Ed25519PublicKey:
    try:
        key = serialization.load_pem_public_key(Path(path).read_bytes())
    except Exception as exc:
        raise SystemExit("invalid qualification receipt verification key") from exc
    if not isinstance(key, Ed25519PublicKey):
        raise SystemExit("qualification receipt verification key is not Ed25519")
    return key


def request_external_signature(
    *,
    unsigned_receipt: dict[str, Any],
    signer_client: Path,
    signer_identity_sha256: str,
    receipt_public_key: Path,
    request_nonce: str,
    timeout_seconds: int = 30,
) -> dict[str, Any]:
    """Request and verify a receipt signature without loading any private key."""
    client = safe_executable(signer_client)
    actual_client_sha = hashlib.sha256(client.read_bytes()).hexdigest()
    if actual_client_sha != signer_identity_sha256:
        raise SystemExit("external signer client identity mismatch")
    if any(token in canonical(unsigned_receipt).decode(errors="ignore").lower() for token in ("private_key_pem", "private-key", "private_key_path")):
        raise SystemExit("signing request contains forbidden private-key material")
    request = {
        "format_version": "1.0",
        "request_kind": "AZPR_V9_EXTERNAL_RECEIPT_SIGNING_REQUEST",
        "request_nonce": request_nonce,
        "signer_identity_sha256": signer_identity_sha256,
        "unsigned_receipt_sha256": sha_bytes(canonical(unsigned_receipt)),
        "unsigned_receipt": unsigned_receipt,
    }
    proc = subprocess.run(
        [str(client), "sign-receipt"],
        input=json.dumps(request, sort_keys=True),
        text=True,
        capture_output=True,
        timeout=timeout_seconds,
        env={"PATH": "/usr/bin:/bin", "LANG": "C", "LC_ALL": "C", "HOME": "/nonexistent"},
    )
    if proc.returncode != 0 or len(proc.stdout.encode()) > MAX_RESPONSE:
        raise SystemExit("external receipt signing service failed closed")
    try:
        response = json.loads(proc.stdout)
    except Exception as exc:
        raise SystemExit("external receipt signer returned invalid JSON") from exc
    expected = {
        "format_version", "response_kind", "request_nonce", "signer_identity_sha256",
        "unsigned_receipt_sha256", "signed_receipt",
    }
    if not isinstance(response, dict) or set(response) != expected:
        raise SystemExit("external signer response shape mismatch")
    if response.get("format_version") != "1.0" or response.get("response_kind") != "AZPR_V9_EXTERNAL_RECEIPT_SIGNING_RESPONSE":
        raise SystemExit("external signer response identity mismatch")
    if response.get("request_nonce") != request_nonce or response.get("signer_identity_sha256") != signer_identity_sha256:
        raise SystemExit("external signer response request/identity mismatch")
    if response.get("unsigned_receipt_sha256") != request["unsigned_receipt_sha256"]:
        raise SystemExit("external signer response receipt hash mismatch")
    receipt = response.get("signed_receipt")
    if not isinstance(receipt, dict):
        raise SystemExit("external signer response lacks signed receipt")
    unsigned = dict(receipt)
    signature = unsigned.pop("signature", None)
    if unsigned != unsigned_receipt:
        raise SystemExit("external signer altered the unsigned receipt")
    try:
        load_receipt_public_key(receipt_public_key).verify(
            base64.b64decode(str(signature), validate=True), canonical(unsigned_receipt)
        )
    except (InvalidSignature, ValueError, TypeError) as exc:
        raise SystemExit("external receipt signature verification failed") from exc
    return receipt
