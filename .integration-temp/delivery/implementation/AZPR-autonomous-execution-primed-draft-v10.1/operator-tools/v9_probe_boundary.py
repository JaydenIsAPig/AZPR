#!/usr/bin/env python3
"""Verify externally produced no-secret probe envelopes without executing targets."""
from __future__ import annotations

import base64
import hashlib
import json
import os
import stat
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

MAX_JSON = 4 * 1024 * 1024
TARGETS = (
    "git_binary", "python_binary", "codex_binary", "container_engine", "anchor_helper",
    "mount_binary", "umount_binary", "cleanroom_adapter", "qualification_verifier",
)


def canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def sha_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def read_regular(path: Path) -> bytes:
    fd = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    try:
        st = os.fstat(fd)
        if not stat.S_ISREG(st.st_mode) or st.st_nlink != 1 or st.st_size > MAX_JSON:
            raise SystemExit(f"unsafe probe envelope input: {path}")
        data = bytearray()
        while True:
            chunk = os.read(fd, 65536)
            if not chunk:
                break
            data.extend(chunk)
            if len(data) > MAX_JSON:
                raise SystemExit(f"probe envelope input too large: {path}")
        return bytes(data)
    finally:
        os.close(fd)


def load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(read_regular(path))
    except Exception as exc:
        raise SystemExit(f"invalid probe envelope JSON: {path}") from exc
    if not isinstance(value, dict):
        raise SystemExit(f"probe envelope must be an object: {path}")
    return value


def load_probe_keyring(value: dict[str, Any]) -> dict[str, tuple[Ed25519PublicKey, set[str], str]]:
    if value.get("format_version") != "1.0" or not isinstance(value.get("keys"), list):
        raise SystemExit("probe keyring format invalid")
    result: dict[str, tuple[Ed25519PublicKey, set[str], str]] = {}
    signers: set[str] = set()
    fingerprints: set[str] = set()
    for row in value["keys"]:
        try:
            key_id = str(row["key_id"])
            signer_id = str(row["signer_id"])
            roles = set(row["roles"])
            key = serialization.load_pem_public_key(str(row["public_key_pem"]).encode())
        except Exception as exc:
            raise SystemExit("invalid probe keyring entry") from exc
        if not isinstance(key, Ed25519PublicKey):
            raise SystemExit("probe keyring contains non-Ed25519 key")
        raw = key.public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
        fp = sha_bytes(raw)
        if key_id in result or signer_id in signers or fp in fingerprints:
            raise SystemExit("duplicate probe key ID, signer, or cryptographic material")
        result[key_id] = (key, roles, signer_id)
        signers.add(signer_id)
        fingerprints.add(fp)
    return result


def _parse_time(value: Any, label: str) -> datetime:
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).astimezone(timezone.utc)
    except Exception as exc:
        raise SystemExit(f"invalid probe {label} timestamp") from exc


