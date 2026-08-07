#!/usr/bin/env python3
"""AZPR v10.1 independently rooted probe-policy and envelope verification."""
from __future__ import annotations

import base64
import hashlib
import json
import os
import stat
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from v10_1_host_trust import HostQualificationContext

MAX_JSON = 4 * 1024 * 1024
MAX_CLOCK_SKEW_SECONDS = 300
TARGETS = (
    "git_binary", "python_binary", "codex_binary", "container_engine", "anchor_helper",
    "mount_binary", "umount_binary", "cleanroom_adapter", "qualification_verifier",
)
TRUST_MANIFEST_KIND = "AZPR_V10_1_QUALIFICATION_TRUST_ROOTS"
ENVELOPE_KIND = "AZPR_V10_1_NO_SECRET_PROBE_RESULT"
MANIFEST_KIND = "AZPR_V10_1_PROBE_ENVELOPES_MANIFEST"
ARTIFACT_SET_VERSION = "2.1"
REQUIRED_OBSERVATION_NAMES = (
    "secret_read_denied", "host_read_denied", "network_denied", "mount_denied",
    "daemon_access_denied", "escape_denied", "resource_exhaustion_contained",
    "evidence_mutation_denied",
)
BOUNDARY_FIELDS = {
    "rootless", "no_secrets", "host_mounts", "daemon_sockets", "pid_namespace",
    "mount_namespace", "cgroup_v2", "disposable", "run_as_uid", "run_as_gid",
    "network_mode",
}


def canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def sha_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _parse_time(value: Any, label: str) -> datetime:
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).astimezone(timezone.utc)
    except Exception as exc:
        raise SystemExit(f"invalid {label} timestamp") from exc


def _read_regular(path: Path) -> bytes:
    path = Path(path).absolute()
    for candidate in [path, *path.parents]:
        info = os.lstat(candidate)
        if stat.S_ISLNK(info.st_mode):
            raise SystemExit(f"symlinked probe input: {candidate}")
        if candidate == candidate.parent:
            break
    fd = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_CLOEXEC", 0))
    try:
        before = os.fstat(fd)
        if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1 or before.st_size > MAX_JSON:
            raise SystemExit(f"unsafe probe input: {path}")
        if before.st_mode & 0o022:
            raise SystemExit(f"writable probe input: {path}")
        chunks: list[bytes] = []
        total = 0
        while True:
            chunk = os.read(fd, 65536)
            if not chunk:
                break
            total += len(chunk)
            if total > MAX_JSON:
                raise SystemExit(f"probe input too large: {path}")
            chunks.append(chunk)
        after = os.fstat(fd)
        before_id = (before.st_dev, before.st_ino, before.st_size, before.st_mode, before.st_uid, before.st_gid, before.st_mtime_ns, before.st_ctime_ns)
        after_id = (after.st_dev, after.st_ino, after.st_size, after.st_mode, after.st_uid, after.st_gid, after.st_mtime_ns, after.st_ctime_ns)
        if before_id != after_id:
            raise SystemExit(f"probe input changed during read: {path}")
        return b"".join(chunks)
    finally:
        os.close(fd)


def _load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(_read_regular(path))
    except Exception as exc:
        raise SystemExit(f"invalid probe JSON: {path}") from exc
    if not isinstance(value, dict):
        raise SystemExit(f"probe JSON must be an object: {path}")
    return value


def _exact(value: dict[str, Any], expected: set[str], label: str) -> None:
    if set(value) != expected:
        raise SystemExit(f"{label} field set mismatch: missing={sorted(expected-set(value))} extra={sorted(set(value)-expected)}")


@dataclass(frozen=True)
class ApprovedProbeKey:
    public_key: Ed25519PublicKey
    roles: frozenset[str]
    signer_id: str
    not_before: datetime
    not_after: datetime


@dataclass(frozen=True)
class ApprovedProbePolicy:
    policy_version: str
    required_boundary: dict[str, Any]
    required_observations: tuple[str, ...]
    maximum_envelope_age_seconds: int


