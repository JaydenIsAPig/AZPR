#!/usr/bin/env python3
"""LEGACY v7 regression-only verifier. Its receipt is not accepted by the v8 installer.

Strict, setup-blocking AZPR v7 clean-room input completeness verifier.

This tool verifies an exact artifact set and writes a signed receipt. It never
installs or activates AZPR, approves a canonical policy, executes Prompt 004,
generates a roadmap, launches Codex, or authorizes an external operation.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import re
import stat
from pathlib import Path
from typing import Any

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey

MAX_INPUT_BYTES = 4 * 1024 * 1024
MAX_ARTIFACT_BYTES = 2 * 1024 * 1024 * 1024
HEX64 = re.compile(r"^[0-9a-f]{64}$")

ARTIFACT_SPECS: dict[str, tuple[str, str]] = {
    "bundle_zip": ("implementation_bundle", "regular"),
    "bundle_attestation": ("release_attestation", "json"),
    "bundle_signing_public_key": ("release_verification_key", "public_key"),
    "runtime_private_key": ("controller_runtime_signing_key", "secret_key"),
    "runtime_public_key": ("controller_runtime_verification_key", "public_key"),
    "evidence_private_key": ("external_evidence_signing_key", "secret_key"),
    "evidence_public_key": ("external_evidence_verification_key", "public_key"),
    "installation_signing_private_key": ("installation_receipt_signing_key", "secret_key"),
    "installation_signing_public_key": ("installation_receipt_verification_key", "public_key"),
    "approval_keyring": ("approval_authorization_keyring", "json"),
    "evidence_keyring": ("external_evidence_keyring", "json"),
    "git_binary": ("trusted_git_executable", "executable"),
    "python_binary": ("trusted_python_executable", "executable"),
    "codex_binary": ("pinned_codex_executable", "executable"),
    "container_engine": ("pinned_container_engine", "executable"),
    "anchor_helper": ("rollback_resistant_anchor_helper", "executable"),
    "governing_policy_source": ("master_operating_prompt_docx", "regular"),
    "requirements_input": ("dependency_requirements_input", "regular"),
    "dependency_lock": ("hash_locked_dependency_lock", "regular"),
    "dependency_mirror_inventory": ("offline_mirror_inventory", "json"),
    "dependency_mirror_attestation": ("offline_mirror_attestation", "json"),
    "dependency_mirror_public_key": ("offline_mirror_verification_key", "public_key"),
    "sbom": ("validation_image_sbom", "json"),
    "build_provenance": ("validation_image_build_provenance", "json"),
    "validation_dockerfile": ("validation_image_build_definition", "regular"),
    "validation_image_attestation": ("validation_image_attestation", "json"),
    "codex_isolation_qualification_report": ("codex_isolation_qualification", "qualification_report"),
    "remote_anchor_qualification_report": ("remote_anchor_qualification", "qualification_report"),
    "key_custody_qualification_report": ("key_custody_qualification", "qualification_report"),
    "installer_fault_matrix_report": ("installer_fault_matrix_qualification", "qualification_report"),
    "supply_chain_rebuild_report": ("supply_chain_rebuild_qualification", "qualification_report"),
    "dedicated_host_policy": ("dedicated_host_security_policy", "qualification_report"),
}

REPORT_KINDS = {
    "codex_isolation_qualification_report": "CODEX_ISOLATION_QUALIFICATION",
    "remote_anchor_qualification_report": "REMOTE_ANCHOR_QUALIFICATION",
    "key_custody_qualification_report": "KEY_CUSTODY_QUALIFICATION",
    "installer_fault_matrix_report": "INSTALLER_FAULT_MATRIX_QUALIFICATION",
    "supply_chain_rebuild_report": "SUPPLY_CHAIN_REBUILD_QUALIFICATION",
    "dedicated_host_policy": "DEDICATED_HOST_POLICY_QUALIFICATION",
}


def canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def sha256_path(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def load_json(path: Path, *, limit: int = MAX_INPUT_BYTES) -> Any:
    raw = path.read_bytes()
    if len(raw) > limit:
        raise SystemExit(f"JSON input is too large: {path}")
    try:
        return json.loads(raw)
    except Exception as exc:
        raise SystemExit(f"invalid JSON: {path}") from exc


def acl_names(path: Path) -> set[str]:
    try:
        return set(os.listxattr(path, follow_symlinks=False))
    except (AttributeError, OSError):
        return set()


def inspect_artifact(name: str, entry: Any) -> tuple[dict[str, Any], tuple[int, int]]:
    if not isinstance(entry, dict) or set(entry) != {"path", "sha256", "role", "type"}:
        raise SystemExit(f"artifact {name} must contain exactly path, sha256, role, and type")
    expected_role, expected_type = ARTIFACT_SPECS[name]
    if entry["role"] != expected_role or entry["type"] != expected_type:
        raise SystemExit(f"artifact {name} has the wrong role/type")
    if not isinstance(entry["path"], str) or not entry["path"].startswith("/"):
        raise SystemExit(f"artifact {name} must use an absolute path")
    if not isinstance(entry["sha256"], str) or not HEX64.fullmatch(entry["sha256"]):
        raise SystemExit(f"artifact {name} has an invalid expected SHA-256")
    path = Path(entry["path"])
    try:
        before = os.lstat(path)
    except FileNotFoundError as exc:
        raise SystemExit(f"artifact {name} is missing") from exc
    if stat.S_ISLNK(before.st_mode) or not stat.S_ISREG(before.st_mode) or before.st_nlink != 1:
        raise SystemExit(f"artifact {name} is not a single-link regular file")
    if before.st_uid != 0 or before.st_mode & 0o022:
        raise SystemExit(f"artifact {name} must be root-owned and non-writable by group/other")
    if before.st_size < 1 or before.st_size > MAX_ARTIFACT_BYTES:
        raise SystemExit(f"artifact {name} has an invalid size")
    mode = before.st_mode & 0o777
    if expected_type == "secret_key" and mode not in (0o400, 0o600):
        raise SystemExit(f"secret artifact {name} must use exact mode 0400 or 0600")
    if expected_type == "secret_key" and {"system.posix_acl_access", "system.posix_acl_default"} & acl_names(path):
        raise SystemExit(f"secret artifact {name} has a POSIX ACL")
    if expected_type == "executable" and not before.st_mode & 0o111:
        raise SystemExit(f"artifact {name} is not executable")
    digest = sha256_path(path)
    after = os.lstat(path)
    if (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns) != (
        after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns
    ):
        raise SystemExit(f"artifact {name} changed during verification")
    if digest != entry["sha256"]:
        raise SystemExit(f"artifact {name} SHA-256 mismatch")
    if expected_type in {"json", "qualification_report"}:
        value = load_json(path)
        if not isinstance(value, dict):
            raise SystemExit(f"artifact {name} JSON must be an object")
        if expected_type == "qualification_report":
            expected_kind = REPORT_KINDS[name]
            if value.get("format_version") != "1.0" or value.get("report_kind") != expected_kind:
                raise SystemExit(f"qualification report {name} has the wrong identity")
            if value.get("status") != "PASS" or value.get("safe_for_unattended_execution_now") is not False:
                raise SystemExit(f"qualification report {name} is not a fail-closed PASS report")
            bindings = value.get("artifact_bindings")
            if not isinstance(bindings, dict) or not bindings:
                raise SystemExit(f"qualification report {name} lacks exact artifact bindings")
            if any(not isinstance(k, str) or not isinstance(v, str) or not HEX64.fullmatch(v) for k, v in bindings.items()):
                raise SystemExit(f"qualification report {name} has invalid artifact bindings")
    return ({
        "name": name,
        "path": str(path),
        "sha256": digest,
        "role": expected_role,
        "type": expected_type,
        "size": before.st_size,
        "mode": format(mode, "04o"),
        "uid": before.st_uid,
        "gid": before.st_gid,
    }, (before.st_dev, before.st_ino))


def load_private(path: Path) -> Ed25519PrivateKey:
    key = serialization.load_pem_private_key(path.read_bytes(), password=None)
    if not isinstance(key, Ed25519PrivateKey):
        raise SystemExit(f"not an Ed25519 private key: {path}")
    return key


def load_public(path: Path) -> Ed25519PublicKey:
    key = serialization.load_pem_public_key(path.read_bytes())
    if not isinstance(key, Ed25519PublicKey):
        raise SystemExit(f"not an Ed25519 public key: {path}")
    return key


def public_raw(key: Ed25519PublicKey) -> bytes:
    return key.public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)


def verify_key_pair(private_path: Path, public_path: Path, label: str) -> None:
    if public_raw(load_private(private_path).public_key()) != public_raw(load_public(public_path)):
        raise SystemExit(f"{label} private/public key pair mismatch")


def write_once(path: Path, data: bytes) -> None:
    path = path.absolute()
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0), 0o400)
    try:
        view = memoryview(data)
        while view:
            view = view[os.write(fd, view):]
        os.fsync(fd)
    finally:
        os.close(fd)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--inputs", required=True)
    parser.add_argument("--receipt-output", required=True)
    args = parser.parse_args()
    if os.geteuid() != 0:
        raise SystemExit("clean-room prerequisite verification must run as root")
    value = load_json(Path(args.inputs))
    if not isinstance(value, dict) or set(value) != {
        "format_version", "safe_for_unattended_execution_now", "agent_uid", "agent_gid",
        "validation_image_digest", "installation_signing_key_id", "artifacts"
    }:
        raise SystemExit("qualification input manifest has unexpected or missing top-level fields")
    if value["format_version"] != "2.0" or value["safe_for_unattended_execution_now"] is not False:
        raise SystemExit("invalid qualification input manifest identity")
    uid, gid = value["agent_uid"], value["agent_gid"]
    if not isinstance(uid, int) or not isinstance(gid, int) or uid <= 0 or gid <= 0:
        raise SystemExit("explicit non-root agent UID/GID required")
    if not isinstance(value["installation_signing_key_id"], str) or not re.fullmatch(r"[A-Za-z0-9._-]{8,128}", value["installation_signing_key_id"]):
        raise SystemExit("invalid installation signing key ID")
    digest = value["validation_image_digest"]
    if not isinstance(digest, str) or not re.fullmatch(r"sha256:[0-9a-f]{64}", digest):
        raise SystemExit("validation_image_digest is not immutable")
    artifacts = value["artifacts"]
    if not isinstance(artifacts, dict):
        raise SystemExit("artifacts must be an object")
    expected, actual = set(ARTIFACT_SPECS), set(artifacts)
    if expected != actual:
        raise SystemExit(f"clean-room artifact set is incomplete or unknown; missing={sorted(expected-actual)} extra={sorted(actual-expected)}")
    results: dict[str, dict[str, Any]] = {}
    identities: dict[tuple[int, int], str] = {}
    resolved: dict[str, str] = {}
    for name in sorted(expected):
        result, identity = inspect_artifact(name, artifacts[name])
        if identity in identities:
            raise SystemExit(f"artifact path alias detected: {identities[identity]} and {name}")
        identities[identity] = name
        rp = str(Path(result["path"]).resolve(strict=True))
        if rp in resolved:
            raise SystemExit(f"resolved artifact path alias detected: {resolved[rp]} and {name}")
        resolved[rp] = name
        results[name] = result
    verify_key_pair(Path(results["runtime_private_key"]["path"]), Path(results["runtime_public_key"]["path"]), "runtime")
    verify_key_pair(Path(results["evidence_private_key"]["path"]), Path(results["evidence_public_key"]["path"]), "evidence")
    verify_key_pair(Path(results["installation_signing_private_key"]["path"]), Path(results["installation_signing_public_key"]["path"]), "installation")
    for name in ("approval_keyring", "evidence_keyring"):
        keyring = load_json(Path(results[name]["path"]))
        if not isinstance(keyring, dict) or not isinstance(keyring.get("keys"), list) or not keyring["keys"]:
            raise SystemExit(f"{name} is not a populated keyring")
    binding_hashes = {name: item["sha256"] for name, item in sorted(results.items())}
    unsigned = {
        "format_version": "1.0",
        "receipt_kind": "AZPR_V7_COMPLETE_CLEANROOM_INPUT_RECEIPT",
        "status": "COMPLETE_REQUIRED_INPUT_SET_VERIFIED_INSTALLATION_STILL_BLOCKED",
        "safe_for_unattended_execution_now": False,
        "agent_uid": uid,
        "agent_gid": gid,
        "validation_image_digest": digest,
        "required_artifact_count": len(ARTIFACT_SPECS),
        "artifact_bindings": binding_hashes,
        "remaining_closed_gates": [
            "ROOT_INSTALLATION_NOT_PERFORMED",
            "CANONICAL_POLICY_NOT_APPROVED",
            "PROMPT_004_NOT_EXECUTED",
            "ROADMAP_NOT_GENERATED_OR_PROMOTED",
            "AUTONOMOUS_AND_EXTERNAL_EXECUTION_NOT_AUTHORIZED",
            "INDEPENDENT_REASSESSMENT_REQUIRED",
        ],
        "signer_key_id": value["installation_signing_key_id"],
    }
    private = load_private(Path(results["installation_signing_private_key"]["path"]))
    receipt = dict(unsigned)
    receipt["signature"] = base64.b64encode(private.sign(canonical(unsigned))).decode("ascii")
    write_once(Path(args.receipt_output), (json.dumps(receipt, indent=2, sort_keys=True) + "\n").encode("utf-8"))
    print(json.dumps({
        "status": receipt["status"],
        "safe_for_unattended_execution_now": False,
        "required_artifact_count": len(results),
        "receipt_path": str(Path(args.receipt_output).absolute()),
        "receipt_sha256": sha256_path(Path(args.receipt_output)),
        "remaining_closed_gates": receipt["remaining_closed_gates"],
    }, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
