#!/usr/bin/env python3
"""Generate the governed AZPR v10.1 integration-staging handoff reports."""

from __future__ import annotations

import csv
import hashlib
import json
import os
import re
import subprocess
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath


ROOT = Path("/Users/jayden/Desktop/Business/AZ-Permit-Radar/AZPR")
PARENT = ROOT.parent
TEMP = ROOT / ".integration-temp"
OUTPUT = ROOT / ".integration-reports"
OUTER = TEMP / "delivery/outer"
IMPLEMENTATION = TEMP / "delivery/implementation/AZPR-autonomous-execution-primed-draft-v10.1"
REPORTS = TEMP / "delivery/reports/AZPR-autonomous-execution-primed-draft-v10.1-reports"
PROMPTS = TEMP / "delivery/prompts"
DELIVERY_ZIP = PARENT / "AZPR-v10.1-final-deliverables.zip"
DELIVERY_SIDECAR = PARENT / "AZPR-v10.1-final-deliverables.zip.sha256"
STAGING_SPEC = PARENT / "AZPR-v10.1-system-integration-staging.codex.yaml"

BASE_SHA = "dac0e0bf1695d44f4b6c0e0e7673559f5d87ec02"
OUTER_SHA = "9194931033552ebde75cad5a9edf53348466d1af786b0a0aa0bdafc93b9a0558"
IMPLEMENTATION_SHA = "618449d73fd921e0fb366c0aed8c9a666b2ead3847e529a6ced9692fe41e2b24"
REPORTS_SHA = "f6c26f3dc745bd9ddba6e47039433bbf0b6687cda64a9b134ce775c4a659c228"
PROMPTS_SHA = "3b235cb7e33ca409241ff26523f60f8fee89cec524b3f09e91a69927a0aa4880"
MASTER_PROMPT_SHA = "37800ebde204070d1ac20c2cfff5c809ee4f318cfcc44312514c393077334ae6"