@dataclass(frozen=True)
class ApprovedProbeAuthority:
    keys: dict[str, ApprovedProbeKey]
    service_id: str
    policy: ApprovedProbePolicy
    trust_binding: dict[str, Any]
    trust_binding_sha256: str
    trust_manifest_sha256: str
    probe_policy_sha256: str
    not_before: datetime
    not_after: datetime
    revoked_key_ids: frozenset[str]

    @property
    def policy_version(self) -> str:
        return self.policy.policy_version


def _load_public_key(raw: bytes, label: str) -> Ed25519PublicKey:
    try:
        key = serialization.load_pem_public_key(raw)
    except Exception as exc:
        raise SystemExit(f"invalid {label} public key") from exc
    if not isinstance(key, Ed25519PublicKey):
        raise SystemExit(f"{label} public key is not Ed25519")
    return key


def _parse_json(raw: bytes, label: str) -> dict[str, Any]:
    try:
        value = json.loads(raw)
    except Exception as exc:
        raise SystemExit(f"invalid {label} JSON") from exc
    if not isinstance(value, dict):
        raise SystemExit(f"{label} must be an object")
    return value


def _load_role_keyring(
    value: dict[str, Any],
    *,
    kind: str,
    expected_service_id: str,
    required_role: str,
    not_before: datetime,
    not_after: datetime,
) -> tuple[dict[str, ApprovedProbeKey], int]:
    _exact(value, {"format_version", "keyring_kind", "keyring_id", "sequence", "service_id", "keys"}, kind)
    if value.get("format_version") != "1.0" or value.get("keyring_kind") != kind:
        raise SystemExit(f"{kind} identity mismatch")
    if value.get("service_id") != expected_service_id or int(value.get("sequence", 0)) < 1:
        raise SystemExit(f"{kind} service or sequence mismatch")
    rows = value.get("keys")
    if not isinstance(rows, list) or not rows or len(rows) > 16:
        raise SystemExit(f"{kind} key count invalid")
    keys: dict[str, ApprovedProbeKey] = {}
    signer_ids: set[str] = set()
    fingerprints: set[str] = set()
    for row in rows:
        if not isinstance(row, dict):
            raise SystemExit(f"{kind} entry is not an object")
        _exact(row, {"key_id", "signer_id", "roles", "public_key_pem", "not_before", "not_after"}, f"{kind} entry")
        key = _load_public_key(str(row["public_key_pem"]).encode(), kind)
        key_id = str(row["key_id"])
        signer_id = str(row["signer_id"])
        roles_raw = row["roles"]
        if not isinstance(roles_raw, list) or not (1 <= len(roles_raw) <= 4):
            raise SystemExit(f"{kind} roles invalid")
        roles = frozenset(str(v) for v in roles_raw)
        key_nb = _parse_time(row["not_before"], f"{kind} key not_before")
        key_na = _parse_time(row["not_after"], f"{kind} key not_after")
        fingerprint = sha_bytes(key.public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw))
        if key_id in keys or signer_id in signer_ids or fingerprint in fingerprints:
            raise SystemExit(f"duplicate {kind} key ID, signer, or key material")
        if signer_id != expected_service_id or required_role not in roles:
            raise SystemExit(f"{kind} key role or service mismatch")
        if key_nb < not_before or key_na > not_after or key_na <= key_nb:
            raise SystemExit(f"{kind} key validity escapes trust interval")
        keys[key_id] = ApprovedProbeKey(key, roles, signer_id, key_nb, key_na)
        signer_ids.add(signer_id)
        fingerprints.add(fingerprint)
    return keys, int(value["sequence"])


