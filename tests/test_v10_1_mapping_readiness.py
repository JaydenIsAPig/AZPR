import csv
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).parents[1]
APPROVED_BASE = "ce80d335aef52c8900bd363bbcfacc1e497c0404"
SCRIPT = ROOT / "scripts" / "check_v10_1_mapping_readiness.py"
SPEC = importlib.util.spec_from_file_location("mapping_readiness", SCRIPT)
assert SPEC and SPEC.loader
mapping_readiness = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(mapping_readiness)


class V101MappingReadinessTests(unittest.TestCase):
    mapping = (
        ROOT
        / "docs"
        / "delivery-provenance"
        / "v10.1"
        / "integration"
        / "AZPR-v10.1-integration-path-mapping.csv"
    )
    contract = ROOT / "automation" / "integration" / "v10.1" / "controller-transition-contract.json"
    validation = (
        ROOT
        / "docs"
        / "delivery-provenance"
        / "v10.1"
        / "validation"
        / "AZPR-v10.1-staging-validation.json"
    )
    attempts = (
        ROOT
        / "docs"
        / "delivery-provenance"
        / "v10.1"
        / "validation"
        / "delivery-verifier-attempts.json"
    )

    def assess(
        self,
        mapping: Path | None = None,
        contract: Path | None = None,
        attempts: Path | None = None,
        head: str = APPROVED_BASE,
    ):
        return mapping_readiness.assess(
            mapping or self.mapping,
            contract or self.contract,
            self.validation,
            attempts or self.attempts,
            root=ROOT,
            head=head,
        )

    def test_current_mapping_is_structurally_ready_but_final_approval_is_deferred(self) -> None:
        result = self.assess()
        self.assertEqual(result["errors"], [])
        self.assertTrue(result["mapping_structurally_ready_for_review"])
        self.assertFalse(result["mapping_ready_for_human_approval"])
        self.assertFalse(result["final_mapping_approval_eligible"])
        self.assertTrue(result["checks"]["deterministic_mapping_matches"])
        self.assertTrue(result["checks"]["verifier_evidence_valid"])
        self.assertTrue(result["checks"]["both_delivery_verifiers_pass"])
        self.assertFalse(result["checks"]["formal_int_01_verification_present"])
        self.assertTrue(result["checks"]["transition_base_human_approved"])
        self.assertTrue(result["checks"]["head_descends_from_approved_base"])
        self.assertEqual(result["base_commit"], APPROVED_BASE)
        self.assertEqual(result["head_commit"], APPROVED_BASE)
        self.assertFalse(result["checks"]["h0_ansible_preparation_complete"])
        self.assertTrue(result["checks"]["h0_ansible_contract_valid"])
        self.assertEqual(
            result["checks"]["h0_ansible_status"],
            "IMPLEMENTED_PENDING_LIVE_VALIDATION",
        )
        self.assertTrue(result["pre_ansible_transition_base_ready"])
        self.assertFalse(result["ready_for_materialization"])
        self.assertFalse(result["ready_for_activation"])
        self.assertFalse(result["safe_for_unattended_execution_now"])
        self.assertEqual(
            result["next_required_action"],
            "COMPLETE_H0_ANSIBLE_LIVE_CHECK_AND_IDEMPOTENCE_VALIDATION",
        )

    def test_prequalification_pass_cannot_impersonate_formal_int_01(self) -> None:
        value = json.loads(self.attempts.read_text(encoding="utf-8"))
        self.assertEqual(value["status"], "PASS_PREQUALIFICATION_ONLY")
        self.assertIsNone(value["formal_stage_id"])
        result = self.assess()
        self.assertTrue(result["checks"]["both_delivery_verifiers_pass"])
        self.assertFalse(result["checks"]["formal_int_01_verification_present"])
        self.assertFalse(result["ready_for_materialization"])

    def test_external_activation_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            altered = Path(directory) / "contract.json"
            value = json.loads(self.contract.read_text(encoding="utf-8"))
            value["controller_states"]["external_controller"]["activation_allowed"] = True
            altered.write_text(json.dumps(value), encoding="utf-8")
            result = self.assess(contract=altered)
        self.assertFalse(result["mapping_structurally_ready_for_review"])
        self.assertTrue(any("external controller" in error for error in result["errors"]))

    def test_unknown_intent_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            altered = Path(directory) / "mapping.csv"
            with self.mapping.open(newline="", encoding="utf-8") as source:
                reader = csv.DictReader(source)
                rows = list(reader)
                fields = reader.fieldnames
            assert fields
            rows[0]["conflict_status"] = "UNKNOWN_INTENT"
            with altered.open("w", newline="", encoding="utf-8") as target:
                writer = csv.DictWriter(target, fieldnames=fields)
                writer.writeheader()
                writer.writerows(rows)
            result = self.assess(mapping=altered)
        self.assertFalse(result["mapping_structurally_ready_for_review"])
        self.assertTrue(any("unresolved conflict" in error for error in result["errors"]))

    def test_omitted_passive_overlay_row_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            altered = Path(directory) / "mapping.csv"
            with self.mapping.open(newline="", encoding="utf-8") as source:
                reader = csv.DictReader(source)
                rows = list(reader)
                fields = reader.fieldnames
            assert fields
            rows.pop(100)
            with altered.open("w", newline="", encoding="utf-8") as target:
                writer = csv.DictWriter(target, fieldnames=fields)
                writer.writeheader()
                writer.writerows(rows)
            result = self.assess(mapping=altered)
        self.assertFalse(result["mapping_structurally_ready_for_review"])
        self.assertTrue(any("omits deterministic dispositions" in error for error in result["errors"]))

    def test_unsafe_destination_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            altered = Path(directory) / "mapping.csv"
            with self.mapping.open(newline="", encoding="utf-8") as source:
                reader = csv.DictReader(source)
                rows = list(reader)
                fields = reader.fieldnames
            assert fields
            row = next(candidate for candidate in rows if candidate["proposed_destination"])
            row["proposed_destination"] = "../../outside"
            with altered.open("w", newline="", encoding="utf-8") as target:
                writer = csv.DictWriter(target, fieldnames=fields)
                writer.writeheader()
                writer.writerows(rows)
            result = self.assess(mapping=altered)
        self.assertFalse(result["mapping_structurally_ready_for_review"])
        self.assertTrue(any("unsafe proposed_destination" in error for error in result["errors"]))

    def test_verifier_expected_count_cannot_be_lowered(self) -> None:
        forged = {
            "status": "PASS",
            "source_tree": {"status": "PASS", "exit_code": 0, "tests_expected": 1, "tests_passed": 1},
            "fresh_extraction": {"status": "PASS", "exit_code": 0, "tests_expected": 1, "tests_passed": 1},
        }
        counts, passed = mapping_readiness.verifier_status({}, forged)
        self.assertEqual(counts["expected"], 120)
        self.assertFalse(passed)

    def test_fabricated_verifier_summary_lacks_raw_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            forged = Path(directory) / "attempts.json"
            value = {
                "status": "PASS",
                "candidate": {
                    "implementation_archive_sha256": "0" * 64,
                    "prompt_archive_sha256": "0" * 64,
                },
                "runtime": {"network_used_during_verification": False},
                "source_tree": {"status": "PASS", "exit_code": 0, "tests_expected": 120, "tests_passed": 120},
                "fresh_extraction": {"status": "PASS", "exit_code": 0, "tests_expected": 120, "tests_passed": 120},
            }
            forged.write_text(json.dumps(value), encoding="utf-8")
            result = self.assess(attempts=forged)
        self.assertFalse(result["checks"]["both_delivery_verifiers_pass"])
        self.assertFalse(result["checks"]["verifier_evidence_valid"])

    def test_empty_human_approval_is_invalid(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            approval = Path(directory) / "approval.json"
            approval.write_text("{}", encoding="utf-8")
            valid, issues = mapping_readiness.approval_binding_status(
                approval,
                mapping_path=self.mapping,
                contract_path=self.contract,
                verifier_attempts_path=self.attempts,
                base_commit=APPROVED_BASE,
                prompt_sha256="3b235cb7e33ca409241ff26523f60f8fee89cec524b3f09e91a69927a0aa4880",
            )
        self.assertFalse(valid)
        self.assertTrue(any("mapping_sha256" in issue for issue in issues))

    def test_exact_human_approval_bindings_are_accepted(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            approval = Path(directory) / "approval.json"
            value = {
                "format_version": "1.0",
                "approval_kind": "AZPR_V10_1_INTEGRATION_MAPPING_APPROVAL",
                "approved": True,
                "base_commit": APPROVED_BASE,
                "mapping_sha256": mapping_readiness.sha256(self.mapping),
                "transition_contract_sha256": mapping_readiness.sha256(self.contract),
                "prompt_archive_sha256": "3b235cb7e33ca409241ff26523f60f8fee89cec524b3f09e91a69927a0aa4880",
                "prompt_stage_hash_manifest_sha256": mapping_readiness.sha256(
                    ROOT
                    / "automation"
                    / "integration"
                    / "v10.1"
                    / "prompt-stages"
                    / "SHA256SUMS.json"
                ),
                "verifier_evidence_sha256": mapping_readiness.sha256(self.attempts),
                "approved_by": "test-reviewer",
                "approved_at": "2026-08-07T00:00:00Z",
            }
            approval.write_text(json.dumps(value), encoding="utf-8")
            valid, issues = mapping_readiness.approval_binding_status(
                approval,
                mapping_path=self.mapping,
                contract_path=self.contract,
                verifier_attempts_path=self.attempts,
                base_commit=value["base_commit"],
                prompt_sha256=value["prompt_archive_sha256"],
            )
        self.assertTrue(valid)
        self.assertEqual(issues, [])

    def test_prompt_stage_contract_authority_widening_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            altered = Path(directory) / "contract.json"
            value = json.loads(self.contract.read_text(encoding="utf-8"))
            value["orchestration_prompt_pack"]["automatic_stage_advancement"] = True
            altered.write_text(json.dumps(value), encoding="utf-8")
            result = self.assess(contract=altered)
        self.assertFalse(result["mapping_structurally_ready_for_review"])
        self.assertTrue(
            any("automatic stage advancement" in error for error in result["errors"])
        )

    def test_transition_base_must_bind_the_human_approved_commit(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            altered = Path(directory) / "contract.json"
            value = json.loads(self.contract.read_text(encoding="utf-8"))
            value["transition_base"]["commit"] = value["transition_base"]["parent_commit"]
            altered.write_text(json.dumps(value), encoding="utf-8")
            result = self.assess(contract=altered)
        self.assertFalse(result["mapping_structurally_ready_for_review"])
        self.assertTrue(any("transition-base" in error for error in result["errors"]))

    def test_controller_owned_descendant_commit_preserves_transition_base(self) -> None:
        descendant = "5" * 40
        with mock.patch.object(
            mapping_readiness,
            "commit_is_ancestor",
            return_value=True,
        ):
            result = self.assess(head=descendant)
        self.assertTrue(result["mapping_structurally_ready_for_review"])
        self.assertTrue(result["checks"]["head_descends_from_approved_base"])
        self.assertEqual(result["base_commit"], APPROVED_BASE)
        self.assertEqual(result["head_commit"], descendant)

    def test_unrelated_head_fails_approved_base_lineage(self) -> None:
        unrelated = "f" * 40
        with mock.patch.object(
            mapping_readiness,
            "commit_is_ancestor",
            return_value=False,
        ):
            result = self.assess(head=unrelated)
        self.assertFalse(result["mapping_structurally_ready_for_review"])
        self.assertFalse(result["checks"]["head_descends_from_approved_base"])
        self.assertTrue(any("does not descend" in error for error in result["errors"]))

    def test_int_00_cannot_be_unblocked_during_pre_ansible_preparation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            altered = Path(directory) / "contract.json"
            value = json.loads(self.contract.read_text(encoding="utf-8"))
            value["pre_int00_lifecycle"]["int_00_status"] = "ELIGIBLE"
            altered.write_text(json.dumps(value), encoding="utf-8")
            result = self.assess(contract=altered)
        self.assertFalse(result["mapping_structurally_ready_for_review"])
        self.assertTrue(any("INT-00" in error for error in result["errors"]))

    def test_delivery_audit_cannot_be_promoted_to_formal_authority(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            altered = Path(directory) / "contract.json"
            value = json.loads(self.contract.read_text(encoding="utf-8"))
            value["audit_authority"]["delivery_audit_authoritative"] = True
            altered.write_text(json.dumps(value), encoding="utf-8")
            result = self.assess(contract=altered)
        self.assertFalse(result["mapping_structurally_ready_for_review"])
        self.assertTrue(any("audit-authority" in error for error in result["errors"]))

    def test_generated_byte_binding_drift_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            altered = Path(directory) / "mapping.csv"
            with self.mapping.open(newline="", encoding="utf-8") as source:
                reader = csv.DictReader(source)
                rows = list(reader)
                fields = reader.fieldnames
            assert fields
            row = next(
                candidate
                for candidate in rows
                if candidate["source_archive"] == "INTEGRATION_GENERATED"
            )
            row["source_sha256"] = "0" * 64
            with altered.open("w", newline="", encoding="utf-8") as target:
                writer = csv.DictWriter(target, fieldnames=fields)
                writer.writeheader()
                writer.writerows(rows)
            result = self.assess(mapping=altered)
        self.assertFalse(result["mapping_structurally_ready_for_review"])
        self.assertTrue(any("generated preparation bytes drifted" in error for error in result["errors"]))

    def test_unmapped_current_file_drift_is_not_preserved(self) -> None:
        with mock.patch.object(
            mapping_readiness,
            "observed_worktree_paths",
            return_value=({"automation/controller.config.json"}, None),
        ):
            result = self.assess()
        self.assertFalse(result["checks"]["worktree_clean_or_mapping_preserved"])
        self.assertEqual(
            result["checks"]["unbound_worktree_changes"],
            ["automation/controller.config.json"],
        )

    def test_nonidentical_verifier_trees_fail_evidence_binding(self) -> None:
        value = json.loads(self.attempts.read_text(encoding="utf-8"))
        value["candidate"]["source_and_fresh_trees_byte_identical_after_attempts"] = False
        with tempfile.TemporaryDirectory() as directory:
            altered = Path(directory) / "attempts.json"
            altered.write_text(json.dumps(value), encoding="utf-8")
            result = self.assess(attempts=altered)
        self.assertFalse(result["checks"]["verifier_evidence_valid"])


if __name__ == "__main__":
    unittest.main()