REQUIRED_COLUMNS = [
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


def now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def git(*args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True).rstrip("\n")


def files_under(root: Path) -> list[Path]:
    return sorted(path for path in root.rglob("*") if path.is_file())


def rel(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()


def classify_repository_path(path: str) -> str:
    if path.startswith("src/"):
        return "REPOSITORY_APPLICATION_CODE"
    if path.startswith("tests/"):
        return "REPOSITORY_TEST"
    if path.startswith("automation/numbered/") or path.startswith("automation/appendices/"):
        return "REPOSITORY_PROMPT"
    if path == "automation/controller.py":
        return "REPOSITORY_CONTROLLER"
    if "schema" in PurePosixPath(path).name and path.endswith(".json"):
        return "REPOSITORY_SCHEMA"
    if path.startswith("automation/"):
        return "REPOSITORY_AUTOMATION"
    if path.startswith("docs/") or path.endswith((".md", ".docx")):
        return "REPOSITORY_DOCUMENTATION"
    if path.startswith("scripts/"):
        return "OPERATOR_TOOL"
    return "REPOSITORY_APPLICATION_CODE"


def classify_implementation(path: str) -> str:
    if path == "repository-overlay/AGENTS.md" or path == "repository-overlay/automation/policy/README.md":
        return "REPOSITORY_DOCUMENTATION"
    if path.startswith("repository-overlay/automation/numbered/") or path.startswith(
        "repository-overlay/automation/appendices/"
    ):
        return "REPOSITORY_PROMPT"
    if path == "markdown-prompts-autonomous-priming-draft.zip":
        return "REPOSITORY_PROMPT"
    if path.startswith("repository-overlay/automation/schemas/"):
        return "REPOSITORY_SCHEMA"
    if path.startswith("repository-overlay/automation/validation-profiles/") or path == "requirements-security.in":
        return "RUNTIME_CONFIGURATION"
    if path.startswith("trusted-controller/"):
        return "REPOSITORY_CONTROLLER"
    if path.startswith("operator-tools/") or path.startswith("external-capability-runner/"):
        return "OPERATOR_TOOL"
    if path.startswith("trusted-installation/") or path.startswith("trusted-validation-runner/"):
        return "HOST_INSTALLATION_TOOL"
    if path.startswith(("assessment-inputs/", "legacy/", "provenance/", "policy-tools/")):
        return "HISTORICAL_ONLY"
    if path.startswith("evidence/") or path.startswith("tests/"):
        return "VERIFICATION_ONLY"
    if path in {"SHA256SUMS.json", "VERIFY-V10-CANDIDATE.py", "V10-RELEASE-TEST-CATALOG.json"}:
        return "VERIFICATION_ONLY"
    return "REPORT_ONLY"


def classify_reports(path: str) -> str:
    if path.startswith("development-evidence/"):
        return "HISTORICAL_ONLY"
    if path == "SHA256SUMS.json" or path.startswith("verification/") or path.endswith(
        "V10-RELEASE-TEST-CATALOG.json"
    ):
        return "VERIFICATION_ONLY"
    return "REPORT_ONLY"


def classify_outer(path: str) -> str:
    if path == "AZPR-autonomous-execution-primed-draft-v10.1-reports.zip":
        return "REPORT_ONLY"
    if path == "markdown-prompts-autonomous-priming-draft-v10.1.zip":
        return "REPOSITORY_PROMPT"
    return "VERIFICATION_ONLY"


def current_prompt_for(delivered_path: str) -> str:
    candidate = delivered_path.removeprefix("repository-overlay/")
    if (ROOT / candidate).is_file():
        return candidate
    match = re.search(r"automation/numbered/(\d{3})-", candidate)
    if match:
        options = sorted((ROOT / "automation/numbered").glob(match.group(1) + "-*.md"))
        if options:
            return rel(options[0], ROOT)
    return ""


def inventory_record(source_archive: str, source_path: str, path: Path, classification: str) -> dict[str, object]:
    return {
        "source_archive": source_archive,
        "source_path": source_path,
        "source_sha256": sha256(path),
        "size_bytes": path.stat().st_size,
        "classification": classification,
    }


def mapping_defaults(record: dict[str, object]) -> dict[str, str]:
    return {
        "source_archive": str(record["source_archive"]),
        "source_path": str(record["source_path"]),
        "source_sha256": str(record["source_sha256"]),
        "classification": str(record["classification"]),
        "current_repository_equivalent": "",
        "proposed_destination": "",
        "action": "DEFER",
        "conflict_status": "NONE",
        "reason": "Retain only as verified delivery evidence; no repository copy is required.",
        "dependencies": "human-approved mapping if later integrated",
        "validation": "SHA-256 and containing archive manifest",
        "rollback": "No repository write; remove only task-created extraction after preserving reports.",
        "approval_needed": "NO",
    }


def make_delivery_inventory() -> tuple[list[dict[str, object]], dict[str, Counter[str]]]:
    records: list[dict[str, object]] = []
    counts: dict[str, Counter[str]] = {}

    groups = [
        ("AZPR-v10.1-final-deliverables.zip", OUTER, classify_outer),
        ("AZPR-autonomous-execution-primed-draft-v10.1.zip", IMPLEMENTATION, classify_implementation),
        ("AZPR-autonomous-execution-primed-draft-v10.1-reports.zip", REPORTS, classify_reports),
        ("markdown-prompts-autonomous-priming-draft-v10.1.zip", PROMPTS, lambda _: "REPOSITORY_PROMPT"),
    ]
    for archive_name, root, classifier in groups:
        archive_counts: Counter[str] = Counter()
        for path in files_under(root):
            source_path = rel(path, root)
            classification = classifier(source_path)
            records.append(inventory_record(archive_name, source_path, path, classification))
            archive_counts[classification] += 1
        counts[archive_name] = archive_counts
    return records, counts


def make_mapping(delivery_records: list[dict[str, object]]) -> tuple[list[dict[str, str]], int, int]:
    rows: list[dict[str, str]] = []
    delivered_rows = 0
    for record in delivery_records:
        row = mapping_defaults(record)
        archive = row["source_archive"]
        path = row["source_path"]
        classification = row["classification"]

        if archive == "AZPR-v10.1-final-deliverables.zip":
            row["action"] = "DEFER"
            row["reason"] = "Frozen outer delivery member remains at the supplied parent location; do not duplicate it in the repository."
            if path.endswith(".zip"):
                row["dependencies"] = "verified nested archive disposition rows"

        elif archive == "AZPR-autonomous-execution-primed-draft-v10.1.zip":
            if path == "repository-overlay/AGENTS.md":
                row.update(
                    current_repository_equivalent="AGENTS.md",
                    proposed_destination="AGENTS.md",
                    action="KEEP_CURRENT",
                    conflict_status="CONTENT_COLLISION;OWNERSHIP_COLLISION",
                    reason="Delivered governance materially differs; this task forbids policy activation or unapproved authority replacement.",
                    dependencies="explicit governance decision",
                    validation="byte diff and authority-order review",
                    approval_needed="YES",
                )
            elif path.startswith(("repository-overlay/automation/numbered/", "repository-overlay/automation/appendices/")):
                destination = path.removeprefix("repository-overlay/")
                current = current_prompt_for(path)
                row.update(
                    current_repository_equivalent=current,
                    proposed_destination=destination,
                    action="DEFER",
                    conflict_status="PROMPT_COLLISION;CONTENT_COLLISION;VERSION_COLLISION",
                    reason="Canonical prompt replacement/rename is forbidden; keep the current prompt unchanged pending human resolution.",
                    dependencies="automation/prompt-manifest.json; roadmap files; prompt archive; documentation references",
                    validation="delivered 41-file byte identity; explicit human semantic review",
                    approval_needed="YES",
                )
            elif path.startswith("repository-overlay/automation/schemas/"):
                destination = path.removeprefix("repository-overlay/")
                basename = PurePosixPath(destination).name
                current = ""
                conflict = "NONE"
                if basename in {"result.schema.json", "roadmap.schema.json"}:
                    current = f"automation/{basename}"
                    conflict = "VERSION_COLLISION;REFERENCE_COLLISION"
                row.update(
                    current_repository_equivalent=current,
                    proposed_destination=destination,
                    action="ADD",
                    conflict_status=conflict,
                    reason="Candidate nested schema path; add only after controller architecture and references are approved.",
                    dependencies="approved controller ownership/layout; schema reference validation",
                    validation="JSON parse; Draft 2020-12 validation when jsonschema is available",
                    rollback="Remove only the exact added nested schema after confirming no approved consumer.",
                    approval_needed="YES",
                )
            elif path.startswith("repository-overlay/automation/validation-profiles/"):
                destination = path.removeprefix("repository-overlay/")
                row.update(
                    proposed_destination=destination,
                    action="ADD",
                    reason="Candidate configuration template; no live runtime state is included.",
                    dependencies="automation/schemas/validation-profile.schema.json; approved controller mapping",
                    validation="JSON parse and profile-schema validation",
                    rollback="Remove only the exact added profile after confirming no approved consumer.",
                    approval_needed="YES",
                )
            elif path == "repository-overlay/automation/policy/README.md":
                row.update(
                    current_repository_equivalent="docs/automation/autonomous-execution-policy.md",
                    proposed_destination="automation/policy/README.md",
                    action="ADD",
                    conflict_status="ACTIVE_STATE_COLLISION;DOCUMENTATION_COLLISION",
                    reason="Candidate fail-closed policy-directory notice only; active-policy semantics conflict with current documentation.",
                    dependencies="human definition of active policy; no canonical policy artifact",
                    validation="confirm only README exists and no active policy authority is added",
                    rollback="Remove only automation/policy/README.md if its approved mapping is reversed.",
                    approval_needed="YES",
                )
            elif path == "markdown-prompts-autonomous-priming-draft.zip":
                row.update(
                    action="QUARANTINE",
                    conflict_status="GENERATED_FILE_COLLISION;PROMPT_COLLISION",
                    reason="Byte-identical duplicate prompt representation; never create a competing active prompt set.",
                    validation="SHA-256 equals standalone prompt archive and overlay prompt bytes",
                )
            elif path == "provenance/independent-v9/AZ-Permit-Radar-Master-Operating-Prompt.docx":
                row.update(
                    current_repository_equivalent="AZ Permit Radar Master Operating Prompt.docx",
                    proposed_destination="AZ Permit Radar Master Operating Prompt.docx",
                    action="KEEP_CURRENT",
                    reason="Repository, supplied Legacy, and provenance DOCX copies are byte-identical.",
                    dependencies="none",
                    validation=f"SHA-256 equals {MASTER_PROMPT_SHA}",
                )
            elif classification == "REPOSITORY_CONTROLLER":
                row.update(
                    current_repository_equivalent="automation/controller.py",
                    action="DEFER",
                    conflict_status="OWNERSHIP_COLLISION;VERSION_COLLISION;REFERENCE_COLLISION",
                    reason="Delivered trusted controller is an external host component and conflicts with the current repository-local controller.",
                    dependencies="approved controller architecture; host trust boundary; missing docs/audits/index.json",
                    validation="controller import/dry-run only after explicit ownership resolution",
                    approval_needed="YES",
                )
            elif classification in {"OPERATOR_TOOL", "HOST_INSTALLATION_TOOL", "RUNTIME_CONFIGURATION"}:
                row.update(
                    action="DEFER",
                    conflict_status="OWNERSHIP_COLLISION;UNKNOWN_INTENT",
                    reason="Host/operator/runtime ownership and destination are not approved; activation and installation are forbidden.",
                    dependencies="separate host/operator authorization and approved destination",
                    validation="source-only verification; never execute privileged/install paths in this task",
                    approval_needed="YES",
                )
            elif classification == "HISTORICAL_ONLY":
                row.update(
                    action="QUARANTINE",
                    reason="Historical or provenance material remains in the frozen archive; no active repository destination is needed.",
                    dependencies="none",
                )
            elif classification == "REPORT_ONLY":
                row.update(
                    action="DEFER",
                    conflict_status="DOCUMENTATION_COLLISION;UNKNOWN_INTENT",
                    reason="Security delivery report is not a governed AZPR product document and must never be placed in docs/current.",
                    dependencies="approved delivery-provenance/history location",
                    approval_needed="YES",
                )
            elif classification == "VERIFICATION_ONLY":
                row.update(
                    action="DEFER",
                    reason="Use only from the isolated extraction for verification; do not add to the application repository without approval.",
                )

        elif archive == "AZPR-autonomous-execution-primed-draft-v10.1-reports.zip":
            row.update(
                action="QUARANTINE",
                conflict_status="GENERATED_FILE_COLLISION",
                reason="Duplicate report, history, or verification copy remains in its frozen reports archive; no permanent repository copy.",
                dependencies="none",
            )

        elif archive == "markdown-prompts-autonomous-priming-draft-v10.1.zip":
            delivered_candidate = "repository-overlay/" + path
            row.update(
                current_repository_equivalent=current_prompt_for(delivered_candidate),
                action="QUARANTINE",
                conflict_status="GENERATED_FILE_COLLISION;PROMPT_COLLISION",
                reason="Standalone prompt copy is byte-identical to the selected delivered candidate set; never copy it as a second active set.",
                dependencies="canonical prompt decision is represented by implementation-overlay rows",
                approval_needed="NO",
            )

        rows.append(row)
        delivered_rows += 1

    affected_paths = set(git("ls-files", "automation/numbered/*.md", "automation/appendices/*.md").splitlines())
    affected_paths.update(
        {
            "AGENTS.md",
            "automation/controller.py",
            "automation/controller.config.json",
            "automation/result.schema.json",
            "automation/roadmap.schema.json",
            "automation/prompt-manifest.json",
            "automation/roadmap.json",
            "automation/roadmap.proposed.json",
            "automation/roadmap.example.json",
            "automation/roadmap-generator-prompt.md",
            "automation/smoke_test.py",
            "automation/numbered/markdown-prompts.zip",
            "automation/reports/roadmap-generation-report.md",
            "AUTONOMOUS_LOOP_INSTALL.md",
            "BUNDLE_MANIFEST.txt",
            "docs/automation/README.md",
            "docs/automation/autonomous-execution-policy.md",
            "docs/automation/current-status.md",
            "docs/automation/AZPR-Autonomous-Agent-Loop-Implementation-Guide.docx",
        }
    )
    affected_current_rows = 0
    for path in sorted(affected_paths):
        absolute = ROOT / path
        if not absolute.is_file():
            continue
        classification = classify_repository_path(path)
        conflicts = "DOCUMENTATION_COLLISION;REFERENCE_COLLISION"
        reason = "Keep current tracked file unchanged until the v10.1 controller/layout decision is approved."
        if classification == "REPOSITORY_PROMPT":
            conflicts = "PROMPT_COLLISION;CONTENT_COLLISION;VERSION_COLLISION"
            reason = "Current canonical prompt is affected by the conflicting delivered prompt set; modification is forbidden in this task."
        elif path == "AGENTS.md":
            conflicts = "CONTENT_COLLISION;OWNERSHIP_COLLISION"
        elif path == "automation/controller.py":
            conflicts = "OWNERSHIP_COLLISION;VERSION_COLLISION;REFERENCE_COLLISION"
        elif path in {"automation/roadmap.json", "automation/roadmap.proposed.json"}:
            conflicts = "ACTIVE_STATE_COLLISION;REFERENCE_COLLISION"
        row = {
            "source_archive": "CURRENT_REPOSITORY",
            "source_path": path,
            "source_sha256": sha256(absolute),
            "classification": classification,
            "current_repository_equivalent": path,
            "proposed_destination": path,
            "action": "KEEP_CURRENT",
            "conflict_status": conflicts,
            "reason": reason,
            "dependencies": "explicit human controller/prompt/policy/layout decision",
            "validation": "tracked SHA-256 preserved; no staged diff",
            "rollback": "No change was applied.",
            "approval_needed": "YES",
        }
        rows.append(row)
        affected_current_rows += 1

    return rows, delivered_rows, affected_current_rows


def validate_internal_manifest(root: Path) -> dict[str, object]:
    manifest = json.loads((root / "SHA256SUMS.json").read_text())
    entries = manifest["entries"]
    actual_paths = {
        rel(path, root)
        for path in files_under(root)
        if path.name != "SHA256SUMS.json"
    }
    mismatches = [name for name, digest in entries.items() if not (root / name).is_file() or sha256(root / name) != digest]
    return {
        "declared_entries": len(entries),
        "expected_inventory_count": manifest.get("expected_inventory_count"),
        "actual_included_paths": len(actual_paths),
        "path_sets_match": set(entries) == actual_paths,
        "hash_mismatches": mismatches,
        "passed": len(entries) == manifest.get("expected_inventory_count") and set(entries) == actual_paths and not mismatches,
        "exclusion_semantics": "all files whose basename is SHA256SUMS.json",
    }


def validate_python_and_schemas() -> dict[str, object]:
    python_issues = []
    python_paths = sorted(IMPLEMENTATION.rglob("*.py"))
    for path in python_paths:
        try:
            source = path.read_text()
            compile(source, str(path), "exec")
        except Exception as exc:
            python_issues.append({"path": rel(path, IMPLEMENTATION), "error": str(exc)})

    schema_root = IMPLEMENTATION / "repository-overlay/automation/schemas"
    schema_paths = sorted(schema_root.glob("*.json"))
    schema_parse_issues = []
    ref_issues = []

    def walk_refs(value: object, source: Path) -> None:
        if isinstance(value, dict):
            reference = value.get("$ref")
            if isinstance(reference, str) and not reference.startswith(("#", "http://", "https://")):
                target_name = reference.split("#", 1)[0]
                target = (source.parent / target_name).resolve()
                try:
                    target.relative_to(schema_root.resolve())
                except ValueError:
                    ref_issues.append({"source": rel(source, schema_root), "reference": reference, "reason": "boundary_escape"})
                else:
                    if not target.is_file():
                        ref_issues.append({"source": rel(source, schema_root), "reference": reference, "reason": "missing_target"})
            for item in value.values():
                walk_refs(item, source)
        elif isinstance(value, list):
            for item in value:
                walk_refs(item, source)

    for path in schema_paths:
        try:
            value = json.loads(path.read_text())
            walk_refs(value, path)
        except Exception as exc:
            schema_parse_issues.append({"path": rel(path, schema_root), "error": str(exc)})

    return {
        "python_files": len(python_paths),
        "python_compile_issues": python_issues,
        "python_compile_passed": len(python_paths) == 69 and not python_issues,
        "schema_files": len(schema_paths),
        "schema_json_parse_issues": schema_parse_issues,
        "schema_local_reference_issues": ref_issues,
        "schema_json_and_local_refs_passed": len(schema_paths) == 73 and not schema_parse_issues and not ref_issues,
        "draft_2020_12_metaschema_validation": "BLOCKED_JSONSCHEMA_UNAVAILABLE",
    }


def make_repository_inventory(generated_at: str) -> dict[str, object]:
    tracked = git("ls-files").splitlines()
    ignored = [
        item
        for item in git("ls-files", "--others", "--ignored", "--exclude-standard").splitlines()
        if not item.startswith((".integration-temp/", ".integration-reports/"))
    ]
    records = []
    for path in tracked:
        absolute = ROOT / path
        records.append(
            {
                "path": path,
                "sha256": sha256(absolute),
                "size_bytes": absolute.stat().st_size,
                "classification": classify_repository_path(path),
            }
        )

    def selected(predicate) -> list[str]:
        return [item for item in tracked if predicate(item)]

    return {
        "generated_at": generated_at,
        "snapshot_kind": "PHASE_1_PRE_WRITE_FREEZE",
        "repository_root": str(ROOT),
        "allowed_parent_root": str(PARENT),
        "repository_basename": ROOT.name,
        "current_branch": "main",
        "current_head_sha": BASE_SHA,
        "upstream": "origin/main",
        "upstream_divergence": {"ahead": 0, "behind": 0},
        "git_status": "CLEAN_AT_PHASE_1_FREEZE",
        "existing_worktrees": [{"path": str(ROOT), "head": BASE_SHA, "branch": "refs/heads/main"}],
        "related_branches": [],
        "tracked_file_count": len(tracked),
        "untracked_files": [],
        "untracked_file_count": 0,
        "ignored_files": ignored,
        "ignored_file_count": len(ignored),
        "tracked_files": records,
        "controller_paths": selected(lambda p: p == "automation/controller.py" or "controller.config" in p),
        "automation_paths": selected(lambda p: p.startswith("automation/")),
        "numbered_prompt_paths": selected(lambda p: p.startswith("automation/numbered/") and p.endswith(".md")),
        "appendix_paths": selected(lambda p: p.startswith("automation/appendices/") and p.endswith(".md")),
        "schema_paths": selected(lambda p: "schema" in PurePosixPath(p).name and p.endswith(".json")),
        "test_paths": selected(lambda p: p.startswith("tests/") or p == "automation/smoke_test.py"),
        "documentation_paths": selected(lambda p: p.startswith("docs/") or p.endswith((".md", ".docx"))),
        "report_paths": selected(lambda p: p.startswith("docs/audits/") or p.startswith("automation/reports/")),
        "runtime_paths": [item for item in ignored if item.startswith(".codex-loop/")],
        "operator_tool_paths": ["automation/controller.py", "automation/smoke_test.py", "scripts/check_docs.py"],
        "installation_tool_paths": selected(lambda p: "INSTALL" in p or "Implementation-Guide" in p),
        "policy_paths": selected(lambda p: p == "AGENTS.md" or "policy" in p.lower()),
        "roadmap_paths": selected(lambda p: "roadmap" in p.lower()) + [item for item in ignored if "roadmap" in item.lower()],
        "master_operating_prompt": {
            "repository_path": "AZ Permit Radar Master Operating Prompt.docx",
            "sha256": MASTER_PROMPT_SHA,
            "supplied_legacy_copy_byte_identical": True,
        },
        "audit_state": {
            "index_path": "docs/audits/index.json",
            "index_present": False,
            "latest_applicable_report": "docs/audits/post-prompt-10-reconciliation-audit.md",
            "latest_report_result": "CORRECTIONS STILL REQUIRED",
            "controller_latest_formal_audit": None,
        },
        "roadmap_state": {
            "canonical_roadmap_path": "automation/roadmap.json",
            "canonical_roadmap_size_bytes": (ROOT / "automation/roadmap.json").stat().st_size,
            "proposal_path": "automation/roadmap.proposed.json",
            "local_state_roadmap_version": None,
            "current_controller_interpretation": "INACTIVE_UNPROMOTED",
            "delivery_controller_interpretation": "PATH_EXISTENCE_FORBIDDEN_ACTIVE_AUTHORITY",
        },
    }


def conflict_catalog() -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    blocking = [
        {
            "id": "B01",
            "type": "PROMPT_COLLISION",
            "stop_conditions": ["integration_requires_prompt_changes"],
            "paths": ["automation/numbered/*.md", "automation/appendices/*.md", "automation/prompt-manifest.json"],
            "detail": "All 41 current canonical prompts conflict: 38 content collisions and three filename/semantic collisions at IDs 031, 033, and 035. Prompt modification is forbidden.",
            "decision": "Choose and explicitly approve one canonical prompt generation and all required reference/manifest retirements.",
        },
        {
            "id": "B02",
            "type": "OWNERSHIP_COLLISION",
            "stop_conditions": ["current_and_delivered_controller_conflict"],
            "paths": ["automation/controller.py", "trusted-controller/controller.py", "automation/controller.config.json"],
            "detail": "Repository-local controller v1.0.1 conflicts with an external trusted-controller v7 draft and a different host/runtime model.",
            "decision": "Approve controller ownership, install boundary, configuration model, and migration mapping.",
        },
        {
            "id": "B03",
            "type": "REFERENCE_COLLISION",
            "stop_conditions": ["unclear_file_destination"],
            "paths": ["automation/result.schema.json", "automation/roadmap.schema.json", "automation/schemas/result.schema.json", "automation/schemas/roadmap.schema.json", "automation/roadmap-generator-prompt.md", "docs/audits/index.json"],
            "detail": "Schema locations/content and roadmap-generator instructions conflict; the delivered controller also requires a missing controller-owned audit index.",
            "decision": "Approve one controller/schema/reference contract; do not fabricate the audit index.",
        },
        {
            "id": "B04",
            "type": "ACTIVE_STATE_COLLISION",
            "stop_conditions": ["unexpected_active_roadmap"],
            "paths": ["automation/roadmap.json", "automation/roadmap.proposed.json", ".codex-loop/generated-roadmap.json", ".codex-loop/state.json"],
            "detail": "Current controller treats the zero-byte roadmap and populated proposal as inactive; delivered verifier semantics reject path existence.",
            "decision": "Define active-roadmap semantics and an approved non-destructive disposition.",
        },
        {
            "id": "B05",
            "type": "ACTIVE_STATE_COLLISION",
            "stop_conditions": ["unexpected_active_policy"],
            "paths": ["docs/automation/autonomous-execution-policy.md", "automation/policy/README.md", "AGENTS.md"],
            "detail": "Current repository has an operative autonomous-execution policy document; delivery checks only a narrower absent canonical-policy authority.",
            "decision": "Define active-policy semantics and approve governance placement without activation.",
        },
        {
            "id": "B06",
            "type": "DOCUMENTATION_COLLISION",
            "stop_conditions": ["documentation_version_conflict"],
            "paths": ["docs/current/", "CURRENT-DOCUMENT-INDEX.json", "AUTONOMOUS_LOOP_INSTALL.md", "docs/automation/"],
            "detail": "Delivery's 17 security current-documents are not the repository's five governed product-document families; old controller documentation has no delivered replacement.",
            "decision": "Approve a delivery-provenance location and a separate governed documentation migration; never copy reports into docs/current.",
        },
        {
            "id": "B07",
            "type": "OWNERSHIP_COLLISION",
            "stop_conditions": ["unclear_tool_ownership", "unclear_file_destination"],
            "paths": ["operator-tools/", "external-capability-runner/", "trusted-installation/", "trusted-validation-runner/", "requirements-security.in"],
            "detail": "Operator, host installation, runtime, historical, and report content lacks an approved repository or host destination.",
            "decision": "Approve ownership and exact destinations separately; host installation remains outside this task.",
        },
        {
            "id": "B08",
            "type": "UNKNOWN_INTENT",
            "stop_conditions": ["mapping_not_approved"],
            "paths": [".integration-reports/AZPR-v10.1-integration-path-mapping.csv"],
            "detail": "The exhaustive mapping exists but has not received the specification's required human approval.",
            "decision": "Review and approve the exact CSV hash or return corrections.",
        },
        {
            "id": "B09",
            "type": "UNKNOWN_INTENT",
            "stop_conditions": ["unapproved_base_commit"],
            "paths": [BASE_SHA],
            "detail": "The clean current HEAD is recorded but was not explicitly approved as the integration base.",
            "decision": f"Explicitly approve base commit {BASE_SHA} or identify another base.",
        },
        {
            "id": "B10",
            "type": "UNKNOWN_INTENT",
            "stop_conditions": ["test_count_mismatch"],
            "paths": ["VERIFY-V10-CANDIDATE.py", "requirements-security.in"],
            "detail": "Both verifier attempts stopped at 'jsonschema unavailable'; pytest is also unavailable. Source tests 0/120 and fresh-extraction tests 0/120 executed.",
            "decision": "Provide an approved offline dependency set/runtime and rerun both complete 120-test verifier passes.",
        },
    ]
    non_blocking = [
        {
            "id": "N01",
            "type": "GENERATED_FILE_COLLISION",
            "detail": "Three prompt representations and duplicate report/verification copies are byte-identical and safely mapped to QUARANTINE.",
        },
        {
            "id": "N02",
            "type": "DOCUMENTATION_COLLISION",
            "detail": "Current generated roadmap notes still say the Master Operating Prompt is absent although the repository now tracks it.",
        },
        {
            "id": "N03",
            "type": "UNKNOWN_INTENT",
            "detail": "No formatter, linter, or static/type checker is configured; existing repository unittest/docs checks still pass.",
        },
        {
            "id": "N04",
            "type": "GENERATED_FILE_COLLISION",
            "detail": "Pre-existing ignored caches and inactive local controller state remain local and were not copied into staging.",
        },
    ]
    return blocking, non_blocking


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def main() -> None:
    generated_at = now()
    OUTPUT.mkdir(parents=True, exist_ok=True)
    delivery_records, classification_counts = make_delivery_inventory()
    mapping_rows, delivered_rows, affected_current_rows = make_mapping(delivery_records)
    blocking, non_blocking = conflict_catalog()

    repository_inventory = make_repository_inventory(generated_at)
    write_json(OUTPUT / "AZPR-v10.1-current-repository-inventory.json", repository_inventory)

    implementation_manifest = validate_internal_manifest(IMPLEMENTATION)
    reports_manifest = validate_internal_manifest(REPORTS)
    code_and_schema = validate_python_and_schemas()
    prompt_files = files_under(PROMPTS)
    overlay_prompts = sorted(
        list((IMPLEMENTATION / "repository-overlay/automation/numbered").glob("*.md"))
        + list((IMPLEMENTATION / "repository-overlay/automation/appendices").glob("*.md"))
    )
    prompt_identity = {
        "standalone_archive_sha256": sha256(OUTER / "markdown-prompts-autonomous-priming-draft-v10.1.zip"),
        "embedded_archive_sha256": sha256(IMPLEMENTATION / "markdown-prompts-autonomous-priming-draft.zip"),
        "archives_byte_identical": (OUTER / "markdown-prompts-autonomous-priming-draft-v10.1.zip").read_bytes()
        == (IMPLEMENTATION / "markdown-prompts-autonomous-priming-draft.zip").read_bytes(),
        "prompt_count": len(prompt_files),
        "overlay_prompt_count": len(overlay_prompts),
        "path_and_bytes_match": {
            rel(path, PROMPTS): sha256(path) for path in prompt_files
        }
        == {
            rel(path, IMPLEMENTATION / "repository-overlay"): sha256(path) for path in overlay_prompts
        },
    }
    outer_manifest = json.loads((OUTER / "AZPR-v10.1-delivery-manifest.json").read_text())
    delivery_inventory = {
        "generated_at": generated_at,
        "outer_delivery": {
            "source_path": str(DELIVERY_ZIP),
            "sha256": sha256(DELIVERY_ZIP),
            "expected_sha256": OUTER_SHA,
            "sidecar_path": str(DELIVERY_SIDECAR),
            "sidecar_verified": True,
            "outer_member_count": len(files_under(OUTER)),
            "archive_safety": json.loads((TEMP / "archive-safety.json").read_text()),
            "delivery_manifest_artifact_count": len(outer_manifest["artifacts"]),
            "delivery_manifest_verified": True,
        },
        "nested_archive_identity": {
            "implementation_sha256": IMPLEMENTATION_SHA,
            "reports_sha256": REPORTS_SHA,
            "prompt_archive_sha256": PROMPTS_SHA,
        },
        "internal_manifests": {
            "implementation": implementation_manifest,
            "reports": reports_manifest,
        },
        "prompt_identity": prompt_identity,
        "readiness_flags": {
            "ready_for_codex_seating_and_application": False,
            "ready_for_final_integration_prompt_authoring": False,
            "pre_autonomous_staging": "FAIL",
            "semi_autonomous_codex_staging_ready": False,
            "trusted_pre_autonomous_installation_ready": False,
            "safe_for_unattended_execution_now": False,
        },
        "classification_counts": {
            archive: dict(sorted(counter.items())) for archive, counter in classification_counts.items()
        },
        "delivered_file_count": len(delivery_records),
        "files": delivery_records,
    }
    write_json(OUTPUT / "AZPR-v10.1-final-deliverables-inventory.json", delivery_inventory)

    mapping_path = OUTPUT / "AZPR-v10.1-integration-path-mapping.csv"
    with mapping_path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=REQUIRED_COLUMNS)
        writer.writeheader()
        writer.writerows(mapping_rows)
    mapping_sha = sha256(mapping_path)
    next(item for item in blocking if item["id"] == "B08")["mapping_sha256"] = mapping_sha

    conflict_lines = [
        "# AZPR v10.1 Integration Conflict Report",
        "",
        f"Generated: `{generated_at}`",
        "",
        "## Verdict",
        "",
        "**BLOCKED BEFORE BRANCH/WORKTREE CREATION OR MATERIALIZATION.** The delivery identity is verified, but ten blocking conflicts and four non-blocking conflicts remain.",
        "",
        "## Blocking conflicts",
        "",
    ]
    for item in blocking:
        conflict_lines.extend(
            [
                f"### {item['id']} — {item['type']}",
                "",
                f"- Stop condition(s): `{', '.join(item['stop_conditions'])}`",
                f"- Paths: `{'; '.join(item['paths'])}`",
                f"- Finding: {item['detail']}",
                f"- Required human decision: {item['decision']}",
                *([f"- Mapping SHA-256: `{item['mapping_sha256']}`"] if "mapping_sha256" in item else []),
                "",
            ]
        )
    conflict_lines.extend(["## Non-blocking conflicts", ""])
    for item in non_blocking:
        conflict_lines.extend([f"- **{item['id']} — {item['type']}:** {item['detail']}"])
    conflict_lines.extend(
        [
            "",
            "## Scope safeguards",
            "",
            "No tracked file, branch, worktree, controller, prompt, policy, roadmap, provider, installer, runtime state, secret, or production capability was changed or activated. Delivery reports were not placed in `docs/current/`.",
            "",
        ]
    )
    (OUTPUT / "AZPR-v10.1-integration-conflict-report.md").write_text("\n".join(conflict_lines))

    plan = f"""# AZPR v10.1 Integration Plan

Generated: `{generated_at}`

## Outcome

The integration plan stops after mapping and validation evidence. Phase 6 onward is not authorized because the base commit and path mapping are not human-approved and declared stop conditions are present.

## Completed phases

1. Discovered and froze clean `main` at `{BASE_SHA}`; confirmed one worktree and the AZPR boundary.
2. Verified outer/nested hashes, sidecars, archive safety, internal manifests, prompt copies, and frozen readiness flags.
3. Inventoried 261 tracked repository files and 407 delivered file instances across all archive representations.
4. Assigned exactly one allowed classification to every delivered file.
5. Created a {len(mapping_rows)}-row mapping: {delivered_rows} delivered dispositions plus {affected_current_rows} explicit affected-current dispositions.

## Proposed integration order after approval

1. Resolve controller ownership, schema locations, `docs/audits/index.json`, policy/roadmap semantics, and documentation migration.
2. Resolve the canonical 41-prompt generation and all renamed prompt/manifest/roadmap references without modifying bytes casually.
3. Approve base `{BASE_SHA}` and mapping CSV SHA-256 `{mapping_sha}`.
4. Create only `integration/v10.1-staging` and `{PARENT / 'AZPR-v10.1-integration-staging'}`.
5. Apply approved `ADD` rows in order: 73 schemas, seven validation profiles, policy-directory notice; then only explicitly approved prompt/controller/document changes.
6. Never copy host installation tools, live runtime state, secrets, private keys, receipts, or ledgers into the repository.
7. Run both complete 120-test verifier passes from an approved offline dependency runtime, plus repository tests/docs/reference checks.

## Approval boundary

This plan is a handoff, not approval. Do not create a branch/worktree, copy mapped files, commit, install, or activate anything until every blocking conflict is resolved and the exact mapping/base are approved.
"""
    (OUTPUT / "AZPR-v10.1-integration-plan.md").write_text(plan)

    staging_diff = f"""# AZPR v10.1 Staging Diff Report

Generated: `{generated_at}`

## Result

No isolated staging worktree or integration branch was created, and no integration overlay was materialized. This is the required stopped state after `mapping_not_approved`, `unapproved_base_commit`, prompt/controller conflicts, and `test_count_mismatch` were found.

## Tracked diff

- Base: `{BASE_SHA}` on `main`, synchronized with `origin/main` at phase-1 freeze.
- Tracked working-tree diff: none.
- Cached/staged diff: none.
- Application, prompt, policy, roadmap, controller, documentation, configuration, and test files changed: 0.

## Task-created untracked paths

- `.integration-temp/`: safe extractions and validation evidence only.
- `.integration-reports/`: the nine required handoff reports only.

## Expected approved candidate additions (not applied)

- 73 files under `automation/schemas/`.
- Seven files under `automation/validation-profiles/`.
- `automation/policy/README.md` as a fail-closed notice only.

Every other delivered component is `DEFER`, `QUARANTINE`, or `KEEP_CURRENT` pending explicit human resolution.
"""
    (OUTPUT / "AZPR-v10.1-staging-diff-report.md").write_text(staging_diff)

    validation = {
        "generated_at": generated_at,
        "overall_status": "BLOCKED",
        "stop_conditions_triggered": sorted({condition for item in blocking for condition in item["stop_conditions"]}),
        "counts": {
            "blocking_conflicts": len(blocking),
            "non_blocking_conflicts": len(non_blocking),
            "repository_tests_passed": 160,
            "source_tests_passed": 0,
            "fresh_extraction_tests_passed": 0,
            "delivered_python_files_compiled": code_and_schema["python_files"] if code_and_schema["python_compile_passed"] else 0,
            "delivered_schemas_json_parsed": code_and_schema["schema_files"] if not code_and_schema["schema_json_parse_issues"] else 0,
            "delivered_files_dispositioned": delivered_rows,
            "affected_current_files_dispositioned": affected_current_rows,
        },
        "checks": {
            "delivery_hashes_match": True,
            "sidecars_verify": True,
            "archive_safety": True,
            "implementation_manifest": implementation_manifest,
            "reports_manifest": reports_manifest,
            "repository_inventory_complete": True,
            "delivery_inventory_complete": len(delivery_records) == 407,
            "every_delivered_file_has_disposition": delivered_rows == len(delivery_records),
            "every_affected_current_file_has_disposition": True,
            "classification_complete": all(record["classification"] for record in delivery_records),
            "path_mapping_columns_exact": list(mapping_rows[0]) == REQUIRED_COLUMNS,
            "path_mapping_complete": True,
            "path_mapping_sha256": mapping_sha,
            "path_mapping_human_approved": False,
            "approved_base_commit": False,
            "isolated_branch_and_worktree": False,
            "materialization_performed": False,
            "prompt_delivery_copies_byte_identical": all(prompt_identity.values()) if False else prompt_identity,
            "prompt_bytes_unchanged_in_repository": True,
            "duplicate_active_prompt_set_created": False,
            "delivery_active_policy_present": False,
            "delivery_active_roadmap_present": False,
            "current_policy_active_semantics_resolved": False,
            "current_roadmap_active_semantics_resolved": False,
            "runtime_state_copied": False,
            "secret_files_copied": False,
            "duplicate_controller_resolved": False,
            "stale_path_references_resolved": False,
            "controller_and_schema_paths_resolve": False,
            "missing_controller_path": "docs/audits/index.json",
            "python_compilation": code_and_schema,
            "schema_validation": {
                "json_and_local_refs": code_and_schema["schema_json_and_local_refs_passed"],
                "draft_2020_12": "BLOCKED_JSONSCHEMA_UNAVAILABLE",
            },
            "source_tree_verifier": {
                "exit_code": 1,
                "tests_passed": 0,
                "tests_expected": 120,
                "error": "VERIFY V10.1 FAILED: jsonschema unavailable",
                "pytest_available": False,
                "jsonschema_available": False,
            },
            "fresh_extraction_verifier": {
                "exit_code": 1,
                "tests_passed": 0,
                "tests_expected": 120,
                "error": "VERIFY V10.1 FAILED: jsonschema unavailable",
                "python_files_compiled_before_stop": 69,
                "source_tree_mutation_detected": False,
            },
            "current_repository_tests": {"status": "PASS", "tests_passed": 160},
            "current_documentation_validation": {
                "status": "PASS",
                "families": 5,
                "checks": ["unique current status", "business-data schema", "logs", "local links"],
            },
            "workspace_boundary_respected": True,
            "writes_outside_allowed_parent_root": [],
            "unnecessary_directories_created": 0,
            "tracked_diff_empty": True,
            "rollback_rehearsal": "PASS_NO_TRACKED_OR_STAGED_INTEGRATION_CHANGE",
        },
        "blocking_conflicts": blocking,
        "non_blocking_conflicts": non_blocking,
        "final_result": {
            "delivery_identity_verified": True,
            "repository_bridge_complete": False,
            "path_mapping_complete": True,
            "blocking_conflicts": len(blocking),
            "non_blocking_conflicts": len(non_blocking),
            "source_tests_passed": 0,
            "fresh_extraction_tests_passed": 0,
            "prompt_bytes_unchanged": True,
            "workspace_boundary_respected": True,
            "unnecessary_directories_created": 0,
            "ready_for_integration_staging": False,
            "ready_for_activation": False,
            "safe_for_unattended_execution_now": False,
            "next_required_action": "HUMAN_RESOLUTION_OF_BLOCKING_CONFLICTS_AND_APPROVAL_OF_BASE_MAPPING_AND_OFFLINE_VALIDATION_RUNTIME",
        },
    }
    write_json(OUTPUT / "AZPR-v10.1-staging-validation.json", validation)

    rollback = f"""# AZPR v10.1 Integration Rollback Plan

Generated: `{generated_at}`

## Current rollback state

No integration branch, worktree, commit, tracked edit, prompt replacement, controller copy, policy/roadmap activation, runtime-state copy, or installation occurred. Rollback is therefore limited to task-created untracked evidence.

## Reproducible rollback procedure

1. Preserve `.integration-reports/` externally if the handoff must be retained.
2. Confirm `git diff --exit-code` and `git diff --cached --exit-code` both succeed.
3. Confirm the only task-created untracked roots are exactly `.integration-temp/` and `.integration-reports/`.
4. Remove only those two exact directories; do not use a repository-wide clean, reset, checkout, or history rewrite.
5. Verify `git status --short --branch` returns `## main...origin/main` and HEAD remains `{BASE_SHA}`.
6. Verify `git worktree list --porcelain` still contains only the main worktree.

## Rehearsal result

Non-destructive rehearsal passed: there is no tracked/cached diff and no integration branch/worktree exists. The exact generated roots are inside the allowed boundary. The required reports intentionally remain present, so cleanup was not executed.

## Future materialized rollback boundary

If a later approved integration creates `integration/v10.1-staging`, record the approved base and mapping hash first. Rollback must remove only files added by approved mapping rows or abandon the isolated worktree/branch; never rewrite `main`, delete source evidence, or modify canonical prompt bytes without a separately approved migration.
"""
    (OUTPUT / "AZPR-v10.1-integration-rollback-plan.md").write_text(rollback)

    handoff = f"""# AZPR v10.1 System Integration Handoff Summary

Generated: `{generated_at}`

## Result

Delivery identity, sidecars, manifests, archive safety, classification, and exhaustive mapping are complete. Repository bridging/materialization is **BLOCKED** before branch/worktree creation by prompt/controller/reference/active-state/documentation/ownership conflicts, missing base/mapping approval, and unavailable offline validation dependencies.

No tracked content or active capability changed. Current repository validation passed 160 tests and the five-family documentation check. Both required delivery verifier runs executed 0 of 120 tests because `jsonschema` was unavailable; `pytest` is also absent. No network fetch was attempted.

## Required human review

1. Resolve blocking conflicts B01–B10 in the conflict report.
2. Approve or correct mapping SHA-256 `{mapping_sha}` and explicitly approve base `{BASE_SHA}`.
3. Supply an approved offline runtime/dependency set containing `pytest` and `jsonschema`, then rerun both 120-test passes.
4. Only after all gates pass, authorize creation of the one isolated integration branch/worktree.

## Exact final-result schema

```json
{json.dumps(validation['final_result'], indent=2)}
```
"""
    (OUTPUT / "AZPR-v10.1-system-integration-handoff-summary.md").write_text(handoff)

    print(
        json.dumps(
            {
                "output_root": str(OUTPUT),
                "required_files_written": len(list(OUTPUT.iterdir())),
                "delivered_rows": delivered_rows,
                "affected_current_rows": affected_current_rows,
                "mapping_rows": len(mapping_rows),
                "blocking_conflicts": len(blocking),
                "non_blocking_conflicts": len(non_blocking),
                "python_compile": code_and_schema["python_compile_passed"],
                "schema_json_and_refs": code_and_schema["schema_json_and_local_refs_passed"],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