def _validate_revocations(
    value: dict[str, Any],
    *,
    expected_kind: str,
    expected_service_id: str,
    minimum_sequence: int,
    keyring_sequence: int,
    trust_issued_at: datetime,
    not_before: datetime,
    now: datetime,
) -> tuple[frozenset[str], int, datetime]:
    _exact(value, {"format_version", "revocation_kind", "sequence", "service_id", "issued_at", "revoked_key_ids"}, expected_kind)
    if value.get("format_version") != "1.0" or value.get("revocation_kind") != expected_kind:
        raise SystemExit(f"{expected_kind} identity mismatch")
    sequence = int(value.get("sequence", 0))
    if value.get("service_id") != expected_service_id or sequence < max(minimum_sequence, keyring_sequence):
        raise SystemExit(f"{expected_kind} sequence/service mismatch")
    issued = _parse_time(value["issued_at"], f"{expected_kind} issued_at")
    skew = timedelta(seconds=MAX_CLOCK_SKEW_SECONDS)
    if issued > now + skew or issued < not_before or issued < trust_issued_at:
        raise SystemExit(f"{expected_kind} issuance chronology invalid")
    rows = value.get("revoked_key_ids")
    if not isinstance(rows, list) or len(rows) > 128 or any(not isinstance(v, str) or len(v) > 128 for v in rows):
        raise SystemExit(f"{expected_kind} revoked key list invalid")
    if len(rows) != len(set(rows)):
        raise SystemExit(f"{expected_kind} duplicate revoked key ID")
    return frozenset(rows), sequence, issued


