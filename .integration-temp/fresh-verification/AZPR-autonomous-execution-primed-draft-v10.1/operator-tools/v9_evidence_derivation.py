#!/usr/bin/env python3
"""Deterministically derive qualification conclusions from strict raw evidence."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

REQUIRED_TRUE = {
    "CODEX_ISOLATION_QUALIFICATION": {
        "cgroup_v2", "pid_namespace", "mount_namespace", "run_as_nonroot",
        "no_signing_keys_present", "no_installer_state_present", "no_host_mounts",
        "no_daemon_sockets", "network_denied", "fork_escape_denied",
        "session_escape_denied", "resource_exhaustion_contained", "evidence_mutation_denied",
    },
    "REMOTE_ANCHOR_QUALIFICATION": {"rollback_test_passed", "restore_test_passed", "compare_and_publish_passed", "outage_failed_closed"},
    "KEY_CUSTODY_QUALIFICATION": {"hardware_or_brokered", "agent_read_denied", "rotation_test_passed", "revocation_test_passed", "compromise_recovery_test_passed", "receipt_signer_external"},
    "INSTALLER_FAULT_MATRIX_QUALIFICATION": {"all_fault_cases_passed", "no_partial_state", "recovery_deterministic", "global_lock_verified", "same_sequence_race_rejected", "rollback_replay_rejected"},
    "SUPPLY_CHAIN_REBUILD_QUALIFICATION": {"reproducible", "registry_binding_verified", "offline_mirror_verified"},
    "DEDICATED_HOST_POLICY_QUALIFICATION": {"dedicated_host", "cgroup_v2", "pid_namespace", "mount_namespace", "lsm_enforced", "measured_boot_verified"},
}

OUTPUT_FIELDS = {
    "CODEX_ISOLATION_QUALIFICATION": ["agent_uid", "agent_gid", "capabilities_sha256", "lsm_profile_sha256", "mount_profile_sha256", "quota_profile_sha256", "cgroup_profile_sha256"],
    "REMOTE_ANCHOR_QUALIFICATION": ["anchor_endpoint_id", "challenge_nonce", "challenge_response_sha256"],
    "KEY_CUSTODY_QUALIFICATION": ["custody_provider_id", "signer_identity_sha256"],
    "INSTALLER_FAULT_MATRIX_QUALIFICATION": ["fault_points_tested", "concurrency_processes", "fault_catalog_sha256"],
    "SUPPLY_CHAIN_REBUILD_QUALIFICATION": ["resolution_pass_count", "wheel_set_sha256", "sbom_sha256", "build_provenance_sha256", "registry_proof_sha256"],
    "DEDICATED_HOST_POLICY_QUALIFICATION": ["measured_boot_policy_sha256", "os_policy_sha256", "cgroup_profile_sha256", "mount_profile_sha256", "quota_profile_sha256", "lsm_profile_sha256"],
}


def canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def sha_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def load_raw_evidence(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(Path(path).read_bytes())
    except Exception as exc:
        raise SystemExit(f"invalid machine-readable raw evidence: {path}") from exc
    if not isinstance(value, dict):
        raise SystemExit("raw evidence must be a JSON object")
    return value


def derive_measurements(raw: dict[str, Any], expected_kind: str) -> dict[str, Any]:
    if raw.get("format_version") != "1.0" or raw.get("evidence_kind") != "AZPR_V9_MACHINE_DERIVABLE_QUALIFICATION_EVIDENCE":
        raise SystemExit("raw evidence identity mismatch")
    if raw.get("report_kind") != expected_kind or expected_kind not in REQUIRED_TRUE:
        raise SystemExit("raw evidence report kind mismatch")
    commands = raw.get("commands")
    if not isinstance(commands, list) or not commands:
        raise SystemExit("raw evidence command catalog missing")
    seen: set[str] = set()
    for command in commands:
        if not isinstance(command, dict):
            raise SystemExit("raw evidence command row malformed")
        command_id = command.get("command_id")
        if not isinstance(command_id, str) or command_id in seen:
            raise SystemExit("raw evidence command IDs must be unique")
        seen.add(command_id)
        if int(command.get("exit_code", -1)) != 0:
            raise SystemExit(f"raw evidence command failed: {command_id}")
        for field in ("argv_sha256", "tool_sha256", "stdout_sha256", "stderr_sha256"):
            value = str(command.get(field, ""))
            if len(value) != 64 or any(c not in "0123456789abcdef" for c in value):
                raise SystemExit(f"raw evidence command identity invalid: {command_id}:{field}")
    checks = raw.get("checks")
    if not isinstance(checks, dict):
        raise SystemExit("raw evidence checks missing")
    for check in REQUIRED_TRUE[expected_kind]:
        if checks.get(check) is not True:
            raise SystemExit(f"raw evidence decisive check failed or missing: {check}")
    measurements = {name: checks[name] for name in OUTPUT_FIELDS[expected_kind] if name in checks}
    measurements.update({name: True for name in sorted(REQUIRED_TRUE[expected_kind])})
    measurements["command_catalog_sha256"] = sha_bytes(canonical(commands))
    measurements["raw_transcript_sha256"] = raw.get("transcript_sha256")
    measurements["challenge_nonce"] = raw.get("challenge_nonce")
    return measurements


def verify_report_derivation(report: dict[str, Any], raw_path: Path) -> dict[str, Any]:
    raw = load_raw_evidence(raw_path)
    kind = str(report.get("report_kind"))
    if raw.get("host_id") != report.get("host_id") or raw.get("candidate_archive_sha256") != report.get("candidate_archive_sha256"):
        raise SystemExit("raw evidence common binding mismatch")
    derived = derive_measurements(raw, kind)
    if report.get("status") != "PASS":
        raise SystemExit("qualification report status is not PASS")
    if report.get("measurements") != derived:
        raise SystemExit("signed qualification measurements do not match machine-derived raw evidence")
    return derived