def verify_probe_envelope(
    envelope: dict[str, Any],
    *,
    expected_role: str,
    expected_target_sha256: str,
    expected_probe_policy_sha256: str,
    keys: dict[str, tuple[Ed25519PublicKey, set[str], str]],
) -> str:
    if envelope.get("format_version") != "1.0" or envelope.get("envelope_kind") != "AZPR_V9_NO_SECRET_PROBE_RESULT":
        raise SystemExit("probe envelope identity mismatch")
    if envelope.get("target_role") != expected_role or envelope.get("target_sha256") != expected_target_sha256:
        raise SystemExit(f"probe envelope target substitution: {expected_role}")
    if envelope.get("probe_policy_sha256") != expected_probe_policy_sha256:
        raise SystemExit(f"probe envelope policy mismatch: {expected_role}")
    boundary = envelope.get("boundary")
    required_boundary = {
        "rootless": True,
        "no_secrets": True,
        "host_mounts": False,
        "daemon_sockets": False,
        "pid_namespace": True,
        "mount_namespace": True,
        "cgroup_v2": True,
        "disposable": True,
    }
    if not isinstance(boundary, dict):
        raise SystemExit(f"probe boundary missing: {expected_role}")
    expected_boundary_keys = set(required_boundary) | {"run_as_uid", "run_as_gid", "network_mode"}
    if set(boundary) != expected_boundary_keys:
        raise SystemExit(f"probe boundary field set mismatch for {expected_role}")
    for key, expected in required_boundary.items():
        if boundary.get(key) is not expected:
            raise SystemExit(f"probe boundary invariant failed for {expected_role}: {key}")
    if int(boundary.get("run_as_uid", 0)) <= 0 or int(boundary.get("run_as_gid", 0)) <= 0:
        raise SystemExit(f"probe ran as root for {expected_role}")
    if boundary.get("network_mode") not in {"DENY_ALL", "ISOLATED_CONTROLLED_ENDPOINT_ONLY"}:
        raise SystemExit(f"probe network boundary invalid for {expected_role}")
    observations = envelope.get("observations")
    required_observations = {
        "secret_read_denied", "host_read_denied", "network_denied", "mount_denied",
        "daemon_access_denied", "escape_denied", "resource_exhaustion_contained",
        "evidence_mutation_denied",
    }
    if not isinstance(observations, dict) or set(observations) != required_observations or any(value is not True for value in observations.values()):
        raise SystemExit(f"probe adverse-action containment failed for {expected_role}")
    if int(envelope.get("exit_code", -1)) != 0:
        raise SystemExit(f"probe target failed for {expected_role}")
    started = _parse_time(envelope.get("started_at"), "started_at")
    completed = _parse_time(envelope.get("completed_at"), "completed_at")
    now = datetime.now(timezone.utc)
    if completed < started or completed > now or (now - completed).total_seconds() > 14 * 86400:
        raise SystemExit(f"probe envelope stale or temporally invalid: {expected_role}")
    unsigned = dict(envelope)
    signature = unsigned.pop("signature", None)
    key_id = str(envelope.get("signer_key_id"))
    entry = keys.get(key_id)
    if not entry or "qualification-probe-service" not in entry[1]:
        raise SystemExit(f"probe envelope signer lacks required role: {expected_role}")
    try:
        entry[0].verify(base64.b64decode(str(signature), validate=True), canonical(unsigned))
    except (InvalidSignature, ValueError, TypeError) as exc:
        raise SystemExit(f"probe envelope signature failed: {expected_role}") from exc
    return entry[2]


def verify_probe_manifest(
    manifest_path: Path,
    *,
    target_hashes: dict[str, str],
    probe_keyring: dict[str, Any],
) -> dict[str, str]:
    manifest = load_json(manifest_path)
    if manifest.get("format_version") != "1.0" or manifest.get("manifest_kind") != "AZPR_V9_PROBE_ENVELOPES_MANIFEST":
        raise SystemExit("probe envelope manifest identity mismatch")
    rows = manifest.get("envelopes")
    if not isinstance(rows, dict) or set(rows) != set(TARGETS):
        raise SystemExit("probe envelope manifest target set mismatch")
    if set(target_hashes) != set(TARGETS):
        raise SystemExit("expected probe target set mismatch")
    keys = load_probe_keyring(probe_keyring)
    policy_hash = str(manifest.get("probe_policy_sha256"))
    hashes: dict[str, str] = {}
    signer_ids: set[str] = set()
    for target in TARGETS:
        row = rows[target]
        if not isinstance(row, dict) or set(row) != {"path", "sha256"}:
            raise SystemExit(f"probe manifest row malformed: {target}")
        path = Path(str(row["path"])).absolute()
        raw = read_regular(path)
        digest = sha_bytes(raw)
        if digest != row["sha256"]:
            raise SystemExit(f"probe envelope file hash mismatch: {target}")
        envelope = json.loads(raw)
        signer = verify_probe_envelope(
            envelope,
            expected_role=target,
            expected_target_sha256=target_hashes[target],
            expected_probe_policy_sha256=policy_hash,
            keys=keys,
        )
        signer_ids.add(signer)
        hashes[target] = digest
    aggregate = sha_bytes(canonical(hashes))
    if manifest.get("aggregate_sha256") != aggregate:
        raise SystemExit("probe envelope aggregate mismatch")
    if not signer_ids:
        raise SystemExit("probe manifest lacks authenticated signer identity")
    return hashes
