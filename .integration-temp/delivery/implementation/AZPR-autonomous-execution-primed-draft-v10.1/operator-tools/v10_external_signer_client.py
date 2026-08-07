#!/usr/bin/env python3
"""AZPR v10.1 external receipt-signing client using fixed host trust context."""
from __future__ import annotations

import base64
import hashlib
import json
import subprocess
from typing import Any

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from v10_1_host_trust import HostQualificationContext

MAX_RESPONSE = 2 * 1024 * 1024


def canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def sha_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _receipt_key(context: HostQualificationContext) -> Ed25519PublicKey:
    try:
        key = serialization.load_pem_public_key(context.reads["qualification_receipt_signing_public_key"].data)
    except Exception as exc:
        raise SystemExit("invalid independently provisioned qualification receipt key") from exc
    if not isinstance(key, Ed25519PublicKey):
        raise SystemExit("qualification receipt verification key is not Ed25519")
    return key


def request_external_signature(
    *,
    unsigned_receipt: dict[str, Any],
    qualification_trust_binding: dict[str, Any],
    host_context: HostQualificationContext,
    request_nonce: str,
    timeout_seconds: int = 30,
) -> dict[str, Any]:
    """Request signing through the client pinned by the independently loaded host root."""
    client = host_context.paths["external_signer_client"]
    actual_client_sha = host_context.hashes["external_signer_client"]
    if actual_client_sha != host_context.manifest["roots"]["external_signer_client"]["sha256"]:
        raise SystemExit("external signer client identity mismatch")
    binding_hash = sha_bytes(canonical(qualification_trust_binding))
    if unsigned_receipt.get("qualification_trust_binding") != qualification_trust_binding:
        raise SystemExit("unsigned receipt omits or changes qualification trust binding")
    if unsigned_receipt.get("qualification_trust_binding_sha256") != binding_hash:
        raise SystemExit("unsigned receipt qualification trust binding hash mismatch")
    if unsigned_receipt.get("external_signer_identity_sha256") != host_context.external_signer_identity_sha256:
        raise SystemExit("unsigned receipt omits independently provisioned external signer identity")
    if unsigned_receipt.get("signer_key_id") != host_context.receipt_signing_key_id:
        raise SystemExit("unsigned receipt signer key ID differs from host root")
    if any(token in canonical(unsigned_receipt).decode(errors="ignore").lower() for token in ("private_key_pem", "private-key", "private_key_path")):
        raise SystemExit("signing request contains forbidden private-key material")
    request = {
        "format_version": "1.1",
        "request_kind": "AZPR_V10_1_EXTERNAL_RECEIPT_SIGNING_REQUEST",
        "request_nonce": request_nonce,
        "signer_id": host_context.external_signer_id,
        "signer_identity_sha256": host_context.external_signer_identity_sha256,
        "host_qualification_roots_manifest_sha256": host_context.manifest_sha256,
        "qualification_trust_binding": qualification_trust_binding,
        "qualification_trust_binding_sha256": binding_hash,
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
        start_new_session=True,
    )
    if proc.returncode != 0 or len(proc.stdout.encode()) > MAX_RESPONSE or len(proc.stderr.encode()) > MAX_RESPONSE:
        raise SystemExit("external receipt signing service failed closed")
    try:
        response = json.loads(proc.stdout)
    except Exception as exc:
        raise SystemExit("external receipt signer returned invalid JSON") from exc
    expected = {
        "format_version", "response_kind", "request_nonce", "signer_id", "signer_identity_sha256",
        "host_qualification_roots_manifest_sha256", "qualification_trust_binding_sha256",
        "unsigned_receipt_sha256", "signed_receipt",
    }
    if not isinstance(response, dict) or set(response) != expected:
        raise SystemExit("external signer response shape mismatch")
    if response.get("format_version") != "1.1" or response.get("response_kind") != "AZPR_V10_1_EXTERNAL_RECEIPT_SIGNING_RESPONSE":
        raise SystemExit("external signer response identity mismatch")
    if response.get("request_nonce") != request_nonce:
        raise SystemExit("external signer response nonce mismatch")
    if response.get("signer_id") != host_context.external_signer_id or response.get("signer_identity_sha256") != host_context.external_signer_identity_sha256:
        raise SystemExit("external signer response identity mismatch")
    if response.get("host_qualification_roots_manifest_sha256") != host_context.manifest_sha256:
        raise SystemExit("external signer did not validate fixed host roots")
    if response.get("qualification_trust_binding_sha256") != binding_hash:
        raise SystemExit("external signer did not validate exact qualification trust binding")
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
        _receipt_key(host_context).verify(base64.b64decode(str(signature), validate=True), canonical(unsigned_receipt))
    except (InvalidSignature, ValueError, TypeError) as exc:
        raise SystemExit("external receipt signature verification failed") from exc
    return receipt
