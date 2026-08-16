from __future__ import annotations

import copy
import json
import os
import shutil
import subprocess
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker

from automation import procedure_approval as approvals


ROOT = Path(__file__).resolve().parents[1]
SCHEMA = ROOT / "automation/approvals/schemas/procedure-approval-decision-v1.schema.json"
TEMPLATE = (
    ROOT
    / "automation/approvals/templates/h0-fingerprint-procedure-decision.template.json"
)


class ProcedureApprovalTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        for relative in (
            approvals.REQUEST_PATH,
            approvals.REVIEW_PATH,
            approvals.PROCEDURE_PATH,
        ):
            target = self.root / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT / relative, target)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def decision(self) -> dict:
        _request, request_digest = approvals.validate_request_artifacts(self.root)
        return {
            "format_version": "1.0",
            "record_kind": "AZPR_PROCEDURE_APPROVAL_DECISION",
            "approval_id": "AZPR-H0-FINGERPRINTPROC-20260814-001",
            "request_id": approvals.REQUEST_ID,
            "request_sha256": request_digest,
            "procedure_id": approvals.PROCEDURE_ID,
            "procedure_path": approvals.PROCEDURE_PATH.as_posix(),
            "procedure_sha256": approvals.sha256_file(self.root / approvals.PROCEDURE_PATH),
            "decision": "APPROVED",
            "decided_at": "2026-08-14T12:00:00Z",
            "decided_by": {"name": "Repository Owner", "role": "Project owner"},
            "acknowledgements": {
                "reviewed_exact_procedure_bytes": True,
                "procedure_identifies_but_does_not_authorize_target": True,
                "no_target_approved": True,
                "no_execution_authorized": True,
                "no_adapter_or_controller_activation_authorized": True,
                "no_h0_stage_advanced": True,
            },
        }

    def test_checked_in_request_is_exact_and_channel_state_is_valid(self) -> None:
        request, digest = approvals.validate_request_artifacts(ROOT)
        self.assertEqual(
            digest,
            "324a976c0918de06cf33a72b5f9edfef9c4eae94a5afed35e41031ec46e98d05",
        )
        self.assertEqual(request["status"], "AWAITING_HUMAN_DECISION")
        decision_path = ROOT / approvals.DECISION_PATH

        if not decision_path.exists():
            result = approvals.assess_repository_channel(ROOT)
            self.assertFalse(result.approved)
            self.assertEqual(result.status, "AWAITING_HUMAN_DECISION")
            self.assertIsNone(result.approval_id)
            self.assertIsNone(result.approval_reference)
        else:
            result = approvals.validate_committed_decision(ROOT)
            self.assertIn(result.status, {"APPROVED", "REJECTED"})
            self.assertEqual(result.approved, result.status == "APPROVED")
            self.assertIsNotNone(result.approval_id)
            self.assertIsNotNone(result.approval_reference)
            self.assertTrue(result.approval_reference.startswith("git:"))
            self.assertTrue(
                result.approval_reference.endswith(
                    f":{approvals.DECISION_PATH.as_posix()}"
                )
            )
            self.assertEqual(result.procedure_sha256, request["procedure_sha256"])
            self.assertEqual(result.decided_role, "Project owner")

    def test_absent_decision_remains_pending(self) -> None:
        result = approvals.assess_repository_channel(self.root)

        self.assertFalse(result.approved)
        self.assertEqual(result.status, "AWAITING_HUMAN_DECISION")
        self.assertIsNone(result.approval_id)
        self.assertIsNone(result.approval_reference)

    def test_schema_and_validator_reject_template_tamper_and_wider_authority(self) -> None:
        schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
        Draft202012Validator.check_schema(schema)
        decision = self.decision()
        self.assertFalse(
            list(Draft202012Validator(schema, format_checker=FormatChecker()).iter_errors(decision))
        )
        approvals.validate_decision_value(
            self.root,
            decision,
            now=datetime(2026, 8, 14, 13, 0, tzinfo=timezone.utc),
        )

        template = json.loads(TEMPLATE.read_text(encoding="utf-8"))
        with self.assertRaisesRegex(approvals.ProcedureApprovalError, "template"):
            approvals.validate_decision_value(self.root, template)

        for mutation in ("target", "authorizes_execution"):
            widened = copy.deepcopy(decision)
            widened[mutation] = True
            with self.subTest(mutation=mutation), self.assertRaisesRegex(
                approvals.ProcedureApprovalError, "field mismatch"
            ):
                approvals.validate_decision_value(self.root, widened)

        false_acknowledgement = copy.deepcopy(decision)
        false_acknowledgement["acknowledgements"]["no_target_approved"] = False
        with self.assertRaisesRegex(approvals.ProcedureApprovalError, "acknowledgements"):
            approvals.validate_decision_value(self.root, false_acknowledgement)

    def test_contract_or_review_drift_blocks_without_fallback(self) -> None:
        contract = self.root / approvals.PROCEDURE_PATH
        contract.write_bytes(contract.read_bytes() + b"\n")
        with self.assertRaisesRegex(approvals.ProcedureApprovalError, "exact procedure bytes"):
            approvals.validate_request_artifacts(self.root)

        shutil.copy2(ROOT / approvals.PROCEDURE_PATH, contract)
        review = self.root / approvals.REVIEW_PATH
        review.write_text(review.read_text(encoding="utf-8") + "drift\n", encoding="utf-8")
        with self.assertRaisesRegex(approvals.ProcedureApprovalError, "review view changed"):
            approvals.validate_request_artifacts(self.root)

    def test_only_committed_unmodified_human_attributed_decision_is_accepted(self) -> None:
        decision_path = self.root / approvals.DECISION_PATH
        decision_path.parent.mkdir(parents=True, exist_ok=True)
        decision_path.write_bytes(approvals.canonical_bytes(self.decision()))

        subprocess.run(["git", "init", "-q"], cwd=self.root, check=True)
        subprocess.run(
            ["git", "config", "user.name", "Repository Owner"], cwd=self.root, check=True
        )
        subprocess.run(
            ["git", "config", "user.email", "owner@example.invalid"], cwd=self.root, check=True
        )
        subprocess.run(["git", "add", "."], cwd=self.root, check=True)
        environment = {
            **os.environ,
            "GIT_AUTHOR_DATE": "2026-08-14T12:01:00Z",
            "GIT_COMMITTER_DATE": "2026-08-14T12:01:00Z",
        }
        subprocess.run(
            ["git", "commit", "-q", "-m", "Human procedure decision"],
            cwd=self.root,
            env=environment,
            check=True,
        )

        result = approvals.validate_committed_decision(
            self.root,
            now=datetime(2026, 8, 14, 13, 0, tzinfo=timezone.utc),
        )
        self.assertTrue(result.approved)
        self.assertEqual(result.status, "APPROVED")
        self.assertTrue(result.approval_reference.startswith("git:"))
        self.assertTrue(result.approval_reference.endswith(approvals.DECISION_PATH.as_posix()))

        decision_path.write_bytes(decision_path.read_bytes() + b"\n")
        with self.assertRaisesRegex(approvals.ProcedureApprovalError, "canonically serialized"):
            approvals.validate_committed_decision(self.root)

    def test_rejection_is_attributable_but_never_approval(self) -> None:
        decision = self.decision()
        decision["decision"] = "REJECTED"

        decision_path = self.root / approvals.DECISION_PATH
        decision_path.parent.mkdir(parents=True, exist_ok=True)
        decision_path.write_bytes(approvals.canonical_bytes(decision))

        subprocess.run(["git", "init", "-q"], cwd=self.root, check=True)
        subprocess.run(
            ["git", "config", "user.name", "Repository Owner"], cwd=self.root, check=True
        )
        subprocess.run(
            ["git", "config", "user.email", "owner@example.invalid"],
            cwd=self.root,
            check=True,
        )
        subprocess.run(["git", "add", "."], cwd=self.root, check=True)
        environment = {
            **os.environ,
            "GIT_AUTHOR_DATE": "2026-08-14T12:01:00Z",
            "GIT_COMMITTER_DATE": "2026-08-14T12:01:00Z",
        }
        subprocess.run(
            ["git", "commit", "-q", "-m", "Human procedure rejection"],
            cwd=self.root,
            env=environment,
            check=True,
        )

        result = approvals.validate_committed_decision(
            self.root,
            now=datetime(2026, 8, 14, 13, 0, tzinfo=timezone.utc),
        )
        self.assertEqual(result.status, "REJECTED")
        self.assertFalse(result.approved)
        self.assertIsNotNone(result.approval_reference)


if __name__ == "__main__":
    unittest.main()
