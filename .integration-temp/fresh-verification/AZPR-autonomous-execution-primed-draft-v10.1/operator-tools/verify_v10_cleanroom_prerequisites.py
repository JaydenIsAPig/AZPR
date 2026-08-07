#!/usr/bin/env python3
"""Non-root v10 semantic qualification verifier.

Security boundary:
- this verifier never executes a qualified target;
- it never accepts or loads a qualification-receipt private key;
- target behavior arrives only as signed no-secret probe envelopes;
- decisive PASS measurements are recomputed from strict raw evidence;
- receipt signing is delegated to an authenticated external signer client.

A successful receipt remains setup-blocking evidence. It is not authorization to
install, activate policy, execute Prompt 004, generate a roadmap, or run agents.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import re
import stat
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey
from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]
SCHEMAS = ROOT / "repository-overlay" / "automation" / "schemas"
sys.path.insert(0, str(Path(__file__).resolve().parent))
from v9_evidence_derivation import verify_report_derivation
from pathlib import Path as _PathAlias
sys.path.insert(0, str(ROOT / "trusted-installation"))
from v10_binding import QUALIFICATION_ARTIFACT_SET_VERSION, REQUIRED_QUALIFIED_ARTIFACTS  # noqa: E402
from v10_external_signer_client import request_external_signature  # noqa: E402
from v10_probe_boundary import TARGETS, load_approved_probe_authority, verify_probe_manifest  # noqa: E402
from v10_1_host_trust import HostQualificationContext, load_host_qualification_context  # noqa: E402

MAX_ARTIFACT = 2 * 1024 * 1024 * 1024
HEX64 = re.compile(r"^[0-9a-f]{64}$")
REPORT_ROLES = {
    "codex_isolation_qualification_report": ("CODEX_ISOLATION_QUALIFICATION", "isolation-qualifier"),
    "remote_anchor_qualification_report": ("REMOTE_ANCHOR_QUALIFICATION", "anchor-qualifier"),
    "key_custody_qualification_report": ("KEY_CUSTODY_QUALIFICATION", "key-custody-qualifier"),
    "installer_fault_matrix_report": ("INSTALLER_FAULT_MATRIX_QUALIFICATION", "installer-fault-qualifier"),
    "supply_chain_rebuild_report": ("SUPPLY_CHAIN_REBUILD_QUALIFICATION", "build-qualifier"),
    "dedicated_host_policy": ("DEDICATED_HOST_POLICY_QUALIFICATION", "host-security-qualifier"),
}
ARTIFACT_KINDS = {
    "bundle_zip": "regular", "bundle_attestation": "json", "bundle_signing_public_key": "public_key",
    "runtime_private_key": "secret_key", "runtime_public_key": "public_key",
    "evidence_private_key": "secret_key", "evidence_public_key": "public_key",
    "installation_signing_private_key": "secret_key", "installation_signing_public_key": "public_key",
    "qualification_receipt_signing_public_key": "public_key",
    "qualification_authorization_keyring": "json", "qualification_revocation_list": "json",
    "approval_keyring": "json", "evidence_keyring": "json", "phase_transition_keyring": "json",
    "git_binary": "executable", "python_binary": "executable", "codex_binary": "executable",
    "container_engine": "executable", "anchor_helper": "executable",
    "governing_policy_source": "regular", "requirements_input": "regular", "dependency_lock": "regular",
    "dependency_mirror_inventory": "json", "dependency_mirror_attestation": "json", "dependency_mirror_public_key": "public_key",
    "sbom": "json", "build_provenance": "json", "validation_dockerfile": "regular",
    "validation_image_attestation": "json", "validation_registry_proof": "json",
    "agent_execution_profile": "json", "handoff_quota_profile": "json", "key_lifecycle_state": "json",
    "host_qualification_roots_manifest": "json",
    "host_qualification_roots_authority_public_key": "public_key",
    "host_root_anchor_client": "executable", "host_root_anchor_identity": "json",
    "qualification_trust_authority_public_key": "public_key", "qualification_trust_manifest": "json",
    "probe_keyring": "json", "probe_policy": "json", "probe_service_identity": "json",
    "probe_service_attestation": "json", "probe_revocation_state": "json",
    "probe_attestor_keyring": "json", "probe_attestor_revocation_state": "json",
    "probe_service_executable": "executable", "external_signer_client": "executable",
    "external_signer_identity": "json", "qualification_probe_envelopes_manifest": "json",
    **{name: "qualification_report" for name in REPORT_ROLES},
}
HOST_OWNED_ARTIFACTS = frozenset({
    "host_qualification_roots_manifest", "host_qualification_roots_authority_public_key",
    "host_root_anchor_client", "host_root_anchor_identity",
    "qualification_trust_authority_public_key", "qualification_trust_manifest",
    "probe_keyring", "probe_policy", "probe_service_identity", "probe_service_attestation",
    "probe_revocation_state", "probe_attestor_keyring", "probe_attestor_revocation_state",
    "probe_service_executable", "external_signer_client", "external_signer_identity",
    "qualification_receipt_signing_public_key",
})
CALLER_ARTIFACT_KINDS = {name: kind for name, kind in ARTIFACT_KINDS.items() if name not in HOST_OWNED_ARTIFACTS}
if tuple(sorted(ARTIFACT_KINDS)) != tuple(sorted(REQUIRED_QUALIFIED_ARTIFACTS)):
    raise RuntimeError("v10.1 artifact-kind map differs from versioned canonical artifact set")
assert len(ARTIFACT_KINDS) == 57



def canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def sha_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def read_regular(path: Path, *, secret: bool = False, executable: bool = False) -> bytes:
    path = Path(path).absolute()
    for candidate in [path, *path.parents]:
        info = os.lstat(candidate)
        if stat.S_ISLNK(info.st_mode):
            raise SystemExit(f"symlinked qualification input: {candidate}")
        if candidate == candidate.parent:
            break
    fd = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    try:
        before = os.fstat(fd)
        if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1 or before.st_size > MAX_ARTIFACT:
            raise SystemExit(f"unsafe qualification input: {path}")
        if before.st_mode & 0o022:
            raise SystemExit(f"writable qualification input: {path}")
        if secret and before.st_mode & 0o077:
            raise SystemExit(f"qualification secret permissions too broad: {path}")
        if executable and not before.st_mode & 0o111:
            raise SystemExit(f"qualified executable lacks execute permission: {path}")
        data = bytearray()
        while True:
            chunk = os.read(fd, 1024 * 1024)
            if not chunk:
                break
            data.extend(chunk)
            if len(data) > MAX_ARTIFACT:
                raise SystemExit(f"qualification input too large: {path}")
        after = os.fstat(fd)
        if (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns) != (
            after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns
        ):
            raise SystemExit(f"qualification input changed during read: {path}")
        return bytes(data)
    finally:
        os.close(fd)


def load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(read_regular(path))
    except Exception as exc:
        raise SystemExit(f"invalid JSON qualification input: {path}") from exc
    if not isinstance(value, dict):
        raise SystemExit(f"qualification JSON must be an object: {path}")
    return value


def validate_schema(name: str, value: dict[str, Any]) -> None:
    schema = json.loads((SCHEMAS / name).read_text())
    Draft202012Validator(schema, format_checker=Draft202012Validator.FORMAT_CHECKER).validate(value)


def load_keyring(value: dict[str, Any]) -> dict[str, tuple[Ed25519PublicKey, set[str], str]]:
    if value.get("format_version") != "1.0" or not isinstance(value.get("keys"), list):
        raise SystemExit("evidence keyring format invalid")
    out: dict[str, tuple[Ed25519PublicKey, set[str], str]] = {}
    fingerprints: set[str] = set()
    signer_ids: set[str] = set()
    for row in value["keys"]:
        try:
            key_id = str(row["key_id"])
            signer_id = str(row["signer_id"])
            roles = set(row["roles"])
            key = serialization.load_pem_public_key(str(row["public_key_pem"]).encode())
        except Exception as exc:
            raise SystemExit("evidence keyring entry invalid") from exc
        if not isinstance(key, Ed25519PublicKey):
            raise SystemExit("evidence keyring entry is not Ed25519")
        fp = sha_bytes(key.public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw))
        if key_id in out or fp in fingerprints or signer_id in signer_ids:
            raise SystemExit("duplicate evidence key ID, signer, or cryptographic material")
        out[key_id] = (key, roles, signer_id)
        fingerprints.add(fp); signer_ids.add(signer_id)
    return out


def verify_signed_report(report: dict[str, Any], keys: dict[str, tuple[Ed25519PublicKey, set[str], str]], role: str) -> None:
    unsigned = dict(report)
    signature = unsigned.pop("signature", None)
    key_id = str(report.get("signer_key_id"))
    entry = keys.get(key_id)
    if not entry or role not in entry[1] or report.get("signer_role") != role:
        raise SystemExit(f"qualification report signer lacks role: {role}")
    try:
        entry[0].verify(base64.b64decode(str(signature), validate=True), canonical(unsigned))
    except (InvalidSignature, ValueError, TypeError) as exc:
        raise SystemExit(f"qualification report signature invalid: {role}") from exc


def verify_key_pair(private_raw: bytes, public_raw: bytes, label: str) -> None:
    try:
        private = serialization.load_pem_private_key(private_raw, password=None)
        public = serialization.load_pem_public_key(public_raw)
    except Exception as exc:
        raise SystemExit(f"invalid {label} key material") from exc
    if not isinstance(private, Ed25519PrivateKey) or not isinstance(public, Ed25519PublicKey):
        raise SystemExit(f"{label} key pair is not Ed25519")
    if private.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw) != public.public_bytes(
        serialization.Encoding.Raw, serialization.PublicFormat.Raw
    ):
        raise SystemExit(f"{label} private/public key mismatch")


def inspect_artifacts(rows: dict[str, Any]) -> tuple[dict[str, dict[str, Any]], dict[tuple[int, int], str]]:
    if set(rows) != set(CALLER_ARTIFACT_KINDS):
        raise SystemExit(f"caller qualification artifact set mismatch: missing={sorted(set(CALLER_ARTIFACT_KINDS)-set(rows))} extra={sorted(set(rows)-set(CALLER_ARTIFACT_KINDS))}")
    results: dict[str, dict[str, Any]] = {}
    identities: dict[tuple[int, int], str] = {}
    for name in sorted(CALLER_ARTIFACT_KINDS):
        row = rows[name]
        if not isinstance(row, dict) or set(row) != {"path"}:
            raise SystemExit(f"qualification artifact row malformed: {name}")
        path = Path(str(row["path"])).absolute()
        kind = ARTIFACT_KINDS[name]
        raw = read_regular(path, secret=kind == "secret_key", executable=kind == "executable")
        st = os.stat(path)
        identity = (st.st_dev, st.st_ino)
        if identity in identities:
            raise SystemExit(f"qualification artifact alias: {identities[identity]} and {name}")
        identities[identity] = name
        if kind in {"json", "qualification_report"}:
            try:
                parsed = json.loads(raw)
            except Exception as exc:
                raise SystemExit(f"invalid JSON artifact: {name}") from exc
            if not isinstance(parsed, dict):
                raise SystemExit(f"JSON artifact must be object: {name}")
        if kind == "public_key":
            try:
                key = serialization.load_pem_public_key(raw)
            except Exception as exc:
                raise SystemExit(f"invalid public key artifact: {name}") from exc
            if not isinstance(key, Ed25519PublicKey):
                raise SystemExit(f"non-Ed25519 public key artifact: {name}")
        results[name] = {"path": str(path), "sha256": sha_bytes(raw), "raw": raw}
    return results, identities


def inspect_host_artifacts(context: HostQualificationContext, identities: dict[tuple[int, int], str]) -> dict[str, dict[str, Any]]:
    results = context.artifact_results()
    if set(results) != set(HOST_OWNED_ARTIFACTS):
        raise SystemExit("independent host artifact set mismatch")
    for name, row in results.items():
        read = context.reads.get(name)
        if name == "host_qualification_roots_manifest":
            identity = None
        elif name == "host_qualification_roots_authority_public_key":
            identity = None
        else:
            identity = (read.device, read.inode) if read else None
        if identity is not None:
            if identity in identities:
                raise SystemExit(f"qualification artifact alias: {identities[identity]} and {name}")
            identities[identity] = name
        kind = ARTIFACT_KINDS[name]
        raw = row["raw"]
        if kind in {"json", "qualification_report"}:
            try:
                parsed = json.loads(raw)
            except Exception as exc:
                raise SystemExit(f"invalid independently provisioned JSON artifact: {name}") from exc
            if not isinstance(parsed, dict):
                raise SystemExit(f"independently provisioned JSON artifact must be object: {name}")
        if kind == "public_key":
            try:
                key = serialization.load_pem_public_key(raw)
            except Exception as exc:
                raise SystemExit(f"invalid independently provisioned public key: {name}") from exc
            if not isinstance(key, Ed25519PublicKey):
                raise SystemExit(f"non-Ed25519 independently provisioned key: {name}")
    return results



def build_unsigned_receipt(
    value: dict[str, Any],
    results: dict[str, dict[str, Any]],
    report_hashes: dict[str, str],
    probe_verification: dict[str, Any],
    host_context: HostQualificationContext,
) -> dict[str, Any]:
    issued = datetime.now(timezone.utc)
    bindings = {name: results[name]["sha256"] for name in sorted(results)}
    return {
        "format_version": "4.1",
        "receipt_kind": "AZPR_V10_1_SEMANTIC_CLEANROOM_QUALIFICATION_RECEIPT",
        "receipt_id": "qual-receipt-v10-1-" + os.urandom(16).hex(),
        "status": "SEMANTIC_QUALIFICATION_EVIDENCE_VERIFIED_INSTALLATION_STILL_BLOCKED",
        "pre_autonomous_staging": "FAIL",
        "semi_autonomous_codex_staging_ready": False,
        "safe_for_unattended_execution_now": False,
        "trusted_pre_autonomous_installation_ready": False,
        "full_autonomous_pathway_viable": True,
        "issued_at": issued.isoformat(),
        "expires_at": (issued + timedelta(days=7)).isoformat(),
        "host_id": value["host_id"],
        "candidate_archive_sha256": value["candidate_archive_sha256"],
        "bundle_manifest_sha256": value["bundle_manifest_sha256"],
        "challenge_sha256": value["challenge_sha256"],
        "agent_uid": int(value["agent_uid"]),
        "agent_gid": int(value["agent_gid"]),
        "validation_image_digest": value["validation_image_digest"],
        "qualification_artifact_set_version": QUALIFICATION_ARTIFACT_SET_VERSION,
        "artifact_bindings": bindings,
        "artifact_bindings_sha256": sha_bytes(canonical(bindings)),
        "qualification_report_hashes": report_hashes,
        "agent_execution_profile_sha256": results["agent_execution_profile"]["sha256"],
        "handoff_quota_profile_sha256": results["handoff_quota_profile"]["sha256"],
        "revocation_list_sha256": results["qualification_revocation_list"]["sha256"],
        "probe_envelopes_manifest_sha256": probe_verification["manifest_sha256"],
        "probe_envelope_hashes": probe_verification["envelope_hashes"],
        "probe_envelope_hashes_sha256": probe_verification["envelope_hashes_sha256"],
        "qualification_trust_binding": probe_verification["qualification_trust_binding"],
        "qualification_trust_binding_sha256": probe_verification["qualification_trust_binding_sha256"],
        "external_signer_identity_sha256": host_context.external_signer_identity_sha256,
        "remaining_closed_gates": [
            "SEPARATE_INSTALLATION_AUTHORIZATION_REQUIRED", "ROOT_INSTALLATION_NOT_PERFORMED",
            "CANONICAL_POLICY_NOT_APPROVED", "PROMPT_004_NOT_EXECUTED",
            "ROADMAP_NOT_GENERATED_OR_PROMOTED", "AUTONOMOUS_AND_EXTERNAL_EXECUTION_NOT_AUTHORIZED",
            "INDEPENDENT_REASSESSMENT_REQUIRED", "REAL_HOST_AND_ORGANIZATION_QUALIFICATION_REQUIRED",
        ],
        "signer_key_id": host_context.receipt_signing_key_id,
    }


def verify_inputs_and_build(value: dict[str, Any]) -> tuple[dict[str, Any], dict[str, dict[str, Any]], dict[str, str], HostQualificationContext]:
    expected_top = {
        "format_version", "safe_for_unattended_execution_now", "trusted_pre_autonomous_installation_ready",
        "candidate_archive_sha256", "bundle_manifest_sha256", "challenge_sha256", "host_id", "agent_uid", "agent_gid",
        "validation_image_digest", "raw_evidence", "probe_targets", "artifacts",
    }
    if set(value) != expected_top or value.get("format_version") != "2.1":
        raise SystemExit("v10.1 qualification input document shape/version mismatch")
    forbidden_tokens = {
        "trusted_ancestor", "expected_trust_owner_uid", "minimum_trust_sequence",
        "external_signer_client", "external_signer_identity_sha256",
        "qualification_receipt_signing_public_key", "receipt_signing_key_id",
    }
    if forbidden_tokens.intersection(value):
        raise SystemExit("qualification caller attempted to select a security trust root")
    if value.get("safe_for_unattended_execution_now") is not False or value.get("trusted_pre_autonomous_installation_ready") is not False:
        raise SystemExit("v10.1 qualification input readiness flags must remain false")
    for name in ("candidate_archive_sha256", "bundle_manifest_sha256", "challenge_sha256"):
        if not HEX64.fullmatch(str(value.get(name))):
            raise SystemExit(f"v10.1 qualification hash invalid: {name}")
    if int(value.get("agent_uid", 0)) <= 0 or int(value.get("agent_gid", 0)) <= 0:
        raise SystemExit("v10.1 qualification agent identity must be explicit non-root")
    host_context = load_host_qualification_context(
        expected_host_id=str(value["host_id"]),
        expected_candidate_archive_sha256=str(value["candidate_archive_sha256"]),
        expected_challenge_sha256=str(value["challenge_sha256"]),
    )
    results, identities = inspect_artifacts(value["artifacts"])
    results.update(inspect_host_artifacts(host_context, identities))
    if set(results) != set(ARTIFACT_KINDS):
        raise SystemExit("complete v10.1 qualification artifact set mismatch")
    if results["bundle_zip"]["sha256"] != value["candidate_archive_sha256"]:
        raise SystemExit("candidate archive hash mismatch")

    verify_key_pair(results["runtime_private_key"]["raw"], results["runtime_public_key"]["raw"], "runtime")
    verify_key_pair(results["evidence_private_key"]["raw"], results["evidence_public_key"]["raw"], "evidence")
    verify_key_pair(results["installation_signing_private_key"]["raw"], results["installation_signing_public_key"]["raw"], "installation")

    authority = load_approved_probe_authority(
        host_context=host_context,
        expected_host_id=str(value["host_id"]),
        expected_candidate_archive_sha256=str(value["candidate_archive_sha256"]),
        expected_challenge_sha256=str(value["challenge_sha256"]),
    )

    probe_targets = value["probe_targets"]
    if not isinstance(probe_targets, dict) or set(probe_targets) != set(TARGETS):
        raise SystemExit("probe target set mismatch")
    target_hashes: dict[str, str] = {}
    for name, path_value in probe_targets.items():
        raw = read_regular(Path(str(path_value)), executable=True)
        target_hashes[name] = sha_bytes(raw)
        if name in results and results[name]["sha256"] != target_hashes[name]:
            raise SystemExit(f"probe target differs from qualified artifact: {name}")
    probe_verification = verify_probe_manifest(
        Path(results["qualification_probe_envelopes_manifest"]["path"]),
        target_hashes=target_hashes,
        approved_authority=authority,
    )

    evidence_keys = load_keyring(json.loads(results["evidence_keyring"]["raw"]))
    raw_map = value["raw_evidence"]
    if not isinstance(raw_map, dict) or set(raw_map) != set(REPORT_ROLES):
        raise SystemExit("raw evidence report set mismatch")
    report_hashes: dict[str, str] = {}
    for name, (expected_kind, role) in REPORT_ROLES.items():
        report = json.loads(results[name]["raw"])
        validate_schema("qualification-evidence-report.schema.json", report)
        if report.get("report_kind") != expected_kind or report.get("safe_for_unattended_execution_now") is not False:
            raise SystemExit(f"qualification report identity/readiness mismatch: {name}")
        if report.get("host_id") != value["host_id"] or report.get("candidate_archive_sha256") != value["candidate_archive_sha256"]:
            raise SystemExit(f"qualification report common binding mismatch: {name}")
        verify_signed_report(report, evidence_keys, role)
        raw_path = Path(str(raw_map[name])).absolute()
        validate_schema("qualification-raw-evidence-v9.schema.json", load_json(raw_path))
        verify_report_derivation(report, raw_path)
        report_hashes[name] = results[name]["sha256"]
    unsigned = build_unsigned_receipt(value, results, report_hashes, probe_verification, host_context)
    validate_schema("cleanroom-qualification-receipt-v10.schema.json", {**unsigned, "signature": "A" * 86 + "=="})
    return unsigned, results, report_hashes, host_context


def write_once(path: Path, data: bytes) -> None:
    path = Path(path).absolute()
    path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0), 0o444)
    try:
        os.write(fd, data); os.fsync(fd)
    finally:
        os.close(fd)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--inputs", required=True)
    parser.add_argument("--receipt-output", required=True)
    args = parser.parse_args()
    if os.geteuid() == 0:
        raise SystemExit("v10.1 cleanroom verifier refuses root execution")
    value = load_json(Path(args.inputs))
    if any("private" in key.lower() for key in value if key not in {"artifacts"}):
        raise SystemExit("v10.1 verifier top-level input must not accept receipt private-key material")
    unsigned, results, report_hashes, host_context = verify_inputs_and_build(value)
    receipt = request_external_signature(
        unsigned_receipt=unsigned,
        qualification_trust_binding=unsigned["qualification_trust_binding"],
        host_context=host_context,
        request_nonce="sign-request-" + os.urandom(16).hex(),
    )
    validate_schema("cleanroom-qualification-receipt-v10.schema.json", receipt)
    output = Path(args.receipt_output)
    write_once(output, (json.dumps(receipt, indent=2, sort_keys=True) + "\n").encode())
    print(json.dumps({
        "status": receipt["status"],
        "safe_for_unattended_execution_now": False,
        "trusted_pre_autonomous_installation_ready": False,
        "required_artifact_count": len(results),
        "probe_target_count": len(TARGETS),
        "qualification_report_count": len(report_hashes),
        "receipt_id": receipt["receipt_id"],
        "receipt_path": str(output.absolute()),
        "receipt_sha256": sha_bytes(output.read_bytes()),
        "remaining_closed_gates": receipt["remaining_closed_gates"],
    }, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
