from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path

from automation import approval_manager as approvals


ROOT = Path(__file__).resolve().parents[1]


class ApprovalManagerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        evidence = self.root / "evidence.json"
        evidence.write_text('{"evidence":true}\n', encoding="utf-8")
        self.manifest = {
            "format_version": "1.0",
            "manifest_kind": "AZPR_STAGE_APPROVAL_MANIFEST",
            "approval_id": "AZPR-H0-TRANSPORT-20260807-001",
            "revision": None,
            "stage_id": "H0-T02",
            "title": "Transport test",
            "lifecycle": "H0",
            "scope": "TRANSPORT",
            "issued_on": "2026-08-07",
            "validity": {
                "activation_event": "AUTHENTICATED_DECISION",
                "maximum_duration_seconds": 7200,
                "expiry_rule": "EARLIER_OF_COMPLETION_OR_TWO_HOURS",
            },
            "actions": [
                {
                    "action_id": "ACT-001",
                    "kind": "SCOPED_CHANGE",
                    "target": {"guest": "disposable-1", "port": 22},
                    "permission": "Change only the named disposable target.",
                    "expected_effect": "The bounded transport probe succeeds.",
                    "test": {"method": "Probe the target.", "expected_result": "PASS"},
                    "stop_condition": "Stop on any mismatch or collateral effect.",
                }
            ],
            "security_boundary": {
                "prohibited_changes": ["No other target or permission."],
                "rollback_required": True,
            },
            "authentication_policy": {
                "authenticated_decision_required": True,
                "adapter": "TRUSTED_CONTROLLER_ADAPTER_REQUIRED",
                "allowed_roles": ["Head of AZPR Operations"],
                "digest_challenge_required": True,
            },
            "evidence": [
                {
                    "path": "evidence.json",
                    "sha256": approvals.digest_file(evidence),
                    "purpose": "Test evidence",
                }
            ],
            "related_records": [],
            "notes": ["Test only"],
        }

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def write_manifest(self, value: dict | None = None) -> Path:
        path = self.root / "stage-manifest.json"
        path.write_text(json.dumps(value or self.manifest, indent=2) + "\n", encoding="utf-8")
        return path

    def generate(self) -> tuple[Path, Path, Path, str]:
        manifest = self.write_manifest()
        ticket = self.root / "ticket.json"
        review = self.root / "review.md"
        digest = approvals.generate_ticket_artifacts(self.root, manifest, ticket, review)
        return manifest, ticket, review, digest

    def authentication(self, digest: str) -> approvals.VerifiedAuthentication:
        return approvals.VerifiedAuthentication(
            subject="operator-123",
            role="Head of AZPR Operations",
            authenticator_id="trusted-controller-test-adapter",
            authentication_event_id="auth-event-001",
            authenticated_at="2026-08-07T20:00:00Z",
            ticket_digest_challenge=digest,
        )

    def test_generation_is_canonical_stable_and_manifest_bound(self) -> None:
        manifest, ticket, review, digest = self.generate()
        self.assertEqual(ticket.read_bytes(), approvals.canonical_bytes(json.loads(ticket.read_text())))
        self.assertEqual(digest, approvals.validate_ticket_artifacts(self.root, manifest, ticket, review))
        self.assertEqual(digest, approvals.digest_file(ticket))
        self.assertIn(digest, review.read_text(encoding="utf-8"))

    def test_missing_fields_or_evidence_fail_closed(self) -> None:
        missing_action_field = copy.deepcopy(self.manifest)
        del missing_action_field["actions"][0]["stop_condition"]
        with self.assertRaisesRegex(approvals.ApprovalError, "field mismatch"):
            approvals.build_ticket(self.root, self.write_manifest(missing_action_field))

        (self.root / "evidence.json").unlink()
        with self.assertRaisesRegex(approvals.ApprovalError, "evidence is missing"):
            approvals.build_ticket(self.root, self.write_manifest())

    def test_ticket_or_review_change_invalidates_checkpoint(self) -> None:
        manifest, ticket, review, _ = self.generate()
        review.write_text(review.read_text() + "changed\n", encoding="utf-8")
        with self.assertRaisesRegex(approvals.ApprovalError, "review view changed"):
            approvals.validate_ticket_artifacts(self.root, manifest, ticket, review)

        approvals.generate_ticket_artifacts(self.root, manifest, ticket, review)
        ticket.write_bytes(ticket.read_bytes() + b"\n")
        with self.assertRaisesRegex(approvals.ApprovalError, "not canonically serialized"):
            approvals.validate_ticket_artifacts(self.root, manifest, ticket, review)

    def test_authenticated_decision_binds_digest_expiry_and_targets(self) -> None:
        manifest, ticket_path, review, digest = self.generate()
        ticket = approvals.load_canonical_object(ticket_path)
        decision = approvals.bind_authenticated_decision(
            ticket,
            self.authentication(digest),
            decision="APPROVED",
            decided_at="2026-08-07T20:01:00Z",
            expires_at="2026-08-07T22:01:00Z",
        )
        decision_path = self.root / "decision.json"
        approvals.write_canonical(decision_path, decision)
        observed = {item["action_id"]: item["target"] for item in ticket["actions"]}

        authorization = approvals.authorize_execution(
            root=self.root,
            manifest_path=manifest,
            ticket_path=ticket_path,
            review_path=review,
            decision_path=decision_path,
            observed_targets=observed,
            authentication_verifier=lambda _: self.authentication(digest),
            now="2026-08-07T20:30:00Z",
        )
        self.assertEqual(authorization["approval_id"], ticket["approval_id"])

        different_event = approvals.VerifiedAuthentication(
            **{**self.authentication(digest).__dict__, "authentication_event_id": "different"}
        )
        with self.assertRaisesRegex(approvals.ApprovalError, "could not be reverified"):
            approvals.authorize_execution(
                root=self.root,
                manifest_path=manifest,
                ticket_path=ticket_path,
                review_path=review,
                decision_path=decision_path,
                observed_targets=observed,
                authentication_verifier=lambda _: different_event,
                now="2026-08-07T20:30:00Z",
            )

        with self.assertRaisesRegex(approvals.ApprovalError, "targets no longer"):
            approvals.authorize_execution(
                root=self.root,
                manifest_path=manifest,
                ticket_path=ticket_path,
                review_path=review,
                decision_path=decision_path,
                observed_targets={"ACT-001": {"guest": "different", "port": 22}},
                authentication_verifier=lambda _: self.authentication(digest),
                now="2026-08-07T20:30:00Z",
            )
        with self.assertRaisesRegex(approvals.ApprovalError, "expired"):
            approvals.authorize_execution(
                root=self.root,
                manifest_path=manifest,
                ticket_path=ticket_path,
                review_path=review,
                decision_path=decision_path,
                observed_targets=observed,
                authentication_verifier=lambda _: self.authentication(digest),
                now="2026-08-07T22:01:00Z",
            )

    def test_digest_mismatch_and_unverified_authentication_fail(self) -> None:
        _, ticket_path, _, digest = self.generate()
        ticket = approvals.load_canonical_object(ticket_path)
        wrong = copy.copy(self.authentication(digest))
        wrong = approvals.VerifiedAuthentication(**{**wrong.__dict__, "ticket_digest_challenge": "0" * 64})
        with self.assertRaisesRegex(approvals.ApprovalError, "digest"):
            approvals.bind_authenticated_decision(
                ticket,
                wrong,
                decision="APPROVED",
                decided_at="2026-08-07T20:01:00Z",
                expires_at="2026-08-07T21:00:00Z",
            )

    def test_outcome_is_separate_and_related_ids_are_consistent(self) -> None:
        authorization = {
            "record_kind": "AZPR_EXECUTION_AUTHORIZATION",
            "approval_id": "AZPR-H0-TRANSPORT-20260807-001",
            "ticket_id": "AZPR-H0-TRANSPORT-20260807-001",
            "ticket_sha256": "a" * 64,
        }
        outcome = approvals.create_outcome_record(
            authorization,
            lifecycle="H0",
            run_id="AZPR-RUN-H0-20260807-0042",
            outcome_id="AZPR-OUT-H0-20260807-0042",
            evidence_id="AZPR-EVD-H0-20260807-0042",
            outcome="SUCCEEDED",
            completed_at="2026-08-07T21:00:00Z",
            action_results=[{"action_id": "ACT-001", "result": "PASS"}],
            evidence_bindings=[{"path": "evidence.json", "sha256": "b" * 64}],
        )
        self.assertFalse(outcome["approval_is_execution_result"])
        self.assertEqual(outcome["approval_id"], authorization["approval_id"])
        with self.assertRaisesRegex(approvals.ApprovalError, "share date and sequence"):
            approvals.create_outcome_record(
                authorization,
                lifecycle="H0",
                run_id="AZPR-RUN-H0-20260807-0042",
                outcome_id="AZPR-OUT-H0-20260807-0043",
                evidence_id="AZPR-EVD-H0-20260807-0042",
                outcome="FAILED",
                completed_at="2026-08-07T21:00:00Z",
                action_results=[{"action_id": "ACT-001", "result": "FAIL"}],
                evidence_bindings=[{"path": "evidence.json", "sha256": "b" * 64}],
            )

    def test_revision_and_delta_rules_fail_closed(self) -> None:
        ticket = approvals.build_ticket(self.root, self.write_manifest())
        revision_manifest = copy.deepcopy(self.manifest)
        revision_manifest["revision"] = "R01"
        revision_manifest["notes"].append("Clarified review note")
        revision = approvals.build_ticket(self.root, self.write_manifest(revision_manifest))
        self.assertEqual(approvals.assess_revision(ticket, revision), "SIMPLE_REVISION")

        material = copy.deepcopy(revision)
        material["actions"][0]["target"]["port"] = 2222
        with self.assertRaisesRegex(approvals.ApprovalError, "requires a new approval ID"):
            approvals.assess_revision(ticket, material)
        self.assertTrue(approvals.remediation_exceeds_authority(ticket, [material["actions"][0]]))
        self.assertFalse(approvals.remediation_exceeds_authority(ticket, [ticket["actions"][0]]))

        within_scope_delta = copy.deepcopy(self.manifest)
        within_scope_delta["approval_id"] = "AZPR-H0-TRANSPORT-20260807-002"
        within_scope_delta["related_records"] = [ticket["approval_id"]]
        with self.assertRaisesRegex(approvals.ApprovalError, "must not be generated"):
            approvals.build_delta_ticket(
                self.root,
                ticket,
                self.write_manifest(within_scope_delta),
            )

        real_delta = copy.deepcopy(within_scope_delta)
        real_delta["actions"][0]["target"]["port"] = 2222
        delta = approvals.build_delta_ticket(
            self.root,
            ticket,
            self.write_manifest(real_delta),
        )
        self.assertEqual(delta["approval_id"], "AZPR-H0-TRANSPORT-20260807-002")

    def test_checked_in_h0_ticket_and_review_are_current(self) -> None:
        manifest = ROOT / "automation/approvals/stage-manifests/AZPR-H0-TRANSPORT-20260807-001.json"
        ticket = ROOT / "automation/approvals/tickets/AZPR-H0-TRANSPORT-20260807-001.json"
        review = ROOT / "automation/approvals/reviews/AZPR-H0-TRANSPORT-20260807-001.md"
        digest = approvals.validate_ticket_artifacts(ROOT, manifest, ticket, review)
        self.assertEqual(digest, "f74a416c8770f7268e8fa2353c880ed46c65adf9ddad67f38db29859373aef67")


if __name__ == "__main__":
    unittest.main()
