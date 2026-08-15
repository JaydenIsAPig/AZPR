#!/usr/bin/env python3
"""Repository-governed approval records for non-executing procedures.

This module is deliberately narrower than ``approval_manager``.  It can prove
that a human-attributed repository decision binds an exact procedure-review
request and exact procedure bytes.  It cannot authorize a target or action,
activate an adapter/controller, or create an approval record.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[1]
CANONICALIZATION = "AZPR_CANONICAL_JSON_V1"
REQUEST_PATH = Path(
    "automation/approvals/procedure-requests/"
    "AZPR-H0-FINGERPRINT-PROCEDURE-20260814-001.json"
)
REVIEW_PATH = Path(
    "automation/approvals/procedure-reviews/"
    "AZPR-H0-FINGERPRINT-PROCEDURE-20260814-001.md"
)
DECISION_PATH = Path(
    "automation/approvals/procedure-decisions/"
    "AZPR_H0_TARGET_FINGERPRINT_V1.json"
)
PROCEDURE_PATH = Path(
    "automation/integration/v10.1/h0-ansible-live-stages/"
    "target-fingerprint-contract.json"
)
PROCEDURE_ID = "AZPR_H0_TARGET_FINGERPRINT_V1"
REQUEST_ID = "AZPR-H0-FINGERPRINT-PROCEDURE-20260814-001"
APPROVAL_ID_PATTERN = re.compile(
    r"^AZPR-H0-FINGERPRINTPROC-(?P<date>[0-9]{8})-(?P<sequence>[0-9]{3})$"
)
SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
COMMIT_PATTERN = re.compile(r"^[0-9a-f]{40,64}$")
DECISION_FIELDS = {
    "format_version",
    "record_kind",
    "approval_id",
    "request_id",
    "request_sha256",
    "procedure_id",
    "procedure_path",
    "procedure_sha256",
    "decision",
    "decided_at",
    "decided_by",
    "acknowledgements",
}
ACKNOWLEDGEMENT_FIELDS = {
    "reviewed_exact_procedure_bytes",
    "procedure_identifies_but_does_not_authorize_target",
    "no_target_approved",
    "no_execution_authorized",
    "no_adapter_or_controller_activation_authorized",
    "no_h0_stage_advanced",
}


class ProcedureApprovalError(RuntimeError):
    """The procedure-approval channel cannot safely accept the record."""


@dataclass(frozen=True)
class ProcedureApprovalStatus:
    approved: bool
    status: str
    approval_id: str | None = None
    approval_reference: str | None = None
    procedure_sha256: str | None = None
    decided_by: str | None = None
    decided_role: str | None = None


def _canonical_types(value: Any, location: str = "$") -> None:
    if value is None or isinstance(value, (str, bool, int)):
        return
    if isinstance(value, float):
        raise ProcedureApprovalError(f"{location}: floating-point values are forbidden")
    if isinstance(value, list):
        for index, item in enumerate(value):
            _canonical_types(item, f"{location}[{index}]")
        return
    if isinstance(value, dict):
        for key, item in value.items():
            if not isinstance(key, str):
                raise ProcedureApprovalError(f"{location}: object keys must be strings")
            _canonical_types(item, f"{location}.{key}")
        return
    raise ProcedureApprovalError(f"{location}: unsupported value type")


def canonical_bytes(value: Any) -> bytes:
    _canonical_types(value)
    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    try:
        return sha256_bytes(path.read_bytes())
    except OSError as exc:
        raise ProcedureApprovalError(f"required file is unavailable: {path}") from exc


def _load_object(path: Path, *, canonical: bool = False) -> dict[str, Any]:
    try:
        raw = path.read_bytes()
        value = json.loads(raw.decode("utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ProcedureApprovalError(f"invalid JSON object: {path}") from exc
    if not isinstance(value, dict):
        raise ProcedureApprovalError(f"expected a JSON object: {path}")
    if canonical and raw != canonical_bytes(value):
        raise ProcedureApprovalError(f"record is not canonically serialized: {path}")
    return value


def _strict_fields(value: Mapping[str, Any], expected: set[str], field: str) -> None:
    missing = sorted(expected - set(value))
    extra = sorted(set(value) - expected)
    if missing or extra:
        raise ProcedureApprovalError(
            f"{field} field mismatch; missing={missing}, extra={extra}"
        )


def _nonempty(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ProcedureApprovalError(f"{field} must be a non-empty string")
    return value


def _utc(value: Any, field: str) -> datetime:
    if not isinstance(value, str):
        raise ProcedureApprovalError(f"{field} must be an ISO-8601 timestamp")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ProcedureApprovalError(f"{field} must be an ISO-8601 timestamp") from exc
    if parsed.utcoffset() is None:
        raise ProcedureApprovalError(f"{field} must include a UTC offset")
    return parsed.astimezone(timezone.utc)


def _repo_relative(root: Path, path: Path, field: str) -> Path:
    resolved = path if path.is_absolute() else root / path
    resolved = resolved.resolve()
    try:
        relative = resolved.relative_to(root.resolve())
    except ValueError as exc:
        raise ProcedureApprovalError(f"{field} must be inside the repository") from exc
    if resolved.is_symlink() or (resolved.exists() and not resolved.is_file()):
        raise ProcedureApprovalError(f"{field} must be a regular non-symlink file")
    return relative


def render_request_review(request: Mapping[str, Any]) -> str:
    boundary = request["authority_effect"]
    lines = [
        f"# Procedure Approval Review - {request['request_id']}",
        "",
        f"- Procedure: `{request['procedure_id']}`",
        f"- Procedure path: `{request['procedure_path']}`",
        f"- Procedure SHA-256: `{request['procedure_sha256']}`",
        f"- Request SHA-256: `{sha256_bytes(canonical_bytes(dict(request)))}`",
        f"- Allowed deciding role: `{request['allowed_decider_role']}`",
        "",
        "This request asks only whether the exact procedure definition is approved. "
        "It contains no target identity and grants no target, execution, adapter, "
        "controller, H0-stage, verifier, or Git authority.",
        "",
        "## Fixed authority boundary",
        "",
    ]
    lines.extend(f"- `{key}`: `{str(value).lower()}`" for key, value in boundary.items())
    lines.extend(
        [
            "",
            "## Required human acknowledgements",
            "",
        ]
    )
    lines.extend(f"- {item}" for item in request["required_acknowledgements"])
    lines.extend(
        [
            "",
            "## Canonical request",
            "",
            "```json",
            canonical_bytes(dict(request)).decode("utf-8"),
            "```",
            "",
        ]
    )
    return "\n".join(lines)


def validate_request_artifacts(root: Path) -> tuple[dict[str, Any], str]:
    request_path = root / REQUEST_PATH
    request = _load_object(request_path, canonical=True)
    expected_fields = {
        "format_version",
        "record_kind",
        "request_id",
        "procedure_id",
        "procedure_path",
        "procedure_sha256",
        "governing_adr",
        "canonicalization",
        "status",
        "decision_scope",
        "allowed_decider_role",
        "required_acknowledgements",
        "authority_effect",
    }
    _strict_fields(request, expected_fields, "request")
    if request["format_version"] != "1.0":
        raise ProcedureApprovalError("request format_version is invalid")
    if request["record_kind"] != "AZPR_PROCEDURE_APPROVAL_REQUEST":
        raise ProcedureApprovalError("request record_kind is invalid")
    if request["request_id"] != REQUEST_ID or request["procedure_id"] != PROCEDURE_ID:
        raise ProcedureApprovalError("request identity drifted")
    if request["canonicalization"] != CANONICALIZATION:
        raise ProcedureApprovalError("request canonicalization is invalid")
    if request["status"] != "AWAITING_HUMAN_DECISION":
        raise ProcedureApprovalError("request fabricates a completed decision")
    if request["decision_scope"] != "PROCEDURE_DEFINITION_ONLY":
        raise ProcedureApprovalError("request scope is wider than procedure definition")
    if request["allowed_decider_role"] != "Project owner":
        raise ProcedureApprovalError("request deciding role drifted")
    if request["procedure_path"] != PROCEDURE_PATH.as_posix():
        raise ProcedureApprovalError("request procedure path drifted")
    if request["governing_adr"] != "docs/adr/0013-h0-live-target-fingerprint.md":
        raise ProcedureApprovalError("request governing ADR drifted")
    procedure_digest = sha256_file(root / PROCEDURE_PATH)
    if request["procedure_sha256"] != procedure_digest:
        raise ProcedureApprovalError("request no longer binds the exact procedure bytes")
    acknowledgements = request["required_acknowledgements"]
    if (
        not isinstance(acknowledgements, list)
        or not all(isinstance(value, str) for value in acknowledgements)
        or len(acknowledgements) != len(ACKNOWLEDGEMENT_FIELDS)
        or set(acknowledgements) != ACKNOWLEDGEMENT_FIELDS
    ):
        raise ProcedureApprovalError("request acknowledgement set drifted")
    expected_boundary = {
        "approves_procedure_definition": True,
        "authorizes_target": False,
        "approves_environment": False,
        "qualifies_environment": False,
        "authorizes_execution": False,
        "activates_operator_approval_adapter": False,
        "activates_controller": False,
        "executes_h0_t02": False,
        "executes_h0_stage": False,
        "executes_azpr_verifier": False,
        "authorizes_git": False,
    }
    if request["authority_effect"] != expected_boundary:
        raise ProcedureApprovalError("request authority boundary widened or drifted")
    request_digest = sha256_bytes(canonical_bytes(request))
    try:
        review = (root / REVIEW_PATH).read_text(encoding="utf-8")
    except OSError as exc:
        raise ProcedureApprovalError("procedure review view is unavailable") from exc
    if review != render_request_review(request):
        raise ProcedureApprovalError("procedure review view changed or is not request-bound")
    return request, request_digest


def validate_decision_value(
    root: Path,
    decision: Mapping[str, Any],
    *,
    now: datetime | None = None,
) -> tuple[dict[str, Any], dict[str, Any], str]:
    request, request_digest = validate_request_artifacts(root)
    _strict_fields(decision, DECISION_FIELDS, "decision")
    if decision["format_version"] != "1.0":
        raise ProcedureApprovalError("decision format_version is invalid")
    if decision["record_kind"] != "AZPR_PROCEDURE_APPROVAL_DECISION":
        raise ProcedureApprovalError("template or non-decision record cannot grant approval")
    approval_id = _nonempty(decision["approval_id"], "decision.approval_id")
    match = APPROVAL_ID_PATTERN.fullmatch(approval_id)
    if match is None:
        raise ProcedureApprovalError("decision approval_id is invalid")
    if decision["request_id"] != REQUEST_ID or decision["request_sha256"] != request_digest:
        raise ProcedureApprovalError("decision does not bind the current canonical request")
    if decision["procedure_id"] != PROCEDURE_ID:
        raise ProcedureApprovalError("decision procedure identity drifted")
    if decision["procedure_path"] != PROCEDURE_PATH.as_posix():
        raise ProcedureApprovalError("decision procedure path drifted")
    if decision["procedure_sha256"] != request["procedure_sha256"]:
        raise ProcedureApprovalError("decision does not bind the exact procedure bytes")
    if not SHA256_PATTERN.fullmatch(str(decision["procedure_sha256"])):
        raise ProcedureApprovalError("decision procedure SHA-256 is invalid")
    if decision["decision"] not in {"APPROVED", "REJECTED"}:
        raise ProcedureApprovalError("decision must be APPROVED or REJECTED")
    decided_at = _utc(decision["decided_at"], "decision.decided_at")
    observed_now = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    if decided_at > observed_now + timedelta(minutes=5):
        raise ProcedureApprovalError("decision time is unreasonably in the future")
    if match.group("date") != decided_at.strftime("%Y%m%d"):
        raise ProcedureApprovalError("decision approval_id date does not match decided_at")
    actor = decision["decided_by"]
    if not isinstance(actor, dict):
        raise ProcedureApprovalError("decision.decided_by must be an object")
    _strict_fields(actor, {"name", "role"}, "decision.decided_by")
    _nonempty(actor["name"], "decision.decided_by.name")
    if actor["role"] != request["allowed_decider_role"]:
        raise ProcedureApprovalError("decision role is not allowed for this procedure")
    acknowledgements = decision["acknowledgements"]
    if not isinstance(acknowledgements, dict):
        raise ProcedureApprovalError("decision.acknowledgements must be an object")
    _strict_fields(acknowledgements, ACKNOWLEDGEMENT_FIELDS, "decision.acknowledgements")
    if any(value is not True for value in acknowledgements.values()):
        raise ProcedureApprovalError("all procedure-boundary acknowledgements must be true")
    return dict(decision), request, request_digest


def _git(root: Path, *args: str) -> str:
    try:
        completed = subprocess.run(
            ["git", *args],
            cwd=root,
            check=True,
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise ProcedureApprovalError("repository provenance could not be verified") from exc
    return completed.stdout


def validate_committed_decision(
    root: Path,
    decision_path: Path = DECISION_PATH,
    *,
    now: datetime | None = None,
) -> ProcedureApprovalStatus:
    relative = _repo_relative(root, decision_path, "decision path")
    if relative != DECISION_PATH:
        raise ProcedureApprovalError("decision must use the governed repository path")
    absolute = root / relative
    decision = _load_object(absolute, canonical=True)
    decision, request, _request_digest = validate_decision_value(root, decision, now=now)

    if _git(root, "status", "--porcelain", "--untracked-files=all", "--", relative.as_posix()):
        raise ProcedureApprovalError("decision must be committed and unmodified")
    commit = _git(root, "log", "-1", "--format=%H", "--", relative.as_posix()).strip()
    if not COMMIT_PATTERN.fullmatch(commit):
        raise ProcedureApprovalError("decision has no attributable repository commit")
    _git(root, "merge-base", "--is-ancestor", commit, "HEAD")
    committed = _git(root, "show", f"{commit}:{relative.as_posix()}").encode("utf-8")
    if committed != absolute.read_bytes():
        raise ProcedureApprovalError("decision bytes differ from the attributable commit")
    changed_paths = _git(
        root,
        "diff-tree",
        "--root",
        "--no-commit-id",
        "--name-only",
        "-r",
        commit,
        "--",
        relative.as_posix(),
    ).splitlines()
    if relative.as_posix() not in changed_paths:
        raise ProcedureApprovalError("attributable commit did not create or change the decision")
    author_name = _git(root, "show", "-s", "--format=%an", commit).strip()
    if author_name != decision["decided_by"]["name"]:
        raise ProcedureApprovalError("decision author does not match repository commit attribution")
    commit_time = _utc(
        _git(root, "show", "-s", "--format=%aI", commit).strip(),
        "repository commit time",
    )
    decided_at = _utc(decision["decided_at"], "decision.decided_at")
    if commit_time < decided_at or commit_time > decided_at + timedelta(hours=24):
        raise ProcedureApprovalError("decision and attributable commit times do not align")

    approved = decision["decision"] == "APPROVED"
    reference = f"git:{commit}:{relative.as_posix()}"
    return ProcedureApprovalStatus(
        approved=approved,
        status="APPROVED" if approved else "REJECTED",
        approval_id=decision["approval_id"],
        approval_reference=reference,
        procedure_sha256=request["procedure_sha256"],
        decided_by=decision["decided_by"]["name"],
        decided_role=decision["decided_by"]["role"],
    )


def assess_repository_channel(root: Path = ROOT) -> ProcedureApprovalStatus:
    validate_request_artifacts(root)
    if not (root / DECISION_PATH).is_file():
        return ProcedureApprovalStatus(
            approved=False,
            status="AWAITING_HUMAN_DECISION",
            procedure_sha256=sha256_file(root / PROCEDURE_PATH),
        )
    return validate_committed_decision(root)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("check",))
    parser.add_argument("--root", type=Path, default=ROOT)
    args = parser.parse_args(argv)
    try:
        result = assess_repository_channel(args.root.resolve())
        payload = {
            "approval_id": result.approval_id,
            "approval_reference": result.approval_reference,
            "authority_effect": False,
            "procedure_approved": result.approved,
            "procedure_sha256": result.procedure_sha256,
            "status": result.status,
        }
        exit_code = 0 if result.approved else 2
    except ProcedureApprovalError as exc:
        payload = {
            "approval_id": None,
            "approval_reference": None,
            "authority_effect": False,
            "errors": [str(exc)],
            "procedure_approved": False,
            "status": "BLOCKED",
        }
        exit_code = 2
    print(json.dumps(payload, indent=2, sort_keys=True))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
