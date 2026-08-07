#!/usr/bin/env python3
"""Versioned v10 qualification bindings and hardened bootstrap-root checks."""
from __future__ import annotations

import base64
import hashlib
import json
import os
import stat
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

TOOLS = Path(__file__).resolve().parents[1] / "operator-tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))
from v10_trusted_io import load_trusted_json, read_trusted_regular  # noqa: E402

QUALIFICATION_ARTIFACT_SET_VERSION = "2.1"
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
    "external_signer_client",
    "external_signer_identity",
    "git_binary",
    "governing_policy_source",
    "handoff_quota_profile",
    "host_qualification_roots_authority_public_key",
    "host_qualification_roots_manifest",
    "host_root_anchor_client",
    "host_root_anchor_identity",
    "installation_signing_private_key",
    "installation_signing_public_key",
    "installer_fault_matrix_report",
    "key_custody_qualification_report",
    "key_lifecycle_state",
    "phase_transition_keyring",
    "probe_attestor_keyring",
    "probe_attestor_revocation_state",
    "probe_keyring",
    "probe_policy",
    "probe_revocation_state",
    "probe_service_attestation",
    "probe_service_executable",
    "probe_service_identity",
    "python_binary",
    "qualification_authorization_keyring",
    "qualification_probe_envelopes_manifest",
    "qualification_receipt_signing_public_key",
    "qualification_revocation_list",
    "qualification_trust_authority_public_key",
    "qualification_trust_manifest",
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
assert len(REQUIRED_QUALIFIED_ARTIFACTS) == 57

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
    fd = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_CLOEXEC", 0))
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
        identity_before = (
            before.st_dev, before.st_ino, before.st_size, before.st_mode,
            before.st_uid, before.st_gid, before.st_mtime_ns, before.st_ctime_ns,
        )
        identity_after = (
            after.st_dev, after.st_ino, after.st_size, after.st_mode,
            after.st_uid, after.st_gid, after.st_mtime_ns, after.st_ctime_ns,
        )
        if identity_before != identity_after:
            raise SystemExit(f"qualified artifact changed during verification: {path}")
        return h.hexdigest(), (before.st_dev, before.st_ino)
    finally:
        os.close(fd)


def verify_versioned_artifact_bindings(
    manifest: dict[str, Any],
    receipt_bindings: dict[str, str],
    expected_paths: dict[str, Path],
) -> tuple[dict[str, str], str]:
    if manifest.get("format_version") != "1.0" or manifest.get("artifact_set_version") != QUALIFICATION_ARTIFACT_SET_VERSION:
        raise SystemExit("qualified artifact input manifest version mismatch")
    entries = manifest.get("artifacts")
    required = set(REQUIRED_QUALIFIED_ARTIFACTS)
    if not isinstance(entries, dict) or set(entries) != required:
        raise SystemExit(
            f"qualified artifact input set mismatch; missing={sorted(required-set(entries or {}))} "
            f"extra={sorted(set(entries or {})-required)}"
        )
    if not isinstance(receipt_bindings, dict) or set(receipt_bindings) != required:
        raise SystemExit("qualification receipt does not contain the exact v10.1 versioned 57-artifact map")
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


# Compatibility name for narrowly shared callers; the semantics are v10/versioned.
verify_complete_artifact_bindings = verify_versioned_artifact_bindings


def _parse_time(value: Any, label: str) -> datetime:
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).astimezone(timezone.utc)
    except Exception as exc:
        raise SystemExit(f"invalid bootstrap {label}") from exc


