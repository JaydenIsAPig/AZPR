#!/usr/bin/env python3
"""Complete v9 qualification-to-installation binding and bootstrap-root checks."""
from __future__ import annotations

import base64
import hashlib
import json
import os
import stat
from pathlib import Path
from typing import Any, Callable

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

REQUIRED_QUALIFIED_ARTIFACTS = (
    "agent_execution_profile",
    "anchor_helper",
    "approval_keyring",
    "build_provenance",
    "bundle_attestation",
    "bundle_signing_public_key",
    "bundle_zip",
    "codex_binary",
    "codex_isolation_qualification_report",
    "container_engine",
    "dedicated_host_policy",
    "dependency_lock",
    "dependency_mirror_attestation",
    "dependency_mirror_inventory",
    "dependency_mirror_public_key",
    "evidence_keyring",
    "evidence_private_key",
    "evidence_public_key",
    "git_binary",
    "governing_policy_source",
    "handoff_quota_profile",
    "installation_signing_private_key",
    "installation_signing_public_key",
    "installer_fault_matrix_report",
    "key_custody_qualification_report",
    "python_binary",
    "qualification_authorization_keyring",
    "key_lifecycle_state",
    "qualification_receipt_signing_public_key",
    "qualification_revocation_list",
    "remote_anchor_qualification_report",
    "requirements_input",
    "runtime_private_key",
    "runtime_public_key",
    "sbom",
    "supply_chain_rebuild_report",
    "validation_dockerfile",
    "validation_image_attestation",
    "validation_registry_proof",
)
assert len(REQUIRED_QUALIFIED_ARTIFACTS) == 39
MAX_ARTIFACT_BYTES = 128 * 1024 * 1024


def canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def sha_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def hash_regular(path: Path, *, allow_secret: bool = False) -> tuple[str, tuple[int, int]]:
    path = Path(path).absolute()
    for parent in [path, *path.parents]:
        st = os.lstat(parent)
        if stat.S_ISLNK(st.st_mode):
            raise SystemExit(f"qualified artifact has symlink ancestor: {path}")
        if parent == parent.parent:
            break
    fd = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    try:
        before = os.fstat(fd)
        if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1:
            raise SystemExit(f"qualified artifact is not a single-link regular file: {path}")
        if before.st_size > MAX_ARTIFACT_BYTES:
            raise SystemExit(f"qualified artifact exceeds size limit: {path}")
        if before.st_mode & 0o022:
            raise SystemExit(f"qualified artifact is group/world writable: {path}")
        if os.geteuid() == 0 and before.st_uid != 0:
            raise SystemExit(f"qualified artifact is not root-owned: {path}")
        if allow_secret and before.st_mode & 0o077:
            raise SystemExit(f"qualified secret artifact permissions are too broad: {path}")
        h = hashlib.sha256()
        total = 0
        while True:
            chunk = os.read(fd, 65536)
            if not chunk:
                break
            total += len(chunk)
            if total > MAX_ARTIFACT_BYTES:
                raise SystemExit(f"qualified artifact exceeds read limit: {path}")
            h.update(chunk)
        after = os.fstat(fd)
        identity_before = (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns)
        identity_after = (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns)
        if identity_before != identity_after:
            raise SystemExit(f"qualified artifact changed during verification: {path}")
        return h.hexdigest(), (before.st_dev, before.st_ino)
    finally:
        os.close(fd)


def verify_complete_artifact_bindings(
    manifest: dict[str, Any],
    receipt_bindings: dict[str, str],
    expected_paths: dict[str, Path],
) -> tuple[dict[str, str], str]:
    if manifest.get("format_version") != "1.0":
        raise SystemExit("qualified artifact input manifest version mismatch")
    entries = manifest.get("artifacts")
    required = set(REQUIRED_QUALIFIED_ARTIFACTS)
    if not isinstance(entries, dict) or set(entries) != required:
        raise SystemExit(
            f"qualified artifact input set mismatch; missing={sorted(required-set(entries or {}))} "
            f"extra={sorted(set(entries or {})-required)}"
        )
    if not isinstance(receipt_bindings, dict) or set(receipt_bindings) != required:
        raise SystemExit("qualification receipt does not contain the exact canonical 39-artifact map")
    actual: dict[str, str] = {}
    identities: dict[tuple[int, int], str] = {}
    for name in REQUIRED_QUALIFIED_ARTIFACTS:
        row = entries[name]
        if not isinstance(row, dict) or set(row) != {"path", "sha256", "secret"}:
            raise SystemExit(f"qualified artifact manifest row malformed: {name}")
        path = Path(str(row["path"])).absolute()
        if name in expected_paths and path != Path(expected_paths[name]).absolute():
            raise SystemExit(f"qualified artifact manifest path differs from installer input: {name}")
        digest, identity = hash_regular(path, allow_secret=bool(row["secret"]))
        if identity in identities:
            raise SystemExit(f"qualified artifact alias: {identities[identity]} and {name}")
        identities[identity] = name
        if row["sha256"] != digest:
            raise SystemExit(f"qualified artifact input manifest hash mismatch: {name}")
        if receipt_bindings[name] != digest:
            raise SystemExit(f"qualified artifact differs from receipt before reservation: {name}")
        actual[name] = digest
    aggregate = sha_bytes(canonical(actual))
    return actual, aggregate


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(Path(path).read_bytes())
    except Exception as exc:
        raise SystemExit(f"invalid bootstrap JSON: {path}") from exc
    if not isinstance(value, dict):
        raise SystemExit(f"bootstrap JSON must be an object: {path}")
    return value