def load_approved_probe_authority(
    *,
    host_context: HostQualificationContext,
    expected_host_id: str,
    expected_candidate_archive_sha256: str,
    expected_challenge_sha256: str,
    now: datetime | None = None,
) -> ApprovedProbeAuthority:
    """Verify the probe authority exclusively from independently loaded host roots."""
    current = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    reads = host_context.reads
    hashes = host_context.hashes
    trust_manifest = _parse_json(reads["qualification_trust_manifest"].data, "qualification trust manifest")
    authority_key = _load_public_key(reads["qualification_trust_authority_public_key"].data, "qualification trust authority")
    trust_fields = {
        "format_version", "trust_manifest_kind", "trust_manifest_id", "sequence", "issued_at",
        "not_before", "not_after", "host_id", "candidate_archive_sha256", "challenge_sha256",
        "probe_service_id", "probe_attestor_id", "probe_keyring_sha256", "probe_policy_sha256",
        "probe_service_identity_sha256", "probe_service_attestation_sha256",
        "probe_revocation_state_sha256", "probe_attestor_keyring_sha256",
        "probe_attestor_revocation_state_sha256", "probe_service_executable_sha256",
        "external_signer_identity_sha256", "qualification_receipt_signing_public_key_sha256",
        "signer_key_id", "signature",
    }
    _exact(trust_manifest, trust_fields, "qualification trust manifest")
    if trust_manifest.get("format_version") != "1.1" or trust_manifest.get("trust_manifest_kind") != TRUST_MANIFEST_KIND:
        raise SystemExit("qualification trust manifest identity mismatch")
    if int(trust_manifest.get("sequence", 0)) < host_context.minimum_trust_sequence:
        raise SystemExit("qualification trust manifest sequence is stale")
    issued = _parse_time(trust_manifest["issued_at"], "trust issued_at")
    not_before = _parse_time(trust_manifest["not_before"], "trust not_before")
    not_after = _parse_time(trust_manifest["not_after"], "trust not_after")
    skew = timedelta(seconds=MAX_CLOCK_SKEW_SECONDS)
    if issued > current + skew or issued < not_before or issued > not_after:
        raise SystemExit("qualification trust manifest issuance chronology invalid")
    if not_before > current + skew or not_after <= current or not_after <= not_before:
        raise SystemExit("qualification trust manifest is not currently valid")
    common = {
        "host_id": expected_host_id,
        "candidate_archive_sha256": expected_candidate_archive_sha256,
        "challenge_sha256": expected_challenge_sha256,
    }
    for field, expected in common.items():
        if trust_manifest.get(field) != expected or getattr(host_context, field) != expected:
            raise SystemExit(f"qualification trust manifest {field} mismatch")
    unsigned = dict(trust_manifest)
    signature = unsigned.pop("signature")
    try:
        authority_key.verify(base64.b64decode(str(signature), validate=True), canonical(unsigned))
    except (InvalidSignature, ValueError, TypeError) as exc:
        raise SystemExit("qualification trust manifest signature failed") from exc

    hash_fields = {
        "probe_keyring": "probe_keyring_sha256",
        "probe_policy": "probe_policy_sha256",
        "probe_service_identity": "probe_service_identity_sha256",
        "probe_service_attestation": "probe_service_attestation_sha256",
        "probe_revocation_state": "probe_revocation_state_sha256",
        "probe_attestor_keyring": "probe_attestor_keyring_sha256",
        "probe_attestor_revocation_state": "probe_attestor_revocation_state_sha256",
        "probe_service_executable": "probe_service_executable_sha256",
        "external_signer_identity": "external_signer_identity_sha256",
        "qualification_receipt_signing_public_key": "qualification_receipt_signing_public_key_sha256",
    }
    for name, field in hash_fields.items():
        if hashes[name] != trust_manifest[field]:
            raise SystemExit(f"qualification trust artifact hash mismatch: {name}")

    service_id = str(trust_manifest["probe_service_id"])
    attestor_id = str(trust_manifest["probe_attestor_id"])
    probe_keyring = _parse_json(reads["probe_keyring"].data, "probe keyring")
    keys, keyring_sequence = _load_role_keyring(
        probe_keyring,
        kind="AZPR_V10_1_APPROVED_PROBE_KEYRING",
        expected_service_id=service_id,
        required_role="qualification-probe-service",
        not_before=not_before,
        not_after=not_after,
    )
    attestor_keyring = _parse_json(reads["probe_attestor_keyring"].data, "probe attestor keyring")
    attestor_keys, attestor_keyring_sequence = _load_role_keyring(
        attestor_keyring,
        kind="AZPR_V10_1_PROBE_ATTESTOR_KEYRING",
        expected_service_id=attestor_id,
        required_role="probe-service-attestor",
        not_before=not_before,
        not_after=not_after,
    )

    policy = _parse_json(reads["probe_policy"].data, "probe policy")
    policy_fields = {
        "format_version", "policy_kind", "policy_version", "host_id", "candidate_archive_sha256",
        "challenge_sha256", "probe_service_id", "required_targets", "required_boundary",
        "required_observations", "maximum_envelope_age_seconds",
    }
    _exact(policy, policy_fields, "probe policy")
    if policy.get("format_version") != "1.1" or policy.get("policy_kind") != "AZPR_V10_1_PROBE_POLICY":
        raise SystemExit("probe policy identity mismatch")
    if policy.get("required_targets") != list(TARGETS):
        raise SystemExit("probe policy target set mismatch")
    for field, expected in {**common, "probe_service_id": service_id}.items():
        if policy.get(field) != expected:
            raise SystemExit(f"probe policy {field} mismatch")
    boundary = policy.get("required_boundary")
    if not isinstance(boundary, dict) or set(boundary) != BOUNDARY_FIELDS:
        raise SystemExit("probe policy required boundary field set mismatch")
    nonnegotiable = {
        "rootless": True, "no_secrets": True, "host_mounts": False, "daemon_sockets": False,
        "pid_namespace": True, "mount_namespace": True, "cgroup_v2": True, "disposable": True,
    }
    for field, expected in nonnegotiable.items():
        if boundary.get(field) is not expected:
            raise SystemExit(f"probe policy weakens non-negotiable boundary: {field}")
    if int(boundary.get("run_as_uid", 0)) <= 0 or int(boundary.get("run_as_gid", 0)) <= 0:
        raise SystemExit("probe policy permits root identity")
    if boundary.get("network_mode") not in {"DENY_ALL", "ISOLATED_CONTROLLED_ENDPOINT_ONLY"}:
        raise SystemExit("probe policy network mode invalid")
    observations = policy.get("required_observations")
    if not isinstance(observations, list) or tuple(observations) != REQUIRED_OBSERVATION_NAMES:
        raise SystemExit("probe policy required observations mismatch")
    maximum_age = int(policy.get("maximum_envelope_age_seconds", 0))
    if not 1 <= maximum_age <= 1209600:
        raise SystemExit("probe policy maximum envelope age invalid")
    approved_policy = ApprovedProbePolicy(str(policy["policy_version"]), dict(boundary), tuple(observations), maximum_age)

    identity = _parse_json(reads["probe_service_identity"].data, "probe service identity")
    identity_fields = {"format_version", "identity_kind", "service_id", "service_binary_sha256", "deployment_identity", "launcher_identity_sha256", "runtime_configuration_sha256"}
    _exact(identity, identity_fields, "probe service identity")
    if identity.get("format_version") != "1.1" or identity.get("identity_kind") != "AZPR_V10_1_PROBE_SERVICE_IDENTITY" or identity.get("service_id") != service_id:
        raise SystemExit("probe service identity mismatch")
    if identity.get("service_binary_sha256") != hashes["probe_service_executable"]:
        raise SystemExit("probe service identity does not match actual executable bytes")

    attestor_revocations = _parse_json(reads["probe_attestor_revocation_state"].data, "probe attestor revocations")
    revoked_attestors, att_rev_sequence, _ = _validate_revocations(
        attestor_revocations,
        expected_kind="AZPR_V10_1_PROBE_ATTESTOR_REVOCATIONS",
        expected_service_id=attestor_id,
        minimum_sequence=host_context.minimum_attestor_revocation_sequence,
        keyring_sequence=attestor_keyring_sequence,
        trust_issued_at=issued,
        not_before=not_before,
        now=current,
    )
    attestation = _parse_json(reads["probe_service_attestation"].data, "probe service attestation")
    attestation_fields = {
        "format_version", "attestation_kind", "attestation_id", "service_id", "service_identity_sha256",
        "service_executable_sha256", "launcher_identity_sha256", "runtime_configuration_sha256",
        "host_id", "candidate_archive_sha256", "challenge_sha256", "issued_at", "expires_at",
        "attestor_id", "attestor_key_id", "attestor_role", "signature",
    }
    _exact(attestation, attestation_fields, "probe service attestation")
    if attestation.get("format_version") != "1.1" or attestation.get("attestation_kind") != "AZPR_V10_1_PROBE_SERVICE_ATTESTATION":
        raise SystemExit("probe service attestation identity mismatch")
    if attestation.get("service_id") != service_id or attestation.get("attestor_id") != attestor_id or attestation.get("attestor_role") != "probe-service-attestor":
        raise SystemExit("probe service attestation service/attestor mismatch")
    if attestation.get("service_identity_sha256") != hashes["probe_service_identity"]:
        raise SystemExit("probe service attestation identity hash mismatch")
    for field in ("service_executable_sha256", "launcher_identity_sha256", "runtime_configuration_sha256"):
        expected = hashes["probe_service_executable"] if field == "service_executable_sha256" else identity[field]
        if attestation.get(field) != expected:
            raise SystemExit(f"probe service attestation {field} mismatch")
    for field, expected in common.items():
        if attestation.get(field) != expected:
            raise SystemExit(f"probe service attestation {field} mismatch")
    att_issued = _parse_time(attestation["issued_at"], "attestation issued_at")
    att_expires = _parse_time(attestation["expires_at"], "attestation expires_at")
    if att_issued > current + skew or att_issued < issued or att_expires <= current or att_expires > not_after or att_expires <= att_issued:
        raise SystemExit("probe service attestation chronology invalid")
    attestor_key_id = str(attestation["attestor_key_id"])
    attestor_key = attestor_keys.get(attestor_key_id)
    if attestor_key is None or attestor_key_id in revoked_attestors or not (attestor_key.not_before <= att_issued <= attestor_key.not_after):
        raise SystemExit("probe service attestation key is unapproved, revoked, or out of validity")
    att_unsigned = dict(attestation)
    att_signature = att_unsigned.pop("signature")
    try:
        attestor_key.public_key.verify(base64.b64decode(str(att_signature), validate=True), canonical(att_unsigned))
    except (InvalidSignature, ValueError, TypeError) as exc:
        raise SystemExit("probe service attestation signature failed") from exc

    revocations = _parse_json(reads["probe_revocation_state"].data, "probe revocations")
    revoked, rev_sequence, _ = _validate_revocations(
        revocations,
        expected_kind="AZPR_V10_1_PROBE_KEY_REVOCATIONS",
        expected_service_id=service_id,
        minimum_sequence=host_context.minimum_probe_revocation_sequence,
        keyring_sequence=keyring_sequence,
        trust_issued_at=issued,
        not_before=not_before,
        now=current,
    )

    trust_binding = {
        "binding_version": "1.1",
        "host_qualification_roots_manifest_sha256": host_context.manifest_sha256,
        "host_qualification_roots_authority_public_key_sha256": host_context.authority_public_key_sha256,
        "host_root_anchor_id": host_context.remote_anchor_id,
        "host_root_anchor_head_sequence": host_context.remote_anchor_head_sequence,
        "host_root_anchor_identity_sha256": host_context.remote_anchor_identity_sha256,
        "host_root_anchor_client_sha256": host_context.remote_anchor_client_sha256,
        "qualification_trust_manifest_sha256": hashes["qualification_trust_manifest"],
        "qualification_trust_authority_public_key_sha256": hashes["qualification_trust_authority_public_key"],
        "probe_keyring_sha256": hashes["probe_keyring"],
        "probe_policy_sha256": hashes["probe_policy"],
        "probe_service_identity_sha256": hashes["probe_service_identity"],
        "probe_service_attestation_sha256": hashes["probe_service_attestation"],
        "probe_revocation_state_sha256": hashes["probe_revocation_state"],
        "probe_attestor_keyring_sha256": hashes["probe_attestor_keyring"],
        "probe_attestor_revocation_state_sha256": hashes["probe_attestor_revocation_state"],
        "probe_service_executable_sha256": hashes["probe_service_executable"],
        "external_signer_identity_sha256": hashes["external_signer_identity"],
        "qualification_receipt_signing_public_key_sha256": hashes["qualification_receipt_signing_public_key"],
        "trust_manifest_id": trust_manifest["trust_manifest_id"],
        "trust_manifest_sequence": int(trust_manifest["sequence"]),
        "probe_keyring_sequence": keyring_sequence,
        "probe_revocation_sequence": rev_sequence,
        "probe_attestor_keyring_sequence": attestor_keyring_sequence,
        "probe_attestor_revocation_sequence": att_rev_sequence,
        "probe_policy_version": approved_policy.policy_version,
        "probe_service_id": service_id,
        "probe_attestor_id": attestor_id,
        "external_signer_id": host_context.external_signer_id,
        "host_id": expected_host_id,
        "candidate_archive_sha256": expected_candidate_archive_sha256,
        "challenge_sha256": expected_challenge_sha256,
        "not_before": trust_manifest["not_before"],
        "not_after": trust_manifest["not_after"],
    }
    return ApprovedProbeAuthority(
        keys=keys,
        service_id=service_id,
        policy=approved_policy,
        trust_binding=trust_binding,
        trust_binding_sha256=sha_bytes(canonical(trust_binding)),
        trust_manifest_sha256=hashes["qualification_trust_manifest"],
        probe_policy_sha256=hashes["probe_policy"],
        not_before=not_before,
        not_after=not_after,
        revoked_key_ids=revoked,
    )