def verify_bootstrap_roots(
    manifest_path: Path,
    authority_public_key_path: Path,
    *,
    qualification_authorization_keyring: Path,
    qualification_receipt_public_key: Path,
    phase_transition_keyring: Path,
    authorization_anchor: Path,
    qualification_trust_manifest: Path,
    qualification_trust_authority_public_key: Path,
    host_qualification_roots_manifest: Path,
    host_qualification_roots_authority_public_key: Path,
    trusted_ancestor: Path = Path("/etc"),
    expected_owner_uid: int = 0,
    minimum_sequence: int = 1,
) -> dict[str, Any]:
    """Verify caller roots against no-follow, independently provisioned bootstrap roots."""
    read_args = {"trusted_ancestor": trusted_ancestor, "expected_owner_uid": expected_owner_uid}
    manifest, manifest_read = load_trusted_json(manifest_path, **read_args)
    authority_read = read_trusted_regular(authority_public_key_path, **read_args)
    required = {
        "format_version", "bootstrap_kind", "manifest_id", "sequence", "issued_at", "expires_at",
        "roots", "signer_key_id", "signature",
    }
    if set(manifest) != required:
        raise SystemExit("bootstrap root manifest field set mismatch")
    if manifest.get("format_version") != "1.0" or manifest.get("bootstrap_kind") != "AZPR_V10_HOST_BOOTSTRAP_ROOTS":
        raise SystemExit("bootstrap root manifest identity mismatch")
    if int(manifest.get("sequence", 0)) < minimum_sequence:
        raise SystemExit("bootstrap root manifest sequence is stale")
    now = datetime.now(timezone.utc)
    if _parse_time(manifest["issued_at"], "issued_at") > now or _parse_time(manifest["expires_at"], "expires_at") < now:
        raise SystemExit("bootstrap root manifest is not currently valid")
    unsigned = dict(manifest)
    signature = unsigned.pop("signature")
    try:
        key = serialization.load_pem_public_key(authority_read.data)
        if not isinstance(key, Ed25519PublicKey):
            raise SystemExit("bootstrap authority key is not Ed25519")
        key.verify(base64.b64decode(str(signature), validate=True), canonical(unsigned))
    except (InvalidSignature, ValueError, TypeError) as exc:
        raise SystemExit("bootstrap root manifest signature verification failed") from exc

    qualification_trust_manifest_read = read_trusted_regular(qualification_trust_manifest, **read_args)
    qualification_trust_authority_read = read_trusted_regular(qualification_trust_authority_public_key, **read_args)
    host_qualification_roots_manifest_read = read_trusted_regular(host_qualification_roots_manifest, **read_args)
    host_qualification_roots_authority_read = read_trusted_regular(host_qualification_roots_authority_public_key, **read_args)
    expected = {
        "qualification_authorization_keyring_sha256": hash_regular(qualification_authorization_keyring)[0],
        "qualification_receipt_signing_public_key_sha256": hash_regular(qualification_receipt_public_key)[0],
        "phase_transition_keyring_sha256": hash_regular(phase_transition_keyring)[0],
        "authorization_anchor_identity_sha256": hash_regular(authorization_anchor)[0],
        "qualification_trust_manifest_sha256": sha_bytes(qualification_trust_manifest_read.data),
        "qualification_trust_authority_public_key_sha256": sha_bytes(qualification_trust_authority_read.data),
        "host_qualification_roots_manifest_sha256": sha_bytes(host_qualification_roots_manifest_read.data),
        "host_qualification_roots_authority_public_key_sha256": sha_bytes(host_qualification_roots_authority_read.data),
    }
    if manifest.get("roots") != expected:
        raise SystemExit("caller-selected security root differs from pinned bootstrap")
    return {
        **manifest,
        "bootstrap_manifest_sha256": sha_bytes(manifest_read.data),
        "bootstrap_authority_public_key_sha256": sha_bytes(authority_read.data),
    }


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
        "qualification_trust_binding_sha256": prior.get("qualification_trust_binding_sha256"),
        "qualification_artifact_set_version": prior.get("qualification_artifact_set_version"),
    }
    for key, value in expected.items():
        if phase_authorization.get(key) != value:
            raise SystemExit(f"phase transition exact prior-state binding mismatch: {key}")
    return phase_authorization
