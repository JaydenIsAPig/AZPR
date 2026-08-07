#!/usr/bin/env python3
"""Build the v10.1 approval-candidate mapping from immutable staging evidence.

The command never changes the source mapping and never creates an approval.
It applies only the project-owner decisions recorded in ADR-0009 and the
machine-readable transition contract.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import tempfile
from pathlib import Path
from typing import Iterable


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE = (
    ROOT
    / "docs"
    / "delivery-provenance"
    / "v10.1"
    / "integration"
    / "AZPR-v10.1-integration-path-mapping.staging-original.csv"
)
DEFAULT_OUTPUT = (
    ROOT
    / "docs"
    / "delivery-provenance"
    / "v10.1"
    / "integration"
    / "AZPR-v10.1-integration-path-mapping.csv"
)
CONTRACT = ROOT / "automation" / "integration" / "v10.1" / "controller-transition-contract.json"
EXPECTED_SOURCE_SHA256 = "007786c1c1748f8264cee452df815b47e41e15deb8b532b31f426cd18b4f2525"

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
EXTRA_FIELDS = ["decision_id", "resolution_status", "transition_phase"]

IMPLEMENTATION_ARCHIVE = "AZPR-autonomous-execution-primed-draft-v10.1.zip"
REPORTS_ARCHIVE = "AZPR-autonomous-execution-primed-draft-v10.1-reports.zip"
STANDALONE_PROMPT_ARCHIVE = "markdown-prompts-autonomous-priming-draft-v10.1.zip"
CURRENT = "CURRENT_REPOSITORY"

RENAMED_CURRENT_PROMPTS = {
    "automation/numbered/031-perform-security-privacy-performance-and-recovery-hardening.md",
    "automation/numbered/033-prepare-and-execute-the-controlled-staging-deployment.md",
    "automation/numbered/035-deploy-the-controlled-production-pilot.md",
}
NEW_DELIVERED_PROMPTS = {
    "repository-overlay/automation/numbered/031-security-privacy-performance-and-recovery-hardening-audit.md",
    "repository-overlay/automation/numbered/033-prepare-controlled-staging-deployment-plan.md",
    "repository-overlay/automation/numbered/035-prepare-controlled-production-pilot-release-plan.md",
}
STALE_AUTOMATION_PATHS = {
    "automation/roadmap.proposed.json",
    "automation/roadmap.example.json",
    "automation/reports/roadmap-generation-report.md",
    "AZPR-roadmap-security-consultation.md",
    "AZPR-roadmap-security-scorecard.json",
}
STALE_CONTROLLER_REFERENCE_PATHS = {
    "BUNDLE_MANIFEST.txt",
    "docs/automation/AZPR-Autonomous-Agent-Loop-Implementation-Guide.docx",
}
REPOSITORY_CONTROLLER_PATHS = {
    "AGENTS.md",
    "automation/controller.py",
    "automation/controller.config.json",
    "automation/result.schema.json",
    "automation/roadmap.schema.json",
    "automation/roadmap-generator-prompt.md",
    "automation/smoke_test.py",
}
AUTHORITY_PATHS = {
    "automation/roadmap.json",
    "automation/policy/README.md",
    "docs/automation/autonomous-execution-policy.md",
}
PREPARATION_MERGES = {
    "AUTONOMOUS_LOOP_INSTALL.md",
    "docs/automation/README.md",
    "docs/automation/current-status.md",
}
GENERATED_PATHS = {
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
    "docs/delivery-provenance/v10.1/integration/AZPR-v10.1-integration-path-mapping.staging-original.csv",
    "docs/delivery-provenance/v10.1/integration/AZPR-v10.1-current-repository-inventory.json",
    "docs/delivery-provenance/v10.1/integration/AZPR-v10.1-final-deliverables-inventory.json",
    "docs/delivery-provenance/v10.1/integration/AZPR-v10.1-integration-conflict-report.md",
    "docs/delivery-provenance/v10.1/integration/AZPR-v10.1-integration-plan.md",
    "docs/delivery-provenance/v10.1/integration/AZPR-v10.1-integration-rollback-plan.md",
    "docs/delivery-provenance/v10.1/integration/AZPR-v10.1-staging-diff-report.md",
    "docs/delivery-provenance/v10.1/integration/README.md",
    "docs/delivery-provenance/v10.1/validation/AZPR-v10.1-staging-validation.json",
    "docs/delivery-provenance/v10.1/validation/AZPR-v10.1-system-integration-handoff-summary.md",
    "docs/delivery-provenance/v10.1/validation/README.md",
    "docs/delivery-provenance/v10.1/validation/candidate-file-inventory.sha256",
    "docs/delivery-provenance/v10.1/validation/requirements-validation.in",
    "docs/delivery-provenance/v10.1/validation/requirements-validation.lock",
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
    "docs/delivery-provenance/v10.1/validation/wheelhouse-manifest.json",
    "scripts/prepare_v10_1_mapping.py",
    "scripts/check_v10_1_mapping_readiness.py",
    "scripts/check_v10_1_prompt_stage_pack.py",
    "tests/test_v10_1_mapping_readiness.py",
    "tests/test_v10_1_prompt_stage_pack.py",
}
MERGED_GENERATED_PATHS = {
    ".gitignore",
    "AGENTS.md",
    "AUTONOMOUS_LOOP_INSTALL.md",
    "docs/adr/README.md",
    "docs/automation/README.md",
    "docs/automation/current-status.md",
    "docs/audits/README.md",
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def decision(
    row: dict[str, str],
    decision_id: str,
    phase: str,
    *,
    action: str | None = None,
    destination: str | None = None,
    conflict: str = "NONE",
    reason: str | None = None,
    dependencies: str | None = None,
    validation: str | None = None,
    rollback: str | None = None,
    approval_needed: str | None = None,
) -> None:
    if action is not None:
        row["action"] = action
    if destination is not None:
        row["proposed_destination"] = destination
    row["conflict_status"] = conflict
    if reason is not None:
        row["reason"] = reason
    if dependencies is not None:
        row["dependencies"] = dependencies
    if validation is not None:
        row["validation"] = validation
    if rollback is not None:
        row["rollback"] = rollback
    row["approval_needed"] = approval_needed or (
        "YES" if phase == "H1_REPOSITORY_INTEGRATION" else "NO"
    )
    row["decision_id"] = decision_id
    row["resolution_status"] = "READY_FOR_APPROVAL"
    row["transition_phase"] = phase


def provenance_destination(source_path: str) -> str:
    return f"docs/delivery-provenance/v10.1/frozen-delivery-reports/{source_path}"


def legacy_destination(source_path: str) -> str:
    return f"docs/delivery-provenance/v10.1/pre-v10.1-controller/{source_path}"


def transform(row: dict[str, str]) -> dict[str, str]:
    row = dict(row)
    row.update(
        decision_id="BASELINE-DISPOSITION",
        resolution_status="NO_APPROVAL_REQUIRED",
        transition_phase="H0_PREPARATION",
    )
    archive = row["source_archive"]
    path = row["source_path"]
    classification = row["classification"]

    overlay_prompt = path.startswith("repository-overlay/automation/numbered/") or path.startswith(
        "repository-overlay/automation/appendices/"
    )
    if archive == IMPLEMENTATION_ARCHIVE and overlay_prompt:
        target = path.removeprefix("repository-overlay/")
        action = "ADD" if path in NEW_DELIVERED_PROMPTS else "REPLACE"
        decision(
            row,
            "MAP-PROMPTS-V10.1",
            "H1_REPOSITORY_INTEGRATION",
            action=action,
            destination=target,
            reason="Use the project-owner-selected v10.1 implementation-overlay prompt as the sole canonical donor.",
            dependencies="ADR-0009; transition contract; whole-mapping human approval",
        )
    elif archive == IMPLEMENTATION_ARCHIVE and path == "markdown-prompts-autonomous-priming-draft.zip":
        decision(
            row,
            "MAP-PROMPTS-V10.1",
            "H1_REPOSITORY_INTEGRATION",
            action="ADD",
            destination="automation/numbered/markdown-prompts.zip",
            reason="Replace the prior canonical prompt archive with the byte-identical selected v10.1 archive after archiving the prior bytes.",
            dependencies="all 41 canonical prompt destinations; prompt manifest rebuild",
        )
    elif archive == STANDALONE_PROMPT_ARCHIVE:
        decision(
            row,
            "MAP-PROMPTS-V10.1",
            "H0_PREPARATION",
            action="QUARANTINE",
            reason="Byte-identical standalone representation; retain hash provenance and never create a competing active set.",
        )
    elif archive == CURRENT and path in RENAMED_CURRENT_PROMPTS:
        decision(
            row,
            "MAP-PROMPTS-V10.1",
            "H1_REPOSITORY_INTEGRATION",
            action="MOVE",
            destination=legacy_destination(path),
            reason="Archive the superseded active filename before adding its selected v10.1 plan/audit replacement.",
        )
    elif archive == CURRENT and (
        path.startswith("automation/numbered/") and path.endswith(".md")
        or path.startswith("automation/appendices/") and path.endswith(".md")
    ):
        decision(
            row,
            "MAP-PROMPTS-V10.1",
            "H1_REPOSITORY_INTEGRATION",
            action="REPLACE",
            destination=path,
            reason="Replace the current prompt with the selected same-path v10.1 donor after whole-mapping approval.",
        )
    elif archive == CURRENT and path == "automation/numbered/markdown-prompts.zip":
        decision(
            row,
            "MAP-PROMPTS-V10.1",
            "H1_REPOSITORY_INTEGRATION",
            action="MOVE",
            destination=legacy_destination(path),
            reason="Archive the pre-v10.1 prompt archive before materializing the selected archive.",
        )
    elif archive == CURRENT and path == "automation/prompt-manifest.json":
        decision(
            row,
            "MAP-PROMPTS-V10.1",
            "H1_REPOSITORY_INTEGRATION",
            action="MERGE",
            destination=path,
            reason="Rebuild the 38 numbered-prompt manifest entries from selected bytes and update renamed stages 031, 033 and 035; validate the three appendices separately.",
            dependencies="38 selected numbered prompts; three canonical appendices; manifest validator",
        )
    elif archive == CURRENT and path in STALE_CONTROLLER_REFERENCE_PATHS:
        decision(
            row,
            "MAP-STALE-CONTROLLER-REFERENCES",
            "H1_REPOSITORY_INTEGRATION",
            action="MOVE",
            destination=legacy_destination(path),
            reason="Archive the pre-v10.1 controller manifest or setup guide because its hashes, prompt names, or roadmap commands will no longer describe the approved mapping.",
            dependencies="selected prompt generation; repository controller remains dormant; replacement documentation review",
        )
    elif archive == CURRENT and path in STALE_AUTOMATION_PATHS:
        decision(
            row,
            "MAP-STALE-ROADMAP-EVIDENCE",
            "H1_REPOSITORY_INTEGRATION",
            action="MOVE",
            destination=legacy_destination(path),
            reason="Retire the stale pre-v10.1 proposal/reference without generating or activating a replacement roadmap.",
            dependencies="selected prompt generation; active roadmap remains null",
        )
    elif archive == CURRENT and path in REPOSITORY_CONTROLLER_PATHS:
        decision(
            row,
            "MAP-REPOSITORY-CONTROLLER",
            "H0_PREPARATION",
            action="KEEP_CURRENT",
            destination=path,
            reason="Keep the repository controller boundary byte-exact and dormant during integration.",
            dependencies="ADR-0009; transition contract single-writer gates",
        )
    elif archive == CURRENT and path in PREPARATION_MERGES:
        decision(
            row,
            "MAP-PREPARATION-DOCUMENTATION",
            "H0_PREPARATION",
            action="MERGE",
            destination=path,
            reason="Add the staged-hybrid dormant-transition notice without activating either controller.",
            dependencies="ADR-0009; transition contract",
            validation="post-merge generated-row SHA-256; documentation check; no controller execution",
            rollback="Restore the exact pre-preparation bytes from the approved base commit.",
        )
    elif archive == CURRENT and path in AUTHORITY_PATHS:
        decision(
            row,
            "MAP-AUTHORITY-INACTIVE",
            "H0_PREPARATION",
            action="KEEP_CURRENT",
            destination=path,
            reason="Preserve repository-primary governance while active policy and roadmap remain null.",
            dependencies="transition contract authority_state",
        )
    elif classification in {"REPOSITORY_CONTROLLER", "OPERATOR_TOOL", "HOST_INSTALLATION_TOOL"} or (
        archive == IMPLEMENTATION_ARCHIVE and path == "requirements-security.in"
    ):
        decision(
            row,
            "MAP-EXTERNAL-CONTROLLER",
            "H2_EXTERNAL_QUALIFICATION",
            action="DEFER",
            destination="",
            reason="Dormant external candidate; no repository destination or execution authority until separate host qualification and cutover approval.",
            dependencies="ADR-0009 H2/H3 gates; approved external trust boundary",
        )
    elif archive == REPORTS_ARCHIVE:
        decision(
            row,
            "MAP-PROVENANCE",
            "H0_PREPARATION",
            action="ADD",
            destination=provenance_destination(path),
            reason="Preserve one byte-exact report-tree copy as non-authoritative delivery provenance.",
            dependencies="delivery reports manifest; provenance identity",
        )
    elif archive == IMPLEMENTATION_ARCHIVE and "UNKNOWN_INTENT" in row["conflict_status"]:
        decision(
            row,
            "MAP-PROVENANCE-REFERENCE-ONLY",
            "H0_PREPARATION",
            action="QUARANTINE",
            destination="",
            reason="Retain only archive/hash provenance; the implementation-root duplicate is not repository authority.",
            dependencies="delivery identity; frozen report-tree copy when applicable",
        )
    elif row["action"] == "ADD":
        decision(
            row,
            "MAP-PASSIVE-REPOSITORY-OVERLAY",
            "H1_REPOSITORY_INTEGRATION",
            action="ADD",
            destination=row["proposed_destination"],
            reason=row["reason"],
            dependencies=f"{row['dependencies']}; whole-mapping human approval".strip("; "),
        )
    elif "UNKNOWN_INTENT" in row["conflict_status"]:
        row["resolution_status"] = "BLOCKED"
        row["decision_id"] = "UNRESOLVED"
    elif row["approval_needed"] == "YES":
        row["resolution_status"] = "READY_FOR_APPROVAL"
    return row


def current_row(path: str, *, action: str, destination: str, decision_id: str) -> dict[str, str]:
    absolute = ROOT / path
    return {
        "source_archive": CURRENT,
        "source_path": path,
        "source_sha256": sha256(absolute),
        "classification": "REPOSITORY_AUTOMATION",
        "current_repository_equivalent": path,
        "proposed_destination": destination,
        "action": action,
        "conflict_status": "NONE",
        "reason": "Disposition added after reference closure identified this affected tracked file.",
        "dependencies": "ADR-0009; selected v10.1 prompt generation; whole-mapping human approval",
        "validation": "tracked SHA-256; reference scan; no active roadmap",
        "rollback": "Restore the exact pre-integration bytes from the provenance destination or Git history.",
        "approval_needed": "YES",
        "decision_id": decision_id,
        "resolution_status": "READY_FOR_APPROVAL",
        "transition_phase": "H1_REPOSITORY_INTEGRATION",
    }


def generated_row(path: str) -> dict[str, str]:
    absolute = ROOT / path
    merged = path in MERGED_GENERATED_PATHS
    if path.startswith("docs/") or path == "AUTONOMOUS_LOOP_INSTALL.md":
        classification = "REPOSITORY_DOCUMENTATION"
    elif path.startswith("tests/"):
        classification = "REPOSITORY_TEST"
    elif path.startswith("scripts/") or path.startswith("automation/"):
        classification = "REPOSITORY_AUTOMATION"
    else:
        classification = "REPOSITORY_CONFIGURATION"
    return {
        "source_archive": "INTEGRATION_GENERATED",
        "source_path": path,
        "source_sha256": sha256(absolute),
        "classification": classification,
        "current_repository_equivalent": path if merged else "",
        "proposed_destination": path,
        "action": "MERGE" if merged else "ADD",
        "conflict_status": "NONE",
        "reason": "Preparation-only safeguard, provenance, dependency, or validation artifact requested for mapping approval readiness.",
        "dependencies": "ADR-0009; transition contract; no approval or activation side effect",
        "validation": "SHA-256; repository tests; mapping-readiness assessment",
        "rollback": (
            "Restore the exact pre-preparation bytes from the approved base commit."
            if merged
            else "Remove this exact preparation artifact before approval if the staged-hybrid decision is withdrawn."
        ),
        "approval_needed": "NO",
        "decision_id": "MAP-INTEGRATION-GENERATED",
        "resolution_status": "READY_FOR_APPROVAL",
        "transition_phase": "H0_PREPARATION",
    }


def build_rows(source: Path) -> list[dict[str, str]]:
    if not source.is_file() or sha256(source) != EXPECTED_SOURCE_SHA256:
        raise ValueError("immutable staging mapping SHA-256 mismatch")
    with source.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames != BASE_FIELDS:
            raise ValueError(f"unexpected source columns: {reader.fieldnames!r}")
        rows = [transform(row) for row in reader]
    keys = {(row["source_archive"], row["source_path"]) for row in rows}
    for path in sorted({"AZPR-roadmap-security-consultation.md", "AZPR-roadmap-security-scorecard.json"}):
        key = (CURRENT, path)
        if key not in keys:
            rows.append(
                current_row(
                    path,
                    action="MOVE",
                    destination=legacy_destination(path),
                    decision_id="MAP-STALE-ROADMAP-EVIDENCE",
                )
            )
            keys.add(key)
    for path in sorted(GENERATED_PATHS):
        if (ROOT / path).is_file() and ("INTEGRATION_GENERATED", path) not in keys:
            rows.append(generated_row(path))
    return rows


def atomic_write(path: Path, rows: Iterable[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=BASE_FIELDS + EXTRA_FIELDS, lineterminator="\n")
            writer.writeheader()
            writer.writerows(rows)
        os.replace(temporary, path)
    except BaseException:
        Path(temporary).unlink(missing_ok=True)
        raise


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    if args.source.resolve() != DEFAULT_SOURCE.resolve():
        raise SystemExit("source must be the preserved immutable staging mapping")
    if args.output.resolve() != DEFAULT_OUTPUT.resolve():
        raise SystemExit("output must be the canonical v10.1 provenance mapping")
    if not args.source.is_file() or sha256(args.source) != EXPECTED_SOURCE_SHA256:
        raise SystemExit("immutable staging mapping SHA-256 mismatch")
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    if contract.get("decision_id") != "AZPR-V10.1-STAGED-HYBRID-CONTROLLER":
        raise SystemExit("transition contract identity mismatch")
    rows = build_rows(args.source)
    atomic_write(args.output, rows)
    print(
        json.dumps(
            {
                "mapping": args.output.resolve().relative_to(ROOT.resolve()).as_posix(),
                "rows": len(rows),
                "sha256": sha256(args.output),
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