def verify_probe_envelope(
    envelope: dict[str, Any],
    *,
    expected_role: str,
    expected_target_sha256: str,
    approved_authority: ApprovedProbeAuthority,
    now: datetime | None = None,
) -> str:
    current = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    required = {
        "format_version", "envelope_kind", "target_role", "target_sha256", "host_id",
        "candidate_archive_sha256", "challenge_sha256", "qualification_trust_manifest_sha256",
        "probe_keyring_sha256", "probe_policy_sha256", "probe_service_identity_sha256",
        "probe_service_attestation_sha256", "probe_revocation_state_sha256",
        "probe_attestor_keyring_sha256", "probe_attestor_revocation_state_sha256",
        "probe_service_executable_sha256", "boundary", "observations", "exit_code",
        "started_at", "completed_at", "signer_key_id", "signer_service_id", "signature",
    }
    _exact(envelope, required, f"probe envelope {expected_role}")
    if envelope.get("format_version") != "1.1" or envelope.get("envelope_kind") != ENVELOPE_KIND:
        raise SystemExit("probe envelope identity mismatch")
    if envelope.get("target_role") != expected_role or envelope.get("target_sha256") != expected_target_sha256:
        raise SystemExit(f"probe envelope target substitution: {expected_role}")
    binding = approved_authority.trust_binding
    map_fields = {
        "host_id": "host_id",
        "candidate_archive_sha256": "candidate_archive_sha256",
        "challenge_sha256": "challenge_sha256",
        "qualification_trust_manifest_sha256": "qualification_trust_manifest_sha256",
        "probe_keyring_sha256": "probe_keyring_sha256",
        "probe_policy_sha256": "probe_policy_sha256",
        "probe_service_identity_sha256": "probe_service_identity_sha256",
        "probe_service_attestation_sha256": "probe_service_attestation_sha256",
        "probe_revocation_state_sha256": "probe_revocation_state_sha256",
        "probe_attestor_keyring_sha256": "probe_attestor_keyring_sha256",
        "probe_attestor_revocation_state_sha256": "probe_attestor_revocation_state_sha256",
        "probe_service_executable_sha256": "probe_service_executable_sha256",
        "signer_service_id": "probe_service_id",
    }
    for envelope_field, binding_field in map_fields.items():
        if envelope.get(envelope_field) != binding[binding_field]:
            raise SystemExit(f"probe envelope trust binding mismatch for {expected_role}: {envelope_field}")
    if envelope.get("boundary") != approved_authority.policy.required_boundary:
        raise SystemExit(f"probe envelope violates exact signed policy boundary: {expected_role}")
    observations = envelope.get("observations")
    expected_observations = set(approved_authority.policy.required_observations)
    if not isinstance(observations, dict) or set(observations) != expected_observations or any(v is not True for v in observations.values()):
        raise SystemExit(f"probe envelope violates exact signed observation policy: {expected_role}")
    if int(envelope.get("exit_code", -1)) != 0:
        raise SystemExit(f"probe target failed for {expected_role}")
    started = _parse_time(envelope["started_at"], "probe started_at")
    completed = _parse_time(envelope["completed_at"], "probe completed_at")
    skew = timedelta(seconds=MAX_CLOCK_SKEW_SECONDS)
    age = (current - completed).total_seconds()
    if completed < started or completed > current + skew or age < -MAX_CLOCK_SKEW_SECONDS or age > approved_authority.policy.maximum_envelope_age_seconds:
        raise SystemExit(f"probe envelope stale or temporally invalid under signed policy: {expected_role}")
    key_id = str(envelope.get("signer_key_id"))
    key = approved_authority.keys.get(key_id)
    if key is None or key_id in approved_authority.revoked_key_ids:
        raise SystemExit(f"probe key is unapproved or revoked: {expected_role}")
    if not (key.not_before <= completed <= key.not_after):
        raise SystemExit(f"probe key is outside validity interval: {expected_role}")
    unsigned = dict(envelope)
    signature = unsigned.pop("signature")
    try:
        key.public_key.verify(base64.b64decode(str(signature), validate=True), canonical(unsigned))
    except (InvalidSignature, ValueError, TypeError) as exc:
        raise SystemExit(f"probe envelope signature failed: {expected_role}") from exc
    return key.signer_id


