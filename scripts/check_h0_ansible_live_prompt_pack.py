#!/usr/bin/env python3
"""Validate the inert AZPR H0 Ansible live-validation prompt pack."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator


ROOT = Path(__file__).resolve().parents[1]
PACK_RELATIVE = Path("automation/integration/v10.1/h0-ansible-live-stages")
EXPECTED_STAGES = [
    {
        "stage_id": "H0-ALV-00",
        "file": "00-authority-and-target-preflight.md",
        "predecessor": None,
        "execution_mode": "READ_ONLY_PREFLIGHT",
        "state_changing": False,
        "requires_human_authorization": True,
    },
    {
        "stage_id": "H0-ALV-01",
        "file": "01-check-mode-and-diff-review.md",
        "predecessor": "H0-ALV-00",
        "execution_mode": "ANSIBLE_CHECK_MODE",
        "state_changing": False,
        "requires_human_authorization": True,
    },
    {
        "stage_id": "H0-ALV-02",
        "file": "02-two-apply-idempotence.md",
        "predecessor": "H0-ALV-01",
        "execution_mode": "BOUNDED_ANSIBLE_APPLY",
        "state_changing": True,
        "requires_human_authorization": True,
    },
    {
        "stage_id": "H0-ALV-03",
        "file": "03-evidence-reconciliation.md",
        "predecessor": "H0-ALV-02",
        "execution_mode": "READ_ONLY_EVIDENCE_RECONCILIATION",
        "state_changing": False,
        "requires_human_authorization": False,
    },
]
EXPECTED_GUIDES = [
    {
        "guide_id": "H0-ALV-GUIDE-00",
        "file": "operator-assistance/00-repository-and-procedure-readiness.md",
        "execution_context": "REPOSITORY_HOST",
        "human_checkpoint": "PROCEDURE_APPROVAL_OR_LOCAL_GUEST_ENTRY",
    },
    {
        "guide_id": "H0-ALV-GUIDE-01",
        "file": "operator-assistance/01-guest-local-observation-and-target-decision.md",
        "execution_context": "DISPOSABLE_GUEST_LOCAL_SESSION",
        "human_checkpoint": "EXACT_TARGET_AUTHORIZATION_AND_OPERATOR_INPUT",
    },
    {
        "guide_id": "H0-ALV-GUIDE-02",
        "file": "operator-assistance/02-operator-input-validation-and-stage-handoff.md",
        "execution_context": "REPOSITORY_HOST",
        "human_checkpoint": "DELIBERATE_H0_ALV_00_INVOCATION",
    },
]
SUPPORT_FILES = {
    "README.md",
    "operator-assistance-result.schema.json",
    "operator-input.schema.json",
    "operator-input.template.json",
    "stage-manifest.json",
    "stage-result.example.json",
    "stage-result.schema.json",
    "target-fingerprint-contract.json",
    "target-fingerprint-test-vectors.json",
}
EXPECTED_FILES = (
    SUPPORT_FILES
    | {stage["file"] for stage in EXPECTED_STAGES}
    | {guide["file"] for guide in EXPECTED_GUIDES}
)
REQUIRED_SECTIONS = {
    "# Identity",
    "# Preconditions",
    "# Authority and context",
    "# Scope",
    "# Required workflow",
    "# Stop conditions",
    "# Validation",
    "# Required final result",
}
COMMON_SAFEGUARDS = {
    "do not use or activate the operator-approval adapter",
    "do not create or modify a human approval file",
    "do not modify `azpr-h0-transport-20260807-001`",
    "return exactly one json object matching `stage-result.schema.json`",
    "do not include prose outside the json object",
}
GUIDE_REQUIRED_SECTIONS = {
    "# Identity",
    "# Preconditions",
    "# Authority and context",
    "# Automated workflow",
    "# Human checkpoints",
    "# Stop conditions",
    "# Resume contract",
    "# Validation",
    "# Required final result",
}
GUIDE_COMMON_SAFEGUARDS = {
    "do not use or activate the operator-approval adapter",
    "do not create",
    "operator-assistance-result.schema.json",
    "do not include prose outside the json object",
}
GUIDE_SAFEGUARDS = {
    "H0-ALV-GUIDE-00": {
        "do not accept chat text as that record",
        "do not open, start, connect to, probe, or select a guest",
        "procedure_approval_reference_required",
        "local_guest_session_required",
    },
    "H0-ALV-GUIDE-01": {
        "exact_target_authorization_required",
        "do not create, populate, or modify a human approval",
        "the human must",
        "never run ansible",
        "matching fingerprint identifies the target but never authorizes it",
    },
    "H0-ALV-GUIDE-02": {
        "validate-operator-input",
        "authorization_attribution_confirmation_required",
        "h0_alv_00_invocation_required",
        "do not invoke it or prepare h0-alv-01",
        "the json's `authorized_by` string and `authorized=true` are not proof",
    },
}
STAGE_SAFEGUARDS = {
    "H0-ALV-00": {
        "`disposable_test`",
        "`human_approved_qualification`",
        "scripts/check_h0_ansible.py",
        "scripts/check_h0_ansible_live_prompt_pack.py",
        "ansible_connection=local",
        "scripts/h0_target_fingerprint.py observe",
        "a fingerprint identifies a target; it never authorizes one",
    },
    "H0-ALV-01": {
        "--check --diff",
        "do not run `qualification-prepare.yml` without `--check`",
        "human check-mode review record",
        "/srv/azpr-approved-inputs",
        "fingerprint identifies the target but does not authorize it",
    },
    "H0-ALV-02": {
        "infrastructure/ansible/tests/run_idempotence.py",
        "--environment-scope disposable_test",
        "--confirm apply h0 qualification preparation",
        "second apply to have exactly `changed=0`",
        "do not retry within this stage",
        "fingerprint identifies but does not authorize the target",
    },
    "H0-ALV-03": {
        "qualification_effect=false",
        "this does not complete h0 ansible preparation",
        "set `next_stage` to null",
        "do not copy guest evidence into the repository",
        "fingerprint identifies but does not authorize a target",
    },
}


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


def load_fingerprint_module(root: Path, errors: list[str]):
    path = root / "scripts" / "h0_target_fingerprint.py"
    if not path.is_file():
        errors.append("target-fingerprint implementation is missing")
        return None
    spec = importlib.util.spec_from_file_location("azpr_h0_target_fingerprint", path)
    if spec is None or spec.loader is None:
        errors.append("target-fingerprint implementation cannot be loaded")
        return None
    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
    except Exception as exc:
        errors.append(f"target-fingerprint implementation cannot be loaded: {exc}")
        return None
    return module


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
        try:
            frontmatter[key.strip()] = json.loads(raw.strip())
        except json.JSONDecodeError:
            frontmatter[key.strip()] = raw.strip()
    return frontmatter, "\n".join(lines[end + 1 :])


def validate_pack(root: Path = ROOT) -> list[str]:
    errors: list[str] = []
    pack = root / PACK_RELATIVE
    manifest = load_object(pack / "stage-manifest.json", errors)
    if set(manifest) != {
        "format_version",
        "pack_id",
        "status",
        "governing_contract",
        "parent_transition_contract",
        "operator_input_template",
        "operator_input_schema",
        "result_schema",
        "result_example",
        "hash_manifest",
        "target_fingerprint",
        "operator_assistance",
        "execution_policy",
        "authority_effect",
        "stages",
    }:
        errors.append("live prompt manifest fields drifted")
    if manifest.get("format_version") != "1.0":
        errors.append("live prompt manifest format_version must be 1.0")
    if manifest.get("pack_id") != "AZPR_H0_ANSIBLE_LIVE_VALIDATION":
        errors.append("live prompt pack identity mismatch")
    if manifest.get("status") != "DRAFT_NOT_ACTIVE":
        errors.append("live prompt pack must remain DRAFT_NOT_ACTIVE")
    if manifest.get("governing_contract") != "infrastructure/ansible/h0-qualification-contract.json":
        errors.append("live prompt pack governing contract drifted")
    if (
        manifest.get("parent_transition_contract")
        != "automation/integration/v10.1/controller-transition-contract.json"
    ):
        errors.append("live prompt pack transition-contract reference drifted")
    expected_support_references = {
        "operator_input_template": (
            "automation/integration/v10.1/h0-ansible-live-stages/"
            "operator-input.template.json"
        ),
        "operator_input_schema": (
            "automation/integration/v10.1/h0-ansible-live-stages/"
            "operator-input.schema.json"
        ),
        "result_schema": (
            "automation/integration/v10.1/h0-ansible-live-stages/"
            "stage-result.schema.json"
        ),
        "result_example": (
            "automation/integration/v10.1/h0-ansible-live-stages/"
            "stage-result.example.json"
        ),
        "hash_manifest": (
            "automation/integration/v10.1/h0-ansible-live-stages/"
            "SHA256SUMS.json"
        ),
    }
    for key, expected in expected_support_references.items():
        if manifest.get(key) != expected:
            errors.append(f"live prompt pack {key} reference drifted")

    expected_target_fingerprint = {
        "status": "PROPOSED_PENDING_HUMAN_APPROVAL",
        "contract": (
            "automation/integration/v10.1/h0-ansible-live-stages/"
            "target-fingerprint-contract.json"
        ),
        "implementation": "scripts/h0_target_fingerprint.py",
        "test_vectors": (
            "automation/integration/v10.1/h0-ansible-live-stages/"
            "target-fingerprint-test-vectors.json"
        ),
        "human_approval_required": True,
        "identifies_target": True,
        "authorizes_target": False,
    }
    if manifest.get("target_fingerprint") != expected_target_fingerprint:
        errors.append("live prompt target-fingerprint boundary widened or drifted")

    assistance = manifest.get("operator_assistance")
    expected_assistance = {
        "status": "DRAFT_NOT_ACTIVE",
        "result_schema": (
            "automation/integration/v10.1/h0-ansible-live-stages/"
            "operator-assistance-result.schema.json"
        ),
        "automatic_execution": False,
        "automatic_stage_advancement": False,
        "operator_input_may_be_created_by_agent": False,
        "human_authorization_may_be_created_or_inferred_by_agent": False,
        "guides": [
            {
                "sequence": sequence,
                "guide_id": guide["guide_id"],
                "file": (PACK_RELATIVE / guide["file"]).as_posix(),
                "execution_context": guide["execution_context"],
                "state_changing": False,
                "human_checkpoint": guide["human_checkpoint"],
            }
            for sequence, guide in enumerate(EXPECTED_GUIDES)
        ],
    }
    if assistance != expected_assistance:
        errors.append("operator-assistance manifest boundary widened or drifted")
    for sequence, guide in enumerate(EXPECTED_GUIDES):
        path = pack / guide["file"]
        frontmatter, body = parse_frontmatter(path, errors)
        expected_frontmatter = {
            "guide_id": guide["guide_id"],
            "sequence": sequence,
            "phase": "H0_PREPARATION",
            "prompt_status": "DRAFT_NOT_ACTIVE",
            "execution_context": guide["execution_context"],
            "state_changing": False,
        }
        if frontmatter != expected_frontmatter:
            errors.append(f"{guide['guide_id']}: guide frontmatter differs")
        for section in GUIDE_REQUIRED_SECTIONS:
            if section not in body:
                errors.append(f"{guide['guide_id']}: missing required section {section}")
        lowered = " ".join(body.lower().split())
        for phrase in GUIDE_COMMON_SAFEGUARDS | GUIDE_SAFEGUARDS[guide["guide_id"]]:
            if phrase not in lowered:
                errors.append(f"{guide['guide_id']}: missing safeguard {phrase!r}")

    execution = manifest.get("execution_policy")
    if execution != {
        "one_stage_per_invocation": True,
        "automatic_stage_advancement": False,
        "human_approval_may_be_created_by_agent": False,
        "exact_target_binding_required": True,
        "environment_scope": "DISPOSABLE_TEST",
    }:
        errors.append("live prompt execution policy widened or drifted")
    authority = manifest.get("authority_effect")
    expected_authority = {
        "authorizes_live_execution": False,
        "approves_environment": False,
        "qualifies_environment": False,
        "activates_operator_approval_adapter": False,
        "activates_controller": False,
        "executes_h0_t02": False,
        "executes_azpr_verifier": False,
        "authorizes_git": False,
    }
    if authority != expected_authority:
        errors.append("live prompt pack grants authority by its existence")

    stages = manifest.get("stages")
    if not isinstance(stages, list) or len(stages) != len(EXPECTED_STAGES):
        errors.append("live prompt manifest must contain exactly four stages")
        stages = []
    for sequence, expected in enumerate(EXPECTED_STAGES):
        if sequence >= len(stages) or not isinstance(stages[sequence], dict):
            continue
        actual = stages[sequence]
        expected_values = dict(expected)
        expected_values["sequence"] = sequence
        expected_values["file"] = (PACK_RELATIVE / expected["file"]).as_posix()
        if actual != expected_values:
            errors.append(f"{expected['stage_id']}: manifest stage contract differs")

        path = root / expected_values["file"]
        frontmatter, body = parse_frontmatter(path, errors)
        expected_frontmatter = {
            "stage_id": expected["stage_id"],
            "sequence": sequence,
            "phase": "H0_PREPARATION",
            "prompt_status": "DRAFT_NOT_ACTIVE",
            "execution_mode": expected["execution_mode"],
            "state_changing": expected["state_changing"],
        }
        if frontmatter != expected_frontmatter:
            errors.append(f"{expected['stage_id']}: prompt frontmatter differs")
        for section in REQUIRED_SECTIONS:
            if section not in body:
                errors.append(f"{expected['stage_id']}: missing required section {section}")
        lowered = " ".join(body.lower().split())
        for phrase in COMMON_SAFEGUARDS | STAGE_SAFEGUARDS[expected["stage_id"]]:
            if phrase not in lowered:
                errors.append(f"{expected['stage_id']}: missing safeguard {phrase!r}")

    expected_ids = [stage["stage_id"] for stage in EXPECTED_STAGES]
    actual_ids = [stage.get("stage_id") for stage in stages if isinstance(stage, dict)]
    if actual_ids != expected_ids:
        errors.append("live prompt stage sequence drifted")

    operator = load_object(pack / "operator-input.template.json", errors)
    if set(operator) != {
        "format_version",
        "record_kind",
        "status",
        "target",
        "authorization_reference",
        "check_mode_review",
        "operator_approval_adapter",
    }:
        errors.append("live operator input fields drifted")
    if operator.get("status") != "TEMPLATE_NOT_APPROVAL":
        errors.append("live operator input must remain a non-approval template")
    target = operator.get("target")
    if not isinstance(target, dict) or target.get("environment_scope") != "DISPOSABLE_TEST":
        errors.append("live operator input target scope drifted")
    elif target.get("disposable_target_confirmed") is not False:
        errors.append("live operator input pre-confirms target disposal")
    authorization = operator.get("authorization_reference")
    if not isinstance(authorization, dict) or authorization.get("authorized") is not False:
        errors.append("live operator input pre-authorizes execution")
    review = operator.get("check_mode_review")
    if not isinstance(review, dict) or review.get("accepted") is not False:
        errors.append("live operator input pre-accepts check mode")
    adapter = operator.get("operator_approval_adapter")
    if adapter != {"must_remain_inactive": True, "activation_authorized": False}:
        errors.append("live operator input permits operator-adapter activation")
    serialized_operator = json.dumps(operator, sort_keys=True).lower()
    for forbidden in ("password", "private_key", "access_token", "secret_value"):
        if forbidden in serialized_operator:
            errors.append(f"live operator input contains forbidden secret field: {forbidden}")

    fingerprint_module = load_fingerprint_module(root, errors)
    fingerprint_contract = load_object(pack / "target-fingerprint-contract.json", errors)
    fingerprint_vectors = load_object(pack / "target-fingerprint-test-vectors.json", errors)
    expected_field_order = [
        "target_id",
        "machine_id",
        "operating_system_id",
        "operating_system_version_id",
        "architecture",
        "reviewer_name",
        "reviewer_uid",
        "reviewer_gid",
        "reviewer_home",
    ]
    if fingerprint_contract.get("contract_id") != "AZPR_H0_TARGET_FINGERPRINT_V1":
        errors.append("target-fingerprint contract identity drifted")
    if fingerprint_contract.get("status") != "PROPOSED_PENDING_HUMAN_APPROVAL":
        errors.append("target-fingerprint contract fabricates or bypasses procedure approval")
    if fingerprint_contract.get("environment_scope") != "DISPOSABLE_TEST":
        errors.append("target-fingerprint contract permits a non-disposable scope")
    if fingerprint_contract.get("field_order") != expected_field_order:
        errors.append("target-fingerprint field order drifted")
    identity_fields = fingerprint_contract.get("identity_fields")
    if not isinstance(identity_fields, list) or [
        item.get("name") for item in identity_fields if isinstance(item, dict)
    ] != expected_field_order:
        errors.append("target-fingerprint approved identity fields drifted")
    fingerprint_authority = fingerprint_contract.get("authority_effect")
    if not isinstance(fingerprint_authority, dict):
        errors.append("target-fingerprint authority boundary is missing")
    elif fingerprint_authority.get("identifies_target") is not True or any(
        value is not False
        for key, value in fingerprint_authority.items()
        if key != "identifies_target"
    ):
        errors.append("target fingerprint grants authority beyond identification")
    canonical = fingerprint_contract.get("canonical_serialization", {})
    if canonical.get("member_order") != ["contract_id", *expected_field_order]:
        errors.append("target-fingerprint canonical member order drifted")
    if (
        canonical.get("encoding") != "UTF-8"
        or canonical.get("trailing_newline") is not False
        or canonical.get("byte_order_mark") is not False
        or fingerprint_contract.get("digest", {}).get("algorithm") != "sha256"
    ):
        errors.append("target-fingerprint canonical bytes or digest contract drifted")
    vectors = fingerprint_vectors.get("vectors")
    if not isinstance(vectors, list) or not vectors:
        errors.append("target-fingerprint golden vectors are missing")
    elif fingerprint_module is not None:
        for vector in vectors:
            if not isinstance(vector, dict):
                errors.append("target-fingerprint golden vector is not an object")
                continue
            try:
                normalized = fingerprint_module.normalize_identity(vector.get("input", {}))
                canonical_bytes = fingerprint_module.canonical_bytes(vector.get("input", {}))
                calculated = fingerprint_module.fingerprint(vector.get("input", {}))
            except Exception as exc:
                errors.append(f"target-fingerprint golden vector is invalid: {exc}")
                continue
            if normalized != vector.get("normalized_identity"):
                errors.append("target-fingerprint golden-vector normalization drifted")
            if canonical_bytes.decode("utf-8") != vector.get("canonical_json"):
                errors.append("target-fingerprint golden-vector canonical JSON drifted")
            if canonical_bytes.hex() != vector.get("canonical_utf8_hex"):
                errors.append("target-fingerprint golden-vector bytes drifted")
            if calculated != vector.get("sha256"):
                errors.append("target-fingerprint golden-vector SHA-256 drifted")

    operator_schema = load_object(pack / "operator-input.schema.json", errors)
    if operator_schema:
        try:
            Draft202012Validator.check_schema(operator_schema)
            format_checker = (
                fingerprint_module.operator_input_format_checker()
                if fingerprint_module is not None
                else None
            )
            for issue in sorted(
                Draft202012Validator(
                    operator_schema, format_checker=format_checker
                ).iter_errors(operator),
                key=lambda value: list(value.absolute_path),
            ):
                location = ".".join(str(part) for part in issue.absolute_path) or "<root>"
                errors.append(f"live operator input template {location}: {issue.message}")
        except Exception as exc:
            errors.append(f"live operator input schema validation failed: {exc}")
        adapter_schema = (
            operator_schema.get("properties", {})
            .get("operator_approval_adapter", {})
            .get("properties", {})
        )
        if adapter_schema != {
            "must_remain_inactive": {"const": True},
            "activation_authorized": {"const": False},
        }:
            errors.append("live operator input schema permits adapter activation")
        target_scope_schema = (
            operator_schema.get("properties", {})
            .get("target", {})
            .get("properties", {})
            .get("environment_scope")
        )
        if target_scope_schema != {"const": "DISPOSABLE_TEST"}:
            errors.append("live operator input schema permits a non-disposable target")

    schema = load_object(pack / "stage-result.schema.json", errors)
    example = load_object(pack / "stage-result.example.json", errors)
    if schema:
        try:
            Draft202012Validator.check_schema(schema)
            for issue in sorted(
                Draft202012Validator(schema).iter_errors(example),
                key=lambda value: list(value.absolute_path),
            ):
                location = ".".join(str(part) for part in issue.absolute_path) or "<root>"
                errors.append(f"live stage result example {location}: {issue.message}")
        except Exception as exc:
            errors.append(f"live stage result schema validation failed: {exc}")
        properties = schema.get("properties", {})
        safety_properties = properties.get("safety", {}).get("properties", {})
        required_false_safety = {
            "operator_approval_adapter_activated",
            "controller_activated",
            "h0_t02_executed",
            "host_transport_modified",
            "network_controls_modified",
            "approved_inputs_modified",
            "git_commit_merge_or_push",
        }
        if set(safety_properties) != required_false_safety or any(
            value != {"const": False} for value in safety_properties.values()
        ):
            errors.append("live result schema safety boundary widened")
        authority_properties = properties.get("authority", {}).get("properties", {})
        for field in ("operator_approval_adapter_active", "h0_transport_ticket_modified"):
            if authority_properties.get(field) != {"const": False}:
                errors.append(f"live result schema authority boundary widened: {field}")
        evidence_properties = properties.get("evidence", {}).get("properties", {})
        if evidence_properties.get("qualification_effect") != {"const": False}:
            errors.append("live result schema permits qualification effect")
        target_properties = properties.get("target", {}).get("properties", {})
        if target_properties.get("environment_scope") != {"const": "DISPOSABLE_TEST"}:
            errors.append("live result schema permits a non-disposable target")
        if target_properties.get("target_fingerprint_contract_sha256") != {
            "type": ["string", "null"],
            "pattern": "^[0-9a-f]{64}$",
        }:
            errors.append("live result schema omits the fingerprint-procedure binding")

    assistance_schema = load_object(pack / "operator-assistance-result.schema.json", errors)
    if assistance_schema:
        try:
            Draft202012Validator.check_schema(assistance_schema)
        except Exception as exc:
            errors.append(f"operator-assistance result schema validation failed: {exc}")
        assistance_properties = assistance_schema.get("properties", {})
        if assistance_properties.get("authority_effect") != {"const": False}:
            errors.append("operator-assistance result schema grants authority")
        outcome_values = assistance_properties.get("outcome", {}).get("enum")
        if outcome_values != ["HUMAN_ACTION_REQUIRED", "BLOCKED", "FAILED"]:
            errors.append("operator-assistance result schema permits unattended success")
        assistance_safety = assistance_properties.get("safety", {}).get("properties", {})
        variable_safety = {"live_target_observed"}
        if set(assistance_safety) - variable_safety != {
            "ansible_playbook_executed",
            "operator_input_created_or_modified_by_agent",
            "human_authorization_created_or_inferred_by_agent",
            "operator_approval_adapter_activated",
            "controller_activated",
            "h0_t02_executed",
            "host_transport_modified",
            "network_controls_modified",
            "protected_artifacts_modified",
            "git_commit_merge_or_push",
            "automatic_next_prompt_started",
        } or any(
            value != {"const": False}
            for key, value in assistance_safety.items()
            if key not in variable_safety
        ):
            errors.append("operator-assistance result schema safety boundary widened")

    actual_files = (
        {
            path.relative_to(pack).as_posix()
            for path in pack.rglob("*")
            if path.is_file() and path.name != "SHA256SUMS.json"
        }
        if pack.is_dir()
        else set()
    )
    if actual_files != EXPECTED_FILES:
        errors.append(
            f"live prompt file set differs: missing={sorted(EXPECTED_FILES - actual_files)} "
            f"extra={sorted(actual_files - EXPECTED_FILES)}"
        )

    hashes = load_object(pack / "SHA256SUMS.json", errors)
    if hashes.get("format_version") != "1.0" or hashes.get("algorithm") != "sha256":
        errors.append("live prompt hash manifest metadata invalid")
    recorded = hashes.get("files")
    if not isinstance(recorded, dict) or set(recorded) != EXPECTED_FILES:
        errors.append("live prompt hash manifest file set differs")
        recorded = {}
    for filename in sorted(EXPECTED_FILES):
        path = pack / filename
        if path.is_file() and recorded.get(filename) != sha256(path):
            errors.append(f"live prompt byte hash mismatch: {filename}")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args()
    errors = validate_pack()
    result = {
        "pack_id": "AZPR_H0_ANSIBLE_LIVE_VALIDATION",
        "status": "DRAFT_NOT_ACTIVE",
        "stage_count": len(EXPECTED_STAGES),
        "hashed_files": len(EXPECTED_FILES),
        "valid": not errors,
        "errors": errors,
    }
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