def verify_bootstrap_roots(
    manifest_path: Path,
    authority_public_key_path: Path,
    *,
    qualification_authorization_keyring: Path,
    qualification_receipt_public_key: Path,
    phase_transition_keyring: Path,
    authorization_anchor: Path,
) -> dict[str, Any]:
    """Verify caller inputs against independently provisioned, fixed bootstrap roots."""
    manifest = _read_json(manifest_path)
    unsigned = dict(manifest)
    signature = unsigned.pop("signature", None)
    if manifest.get("format_version") != "1.0" or manifest.get("bootstrap_kind") != "AZPR_V9_HOST_BOOTSTRAP_ROOTS":
        raise SystemExit("bootstrap root manifest identity mismatch")
    try:
        key = serialization.load_pem_public_key(Path(authority_public_key_path).read_bytes())
        if not isinstance(key, Ed25519PublicKey):
            raise SystemExit("bootstrap authority key is not Ed25519")
        key.verify(base64.b64decode(str(signature), validate=True), canonical(unsigned))
    except (InvalidSignature, ValueError, TypeError) as exc:
        raise SystemExit("bootstrap root manifest signature verification failed") from exc
    roots = manifest.get("roots")
    expected = {
        "qualification_authorization_keyring_sha256": hash_regular(qualification_authorization_keyring)[0],
        "qualification_receipt_signing_public_key_sha256": hash_regular(qualification_receipt_public_key)[0],
        "phase_transition_keyring_sha256": hash_regular(phase_transition_keyring)[0],
        "authorization_anchor_identity_sha256": hash_regular(authorization_anchor)[0],
    }
    if roots != expected:
        raise SystemExit("caller-selected qualification, receipt, phase, or anchor root differs from pinned bootstrap")
    return manifest


def verify_phase_transition(
    *,
    installation_phase: str,
    active_lock_path: Path,
    authorization: dict[str, Any],
    phase_authorization: dict[str, Any] | None,
    canonical_policy_record_path: Path | None,
    prior_receipt_path: Path | None,
    qualification_launcher_evidence_path: Path | None,
    fault_matrix_evidence_path: Path | None,
    load_json: Callable[[Path, str], dict[str, Any]],
) -> dict[str, Any] | None:
    active_exists = Path(active_lock_path).exists()
    if not active_exists:
        if installation_phase != "QUALIFICATION_ONLY":
            raise SystemExit("first installation may only be QUALIFICATION_ONLY")
        if authorization.get("canonical_policy_status") != "NOT_YET_APPROVED":
            raise SystemExit("first installation cannot authorize an approved canonical policy")
        if phase_authorization is not None:
            raise SystemExit("first installation must not include a phase-transition authorization")
        return None
    if installation_phase == "QUALIFICATION_ONLY":
        if phase_authorization is not None:
            raise SystemExit("qualification-only installation must not include a phase-transition authorization")
        return None
    if installation_phase != "POLICY_ACTIVATED":
        raise SystemExit("unknown installation phase")
    if phase_authorization is None or canonical_policy_record_path is None:
        raise SystemExit("policy activation requires a separate phase-transition authorization and policy record")
    lock = load_json(Path(active_lock_path), "prior active installation lock")
    prior_manifest = Path(str(lock.get("manifest_path")))
    prior = load_json(prior_manifest, "prior trusted installation manifest")
    if prior.get("installation_phase") != "QUALIFICATION_ONLY":
        raise SystemExit("policy activation requires an immutable prior qualification-only generation")
    if prior_receipt_path is None or qualification_launcher_evidence_path is None or fault_matrix_evidence_path is None:
        raise SystemExit("phase transition requires prior receipt and exact launcher/fault evidence")
    expected = {
        "prior_installation_id": prior.get("installation_id"),
        "prior_manifest_sha256": hash_regular(prior_manifest)[0],
        "prior_lock_sha256": hash_regular(Path(active_lock_path))[0],
        "prior_installation_receipt_sha256": hash_regular(prior_receipt_path)[0],
        "host_id": prior.get("host_id"),
        "qualification_launcher_evidence_sha256": hash_regular(qualification_launcher_evidence_path)[0],
        "fault_matrix_evidence_sha256": hash_regular(fault_matrix_evidence_path)[0],
        "canonical_policy_record_sha256": hash_regular(canonical_policy_record_path)[0],
    }
    for key, value in expected.items():
        if phase_authorization.get(key) != value:
            raise SystemExit(f"phase-transition authorization does not bind exact {key}")
    if phase_authorization.get("qualification_launcher_status") != "PASS" or phase_authorization.get("fault_matrix_status") != "PASS":
        raise SystemExit("phase transition lacks successful launcher/fault qualification")
    return prior