def verify_probe_manifest(
    manifest_path: Path,
    *,
    target_hashes: dict[str, str],
    approved_authority: ApprovedProbeAuthority,
    now: datetime | None = None,
) -> dict[str, Any]:
    current = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    manifest = _load_json(manifest_path)
    required = {
        "format_version", "manifest_kind", "artifact_set_version", "issued_at", "host_id",
        "candidate_archive_sha256", "challenge_sha256", "qualification_trust_binding_sha256",
        "qualification_trust_manifest_sha256", "probe_keyring_sha256", "probe_policy_sha256",
        "probe_service_identity_sha256", "probe_service_attestation_sha256",
        "probe_revocation_state_sha256", "probe_attestor_keyring_sha256",
        "probe_attestor_revocation_state_sha256", "probe_service_executable_sha256",
        "envelopes", "aggregate_sha256",
    }
    _exact(manifest, required, "probe envelope manifest")
    if manifest.get("format_version") != "1.1" or manifest.get("manifest_kind") != MANIFEST_KIND:
        raise SystemExit("probe envelope manifest identity mismatch")
    if manifest.get("artifact_set_version") != ARTIFACT_SET_VERSION:
        raise SystemExit("probe envelope manifest artifact-set version mismatch")
    binding = approved_authority.trust_binding
    mapped = {
        "host_id": "host_id",
        "candidate_archive_sha256": "candidate_archive_sha256",
        "challenge_sha256": "challenge_sha256",
        "qualification_trust_manifest_sha256": "qualification_trust_manifest_sha256",
        "probe_keyring_sha256": "probe_keyring_sha256",
        "probe_policy_sha256": "probe_policy_sha256",
        "probe_service_identity_sha256": "probe_service_identity_sha256",
        "probe_service_attestation_sha256": "probe_service_attestation_sha256",
        "probe_revocation_state_sha256": "probe_revocation_state_sha256",
        "probe_attestor_keyring_sha256": "probe_attestor_keyring_sha256",
        "probe_attestor_revocation_state_sha256": "probe_attestor_revocation_state_sha256",
        "probe_service_executable_sha256": "probe_service_executable_sha256",
    }
    for manifest_field, binding_field in mapped.items():
        if manifest.get(manifest_field) != binding[binding_field]:
            raise SystemExit(f"probe manifest trust binding mismatch: {manifest_field}")
    if manifest.get("qualification_trust_binding_sha256") != approved_authority.trust_binding_sha256:
        raise SystemExit("probe manifest trust binding aggregate mismatch")
    issued = _parse_time(manifest["issued_at"], "probe manifest issued_at")
    skew = timedelta(seconds=MAX_CLOCK_SKEW_SECONDS)
    if issued < approved_authority.not_before or issued > approved_authority.not_after or issued > current + skew:
        raise SystemExit("probe manifest issued outside approved interval")
    rows = manifest.get("envelopes")
    if not isinstance(rows, dict) or set(rows) != set(TARGETS) or set(target_hashes) != set(TARGETS):
        raise SystemExit("probe envelope manifest target set mismatch")
    hashes: dict[str, str] = {}
    signer_ids: set[str] = set()
    for target in TARGETS:
        row = rows[target]
        if not isinstance(row, dict) or set(row) != {"path", "sha256"}:
            raise SystemExit(f"probe manifest row malformed: {target}")
        raw = _read_regular(Path(str(row["path"])).absolute())
        digest = sha_bytes(raw)
        if digest != row["sha256"]:
            raise SystemExit(f"probe envelope file hash mismatch: {target}")
        try:
            envelope = json.loads(raw)
        except Exception as exc:
            raise SystemExit(f"invalid probe envelope JSON: {target}") from exc
        if not isinstance(envelope, dict):
            raise SystemExit(f"probe envelope must be object: {target}")
        signer_ids.add(verify_probe_envelope(
            envelope,
            expected_role=target,
            expected_target_sha256=target_hashes[target],
            approved_authority=approved_authority,
            now=current,
        ))
        hashes[target] = digest
    aggregate = sha_bytes(canonical(hashes))
    if manifest.get("aggregate_sha256") != aggregate:
        raise SystemExit("probe envelope manifest aggregate mismatch")
    if signer_ids != {approved_authority.service_id}:
        raise SystemExit("probe envelope signer-service set mismatch")
    return {
        "envelope_hashes": hashes,
        "envelope_hashes_sha256": aggregate,
        "manifest_sha256": sha_bytes(_read_regular(manifest_path)),
        "qualification_trust_binding": approved_authority.trust_binding,
        "qualification_trust_binding_sha256": approved_authority.trust_binding_sha256,
    }
