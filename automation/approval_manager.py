#!/usr/bin/env python3
"""Deterministic, fail-closed approval checkpoints for AZPR controller stages.

The manager creates reviewable tickets from committed stage manifests.  It does
not authenticate humans or execute actions.  A trusted controller must supply
an authentication verifier at the execution boundary.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Mapping


CANONICALIZATION = "AZPR_CANONICAL_JSON_V1"
APPROVAL_ID = re.compile(
    r"^AZPR-(?P<lifecycle>[A-Z0-9]+)-(?P<scope>[A-Z0-9]+)-"
    r"(?P<date>[0-9]{8})-(?P<sequence>[0-9]{3})$"
)
REVISION = re.compile(r"^R(?P<sequence>[0-9]{2})$")
RUN_ID = re.compile(r"^AZPR-RUN-(?P<lifecycle>[A-Z0-9]+)-(?P<date>[0-9]{8})-(?P<sequence>[0-9]{4})$")
OUTCOME_ID = re.compile(r"^AZPR-OUT-(?P<lifecycle>[A-Z0-9]+)-(?P<date>[0-9]{8})-(?P<sequence>[0-9]{4})$")
EVIDENCE_ID = re.compile(r"^AZPR-EVD-(?P<lifecycle>[A-Z0-9]+)-(?P<date>[0-9]{8})-(?P<sequence>[0-9]{4})$")

MANIFEST_FIELDS = {
    "format_version",
    "manifest_kind",
    "approval_id",
    "revision",
    "stage_id",
    "title",
    "lifecycle",
    "scope",
    "issued_on",
    "validity",
    "actions",
    "security_boundary",
    "authentication_policy",
    "evidence",
    "related_records",
    "notes",
}
ACTION_FIELDS = {
    "action_id",
    "kind",
    "target",
    "permission",
    "expected_effect",
    "test",
    "stop_condition",
}
DECISION_FIELDS = {
    "format_version",
    "record_kind",
    "approval_id",
    "ticket_id",
    "ticket_sha256",
    "decision",
    "decided_at",
    "expires_at",
    "authenticated_actor",
    "authentication_binding",
}
MATERIAL_AUTHORITY_FIELDS = (
    "stage_id",
    "lifecycle",
    "scope",
    "validity",
    "actions",
    "security_boundary",
    "authentication_policy",
)


class ApprovalError(RuntimeError):
    """The approval checkpoint cannot safely continue."""


@dataclass(frozen=True)
class VerifiedAuthentication:
    """Result returned by a trusted controller authentication adapter."""

    subject: str
    role: str
    authenticator_id: str
    authentication_event_id: str
    authenticated_at: str
    ticket_digest_challenge: str


AuthenticationVerifier = Callable[[Mapping[str, Any]], VerifiedAuthentication]


def _reject_noncanonical_types(value: Any, location: str = "$") -> None:
    if value is None or isinstance(value, (str, bool, int)):
        return
    if isinstance(value, float):
        raise ApprovalError(f"{location}: floating-point values are forbidden in canonical records")
    if isinstance(value, list):
        for index, item in enumerate(value):
            _reject_noncanonical_types(item, f"{location}[{index}]")
        return
    if isinstance(value, dict):
        for key, item in value.items():
            if not isinstance(key, str):
                raise ApprovalError(f"{location}: canonical object keys must be strings")
            _reject_noncanonical_types(item, f"{location}.{key}")
        return
    raise ApprovalError(f"{location}: unsupported canonical value type {type(value).__name__}")


def canonical_bytes(value: Any) -> bytes:
    """Return deterministic UTF-8 JSON bytes for AZPR controller records."""

    _reject_noncanonical_types(value)
    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def digest_value(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def digest_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_object(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ApprovalError(f"required record does not exist: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ApprovalError(f"invalid JSON in {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ApprovalError(f"expected a JSON object in {path}")
    return value


def load_canonical_object(path: Path) -> dict[str, Any]:
    value = load_object(path)
    if path.read_bytes() != canonical_bytes(value):
        raise ApprovalError(f"record is not canonically serialized or changed after generation: {path}")
    return value


def write_canonical(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_bytes(canonical_bytes(dict(value)))
    temporary.replace(path)


def parse_utc(value: str, field: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (ValueError, AttributeError) as exc:
        raise ApprovalError(f"{field} must be an ISO-8601 timestamp") from exc
    if parsed.utcoffset() is None:
        raise ApprovalError(f"{field} must include a UTC offset")
    return parsed.astimezone(timezone.utc)


def _nonempty_string(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ApprovalError(f"{field} must be a non-empty string")
    return value


def _strict_fields(value: Mapping[str, Any], expected: set[str], field: str) -> None:
    actual = set(value)
    missing = sorted(expected - actual)
    extra = sorted(actual - expected)
    if missing or extra:
        raise ApprovalError(f"{field} field mismatch; missing={missing}, extra={extra}")


def _safe_repo_path(root: Path, value: str, field: str) -> Path:
    candidate = Path(value)
    if candidate.is_absolute() or ".." in candidate.parts:
        raise ApprovalError(f"{field} must be a repository-relative path")
    resolved = (root / candidate).resolve()
    try:
        resolved.relative_to(root.resolve())
    except ValueError as exc:
        raise ApprovalError(f"{field} escapes the repository") from exc
    return resolved


def ticket_id(approval_id: str, revision: str | None) -> str:
    return approval_id if revision is None else f"{approval_id}-{revision}"


def validate_manifest(root: Path, manifest: Mapping[str, Any]) -> None:
    _strict_fields(manifest, MANIFEST_FIELDS, "manifest")
    if manifest["format_version"] != "1.0":
        raise ApprovalError("manifest.format_version must be '1.0'")
    if manifest["manifest_kind"] != "AZPR_STAGE_APPROVAL_MANIFEST":
        raise ApprovalError("manifest.manifest_kind is invalid")

    approval_match = APPROVAL_ID.fullmatch(_nonempty_string(manifest["approval_id"], "approval_id"))
    if approval_match is None:
        raise ApprovalError("approval_id must match AZPR-<LIFECYCLE>-<SCOPE>-<YYYYMMDD>-<NNN>")
    if manifest["lifecycle"] != approval_match.group("lifecycle"):
        raise ApprovalError("manifest.lifecycle does not match approval_id")
    if manifest["scope"] != approval_match.group("scope"):
        raise ApprovalError("manifest.scope does not match approval_id")
    if manifest["issued_on"].replace("-", "") != approval_match.group("date"):
        raise ApprovalError("manifest.issued_on does not match approval_id date")

    revision = manifest["revision"]
    if revision is not None and (not isinstance(revision, str) or REVISION.fullmatch(revision) is None):
        raise ApprovalError("manifest.revision must be null or RNN")
    _nonempty_string(manifest["stage_id"], "stage_id")
    _nonempty_string(manifest["title"], "title")

    validity = manifest["validity"]
    if not isinstance(validity, dict):
        raise ApprovalError("manifest.validity must be an object")
    _strict_fields(validity, {"activation_event", "maximum_duration_seconds", "expiry_rule"}, "validity")
    _nonempty_string(validity["activation_event"], "validity.activation_event")
    if not isinstance(validity["maximum_duration_seconds"], int) or isinstance(validity["maximum_duration_seconds"], bool) or validity["maximum_duration_seconds"] <= 0:
        raise ApprovalError("validity.maximum_duration_seconds must be a positive integer")
    _nonempty_string(validity["expiry_rule"], "validity.expiry_rule")

    actions = manifest["actions"]
    if not isinstance(actions, list) or not actions:
        raise ApprovalError("manifest.actions must contain at least one action")
    seen_actions: set[str] = set()
    for index, action in enumerate(actions):
        if not isinstance(action, dict):
            raise ApprovalError(f"actions[{index}] must be an object")
        _strict_fields(action, ACTION_FIELDS, f"actions[{index}]")
        action_id = _nonempty_string(action["action_id"], f"actions[{index}].action_id")
        if action_id in seen_actions:
            raise ApprovalError(f"duplicate action_id: {action_id}")
        seen_actions.add(action_id)
        for field in ("kind", "permission", "expected_effect", "stop_condition"):
            _nonempty_string(action[field], f"actions[{index}].{field}")
        target = action["target"]
        if not isinstance(target, dict) or not target:
            raise ApprovalError(f"actions[{index}].target must be a non-empty object")
        test = action["test"]
        if not isinstance(test, dict):
            raise ApprovalError(f"actions[{index}].test must be an object")
        _strict_fields(test, {"method", "expected_result"}, f"actions[{index}].test")
        _nonempty_string(test["method"], f"actions[{index}].test.method")
        _nonempty_string(test["expected_result"], f"actions[{index}].test.expected_result")

    boundary = manifest["security_boundary"]
    if not isinstance(boundary, dict):
        raise ApprovalError("manifest.security_boundary must be an object")
    _strict_fields(boundary, {"prohibited_changes", "rollback_required"}, "security_boundary")
    if boundary["rollback_required"] is not True:
        raise ApprovalError("security_boundary.rollback_required must be true")
    if not isinstance(boundary["prohibited_changes"], list) or not boundary["prohibited_changes"]:
        raise ApprovalError("security_boundary.prohibited_changes must not be empty")
    for index, value in enumerate(boundary["prohibited_changes"]):
        _nonempty_string(value, f"security_boundary.prohibited_changes[{index}]")

    auth = manifest["authentication_policy"]
    if not isinstance(auth, dict):
        raise ApprovalError("manifest.authentication_policy must be an object")
    _strict_fields(auth, {"authenticated_decision_required", "adapter", "allowed_roles", "digest_challenge_required"}, "authentication_policy")
    if auth["authenticated_decision_required"] is not True or auth["digest_challenge_required"] is not True:
        raise ApprovalError("authentication policy must require authentication and the ticket digest challenge")
    if auth["adapter"] != "TRUSTED_CONTROLLER_ADAPTER_REQUIRED":
        raise ApprovalError("authentication policy must fail closed on the trusted-controller adapter boundary")
    if not isinstance(auth["allowed_roles"], list) or not auth["allowed_roles"]:
        raise ApprovalError("authentication_policy.allowed_roles must not be empty")
    for index, value in enumerate(auth["allowed_roles"]):
        _nonempty_string(value, f"authentication_policy.allowed_roles[{index}]")

    evidence = manifest["evidence"]
    if not isinstance(evidence, list) or not evidence:
        raise ApprovalError("manifest.evidence must not be empty")
    for index, item in enumerate(evidence):
        if not isinstance(item, dict):
            raise ApprovalError(f"evidence[{index}] must be an object")
        _strict_fields(item, {"path", "sha256", "purpose"}, f"evidence[{index}]")
        evidence_path = _safe_repo_path(root, _nonempty_string(item["path"], f"evidence[{index}].path"), f"evidence[{index}].path")
        expected_digest = _nonempty_string(item["sha256"], f"evidence[{index}].sha256")
        if not re.fullmatch(r"[0-9a-f]{64}", expected_digest):
            raise ApprovalError(f"evidence[{index}].sha256 is invalid")
        if not evidence_path.is_file():
            raise ApprovalError(f"required evidence is missing: {item['path']}")
        if digest_file(evidence_path) != expected_digest:
            raise ApprovalError(f"required evidence digest changed: {item['path']}")
        _nonempty_string(item["purpose"], f"evidence[{index}].purpose")

    if not isinstance(manifest["related_records"], list) or not all(isinstance(value, str) and value for value in manifest["related_records"]):
        raise ApprovalError("manifest.related_records must be an array of non-empty strings")
    if not isinstance(manifest["notes"], list) or not all(isinstance(value, str) and value for value in manifest["notes"]):
        raise ApprovalError("manifest.notes must be an array of non-empty strings")


def build_ticket(root: Path, manifest_path: Path) -> dict[str, Any]:
    manifest = load_object(manifest_path)
    validate_manifest(root, manifest)
    try:
        relative_manifest = manifest_path.resolve().relative_to(root.resolve())
    except ValueError as exc:
        raise ApprovalError("stage manifest must be version-controlled inside the repository") from exc
    ticket = dict(manifest)
    ticket.pop("manifest_kind")
    ticket["record_kind"] = "AZPR_APPROVAL_TICKET"
    ticket["ticket_id"] = ticket_id(str(manifest["approval_id"]), manifest["revision"])
    ticket["canonicalization"] = CANONICALIZATION
    ticket["manifest_binding"] = {
        "path": relative_manifest.as_posix(),
        "sha256": digest_file(manifest_path),
    }
    return ticket


def render_review(ticket: Mapping[str, Any], ticket_sha256: str) -> str:
    actions = ticket["actions"]
    lines = [
        f"# Immutable Approval Review - {ticket['ticket_id']}",
        "",
        f"- Approval ID: `{ticket['approval_id']}`",
        f"- Stage: `{ticket['stage_id']}`",
        f"- Ticket SHA-256: `{ticket_sha256}`",
        f"- Canonicalization: `{CANONICALIZATION}`",
        f"- Maximum authority window: `{ticket['validity']['maximum_duration_seconds']}` seconds after activation",
        "",
        "Any byte change to the manifest, ticket, evidence bindings, or this review view invalidates this checkpoint. Approval does not imply successful execution.",
        "",
        "## Actions",
        "",
    ]
    for action in actions:
        lines.extend(
            [
                f"### {action['action_id']} - {action['kind']}",
                "",
                f"- Target: `{json.dumps(action['target'], sort_keys=True, separators=(',', ':'))}`",
                f"- Permission: {action['permission']}",
                f"- Expected effect: {action['expected_effect']}",
                f"- Test: {action['test']['method']} -> {action['test']['expected_result']}",
                f"- Stop condition: {action['stop_condition']}",
                "",
            ]
        )
    lines.extend(
        [
            "## Canonical ticket",
            "",
            "```json",
            canonical_bytes(dict(ticket)).decode("utf-8"),
            "```",
            "",
        ]
    )
    return "\n".join(lines)


def generate_ticket_artifacts(
    root: Path,
    manifest_path: Path,
    ticket_path: Path,
    review_path: Path,
) -> str:
    ticket = build_ticket(root, manifest_path)
    ticket_sha256 = digest_value(ticket)
    write_canonical(ticket_path, ticket)
    review_path.parent.mkdir(parents=True, exist_ok=True)
    review_path.write_text(render_review(ticket, ticket_sha256), encoding="utf-8")
    return ticket_sha256


def validate_ticket_artifacts(
    root: Path,
    manifest_path: Path,
    ticket_path: Path,
    review_path: Path,
) -> str:
    expected = build_ticket(root, manifest_path)
    actual = load_canonical_object(ticket_path)
    if actual != expected:
        raise ApprovalError("ticket no longer matches its version-controlled stage manifest")
    ticket_sha256 = digest_value(actual)
    expected_review = render_review(actual, ticket_sha256)
    try:
        actual_review = review_path.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise ApprovalError(f"immutable review view is missing: {review_path}") from exc
    if actual_review != expected_review:
        raise ApprovalError("immutable review view changed or does not match the ticket digest")
    return ticket_sha256


def bind_authenticated_decision(
    ticket: Mapping[str, Any],
    authentication: VerifiedAuthentication,
    *,
    decision: str,
    decided_at: str,
    expires_at: str,
) -> dict[str, Any]:
    ticket_sha256 = digest_value(ticket)
    if decision not in {"APPROVED", "REJECTED"}:
        raise ApprovalError("decision must be APPROVED or REJECTED")
    for field in (
        "subject",
        "role",
        "authenticator_id",
        "authentication_event_id",
        "authenticated_at",
        "ticket_digest_challenge",
    ):
        _nonempty_string(getattr(authentication, field), f"authentication.{field}")
    if authentication.ticket_digest_challenge != ticket_sha256:
        raise ApprovalError("authenticated decision was not challenged with the current ticket digest")
    if authentication.role not in ticket["authentication_policy"]["allowed_roles"]:
        raise ApprovalError("authenticated actor role is not authorized for this ticket")
    authenticated_at = parse_utc(authentication.authenticated_at, "authenticated_at")
    decided = parse_utc(decided_at, "decided_at")
    expires = parse_utc(expires_at, "expires_at")
    if authenticated_at > decided:
        raise ApprovalError("decision precedes the authentication event")
    maximum = timedelta(seconds=ticket["validity"]["maximum_duration_seconds"])
    if expires <= decided or expires > decided + maximum:
        raise ApprovalError("decision expiration exceeds the manifest authority window")
    return {
        "format_version": "1.0",
        "record_kind": "AZPR_APPROVAL_DECISION",
        "approval_id": ticket["approval_id"],
        "ticket_id": ticket["ticket_id"],
        "ticket_sha256": ticket_sha256,
        "decision": decision,
        "decided_at": decided_at,
        "expires_at": expires_at,
        "authenticated_actor": {
            "subject": authentication.subject,
            "role": authentication.role,
        },
        "authentication_binding": {
            "authenticator_id": authentication.authenticator_id,
            "authentication_event_id": authentication.authentication_event_id,
            "authenticated_at": authentication.authenticated_at,
            "ticket_digest_challenge": authentication.ticket_digest_challenge,
        },
    }


def authorize_execution(
    *,
    root: Path,
    manifest_path: Path,
    ticket_path: Path,
    review_path: Path,
    decision_path: Path,
    observed_targets: Mapping[str, Any],
    authentication_verifier: AuthenticationVerifier,
    now: str,
) -> dict[str, Any]:
    ticket_sha256 = validate_ticket_artifacts(root, manifest_path, ticket_path, review_path)
    ticket = load_canonical_object(ticket_path)
    decision = load_canonical_object(decision_path)
    _strict_fields(decision, DECISION_FIELDS, "decision")
    if decision.get("record_kind") != "AZPR_APPROVAL_DECISION" or decision.get("decision") != "APPROVED":
        raise ApprovalError("execution requires a canonical APPROVED decision record")
    if decision.get("approval_id") != ticket["approval_id"] or decision.get("ticket_id") != ticket["ticket_id"]:
        raise ApprovalError("decision targets a different approval ticket")
    if decision.get("ticket_sha256") != ticket_sha256:
        raise ApprovalError("ticket changed after the decision was made")
    current_time = parse_utc(now, "now")
    if current_time < parse_utc(decision["decided_at"], "decided_at"):
        raise ApprovalError("decision is not yet effective")
    if current_time >= parse_utc(decision["expires_at"], "expires_at"):
        raise ApprovalError("approval decision expired")

    verified = authentication_verifier(decision)
    if not isinstance(verified, VerifiedAuthentication):
        raise ApprovalError("trusted authentication verifier returned an invalid result")
    binding = decision.get("authentication_binding", {})
    actor = decision.get("authenticated_actor", {})
    if not isinstance(binding, dict) or not isinstance(actor, dict):
        raise ApprovalError("decision authentication fields are invalid")
    _strict_fields(
        binding,
        {"authenticator_id", "authentication_event_id", "authenticated_at", "ticket_digest_challenge"},
        "decision.authentication_binding",
    )
    _strict_fields(actor, {"subject", "role"}, "decision.authenticated_actor")
    expected_authentication = {
        "authenticator_id": verified.authenticator_id,
        "authentication_event_id": verified.authentication_event_id,
        "authenticated_at": verified.authenticated_at,
        "ticket_digest_challenge": verified.ticket_digest_challenge,
    }
    if binding != expected_authentication:
        raise ApprovalError("decision authentication binding could not be reverified")
    if actor != {"subject": verified.subject, "role": verified.role}:
        raise ApprovalError("decision actor does not match the verified authentication result")
    if verified.ticket_digest_challenge != ticket_sha256:
        raise ApprovalError("authentication challenge does not bind the current ticket digest")
    if verified.role not in ticket["authentication_policy"]["allowed_roles"]:
        raise ApprovalError("verified actor role is no longer authorized")

    expected_targets = {action["action_id"]: action["target"] for action in ticket["actions"]}
    if dict(observed_targets) != expected_targets:
        raise ApprovalError("execution targets no longer exactly match the approved ticket")
    return {
        "format_version": "1.0",
        "record_kind": "AZPR_EXECUTION_AUTHORIZATION",
        "approval_id": ticket["approval_id"],
        "ticket_id": ticket["ticket_id"],
        "ticket_sha256": ticket_sha256,
        "stage_id": ticket["stage_id"],
        "authorized_at": now,
        "expires_at": decision["expires_at"],
        "action_ids": [action["action_id"] for action in ticket["actions"]],
    }


def _related_execution_ids(run_id: str, outcome_id: str, evidence_id: str, lifecycle: str) -> None:
    run = RUN_ID.fullmatch(run_id)
    outcome = OUTCOME_ID.fullmatch(outcome_id)
    evidence = EVIDENCE_ID.fullmatch(evidence_id)
    if run is None or outcome is None or evidence is None:
        raise ApprovalError("run, outcome, and evidence IDs do not match the governed AZPR formats")
    values = (run, outcome, evidence)
    if any(value.group("lifecycle") != lifecycle for value in values):
        raise ApprovalError("related execution IDs do not match the approval lifecycle")
    if len({value.group("date") for value in values}) != 1 or len({value.group("sequence") for value in values}) != 1:
        raise ApprovalError("run, outcome, and evidence records must share date and sequence")


def create_outcome_record(
    authorization: Mapping[str, Any],
    *,
    lifecycle: str,
    run_id: str,
    outcome_id: str,
    evidence_id: str,
    outcome: str,
    completed_at: str,
    action_results: list[dict[str, Any]],
    evidence_bindings: list[dict[str, str]],
) -> dict[str, Any]:
    if authorization.get("record_kind") != "AZPR_EXECUTION_AUTHORIZATION":
        raise ApprovalError("an execution authorization is required before recording an outcome")
    _related_execution_ids(run_id, outcome_id, evidence_id, lifecycle)
    if outcome not in {"SUCCEEDED", "FAILED", "STOPPED", "ROLLED_BACK"}:
        raise ApprovalError("invalid execution outcome")
    parse_utc(completed_at, "completed_at")
    if not action_results:
        raise ApprovalError("outcome requires per-action results")
    if not evidence_bindings:
        raise ApprovalError("outcome requires a separate evidence bundle binding")
    return {
        "format_version": "1.0",
        "record_kind": "AZPR_EXECUTION_OUTCOME",
        "approval_id": authorization["approval_id"],
        "ticket_id": authorization["ticket_id"],
        "ticket_sha256": authorization["ticket_sha256"],
        "run_id": run_id,
        "outcome_id": outcome_id,
        "evidence_id": evidence_id,
        "outcome": outcome,
        "completed_at": completed_at,
        "action_results": action_results,
        "evidence_bindings": evidence_bindings,
        "approval_is_execution_result": False,
    }


def authority_fingerprint(ticket: Mapping[str, Any]) -> str:
    return digest_value({field: ticket[field] for field in MATERIAL_AUTHORITY_FIELDS})


def assess_revision(previous_ticket: Mapping[str, Any], candidate_ticket: Mapping[str, Any]) -> str:
    same_authority = authority_fingerprint(previous_ticket) == authority_fingerprint(candidate_ticket)
    same_approval = previous_ticket["approval_id"] == candidate_ticket["approval_id"]
    if same_approval and not same_authority:
        raise ApprovalError("material target, permission, security, validity, or action change requires a new approval ID")
    if not same_approval:
        return "NEW_APPROVAL_ID"
    previous_revision = previous_ticket.get("revision")
    candidate_revision = candidate_ticket.get("revision")
    previous_sequence = 0 if previous_revision is None else int(previous_revision[1:])
    if candidate_revision is None or int(candidate_revision[1:]) != previous_sequence + 1:
        raise ApprovalError("simple revisions must preserve the approval ID and increment the RNN suffix")
    return "SIMPLE_REVISION"


def remediation_exceeds_authority(ticket: Mapping[str, Any], remediation_actions: list[Mapping[str, Any]]) -> bool:
    approved = {action["action_id"]: action for action in ticket["actions"]}
    for action in remediation_actions:
        action_id = action.get("action_id")
        if action_id not in approved or dict(action) != approved[action_id]:
            return True
    return False


def build_delta_ticket(
    root: Path,
    original_ticket: Mapping[str, Any],
    delta_manifest_path: Path,
) -> dict[str, Any]:
    """Build a new-ID ticket only when remediation exceeds prior authority."""

    candidate = build_ticket(root, delta_manifest_path)
    if candidate["approval_id"] == original_ticket["approval_id"]:
        raise ApprovalError("out-of-scope remediation requires a new approval ID, not a revision")
    if not remediation_exceeds_authority(original_ticket, candidate["actions"]):
        raise ApprovalError("remediation is within original authority; a delta ticket must not be generated")
    if original_ticket["approval_id"] not in candidate["related_records"]:
        raise ApprovalError("delta ticket must refer to the original immutable approval ID")
    return candidate


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="AZPR deterministic approval-ticket manager")
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("generate", "check"):
        command = sub.add_parser(name)
        command.add_argument("--manifest", required=True)
        command.add_argument("--ticket", required=True)
        command.add_argument("--review", required=True)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    try:
        manifest = _safe_repo_path(root, args.manifest, "manifest")
        ticket = _safe_repo_path(root, args.ticket, "ticket")
        review = _safe_repo_path(root, args.review, "review")
        if args.command == "generate":
            digest = generate_ticket_artifacts(root, manifest, ticket, review)
        else:
            digest = validate_ticket_artifacts(root, manifest, ticket, review)
        print(json.dumps({"approval_ticket": str(ticket.relative_to(root)), "ticket_sha256": digest, "result": "PASS"}, sort_keys=True))
        return 0
    except (ApprovalError, OSError) as exc:
        print(f"APPROVAL CHECKPOINT STOPPED: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
