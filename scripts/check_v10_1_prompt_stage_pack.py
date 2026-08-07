#!/usr/bin/env python3
"""Validate the inert AZPR v10.1 staged-hybrid integration prompt pack."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator


ROOT = Path(__file__).resolve().parents[1]
PACK_RELATIVE = Path("automation/integration/v10.1/prompt-stages")
EXPECTED_STAGE_IDS = [f"INT-{index:02d}" for index in range(10)]
EXPECTED_STAGES = [
    {
        "stage_id": "INT-00",
        "phase": "H0_PREPARATION",
        "file": "00-preflight-authority-and-inputs.md",
        "predecessor": None,
        "execution_mode": "READ_ONLY",
        "controller_writer": "NONE",
        "materializes_repository": False,
        "external_write": False,
        "requires_human_authorization": False,
    },
    {
        "stage_id": "INT-01",
        "phase": "H0_PREPARATION",
        "file": "01-linux-delivery-reverification.md",
        "predecessor": "INT-00",
        "execution_mode": "EXTERNAL_READ_ONLY_VALIDATION",
        "controller_writer": "NONE",
        "materializes_repository": False,
        "external_write": False,
        "requires_human_authorization": True,
    },
    {
        "stage_id": "INT-02",
        "phase": "H0_PREPARATION",
        "file": "02-freeze-mapping-and-human-approval-handoff.md",
        "predecessor": "INT-01",
        "execution_mode": "REPOSITORY_PREPARATION",
        "controller_writer": "NONE",
        "materializes_repository": False,
        "external_write": False,
        "requires_human_authorization": False,
    },
    {
        "stage_id": "INT-03",
        "phase": "H1_REPOSITORY_INTEGRATION",
        "file": "03-h1-materialize-approved-repository-mapping.md",
        "predecessor": "INT-02",
        "execution_mode": "ISOLATED_REPOSITORY_MATERIALIZATION",
        "controller_writer": "NONE",
        "materializes_repository": True,
        "external_write": False,
        "requires_human_authorization": True,
    },
    {
        "stage_id": "INT-04",
        "phase": "H1_REPOSITORY_INTEGRATION",
        "file": "04-h1-repository-integration-audit.md",
        "predecessor": "INT-03",
        "execution_mode": "READ_ONLY_AUDIT",
        "controller_writer": "NONE",
        "materializes_repository": False,
        "external_write": False,
        "requires_human_authorization": False,
    },
    {
        "stage_id": "INT-05",
        "phase": "H2_EXTERNAL_QUALIFICATION",
        "file": "05-h2-read-only-external-controller-qualification.md",
        "predecessor": "INT-04",
        "execution_mode": "EXTERNAL_READ_ONLY_SHADOW",
        "controller_writer": "NONE",
        "materializes_repository": False,
        "external_write": False,
        "requires_human_authorization": True,
    },
    {
        "stage_id": "INT-06",
        "phase": "H2_EXTERNAL_QUALIFICATION",
        "file": "06-h2-cutover-readiness-audit.md",
        "predecessor": "INT-05",
        "execution_mode": "READ_ONLY_AUDIT",
        "controller_writer": "NONE",
        "materializes_repository": False,
        "external_write": False,
        "requires_human_authorization": False,
    },
    {
        "stage_id": "INT-07",
        "phase": "H3_CONTROLLED_CUTOVER",
        "file": "07-h3-cutover-plan-and-authorization-package.md",
        "predecessor": "INT-06",
        "execution_mode": "CUTOVER_PLANNING_ONLY",
        "controller_writer": "NONE",
        "materializes_repository": False,
        "external_write": False,
        "requires_human_authorization": True,
    },
    {
        "stage_id": "INT-08",
        "phase": "H3_CONTROLLED_CUTOVER",
        "file": "08-h3-controlled-single-writer-cutover.md",
        "predecessor": "INT-07",
        "execution_mode": "ATOMIC_CUTOVER",
        "controller_writer": "EXTERNAL_CONTROLLER",
        "materializes_repository": False,
        "external_write": True,
        "requires_human_authorization": True,
    },
    {
        "stage_id": "INT-09",
        "phase": "H3_CONTROLLED_CUTOVER",
        "file": "09-post-cutover-reconciliation-audit.md",
        "predecessor": "INT-08",
        "execution_mode": "POST_CUTOVER_READ_ONLY_AUDIT",
        "controller_writer": "EXTERNAL_CONTROLLER",
        "materializes_repository": False,
        "external_write": False,
        "requires_human_authorization": False,
    },
]
REQUIRED_SECTIONS = [
    "# Identity",
    "# Preconditions",
    "# Authority and context",
    "# Scope",
    "# Required workflow",
    "# Stop conditions",
    "# Validation",
    "# Required final result",
]
SUPPORT_FILES = {
    "README.md",
    "MASTER-ORCHESTRATION-PROMPT.md",
    "operator-input.template.json",
    "stage-manifest.json",
    "stage-result.example.json",
    "stage-result.schema.json",
}
EXPECTED_PACK_FILES = SUPPORT_FILES | {stage["file"] for stage in EXPECTED_STAGES}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_object(path: Path, errors: list[str]) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        errors.append(f"{path}: invalid JSON: {exc}")
        return {}
    if not isinstance(value, dict):
        errors.append(f"{path}: expected JSON object")
        return {}
    return value


def parse_frontmatter(path: Path, errors: list[str]) -> tuple[dict[str, Any], str]:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        errors.append(f"{path}: cannot read prompt: {exc}")
        return {}, ""
    lines = text.splitlines()
    if not lines or lines[0] != "---":
        errors.append(f"{path}: missing opening frontmatter delimiter")
        return {}, text
    try:
        end = lines.index("---", 1)
    except ValueError:
        errors.append(f"{path}: missing closing frontmatter delimiter")
        return {}, text
    frontmatter: dict[str, Any] = {}
    for line in lines[1:end]:
        if not line.strip():
            continue
        if ":" not in line:
            errors.append(f"{path}: malformed frontmatter line {line!r}")
            continue
        key, raw = line.split(":", 1)
        key = key.strip()
        raw = raw.strip()
        try:
            frontmatter[key] = json.loads(raw)
        except json.JSONDecodeError:
            frontmatter[key] = raw
    return frontmatter, "\n".join(lines[end + 1 :])


def validate_pack(root: Path = ROOT) -> list[str]:
    errors: list[str] = []
    pack = root / PACK_RELATIVE
    manifest = load_object(pack / "stage-manifest.json", errors)
    if manifest.get("format_version") != "1.0":
        errors.append("stage manifest format_version must be 1.0")
    if manifest.get("pack_id") != "AZPR_V10_1_STAGED_HYBRID_INTEGRATION":
        errors.append("stage manifest pack identity mismatch")
    if manifest.get("status") != "DRAFT_NOT_ACTIVE":
        errors.append("prompt-stage pack must remain DRAFT_NOT_ACTIVE")

    payload = manifest.get("selected_prompt_payload", {})
    if not isinstance(payload, dict) or payload != {
        "status": "SELECTED_NOT_ACTIVE",
        "sha256": "3b235cb7e33ca409241ff26523f60f8fee89cec524b3f09e91a69927a0aa4880",
        "numbered_prompts": 38,
        "appendices": 3,
    }:
        errors.append("selected prompt payload binding differs from 38 plus 3 inactive v10.1 bytes")

    execution = manifest.get("execution_policy", {})
    required_execution = {
        "one_stage_per_invocation": True,
        "automatic_stage_advancement": False,
        "human_approval_may_be_created_by_agent": False,
        "live_runtime_state_transfer_allowed": False,
        "concurrent_controller_writers_allowed": False,
    }
    if not isinstance(execution, dict) or execution != required_execution:
        errors.append("stage execution policy widened or drifted")

    authority = manifest.get("authority_effect", {})
    if not isinstance(authority, dict) or not authority or any(value is not False for value in authority.values()):
        errors.append("prompt-stage pack must grant no authority by its existence")

    stages = manifest.get("stages")
    if not isinstance(stages, list) or len(stages) != len(EXPECTED_STAGES):
        errors.append("stage manifest must contain exactly ten stages")
        stages = []
    for sequence, expected in enumerate(EXPECTED_STAGES):
        if sequence >= len(stages) or not isinstance(stages[sequence], dict):
            continue
        actual = stages[sequence]
        expected_file = (PACK_RELATIVE / expected["file"]).as_posix()
        checks = dict(expected)
        checks["sequence"] = sequence
        checks["file"] = expected_file
        for key, value in checks.items():
            if actual.get(key) != value:
                errors.append(f"{expected['stage_id']}: manifest {key} differs from fail-closed design")

        prompt_path = root / expected_file
        frontmatter, body = parse_frontmatter(prompt_path, errors)
        for key in ("stage_id", "sequence", "phase", "controller_writer", "execution_mode"):
            if frontmatter.get(key) != checks[key]:
                errors.append(f"{expected['stage_id']}: prompt frontmatter {key} differs from manifest")
        if frontmatter.get("prompt_status") != "DRAFT_NOT_ACTIVE":
            errors.append(f"{expected['stage_id']}: prompt must remain DRAFT_NOT_ACTIVE")
        for section in REQUIRED_SECTIONS:
            if section not in body:
                errors.append(f"{expected['stage_id']}: missing required section {section}")
        lowered = body.lower()
        if "do not create or modify a human approval file" not in lowered:
            errors.append(f"{expected['stage_id']}: human approval creation prohibition missing")
        if "return exactly one json object matching `stage-result.schema.json`" not in lowered:
            errors.append(f"{expected['stage_id']}: strict result-schema instruction missing")

    if [stage.get("stage_id") for stage in stages if isinstance(stage, dict)] != EXPECTED_STAGE_IDS:
        errors.append("stage sequence is not the exact INT-00 through INT-09 chain")

    master_path = pack / "MASTER-ORCHESTRATION-PROMPT.md"
    try:
        master = master_path.read_text(encoding="utf-8")
    except OSError as exc:
        errors.append(f"{master_path}: cannot read master prompt: {exc}")
        master = ""
    for phrase in (
        "routing-only coordinator",
        "You do not execute stages",
        "Never select more than one stage",
        "docs/audits/index.json",
        "docs/audits/README.md",
        "INT-04",
    ):
        if phrase not in master:
            errors.append(f"master prompt lacks routing safeguard: {phrase}")

    stage_zero = pack / "00-preflight-authority-and-inputs.md"
    stage_four = pack / "04-h1-repository-integration-audit.md"
    try:
        stage_zero_text = stage_zero.read_text(encoding="utf-8")
        stage_four_text = stage_four.read_text(encoding="utf-8")
    except OSError as exc:
        errors.append(f"cannot inspect audit bootstrap prompts: {exc}")
    else:
        for phrase in ("docs/audits/README.md", "named governance owner", "INT-04"):
            if phrase not in stage_zero_text:
                errors.append(f"INT-00 lacks interim audit-authority safeguard: {phrase}")
        for phrase in ("docs/audits/index.json", "write_audit_artifacts", "commit the report and index together"):
            if phrase not in stage_four_text:
                errors.append(f"INT-04 lacks first-audit bootstrap safeguard: {phrase}")

    operator = load_object(pack / "operator-input.template.json", errors)
    if operator.get("status") != "TEMPLATE_NOT_APPROVAL":
        errors.append("operator input must remain a non-approval template")
    governance = operator.get("governance", {})
    if not isinstance(governance, dict) or set(governance) != {
        "audit_index_owner",
        "audit_index_schema_reference",
        "audit_index_restoration_authorized",
    }:
        errors.append("operator input lacks the explicit audit-index governance decision")
    elif governance.get("audit_index_restoration_authorized") is not False:
        errors.append("operator input template must not pre-authorize audit-index restoration")
    serialized_operator = json.dumps(operator, sort_keys=True).lower()
    for forbidden in ("password", "private_key", "access_token", "secret_value"):
        if forbidden in serialized_operator:
            errors.append(f"operator input template contains forbidden secret field: {forbidden}")

    schema = load_object(pack / "stage-result.schema.json", errors)
    example = load_object(pack / "stage-result.example.json", errors)
    if schema:
        try:
            Draft202012Validator.check_schema(schema)
            validation_errors = sorted(
                Draft202012Validator(schema).iter_errors(example),
                key=lambda issue: list(issue.absolute_path),
            )
            for issue in validation_errors:
                location = ".".join(str(part) for part in issue.absolute_path) or "<root>"
                errors.append(f"stage result example {location}: {issue.message}")
        except Exception as exc:  # jsonschema exposes multiple schema exception types
            errors.append(f"stage result schema validation failed: {exc}")

    actual_files = {
        path.name
        for path in pack.iterdir()
        if path.is_file() and path.name != "SHA256SUMS.json"
    } if pack.is_dir() else set()
    if actual_files != EXPECTED_PACK_FILES:
        errors.append(
            f"prompt pack file set differs: missing={sorted(EXPECTED_PACK_FILES - actual_files)} "
            f"extra={sorted(actual_files - EXPECTED_PACK_FILES)}"
        )

    hashes = load_object(pack / "SHA256SUMS.json", errors)
    if hashes.get("format_version") != "1.0" or hashes.get("algorithm") != "sha256":
        errors.append("prompt pack hash manifest metadata invalid")
    recorded = hashes.get("files")
    if not isinstance(recorded, dict) or set(recorded) != EXPECTED_PACK_FILES:
        errors.append("prompt pack hash manifest file set differs")
        recorded = {}
    for filename in sorted(EXPECTED_PACK_FILES):
        path = pack / filename
        if not path.is_file():
            continue
        if recorded.get(filename) != sha256(path):
            errors.append(f"prompt pack byte hash mismatch: {filename}")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args()
    errors = validate_pack()
    result = {
        "pack_id": "AZPR_V10_1_STAGED_HYBRID_INTEGRATION",
        "status": "DRAFT_NOT_ACTIVE",
        "stage_count": len(EXPECTED_STAGES),
        "hashed_files": len(EXPECTED_PACK_FILES),
        "valid": not errors,
        "errors": errors,
    }
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
