#!/usr/bin/env python3
"""Independently provisioned host qualification roots for AZPR v10.1.

The production loader accepts no caller-selected root path, owner UID, sequence
floor, signer executable, or receipt key. Tests may use the explicitly named
private loader to construct isolated fixtures; that function is not reachable
from the qualification input contract or CLI.
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
import secrets
import subprocess
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from v10_trusted_io import TrustedRead, read_trusted_regular

HOST_ROOT = Path("/etc/azpr/bootstrap")
HOST_OWNER_UID = 0
HOST_MANIFEST_NAME = "host-qualification-roots-v10.1.json"
HOST_AUTHORITY_KEY_NAME = "host-qualification-roots-authority-v10.1.pem"
HOST_MANIFEST_KIND = "AZPR_V10_1_HOST_QUALIFICATION_ROOTS"
MAX_CLOCK_SKEW_SECONDS = 300

ROOT_FILENAMES = {
    "qualification_trust_manifest": "qualification-trust-manifest-v10.1.json",
    "qualification_trust_authority_public_key": "qualification-trust-authority-v10.1.pem",
    "probe_keyring": "probe-keyring-v10.1.json",
    "probe_policy": "probe-policy-v10.1.json",
    "probe_service_identity": "probe-service-identity-v10.1.json",
    "probe_service_attestation": "probe-service-attestation-v10.1.json",
    "probe_revocation_state": "probe-revocation-state-v10.1.json",
    "probe_attestor_keyring": "probe-attestor-keyring-v10.1.json",
    "probe_attestor_revocation_state": "probe-attestor-revocation-state-v10.1.json",
    "probe_service_executable": "probe-service-v10.1",
    "external_signer_client": "external-receipt-signer-client-v10.1",
    "external_signer_identity": "external-receipt-signer-identity-v10.1.json",
    "qualification_receipt_signing_public_key": "qualification-receipt-signing-v10.1.pem",
    "host_root_anchor_client": "host-root-anchor-client-v10.1",
    "host_root_anchor_identity": "host-root-anchor-identity-v10.1.json",
}


def canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def sha_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def parse_time(value: Any, label: str) -> datetime:
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).astimezone(timezone.utc)
    except Exception as exc:
        raise SystemExit(f"invalid host qualification {label} timestamp") from exc


@dataclass(frozen=True)
class HostQualificationContext:
    root: Path
    owner_uid: int
    manifest: dict[str, Any]
    manifest_sha256: str
    manifest_raw: bytes
    authority_public_key_sha256: str
    authority_public_key_raw: bytes
    paths: dict[str, Path]
    reads: dict[str, TrustedRead]
    hashes: dict[str, str]
    minimum_trust_sequence: int
    minimum_probe_revocation_sequence: int
    minimum_attestor_revocation_sequence: int
    external_signer_identity_sha256: str
    external_signer_id: str
    receipt_signing_key_id: str
    host_id: str
    candidate_archive_sha256: str
    challenge_sha256: str
    remote_anchor_id: str
    remote_anchor_head_sequence: int
    remote_anchor_identity_sha256: str
    remote_anchor_client_sha256: str

    def artifact_results(self) -> dict[str, dict[str, Any]]:
        result: dict[str, dict[str, Any]] = {
            "host_qualification_roots_manifest": {
                "path": str(self.root / HOST_MANIFEST_NAME),
                "sha256": self.manifest_sha256,
                "raw": self.manifest_raw,
            },
            "host_qualification_roots_authority_public_key": {
                "path": str(self.root / HOST_AUTHORITY_KEY_NAME),
                "sha256": self.authority_public_key_sha256,
                "raw": self.authority_public_key_raw,
            },
        }
        for name in ROOT_FILENAMES:
            result[name] = {
                "path": str(self.paths[name]),
                "sha256": self.hashes[name],
                "raw": self.reads[name].data,
            }
        return result



def _verify_remote_anchor_head(
    *,
    manifest: dict[str, Any],
    manifest_sha256: str,
    reads: dict[str, TrustedRead],
    hashes: dict[str, str],
    paths: dict[str, Path],
    current: datetime,
) -> tuple[str, int, str, str]:
    try:
        identity = json.loads(reads["host_root_anchor_identity"].data)
    except Exception as exc:
        raise SystemExit("invalid host-root anchor identity JSON") from exc
    fields = {
        "format_version", "identity_kind", "anchor_id", "anchor_client_sha256",
        "anchor_public_key_pem", "host_id", "candidate_archive_sha256",
        "not_before", "not_after",
    }
    if not isinstance(identity, dict) or set(identity) != fields:
        raise SystemExit("host-root anchor identity field set mismatch")
    if identity.get("format_version") != "1.0" or identity.get("identity_kind") != "AZPR_V10_1_HOST_ROOT_ANCHOR_IDENTITY":
        raise SystemExit("host-root anchor identity mismatch")
    if identity.get("anchor_client_sha256") != hashes["host_root_anchor_client"]:
        raise SystemExit("host-root anchor identity does not bind fixed client")
    if identity.get("host_id") != manifest["host_id"] or identity.get("candidate_archive_sha256") != manifest["candidate_archive_sha256"]:
        raise SystemExit("host-root anchor identity common binding mismatch")
    skew = timedelta(seconds=MAX_CLOCK_SKEW_SECONDS)
    not_before = parse_time(identity["not_before"], "anchor identity not_before")
    not_after = parse_time(identity["not_after"], "anchor identity not_after")
    if not_before > current + skew or not_after <= current or not_after <= not_before:
        raise SystemExit("host-root anchor identity is not currently valid")
    try:
        anchor_key = serialization.load_pem_public_key(str(identity["anchor_public_key_pem"]).encode())
    except Exception as exc:
        raise SystemExit("invalid host-root anchor public key") from exc
    if not isinstance(anchor_key, Ed25519PublicKey):
        raise SystemExit("host-root anchor key is not Ed25519")
    nonce = "host-root-head-" + secrets.token_hex(16)
    request = {
        "format_version": "1.0",
        "request_kind": "AZPR_V10_1_VERIFY_HOST_ROOT_HEAD",
        "request_nonce": nonce,
        "anchor_id": identity["anchor_id"],
        "host_id": manifest["host_id"],
        "candidate_archive_sha256": manifest["candidate_archive_sha256"],
        "challenge_sha256": manifest["challenge_sha256"],
        "host_qualification_roots_manifest_sha256": manifest_sha256,
        "host_qualification_roots_manifest_sequence": int(manifest["sequence"]),
    }
    try:
        proc = subprocess.run(
            [str(paths["host_root_anchor_client"]), "verify-host-root-head"],
            input=json.dumps(request, sort_keys=True), text=True, capture_output=True,
            timeout=15, start_new_session=True,
            env={"PATH": "/usr/bin:/bin", "HOME": "/nonexistent", "LANG": "C", "LC_ALL": "C"},
        )
    except subprocess.TimeoutExpired as exc:
        raise SystemExit("host-root remote anchor query timed out") from exc
    if proc.returncode != 0 or len(proc.stdout.encode()) > 1024 * 1024 or len(proc.stderr.encode()) > 1024 * 1024:
        raise SystemExit("host-root remote anchor query failed closed")
    try:
        response = json.loads(proc.stdout)
    except Exception as exc:
        raise SystemExit("host-root remote anchor returned invalid JSON") from exc
    response_fields = {
        "format_version", "response_kind", "request_nonce", "anchor_id", "host_id",
        "candidate_archive_sha256", "challenge_sha256",
        "host_qualification_roots_manifest_sha256",
        "host_qualification_roots_manifest_sequence", "observed_at",
        "previous_anchor_head_sha256", "signature",
    }
    if not isinstance(response, dict) or set(response) != response_fields:
        raise SystemExit("host-root remote anchor response shape mismatch")
    if response.get("format_version") != "1.0" or response.get("response_kind") != "AZPR_V10_1_HOST_ROOT_HEAD_RESPONSE":
        raise SystemExit("host-root remote anchor response identity mismatch")
    checks = {
        "request_nonce": nonce, "anchor_id": identity["anchor_id"],
        "host_id": manifest["host_id"], "candidate_archive_sha256": manifest["candidate_archive_sha256"],
        "challenge_sha256": manifest["challenge_sha256"],
        "host_qualification_roots_manifest_sha256": manifest_sha256,
        "host_qualification_roots_manifest_sequence": int(manifest["sequence"]),
    }
    for field, expected in checks.items():
        if response.get(field) != expected:
            raise SystemExit(f"host-root remote anchor head mismatch: {field}")
    observed = parse_time(response["observed_at"], "anchor observed_at")
    manifest_issued = parse_time(manifest["issued_at"], "issued_at")
    if observed > current + skew or observed < manifest_issued:
        raise SystemExit("host-root remote anchor chronology invalid")
    previous = response.get("previous_anchor_head_sha256")
    if previous is not None and (not isinstance(previous, str) or len(previous) != 64 or any(c not in "0123456789abcdef" for c in previous)):
        raise SystemExit("host-root remote anchor previous head invalid")
    unsigned = dict(response)
    signature = unsigned.pop("signature")
    try:
        anchor_key.verify(base64.b64decode(str(signature), validate=True), canonical(unsigned))
    except (InvalidSignature, ValueError, TypeError) as exc:
        raise SystemExit("host-root remote anchor signature failed") from exc
    return str(identity["anchor_id"]), int(response["host_qualification_roots_manifest_sequence"]), hashes["host_root_anchor_identity"], hashes["host_root_anchor_client"]

def _load_host_qualification_context(
    root: Path,
    *,
    owner_uid: int,
    expected_host_id: str,
    expected_candidate_archive_sha256: str,
    expected_challenge_sha256: str,
    now: datetime | None = None,
) -> HostQualificationContext:
    """Private fixture-capable loader; production calls the fixed wrapper below."""
    current = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    root = Path(root).absolute()
    kwargs = {"trusted_ancestor": root, "expected_owner_uid": owner_uid}
    manifest_read = read_trusted_regular(root / HOST_MANIFEST_NAME, **kwargs)
    authority_read = read_trusted_regular(root / HOST_AUTHORITY_KEY_NAME, **kwargs)
    try:
        manifest = json.loads(manifest_read.data)
    except Exception as exc:
        raise SystemExit("invalid host qualification root manifest JSON") from exc
    required = {
        "format_version", "manifest_kind", "manifest_id", "sequence", "issued_at",
        "not_before", "not_after", "host_id", "candidate_archive_sha256",
        "challenge_sha256", "minimum_trust_sequence", "minimum_probe_revocation_sequence",
        "minimum_attestor_revocation_sequence", "external_signer_id",
        "external_signer_identity_sha256", "receipt_signing_key_id", "roots",
        "signer_key_id", "signature",
    }
    if not isinstance(manifest, dict) or set(manifest) != required:
        raise SystemExit("host qualification root manifest field set mismatch")
    if manifest.get("format_version") != "1.0" or manifest.get("manifest_kind") != HOST_MANIFEST_KIND:
        raise SystemExit("host qualification root manifest identity mismatch")
    if int(manifest.get("sequence", 0)) < 1:
        raise SystemExit("host qualification root manifest sequence invalid")
    issued = parse_time(manifest["issued_at"], "issued_at")
    not_before = parse_time(manifest["not_before"], "not_before")
    not_after = parse_time(manifest["not_after"], "not_after")
    skew = timedelta(seconds=MAX_CLOCK_SKEW_SECONDS)
    if issued > current + skew or issued < not_before or issued > not_after:
        raise SystemExit("host qualification root manifest issuance chronology invalid")
    if not_before > current + skew or not_after <= current or not_after <= not_before:
        raise SystemExit("host qualification root manifest is not currently valid")
    expected_common = {
        "host_id": expected_host_id,
        "candidate_archive_sha256": expected_candidate_archive_sha256,
        "challenge_sha256": expected_challenge_sha256,
    }
    for field, expected in expected_common.items():
        if manifest.get(field) != expected:
            raise SystemExit(f"host qualification root manifest {field} mismatch")
    unsigned = dict(manifest)
    signature = unsigned.pop("signature")
    try:
        key = serialization.load_pem_public_key(authority_read.data)
        if not isinstance(key, Ed25519PublicKey):
            raise SystemExit("host qualification authority key is not Ed25519")
        key.verify(base64.b64decode(str(signature), validate=True), canonical(unsigned))
    except (InvalidSignature, ValueError, TypeError) as exc:
        raise SystemExit("host qualification root manifest signature failed") from exc

    roots = manifest.get("roots")
    if not isinstance(roots, dict) or set(roots) != set(ROOT_FILENAMES):
        raise SystemExit("host qualification root membership mismatch")
    paths: dict[str, Path] = {}
    reads: dict[str, TrustedRead] = {}
    hashes: dict[str, str] = {}
    identities: set[tuple[int, int]] = set()
    for name, filename in ROOT_FILENAMES.items():
        row = roots.get(name)
        if not isinstance(row, dict) or set(row) != {"filename", "sha256"} or row.get("filename") != filename:
            raise SystemExit(f"host qualification root row malformed: {name}")
        path = root / filename
        read = read_trusted_regular(
            path,
            trusted_ancestor=root,
            expected_owner_uid=owner_uid,
            require_executable=name in {"probe_service_executable", "external_signer_client", "host_root_anchor_client"},
        )
        identity = (read.device, read.inode)
        if identity in identities:
            raise SystemExit(f"host qualification root alias detected: {name}")
        identities.add(identity)
        digest = sha_bytes(read.data)
        if digest != row.get("sha256"):
            raise SystemExit(f"host qualification root hash mismatch: {name}")
        paths[name] = path
        reads[name] = read
        hashes[name] = digest

    try:
        signer_identity = json.loads(reads["external_signer_identity"].data)
    except Exception as exc:
        raise SystemExit("invalid external signer identity JSON") from exc
    expected_signer_fields = {
        "format_version", "identity_kind", "signer_id", "signer_client_sha256",
        "receipt_signing_public_key_sha256", "host_id", "candidate_archive_sha256",
        "not_before", "not_after",
    }
    if not isinstance(signer_identity, dict) or set(signer_identity) != expected_signer_fields:
        raise SystemExit("external signer identity field set mismatch")
    if signer_identity.get("format_version") != "1.0" or signer_identity.get("identity_kind") != "AZPR_V10_1_EXTERNAL_RECEIPT_SIGNER_IDENTITY":
        raise SystemExit("external signer identity mismatch")
    if signer_identity.get("signer_client_sha256") != hashes["external_signer_client"]:
        raise SystemExit("external signer identity does not bind fixed client")
    if signer_identity.get("receipt_signing_public_key_sha256") != hashes["qualification_receipt_signing_public_key"]:
        raise SystemExit("external signer identity does not bind fixed receipt key")
    for field in ("host_id", "candidate_archive_sha256"):
        if signer_identity.get(field) != expected_common[field]:
            raise SystemExit(f"external signer identity {field} mismatch")
    s_nb = parse_time(signer_identity["not_before"], "signer not_before")
    s_na = parse_time(signer_identity["not_after"], "signer not_after")
    if s_nb > current + skew or s_na <= current or s_na <= s_nb:
        raise SystemExit("external signer identity is not currently valid")
    if sha_bytes(reads["external_signer_identity"].data) != manifest["external_signer_identity_sha256"]:
        raise SystemExit("host manifest external signer identity hash mismatch")

    remote_anchor_id, remote_anchor_head_sequence, remote_anchor_identity_sha256, remote_anchor_client_sha256 = _verify_remote_anchor_head(
        manifest=manifest, manifest_sha256=sha_bytes(manifest_read.data), reads=reads, hashes=hashes, paths=paths, current=current
    )

    return HostQualificationContext(
        root=root,
        owner_uid=owner_uid,
        manifest=manifest,
        manifest_sha256=sha_bytes(manifest_read.data),
        manifest_raw=manifest_read.data,
        authority_public_key_sha256=sha_bytes(authority_read.data),
        authority_public_key_raw=authority_read.data,
        paths=paths,
        reads=reads,
        hashes=hashes,
        minimum_trust_sequence=int(manifest["minimum_trust_sequence"]),
        minimum_probe_revocation_sequence=int(manifest["minimum_probe_revocation_sequence"]),
        minimum_attestor_revocation_sequence=int(manifest["minimum_attestor_revocation_sequence"]),
        external_signer_identity_sha256=str(manifest["external_signer_identity_sha256"]),
        external_signer_id=str(manifest["external_signer_id"]),
        receipt_signing_key_id=str(manifest["receipt_signing_key_id"]),
        host_id=expected_host_id,
        candidate_archive_sha256=expected_candidate_archive_sha256,
        challenge_sha256=expected_challenge_sha256,
        remote_anchor_id=remote_anchor_id,
        remote_anchor_head_sequence=remote_anchor_head_sequence,
        remote_anchor_identity_sha256=remote_anchor_identity_sha256,
        remote_anchor_client_sha256=remote_anchor_client_sha256,
    )


def load_host_qualification_context(
    *,
    expected_host_id: str,
    expected_candidate_archive_sha256: str,
    expected_challenge_sha256: str,
    now: datetime | None = None,
) -> HostQualificationContext:
    """Production loader: all root-selection values are fixed in source/host state."""
    return _load_host_qualification_context(
        HOST_ROOT,
        owner_uid=HOST_OWNER_UID,
        expected_host_id=expected_host_id,
        expected_candidate_archive_sha256=expected_candidate_archive_sha256,
        expected_challenge_sha256=expected_challenge_sha256,
        now=now,
    )
