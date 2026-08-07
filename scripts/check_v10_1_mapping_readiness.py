#!/usr/bin/env python3
"""Assess whether the AZPR v10.1 mapping is ready for human approval.

The default assessment is read-only, emits JSON, and never creates or modifies
an approval. Mapping approval readiness is intentionally distinct from
materialization or external-controller activation readiness.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.util
import json
import os
import re
import subprocess
import tempfile
from datetime import datetime
from pathlib import Path, PurePosixPath
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MAPPING = (
    ROOT
    / "docs"
    / "delivery-provenance"
    / "v10.1"
    / "integration"
    / "AZPR-v10.1-integration-path-mapping.csv"
)
DEFAULT_CONTRACT = ROOT / "automation" / "integration" / "v10.1" / "controller-transition-contract.json"
DEFAULT_STAGING_VALIDATION = (
    ROOT
    / "docs"
    / "delivery-provenance"
    / "v10.1"
    / "validation"
    / "AZPR-v10.1-staging-validation.json"
)
DEFAULT_VERIFIER_ATTEMPTS = (
    ROOT
    / "docs"
    / "delivery-provenance"
    / "v10.1"
    / "validation"
    / "delivery-verifier-attempts.json"
)
DEFAULT_ASSESSMENT_OUTPUT = (
    ROOT
    / "docs"
    / "delivery-provenance"
    / "v10.1"
    / "validation"
    / "mapping-readiness-assessment.json"
)
EXPECTED_STAGING_MAPPING_SHA256 = "007786c1c1748f8264cee452df815b47e41e15deb8b532b31f426cd18b4f2525"

BASE_FIELDS = [
    "source_archive",
    "source_path",
    "source_sha256",
    "classification",
    "current_repository_equivalent",
    "proposed_destination",
    "action",
    "conflict_status",
    "reason",
    "dependencies",
    "validation",
    "rollback",
    "approval_needed",
]
REQUIRED_FIELDS = BASE_FIELDS + [
    "decision_id",
    "resolution_status",
    "transition_phase",
]
VALID_ACTIONS = {"ADD", "REPLACE", "MERGE", "MOVE", "KEEP_CURRENT", "DEFER", "QUARANTINE"}
ACTIONABLE = {"ADD", "REPLACE", "MERGE", "MOVE", "KEEP_CURRENT"}
SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
FORBIDDEN_CONFLICTS = {"UNKNOWN_INTENT", "ACTIVE_STATE_COLLISION"}
EXTERNAL_CLASSES = {"REPOSITORY_CONTROLLER", "OPERATOR_TOOL", "HOST_INSTALLATION_TOOL"}
VALID_RESOLUTION_STATES = {"NO_APPROVAL_REQUIRED", "READY_FOR_APPROVAL"}
REQUIRED_GENERATED_PATHS = {
    ".gitignore",
    "AGENTS.md",
    "AUTONOMOUS_LOOP_INSTALL.md",
    "automation/integration/v10.1/controller-transition-contract.json",
    "automation/integration/v10.1/prompt-stages/00-preflight-authority-and-inputs.md",
    "automation/integration/v10.1/prompt-stages/01-linux-delivery-reverification.md",
    "automation/integration/v10.1/prompt-stages/02-freeze-mapping-and-human-approval-handoff.md",
    "automation/integration/v10.1/prompt-stages/03-h1-materialize-approved-repository-mapping.md",
    "automation/integration/v10.1/prompt-stages/04-h1-repository-integration-audit.md",
    "automation/integration/v10.1/prompt-stages/05-h2-read-only-external-controller-qualification.md",
    "automation/integration/v10.1/prompt-stages/06-h2-cutover-readiness-audit.md",
    "automation/integration/v10.1/prompt-stages/07-h3-cutover-plan-and-authorization-package.md",
    "automation/integration/v10.1/prompt-stages/08-h3-controlled-single-writer-cutover.md",
    "automation/integration/v10.1/prompt-stages/09-post-cutover-reconciliation-audit.md",
    "automation/integration/v10.1/prompt-stages/MASTER-ORCHESTRATION-PROMPT.md",
    "automation/integration/v10.1/prompt-stages/README.md",
    "automation/integration/v10.1/prompt-stages/SHA256SUMS.json",
    "automation/integration/v10.1/prompt-stages/operator-input.template.json",
    "automation/integration/v10.1/prompt-stages/stage-manifest.json",
    "automation/integration/v10.1/prompt-stages/stage-result.example.json",
    "automation/integration/v10.1/prompt-stages/stage-result.schema.json",
    "docs/adr/0009-staged-hybrid-controller-transition.md",
    "docs/adr/README.md",
    "docs/automation/README.md",
    "docs/automation/current-status.md",
    "docs/audits/README.md",
    "docs/delivery-provenance/v10.1/README.md",
    "docs/delivery-provenance/v10.1/delivery-identity.json",
    "docs/delivery-provenance/v10.1/integration/AZPR-v10.1-current-repository-inventory.json",
    "docs/delivery-provenance/v10.1/integration/AZPR-v10.1-final-deliverables-inventory.json",
    "docs/delivery-provenance/v10.1/integration/AZPR-v10.1-integration-conflict-report.md",
    "docs/delivery-provenance/v10.1/integration/AZPR-v10.1-integration-plan.md",
    "docs/delivery-provenance/v10.1/integration/AZPR-v10.1-integration-path-mapping.staging-original.csv",
    "docs/delivery-provenance/v10.1/integration/AZPR-v10.1-integration-rollback-plan.md",
    "docs/delivery-provenance/v10.1/integration/AZPR-v10.1-staging-diff-report.md",
    "docs/delivery-provenance/v10.1/integration/README.md",
    "docs/delivery-provenance/v10.1/validation/AZPR-v10.1-staging-validation.json",
    "docs/delivery-provenance/v10.1/validation/AZPR-v10.1-system-integration-handoff-summary.md",
    "docs/delivery-provenance/v10.1/validation/README.md",
    "docs/delivery-provenance/v10.1/validation/candidate-file-inventory.sha256",
    "docs/delivery-provenance/v10.1/validation/delivery-verifier-attempts.json",
    "docs/delivery-provenance/v10.1/validation/inventory-comparison.json",
    "docs/delivery-provenance/v10.1/validation/python-runtime-manifest.json",
    "docs/delivery-provenance/v10.1/validation/historical-macos/README.md",
    "docs/delivery-provenance/v10.1/validation/historical-macos/delivery-verifier-attempts.json",
    "docs/delivery-provenance/v10.1/validation/historical-macos/offline-wheelhouse-bundle.json",
    "docs/delivery-provenance/v10.1/validation/historical-macos/python-runtime-manifest.json",
    "docs/delivery-provenance/v10.1/validation/historical-macos/requirements-validation.in",
    "docs/delivery-provenance/v10.1/validation/historical-macos/requirements-validation.lock",
    "docs/delivery-provenance/v10.1/validation/historical-macos/wheelhouse-manifest.json",
    "docs/delivery-provenance/v10.1/validation/historical-macos/raw/fresh-extraction-full-suite.stderr.txt",
    "docs/delivery-provenance/v10.1/validation/historical-macos/raw/fresh-extraction-full-suite.stdout.txt",
    "docs/delivery-provenance/v10.1/validation/historical-macos/raw/fresh-extraction-verifier.stderr.txt",
    "docs/delivery-provenance/v10.1/validation/historical-macos/raw/fresh-extraction-verifier.stdout.txt",
    "docs/delivery-provenance/v10.1/validation/historical-macos/raw/source-tree-full-suite.stderr.txt",
    "docs/delivery-provenance/v10.1/validation/historical-macos/raw/source-tree-full-suite.stdout.txt",
    "docs/delivery-provenance/v10.1/validation/historical-macos/raw/source-tree-verifier.stderr.txt",
    "docs/delivery-provenance/v10.1/validation/historical-macos/raw/source-tree-verifier.stdout.txt",
    "docs/delivery-provenance/v10.1/validation/raw/fresh-extraction-verifier.stderr.txt",
    "docs/delivery-provenance/v10.1/validation/raw/fresh-extraction-verifier.stdout.txt",
    "docs/delivery-provenance/v10.1/validation/raw/network-before.txt",
    "docs/delivery-provenance/v10.1/validation/raw/network-disabled.txt",
    "docs/delivery-provenance/v10.1/validation/raw/network-probe.stderr.txt",
    "docs/delivery-provenance/v10.1/validation/raw/offline-verification-summary.txt",
    "docs/delivery-provenance/v10.1/validation/raw/source-tree-verifier.stderr.txt",
    "docs/delivery-provenance/v10.1/validation/raw/source-tree-verifier.stdout.txt",
    "docs/delivery-provenance/v10.1/validation/requirements-validation.in",
    "docs/delivery-provenance/v10.1/validation/requirements-validation.lock",
    "docs/delivery-provenance/v10.1/validation/wheelhouse-manifest.json",
    "scripts/check_v10_1_mapping_readiness.py",
    "scripts/check_v10_1_prompt_stage_pack.py",
    "scripts/prepare_v10_1_mapping.py",
    "tests/test_v10_1_prompt_stage_pack.py",
    "tests/test_v10_1_mapping_readiness.py",
}
REQUIRED_PHASE_GATES = {
    ("H0_PREPARATION", "exit_gates"): {
        "MAPPING_ASSESSMENT_READY",
        "STAGED_PROMPT_PACK_VALID",
        "HUMAN_MAPPING_APPROVAL",
        "SOURCE_AND_FRESH_VERIFIER_EVIDENCE",
    },
    ("H1_REPOSITORY_INTEGRATION", "entry_gates"): {
        "HUMAN_MAPPING_APPROVAL",
        "APPROVED_BASE_COMMIT",
        "CLEAN_OR_PRESERVED_WORKTREE",
    },
    ("H1_REPOSITORY_INTEGRATION", "exit_gates"): {
        "ONE_CANONICAL_PROMPT_SET",
        "PROMPT_MANIFEST_REBUILT",
        "REPOSITORY_VALIDATION_PASS",
        "ROLLBACK_SNAPSHOT_RECORDED",
    },
    ("H2_EXTERNAL_QUALIFICATION", "entry_gates"): {
        "H1_COMMITTED_AND_AUDITED",
        "APPROVED_HOST_TRUST_BOUNDARY",
        "SIGNED_INSTALLATION_AUTHORIZATION",
        "HASH_LOCKED_LINUX_VALIDATION_RUNTIME",
    },
    ("H2_EXTERNAL_QUALIFICATION", "exit_gates"): {
        "EXTERNAL_CONTROLLER_READ_ONLY",
        "DUAL_RUN_EQUIVALENCE_PASS",
        "STATE_IMPORT_DRY_RUN_PASS",
        "INDEPENDENT_CUTOVER_AUDIT_PASS",
    },
    ("H3_CONTROLLED_CUTOVER", "entry_gates"): {
        "H2_QUALIFICATION_PASS",
        "REPOSITORY_CONTROLLER_QUIESCED",
        "SIGNED_STATE_SNAPSHOT",
        "TWO_PERSON_CUTOVER_APPROVAL",
        "ROLLBACK_TEST_PASS",
    },
    ("H3_CONTROLLED_CUTOVER", "exit_gates"): {
        "EXTERNAL_CONTROLLER_PRIMARY",
        "REPOSITORY_CONTROLLER_DISABLED_FOR_WRITES",
        "POST_CUTOVER_RECONCILIATION_PASS",
    },
}
REQUIRED_CUTOVER_SAFEGUARDS = {
    "Never permit both controllers to write stage state or Git history concurrently.",
    "Bind every transition artifact to the exact source commit, tree, prompt archive hash and policy identity.",
    "Run the external controller read-only against an immutable snapshot before any state handoff.",
    "Compare repository and external controller decisions on the same fixtures and require zero unexplained differences.",
    "Transfer only schema-validated committed evidence; never copy .codex-loop live state, secrets, keys, receipts or mutable ledgers.",
    "Require a signed state snapshot, consumed nonce, short expiry and explicit rollback point for cutover.",
    "Keep provider, installer and production apply capabilities unavailable until separately approved.",
    "Execute one transition prompt stage per invocation and never advance stages automatically.",
    "Fail closed if any mapped path, reference, audit authority, runtime dependency or host ownership decision remains unresolved.",
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def display_path(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return str(path)


def load_json(path: Path, errors: list[str]) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        errors.append(f"{path}: invalid JSON: {exc}")
        return {}
    if not isinstance(value, dict):
        errors.append(f"{path}: expected a JSON object")
        return {}
    return value


def load_mapping(path: Path, errors: list[str]) -> list[dict[str, str]]:
    try:
        with path.open(newline="", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            if reader.fieldnames != REQUIRED_FIELDS:
                errors.append(f"mapping columns differ: {reader.fieldnames!r}")
                return []
            return list(reader)
    except OSError as exc:
        errors.append(f"{path}: cannot read mapping: {exc}")
        return []


def deterministic_mapping(source: Path) -> list[dict[str, str]]:
    script = ROOT / "scripts" / "prepare_v10_1_mapping.py"
    spec = importlib.util.spec_from_file_location("azpr_v10_1_mapping_preparer", script)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load mapping preparation module")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.build_rows(source)


def prompt_stage_pack_errors(root: Path) -> list[str]:
    script = root / "scripts" / "check_v10_1_prompt_stage_pack.py"
    spec = importlib.util.spec_from_file_location("azpr_v10_1_prompt_stage_pack", script)
    if spec is None or spec.loader is None:
        return ["cannot load prompt-stage pack validator"]
    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
        result = module.validate_pack(root)
    except Exception as exc:
        return [f"prompt-stage pack validator failed: {exc}"]
    return list(result) if isinstance(result, list) else ["prompt-stage pack validator returned invalid result"]


def approval_binding_status(
    path: Path,
    *,
    mapping_path: Path,
    contract_path: Path,
    verifier_attempts_path: Path,
    base_commit: str | None,
    prompt_sha256: str | None,
) -> tuple[bool, list[str]]:
    if not path.is_file():
        return False, []
    issues: list[str] = []
    value = load_json(path, issues)
    expected = {
        "format_version": "1.0",
        "approval_kind": "AZPR_V10_1_INTEGRATION_MAPPING_APPROVAL",
        "approved": True,
        "base_commit": base_commit,
        "mapping_sha256": sha256(mapping_path) if mapping_path.is_file() else None,
        "transition_contract_sha256": sha256(contract_path) if contract_path.is_file() else None,
        "prompt_archive_sha256": prompt_sha256,
        "prompt_stage_hash_manifest_sha256": (
            sha256(contract_path.parent / "prompt-stages" / "SHA256SUMS.json")
            if (contract_path.parent / "prompt-stages" / "SHA256SUMS.json").is_file()
            else None
        ),
        "verifier_evidence_sha256": (
            sha256(verifier_attempts_path) if verifier_attempts_path.is_file() else None
        ),
    }
    for field, required in expected.items():
        if value.get(field) != required:
            issues.append(f"human approval binding mismatch: {field}")
    if not isinstance(value.get("approved_by"), str) or not value.get("approved_by", "").strip():
        issues.append("human approval lacks approved_by")
    approved_at = value.get("approved_at")
    try:
        parsed_approval_time = datetime.fromisoformat(
            approved_at.removesuffix("Z") + "+00:00"
        ) if isinstance(approved_at, str) and approved_at.endswith("Z") else None
    except ValueError:
        parsed_approval_time = None
    if parsed_approval_time is None or parsed_approval_time.utcoffset() is None:
        issues.append("human approval lacks a UTC approved_at timestamp")
    return not issues, issues


def verifier_evidence_status(
    attempts: dict[str, Any],
    *,
    root: Path,
    runtime_manifest_path: Path,
    implementation_sha256: str,
    prompt_sha256: str,
) -> tuple[bool, list[str]]:
    issues: list[str] = []
    if not attempts:
        return False, ["delivery verifier attempt evidence is absent"]
    candidate = attempts.get("candidate", {})
    if candidate.get("implementation_archive_sha256") != implementation_sha256:
        issues.append("verifier evidence implementation archive binding mismatch")
    if candidate.get("prompt_archive_sha256") != prompt_sha256:
        issues.append("verifier evidence prompt archive binding mismatch")
    if candidate.get("source_and_fresh_trees_byte_identical_after_attempts") is not True:
        issues.append("verifier evidence does not prove byte-identical source and fresh trees")
    if candidate.get("verifier_sha256") != "e0058361f6e01f3ca44931d42ae3ef1aad811150c0e39c27c8fcf93cb8a4cb84":
        issues.append("verifier evidence executable binding mismatch")
    runtime = attempts.get("runtime", {})
    if (
        not runtime_manifest_path.is_file()
        or runtime.get("runtime_manifest_sha256") != sha256(runtime_manifest_path)
    ):
        issues.append("verifier evidence runtime-manifest binding mismatch")
    if runtime.get("network_used_during_verification") is not False:
        issues.append("verifier evidence must record network-disabled execution")

    inventory = candidate.get("inventory_comparison", {})
    if not isinstance(inventory, dict):
        issues.append("verifier evidence lacks inventory-comparison binding")
    else:
        inventory_path = root / str(inventory.get("path", ""))
        if (
            not inventory_path.is_file()
            or inventory.get("sha256") != sha256(inventory_path)
        ):
            issues.append("verifier evidence inventory-comparison binding mismatch")

    network_evidence = runtime.get("network_evidence", {})
    if not isinstance(network_evidence, dict):
        issues.append("verifier evidence lacks network-state bindings")
    else:
        for label in ("before", "disabled", "probe_stderr"):
            evidence = network_evidence.get(label, {})
            relative = evidence.get("path") if isinstance(evidence, dict) else None
            expected_sha = evidence.get("sha256") if isinstance(evidence, dict) else None
            absolute = root / str(relative or "")
            if not absolute.is_file() or expected_sha != sha256(absolute):
                issues.append(f"verifier evidence network binding mismatch: {label}")

    validation_root = (root / "docs" / "delivery-provenance" / "v10.1" / "validation").resolve()
    for key, fresh_flag in (("source_tree", False), ("fresh_extraction", True)):
        entry = attempts.get(key, {}) if isinstance(attempts.get(key), dict) else {}
        for stream in ("raw_stdout", "raw_stderr"):
            evidence = entry.get(stream, {}) if isinstance(entry.get(stream), dict) else {}
            relative = evidence.get("path")
            expected_sha = evidence.get("sha256")
            if not isinstance(relative, str) or not isinstance(expected_sha, str):
                issues.append(f"{key} lacks {stream} hash evidence")
                continue
            relative_path = PurePosixPath(relative)
            if relative_path.is_absolute() or ".." in relative_path.parts or "\\" in relative:
                issues.append(f"{key} has unsafe {stream} path")
                continue
            absolute = (root / relative).resolve()
            try:
                absolute.relative_to(validation_root)
            except ValueError:
                issues.append(f"{key} {stream} lies outside validation provenance")
                continue
            if not absolute.is_file() or sha256(absolute) != expected_sha:
                issues.append(f"{key} {stream} bytes do not match evidence hash")
        if str(entry.get("status", "")).startswith("PASS"):
            stdout = entry.get("raw_stdout", {})
            stdout_path = root / str(stdout.get("path", ""))
            try:
                raw_result = json.loads(stdout_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                issues.append(f"{key} PASS stdout is not verifier JSON: {exc}")
                continue
            if (
                raw_result.get("release_tests_passed") != 120
                or raw_result.get("collected_tests_verified") != 120
                or raw_result.get("candidate_version") != "v10.1"
                or raw_result.get("prompt_zip_sha256") != prompt_sha256
                or raw_result.get("fresh_extraction_invocation") is not fresh_flag
                or not str(raw_result.get("status", "")).startswith("PASS")
            ):
                issues.append(f"{key} PASS stdout fields do not prove a complete verifier run")
            environment = raw_result.get("environment", {})
            if (
                environment.get("network_required") is not False
                or environment.get("credential_environment_inherited") is not False
                or environment.get("source_tree_mutation_detected") is not False
                or raw_result.get("safe_for_unattended_execution_now") is not False
                or raw_result.get("organization_release_signature_status")
                != "NOT_PROVIDED_UNSIGNED_DEVELOPMENT_CANDIDATE"
            ):
                issues.append(f"{key} PASS stdout violates verifier safety disposition")
        diagnostic = (
            entry.get("complete_suite_diagnostic", {})
            if isinstance(entry.get("complete_suite_diagnostic"), dict)
            else {}
        )
        if not diagnostic:
            continue
        diagnostic_stdout_path: Path | None = None
        for stream in ("raw_stdout", "raw_stderr"):
            evidence = diagnostic.get(stream, {}) if isinstance(diagnostic.get(stream), dict) else {}
            relative = evidence.get("path")
            expected_sha = evidence.get("sha256")
            if not isinstance(relative, str) or not isinstance(expected_sha, str):
                issues.append(f"{key} diagnostic lacks {stream} hash evidence")
                continue
            relative_path = PurePosixPath(relative)
            if relative_path.is_absolute() or ".." in relative_path.parts or "\\" in relative:
                issues.append(f"{key} diagnostic has unsafe {stream} path")
                continue
            absolute = (root / relative).resolve()
            try:
                absolute.relative_to(validation_root)
            except ValueError:
                issues.append(f"{key} diagnostic {stream} lies outside validation provenance")
                continue
            if not absolute.is_file() or sha256(absolute) != expected_sha:
                issues.append(f"{key} diagnostic {stream} bytes do not match evidence hash")
                continue
            if stream == "raw_stdout":
                diagnostic_stdout_path = absolute
        if diagnostic_stdout_path is not None:
            summary = diagnostic_stdout_path.read_text(encoding="utf-8", errors="replace")
            expected_summary = (
                f"{diagnostic.get('tests_failed')} failed, "
                f"{diagnostic.get('tests_passed')} passed, "
                f"{diagnostic.get('subtests_passed')} subtests passed"
            )
            if expected_summary not in summary:
                issues.append(f"{key} diagnostic counts are not present in raw pytest output")
    return not issues, issues


def observed_head(root: Path) -> str | None:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=root, text=True, capture_output=True, check=False
    )
    return result.stdout.strip() if result.returncode == 0 else None


def observed_worktree_paths(root: Path) -> tuple[set[str], str | None]:
    result = subprocess.run(
        ["git", "status", "--porcelain=v1", "-z", "--untracked-files=all"],
        cwd=root,
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        return set(), result.stderr.strip() or "git status failed"
    paths: set[str] = set()
    records = result.stdout.split("\0")
    skip_rename_source = False
    for record in records:
        if not record:
            continue
        if skip_rename_source:
            paths.add(record)
            skip_rename_source = False
            continue
        if len(record) < 4:
            return set(), f"unrecognized git status record: {record!r}"
        status = record[:2]
        paths.add(record[3:])
        if "R" in status or "C" in status:
            skip_rename_source = True
    return paths, None


def phase(contract: dict[str, Any], phase_id: str) -> dict[str, Any]:
    for candidate in contract.get("phases", []):
        if isinstance(candidate, dict) and candidate.get("phase_id") == phase_id:
            return candidate
    return {}


def verifier_status(
    baseline: dict[str, Any], attempts: dict[str, Any]
) -> tuple[dict[str, Any], bool]:
    expected = 120
    result: dict[str, Any] = {
        "source_tests_passed": 0,
        "fresh_extraction_tests_passed": 0,
        "expected": expected,
        "source_status": "MISSING",
        "fresh_extraction_status": "MISSING",
    }
    checks = baseline.get("checks", {}) if isinstance(baseline.get("checks"), dict) else {}
    source = checks.get("source_tree_verifier", {}) if isinstance(checks.get("source_tree_verifier"), dict) else {}
    fresh = checks.get("fresh_extraction_verifier", {}) if isinstance(checks.get("fresh_extraction_verifier"), dict) else {}
    entries: dict[str, dict[str, Any]] = {"source_tree": source, "fresh_extraction": fresh}
    for key in ("source_tree", "fresh_extraction"):
        attempt = attempts.get(key, {}) if isinstance(attempts.get(key), dict) else {}
        if attempt:
            entries[key] = attempt
    source_entry = entries["source_tree"]
    fresh_entry = entries["fresh_extraction"]
    result["source_tests_passed"] = int(source_entry.get("tests_passed", 0) or 0)
    result["fresh_extraction_tests_passed"] = int(fresh_entry.get("tests_passed", 0) or 0)
    result["source_status"] = str(source_entry.get("status", "FAIL"))
    result["fresh_extraction_status"] = str(fresh_entry.get("status", "FAIL"))

    def complete(entry: dict[str, Any]) -> bool:
        return (
            entry.get("tests_expected") == expected
            and entry.get("tests_passed") == expected
            and entry.get("exit_code") == 0
            and str(entry.get("status", "")).startswith("PASS")
        )

    passed = (
        complete(source_entry)
        and complete(fresh_entry)
        and str(attempts.get("status", "")).startswith("PASS")
    )
    return result, passed


def assess(
    mapping_path: Path,
    contract_path: Path,
    staging_validation_path: Path,
    verifier_attempts_path: Path,
    *,
    root: Path = ROOT,
    head: str | None = None,
) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    mapping = load_mapping(mapping_path, errors)
    contract = load_json(contract_path, errors)
    baseline = load_json(staging_validation_path, errors)
    attempts = load_json(verifier_attempts_path, []) if verifier_attempts_path.is_file() else {}
    identity_path = root / "docs" / "delivery-provenance" / "v10.1" / "delivery-identity.json"
    identity = load_json(identity_path, errors)
    immutable_mapping_path = (
        root
        / "docs"
        / "delivery-provenance"
        / "v10.1"
        / "integration"
        / "AZPR-v10.1-integration-path-mapping.staging-original.csv"
    )

    if contract.get("decision_id") != "AZPR-V10.1-STAGED-HYBRID-CONTROLLER":
        errors.append("transition contract decision identity mismatch")
    if contract.get("decision_status") != "SELECTED_FOR_MAPPING_APPROVAL":
        errors.append("transition contract is not preparation-only")
    if contract.get("strategy") != "STAGED_HYBRID":
        errors.append("transition strategy is not STAGED_HYBRID")
    if contract.get("provenance_root") != "docs/delivery-provenance/v10.1":
        errors.append("delivery provenance destination mismatch")

    prompt_set = contract.get("prompt_set", {})
    if prompt_set.get("status") != "SELECTED_NOT_ACTIVE":
        errors.append("selected prompt set must remain inactive")
    if prompt_set.get("duplicate_active_sets_allowed") is not False:
        errors.append("duplicate active prompt sets must be forbidden")
    if prompt_set.get("numbered_prompts") != 38 or prompt_set.get("appendices") != 3:
        errors.append("transition contract prompt counts differ from 38 plus 3")

    prompt_pack = contract.get("orchestration_prompt_pack", {})
    expected_pack_manifest = "automation/integration/v10.1/prompt-stages/stage-manifest.json"
    expected_pack_hash_manifest = "automation/integration/v10.1/prompt-stages/SHA256SUMS.json"
    expected_pack_validator = "scripts/check_v10_1_prompt_stage_pack.py"
    if prompt_pack.get("pack_id") != "AZPR_V10_1_STAGED_HYBRID_INTEGRATION":
        errors.append("orchestration prompt-pack identity mismatch")
    if prompt_pack.get("status") != "DRAFT_NOT_ACTIVE":
        errors.append("orchestration prompt pack must remain draft and inactive")
    if prompt_pack.get("manifest") != expected_pack_manifest:
        errors.append("orchestration prompt-pack manifest path drifted")
    if prompt_pack.get("hash_manifest") != expected_pack_hash_manifest:
        errors.append("orchestration prompt-pack hash-manifest path drifted")
    if prompt_pack.get("validator") != expected_pack_validator:
        errors.append("orchestration prompt-pack validator path drifted")
    if prompt_pack.get("stage_count") != 10:
        errors.append("orchestration prompt pack must contain exactly ten stages")
    if prompt_pack.get("one_stage_per_invocation") is not True:
        errors.append("orchestration prompt pack must permit only one stage per invocation")
    if prompt_pack.get("automatic_stage_advancement") is not False:
        errors.append("orchestration prompt pack must forbid automatic stage advancement")
    if prompt_pack.get("authority_effect") is not False:
        errors.append("orchestration prompt pack must grant no authority")
    pack_hash_manifest_path = root / expected_pack_hash_manifest
    if (
        not pack_hash_manifest_path.is_file()
        or prompt_pack.get("hash_manifest_sha256") != sha256(pack_hash_manifest_path)
    ):
        errors.append("orchestration prompt-pack hash-manifest binding mismatch")
    pack_errors = prompt_stage_pack_errors(root)
    prompt_stage_pack_valid = not pack_errors
    errors.extend(f"prompt-stage pack: {issue}" for issue in pack_errors)

    expected_audit_authority = {
        "interim_source": "docs/audits/README.md",
        "index_path": "docs/audits/index.json",
        "index_status": "ABSENT_UNTIL_FIRST_CONTROLLER_FORMAL_AUDIT",
        "bootstrap_stage": "INT-04",
        "schema_implementation": "automation/controller.py:write_audit_artifacts",
        "result_schema": "automation/result.schema.json",
        "governance_owner_required": True,
        "delivery_audit_authoritative": False,
    }
    interim_audit_authority_valid = contract.get("audit_authority") == expected_audit_authority
    if not interim_audit_authority_valid:
        errors.append("interim audit-authority contract drifted or grants delivery evidence authority")

    repo_controller = contract.get("controller_states", {}).get("repository_controller", {})
    external_controller = contract.get("controller_states", {}).get("external_controller", {})
    if repo_controller.get("path") != "automation/controller.py":
        errors.append("repository controller path is not canonical")
    if repo_controller.get("status") != "DEVELOPMENT_ONLY":
        errors.append("repository controller status is not development-only")
    if repo_controller.get("activation_allowed") is not False:
        errors.append("repository controller must remain activation-disabled during integration")
    if repo_controller.get("execution_allowed_during_integration") is not False:
        errors.append("repository controller must remain inert during integration")
    if external_controller.get("activation_allowed") is not False:
        errors.append("external controller must remain activation-disabled")
    if external_controller.get("repository_destination") is not None:
        errors.append("external controller must not have a repository destination")
    if external_controller.get("status") != "DEFERRED_UNQUALIFIED":
        errors.append("external controller must remain deferred and unqualified")
    if external_controller.get("source_prefix") != "trusted-controller/":
        errors.append("external controller source prefix drifted")
    expected_external_controller_sha256 = (
        "5f65a20153f30a08b64ef8e5b56a1dd0d9c885dc40c5249fe103485931d9d1d3"
    )
    if external_controller.get("candidate_controller_sha256") != expected_external_controller_sha256:
        errors.append("external controller candidate identity drifted")

    h0 = phase(contract, "H0_PREPARATION")
    h1 = phase(contract, "H1_REPOSITORY_INTEGRATION")
    h2 = phase(contract, "H2_EXTERNAL_QUALIFICATION")
    h3 = phase(contract, "H3_CONTROLLED_CUTOVER")
    if h0.get("controller_writer") != "NONE":
        errors.append("H0 must have no controller writer")
    if h1.get("controller_writer") != "NONE":
        errors.append("H1 must have no controller writer")
    if h2.get("controller_writer") != "NONE":
        errors.append("H2 qualification must be read-only")
    if h3.get("controller_writer") != "EXTERNAL_CONTROLLER":
        errors.append("H3 must identify the external controller as the post-fence writer")
    for (phase_id, gate_kind), required in REQUIRED_PHASE_GATES.items():
        phase_value = phase(contract, phase_id)
        actual = phase_value.get(gate_kind, [])
        actual_set = set(actual) if isinstance(actual, list) else set()
        missing = sorted(required - actual_set)
        if missing:
            errors.append(f"{phase_id} lacks required {gate_kind}: {missing}")

    cutover_safeguards = contract.get("cutover_safeguards", [])
    safeguard_set = set(cutover_safeguards) if isinstance(cutover_safeguards, list) else set()
    missing_safeguards = sorted(REQUIRED_CUTOVER_SAFEGUARDS - safeguard_set)
    if missing_safeguards:
        errors.append(f"transition contract lacks cutover safeguards: {missing_safeguards}")
    rollback_forbidden = set(contract.get("rollback", {}).get("forbidden", []))
    required_rollback_forbidden = {
        "rewriting source evidence",
        "copying live external state into the repository",
        "running both controller writers",
        "advancing a roadmap during rollback",
    }
    if not required_rollback_forbidden.issubset(rollback_forbidden):
        errors.append("transition rollback prohibitions are incomplete")

    authority = contract.get("authority_state", {})
    if authority.get("active_policy") is not None or authority.get("active_roadmap") is not None:
        errors.append("policy and roadmap must remain inactive")
    if authority.get("single_controller_writer_required") is not True:
        errors.append("single-controller-writer safeguard is missing")
    if authority.get("live_runtime_state_transfer_allowed") is not False:
        errors.append("live runtime state transfer must be forbidden")
    approval = contract.get("approval", {})
    if approval.get("codex_may_create_approval") is not False:
        errors.append("contract must forbid Codex-created approvals")
    if approval.get("status") != "PENDING_HUMAN_APPROVAL":
        errors.append("mapping approval status must remain pending during preparation")
    if approval.get("format_version") != "1.0" or approval.get("approval_kind") != "AZPR_V10_1_INTEGRATION_MAPPING_APPROVAL":
        errors.append("mapping approval contract shape drifted")
    required_approval_bindings = {
        "base_commit",
        "mapping_sha256",
        "transition_contract_sha256",
        "prompt_archive_sha256",
        "prompt_stage_hash_manifest_sha256",
        "verifier_evidence_sha256",
        "approved_by",
        "approved_at",
    }
    if set(approval.get("required_bindings", [])) != required_approval_bindings:
        errors.append("mapping approval required bindings are incomplete")
    approval_value = approval.get("approval_file")
    expected_approval = "automation/approvals/v10.1-integration-path-mapping-approved.json"
    if approval_value != expected_approval:
        errors.append("mapping approval destination drifted from the human-only location")
    approval_relative = Path(str(approval_value or ""))
    if approval_relative.is_absolute() or ".." in approval_relative.parts:
        errors.append("mapping approval destination is unsafe")
        approval_path = root / "automation" / "approvals" / ".invalid-v10.1-approval-path"
    else:
        approval_path = root / approval_relative

    if not immutable_mapping_path.is_file() or sha256(immutable_mapping_path) != EXPECTED_STAGING_MAPPING_SHA256:
        errors.append("immutable staging mapping is absent or changed")
    mapping_lineage = identity.get("mapping_lineage", {})
    if mapping_lineage.get("immutable_staging_mapping_sha256") != EXPECTED_STAGING_MAPPING_SHA256:
        errors.append("delivery identity does not bind the immutable staging mapping")
    authority_effect = identity.get("authority_effect", {})
    if any(authority_effect.get(key) is not False for key in (
        "activates_policy",
        "activates_roadmap",
        "activates_repository_controller",
        "activates_external_controller",
        "authorizes_materialization",
        "authorizes_production",
    )):
        errors.append("delivery provenance identity grants forbidden authority")
    identity_controller = identity.get("controller_identity", {})
    if identity_controller.get("external_candidate_sha256") != expected_external_controller_sha256:
        errors.append("delivery identity does not bind the external controller candidate")
    implementation_inputs = [
        item
        for item in identity.get("received_inputs", [])
        if isinstance(item, dict) and item.get("role") == "implementation_candidate"
    ]
    expected_implementation_sha256 = (
        "618449d73fd921e0fb366c0aed8c9a666b2ead3847e529a6ced9692fe41e2b24"
    )
    if (
        len(implementation_inputs) != 1
        or implementation_inputs[0].get("sha256") != expected_implementation_sha256
    ):
        errors.append("delivery identity does not bind the implementation archive")

    current_head = head if head is not None else observed_head(root)
    if current_head != contract.get("base_commit"):
        errors.append(f"HEAD {current_head!r} does not match contract base commit")
    controller_path = root / "automation" / "controller.py"
    if not controller_path.is_file() or sha256(controller_path) != repo_controller.get("sha256"):
        errors.append("repository controller bytes drifted from the transition contract")

    expected_rows: list[dict[str, str]] = []
    try:
        expected_rows = deterministic_mapping(immutable_mapping_path)
    except (OSError, RuntimeError, ValueError) as exc:
        errors.append(f"cannot reproduce deterministic mapping: {exc}")
    deterministic_mapping_matches = bool(expected_rows) and mapping == expected_rows
    if expected_rows and not deterministic_mapping_matches:
        actual_by_key = {
            (row["source_archive"], row["source_path"]): row for row in mapping
        }
        expected_by_key = {
            (row["source_archive"], row["source_path"]): row for row in expected_rows
        }
        missing = sorted(set(expected_by_key) - set(actual_by_key))
        extra = sorted(set(actual_by_key) - set(expected_by_key))
        if missing:
            errors.append(f"mapping omits deterministic dispositions: {missing[:10]}")
        if extra:
            errors.append(f"mapping contains unexpected dispositions: {extra[:10]}")
        differences: list[str] = []
        for key in sorted(set(expected_by_key) & set(actual_by_key)):
            for field in REQUIRED_FIELDS:
                if actual_by_key[key].get(field) != expected_by_key[key].get(field):
                    differences.append(f"{key!r}:{field}")
                    break
        if differences:
            errors.append(f"mapping differs from deterministic decisions: {differences[:10]}")
        actual_order = [(row["source_archive"], row["source_path"]) for row in mapping]
        expected_order = [(row["source_archive"], row["source_path"]) for row in expected_rows]
        if actual_order != expected_order:
            errors.append("mapping row order differs from deterministic preparation output")

    seen: set[tuple[str, str]] = set()
    destinations: dict[str, list[tuple[str, str]]] = {}
    for index, row in enumerate(mapping, start=2):
        key = (row["source_archive"], row["source_path"])
        if key in seen:
            errors.append(f"row {index}: duplicate source disposition {key!r}")
        seen.add(key)
        if not SHA256_PATTERN.fullmatch(row["source_sha256"]):
            errors.append(f"row {index}: invalid SHA-256")
        for label, value in (
            ("source_path", row["source_path"]),
            ("proposed_destination", row["proposed_destination"]),
        ):
            if not value:
                continue
            candidate_path = PurePosixPath(value)
            if candidate_path.is_absolute() or ".." in candidate_path.parts or "\\" in value:
                errors.append(f"row {index}: unsafe {label}")
        if row["action"] not in VALID_ACTIONS:
            errors.append(f"row {index}: invalid action {row['action']!r}")
        if row["action"] in ACTIONABLE and not row["proposed_destination"]:
            errors.append(f"row {index}: actionable row lacks a destination")
        if row["resolution_status"] not in VALID_RESOLUTION_STATES:
            errors.append(f"row {index}: invalid resolution state {row['resolution_status']!r}")
        if row["decision_id"] == "UNRESOLVED":
            errors.append(f"row {index}: unresolved disposition")
        if row["approval_needed"] not in {"YES", "NO"}:
            errors.append(f"row {index}: invalid approval_needed value")
        if (
            row["transition_phase"] == "H1_REPOSITORY_INTEGRATION"
            and row["action"] in {"ADD", "REPLACE", "MERGE", "MOVE"}
            and row["approval_needed"] != "YES"
        ):
            errors.append(f"row {index}: H1 materialization is not gated by human approval")
        tokens = set(filter(None, row["conflict_status"].split(";")))
        if tokens & FORBIDDEN_CONFLICTS:
            errors.append(f"row {index}: unresolved conflict tokens {sorted(tokens & FORBIDDEN_CONFLICTS)}")
        for field in ("reason", "dependencies", "validation", "rollback", "decision_id", "transition_phase"):
            if not row[field].strip():
                errors.append(f"row {index}: missing {field}")
        destination = row["proposed_destination"]
        if (
            row["source_archive"] != "CURRENT_REPOSITORY"
            and row["action"] in {"ADD", "REPLACE"}
            and destination
        ):
            destinations.setdefault(destination, []).append(key)

    generated_rows = {
        row["source_path"]: row
        for row in mapping
        if row["source_archive"] == "INTEGRATION_GENERATED"
    }
    if set(generated_rows) != REQUIRED_GENERATED_PATHS:
        missing = sorted(REQUIRED_GENERATED_PATHS - set(generated_rows))
        extra = sorted(set(generated_rows) - REQUIRED_GENERATED_PATHS)
        errors.append(f"generated preparation disposition set differs: missing={missing} extra={extra}")
    for path, row in generated_rows.items():
        absolute = root / path
        if not absolute.is_file() or sha256(absolute) != row["source_sha256"]:
            errors.append(f"generated preparation bytes drifted: {path}")
        if row["proposed_destination"] != path:
            errors.append(f"generated preparation destination drifted: {path}")

    for destination, donors in destinations.items():
        if len(donors) > 1:
            errors.append(f"multiple materializing donors for {destination}: {donors!r}")

    implementation_prompts = [
        row
        for row in mapping
        if row["source_archive"] == "AZPR-autonomous-execution-primed-draft-v10.1.zip"
        and (
            row["source_path"].startswith("repository-overlay/automation/numbered/")
            or row["source_path"].startswith("repository-overlay/automation/appendices/")
        )
    ]
    prompt_actions = {action: sum(row["action"] == action for row in implementation_prompts) for action in VALID_ACTIONS}
    if len(implementation_prompts) != 41 or prompt_actions["REPLACE"] != 38 or prompt_actions["ADD"] != 3:
        errors.append(f"selected prompt donor mapping is not 38 REPLACE plus 3 ADD: {prompt_actions}")

    current_prompts = [
        row
        for row in mapping
        if row["source_archive"] == "CURRENT_REPOSITORY"
        and (
            row["source_path"].startswith("automation/numbered/")
            or row["source_path"].startswith("automation/appendices/")
        )
        and row["source_path"].endswith(".md")
    ]
    current_prompt_actions = {
        action: sum(row["action"] == action for row in current_prompts) for action in VALID_ACTIONS
    }
    if (
        len(current_prompts) != 41
        or current_prompt_actions["REPLACE"] != 38
        or current_prompt_actions["MOVE"] != 3
    ):
        errors.append(
            f"current prompt retirement is not 38 replacements plus 3 moves: {current_prompt_actions}"
        )

    stale_reference_paths = {
        "BUNDLE_MANIFEST.txt",
        "docs/automation/AZPR-Autonomous-Agent-Loop-Implementation-Guide.docx",
    }
    stale_reference_rows = [
        row
        for row in mapping
        if row["source_archive"] == "CURRENT_REPOSITORY"
        and row["source_path"] in stale_reference_paths
    ]
    if len(stale_reference_rows) != 2 or any(
        row["action"] != "MOVE"
        or row["proposed_destination"]
        != f"docs/delivery-provenance/v10.1/pre-v10.1-controller/{row['source_path']}"
        for row in stale_reference_rows
    ):
        errors.append("stale controller manifest/setup-guide retirement is incomplete")

    reports_rows = [
        row
        for row in mapping
        if row["source_archive"] == "AZPR-autonomous-execution-primed-draft-v10.1-reports.zip"
    ]
    if len(reports_rows) != 39 or any(
        row["action"] != "ADD"
        or row["proposed_destination"]
        != f"docs/delivery-provenance/v10.1/frozen-delivery-reports/{row['source_path']}"
        for row in reports_rows
    ):
        errors.append("frozen delivery report provenance mapping is incomplete")
    for row in reports_rows:
        destination = root / row["proposed_destination"]
        if not destination.is_file() or sha256(destination) != row["source_sha256"]:
            errors.append(f"frozen delivery report bytes drifted: {row['proposed_destination']}")

    external_rows = [
        row
        for row in mapping
        if row["source_archive"] == "AZPR-autonomous-execution-primed-draft-v10.1.zip"
        and (
            row["classification"] in EXTERNAL_CLASSES
            or row["source_path"] == "requirements-security.in"
        )
    ]
    if len(external_rows) != 52:
        errors.append(f"expected 52 deferred external candidates, found {len(external_rows)}")
    external_candidates_deferred = len(external_rows) == 52 and all(
        row["action"] == "DEFER" and not row["proposed_destination"] for row in external_rows
    )
    if not external_candidates_deferred:
        errors.append("external controller/operator/installer candidates are not uniformly deferred")

    contract_rows = [
        row
        for row in mapping
        if row["source_archive"] == "INTEGRATION_GENERATED"
        and row["source_path"] == "automation/integration/v10.1/controller-transition-contract.json"
    ]
    if len(contract_rows) != 1 or contract_rows[0]["source_sha256"] != sha256(contract_path):
        errors.append("mapping does not bind the exact transition contract")

    staging_mapping_rows = [
        row
        for row in mapping
        if row["source_archive"] == "INTEGRATION_GENERATED"
        and row["source_path"]
        == "docs/delivery-provenance/v10.1/integration/AZPR-v10.1-integration-path-mapping.staging-original.csv"
    ]
    if (
        len(staging_mapping_rows) != 1
        or staging_mapping_rows[0]["source_sha256"] != EXPECTED_STAGING_MAPPING_SHA256
    ):
        errors.append("mapping does not bind the immutable staging mapping")

    expected_prompt_sha256 = "3b235cb7e33ca409241ff26523f60f8fee89cec524b3f09e91a69927a0aa4880"
    if contract.get("prompt_set", {}).get("archive_sha256") != expected_prompt_sha256:
        errors.append("selected prompt archive identity mismatch")
    roadmap = root / "automation" / "roadmap.json"
    if not roadmap.is_file() or roadmap.stat().st_size != 0:
        errors.append("repository roadmap must remain the zero-byte inactive sentinel")
    state = load_json(root / ".codex-loop" / "state.json", errors)
    if state.get("roadmap_version") is not None:
        errors.append("local controller state contains an active roadmap version")

    runtime_manifest_path = (
        root
        / "docs"
        / "delivery-provenance"
        / "v10.1"
        / "validation"
        / "python-runtime-manifest.json"
    )
    verifier_counts, verifier_pass = verifier_status(baseline, attempts)
    verifier_evidence_valid, verifier_evidence_issues = verifier_evidence_status(
        attempts,
        root=root,
        runtime_manifest_path=runtime_manifest_path,
        implementation_sha256=expected_implementation_sha256,
        prompt_sha256=expected_prompt_sha256,
    )
    verifier_pass = verifier_pass and verifier_evidence_valid
    if not verifier_pass:
        warnings.append("both complete 120-test delivery verifier passes are still required before materialization")
    formal_delivery_verification = False
    formal_binding = attempts.get("formal_stage_result", {})
    if (
        attempts.get("status") == "PASS_FORMAL_INT_01"
        and attempts.get("formal_stage_id") == "INT-01"
        and isinstance(formal_binding, dict)
    ):
        formal_path = root / str(formal_binding.get("path", ""))
        if (
            formal_path.is_file()
            and formal_binding.get("sha256") == sha256(formal_path)
        ):
            formal_result = load_json(formal_path, warnings)
            formal_delivery_verification = (
                formal_result.get("stage_id") == "INT-01"
                and formal_result.get("phase") == "H0_PREPARATION"
                and formal_result.get("outcome") in {"COMPLETED", "PASS"}
                and formal_result.get("preconditions", {}).get("failed") == []
                and formal_result.get("next_stage") == "INT-02"
            )
    if verifier_pass and not formal_delivery_verification:
        warnings.append(
            "both verifier modes passed as pre-qualification evidence, but a valid INT-00 and formal INT-01 result are still required"
        )
    warnings.extend(verifier_evidence_issues)

    approval_valid, approval_errors = approval_binding_status(
        approval_path,
        mapping_path=mapping_path,
        contract_path=contract_path,
        verifier_attempts_path=verifier_attempts_path,
        base_commit=current_head,
        prompt_sha256=expected_prompt_sha256,
    )
    if not approval_path.is_file():
        warnings.append("human mapping approval file is intentionally absent")
    elif not approval_valid:
        warnings.append("human mapping approval exists but its exact bindings are invalid")

    changed_paths, worktree_error = observed_worktree_paths(root)
    bound_paths = {
        row["source_path"]
        for row in mapping
        if row["source_archive"] == "INTEGRATION_GENERATED"
    }
    bound_paths.update(row["proposed_destination"] for row in reports_rows)
    bound_paths.update(
        {
            "docs/delivery-provenance/v10.1/integration/AZPR-v10.1-integration-path-mapping.csv",
            "docs/delivery-provenance/v10.1/validation/mapping-readiness-assessment.json",
        }
    )
    unbound_changes = sorted(changed_paths - bound_paths)
    worktree_clean_or_preserved = worktree_error is None and not unbound_changes
    if worktree_error:
        warnings.append(f"could not inspect worktree preservation: {worktree_error}")
    if unbound_changes:
        warnings.append(f"worktree contains changes outside the mapping: {unbound_changes[:10]}")

    single_writer_transition = (
        h0.get("controller_writer") == "NONE"
        and h1.get("controller_writer") == "NONE"
        and h2.get("controller_writer") == "NONE"
        and h3.get("controller_writer") == "EXTERNAL_CONTROLLER"
        and repo_controller.get("activation_allowed") is False
        and external_controller.get("activation_allowed") is False
        and authority.get("single_controller_writer_required") is True
        and authority.get("live_runtime_state_transfer_allowed") is False
        and not missing_safeguards
    )
    mapping_ready = not errors
    materialization_ready = (
        mapping_ready
        and verifier_pass
        and formal_delivery_verification
        and approval_valid
        and worktree_clean_or_preserved
    )
    return {
        "assessment": "AZPR_V10_1_MAPPING_READINESS",
        "mapping": display_path(mapping_path, root),
        "mapping_sha256": sha256(mapping_path) if mapping_path.is_file() else None,
        "transition_contract_sha256": sha256(contract_path) if contract_path.is_file() else None,
        "prompt_stage_hash_manifest_sha256": (
            sha256(pack_hash_manifest_path) if pack_hash_manifest_path.is_file() else None
        ),
        "base_commit": current_head,
        "row_count": len(mapping),
        "checks": {
            "mapping_structurally_complete": mapping_ready,
            "deterministic_mapping_matches": deterministic_mapping_matches,
            "prompt_stage_pack_valid": prompt_stage_pack_valid,
            "interim_audit_authority_valid": interim_audit_authority_valid,
            "selected_prompt_actions": prompt_actions,
            "current_prompt_retirement_actions": current_prompt_actions,
            "frozen_delivery_report_rows": len(reports_rows),
            "external_candidates_deferred": external_candidates_deferred,
            "single_writer_transition": single_writer_transition,
            "policy_and_roadmap_inactive": authority.get("active_policy") is None
            and authority.get("active_roadmap") is None,
            "human_approval_present": approval_path.is_file(),
            "human_approval_valid": approval_valid,
            "worktree_clean_or_mapping_preserved": worktree_clean_or_preserved,
            "unbound_worktree_changes": unbound_changes,
            "verifier_counts": verifier_counts,
            "verifier_evidence_valid": verifier_evidence_valid,
            "both_delivery_verifiers_pass": verifier_pass,
            "formal_int_01_verification_present": formal_delivery_verification,
        },
        "mapping_ready_for_human_approval": mapping_ready,
        "prequalification_patch_ready": (
            mapping_ready and verifier_pass and not formal_delivery_verification
        ),
        "ready_for_materialization": materialization_ready,
        "ready_for_activation": False,
        "safe_for_unattended_execution_now": False,
        "errors": errors,
        "approval_errors": approval_errors,
        "verifier_evidence_issues": verifier_evidence_issues,
        "warnings": warnings,
        "next_required_action": (
            "CORRECT_MAPPING_OR_TRANSITION_CONTRACT"
            if not mapping_ready
            else "COMPLETE_HASH_LOCKED_LINUX_DELIVERY_VERIFICATION"
            if not verifier_pass
            else "EXECUTE_INT_00_THEN_FORMAL_INT_01"
            if not formal_delivery_verification
            else "HUMAN_REVIEW_AND_APPROVAL_OF_EXACT_MAPPING_HASH"
            if not approval_valid
            else "MATERIALIZATION_PREREQUISITES_SATISFIED"
        ),
    }


def atomic_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(value, handle, indent=2, sort_keys=True)
            handle.write("\n")
        os.replace(temporary, path)
    except BaseException:
        Path(temporary).unlink(missing_ok=True)
        raise


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mapping", type=Path, default=DEFAULT_MAPPING)
    parser.add_argument("--contract", type=Path, default=DEFAULT_CONTRACT)
    parser.add_argument("--staging-validation", type=Path, default=DEFAULT_STAGING_VALIDATION)
    parser.add_argument("--verifier-attempts", type=Path, default=DEFAULT_VERIFIER_ATTEMPTS)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--require-materialization-ready", action="store_true")
    args = parser.parse_args()
    if args.output and args.output.resolve() != DEFAULT_ASSESSMENT_OUTPUT.resolve():
        raise SystemExit("output must be the canonical v10.1 mapping assessment path")
    result = assess(
        args.mapping,
        args.contract,
        args.staging_validation,
        args.verifier_attempts,
    )
    if args.output:
        atomic_json(args.output, result)
    print(json.dumps(result, indent=2, sort_keys=True))
    ready = result["ready_for_materialization"] if args.require_materialization_ready else result[
        "mapping_ready_for_human_approval"
    ]
    return 0 if ready else 1


if __name__ == "__main__":
    raise SystemExit(main())
