import hashlib
import importlib.util
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator


ROOT = Path(__file__).parents[1]
SCRIPT = ROOT / "scripts" / "check_h0_ansible_live_prompt_pack.py"
SPEC = importlib.util.spec_from_file_location("h0_ansible_live_prompt_pack", SCRIPT)
assert SPEC and SPEC.loader
live_pack = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(live_pack)


class H0AnsibleLivePromptPackTests(unittest.TestCase):
    pack = ROOT / live_pack.PACK_RELATIVE

    def copied_root(self, directory: str) -> Path:
        root = Path(directory)
        destination = root / live_pack.PACK_RELATIVE
        destination.parent.mkdir(parents=True)
        shutil.copytree(self.pack, destination)
        implementation = root / "scripts" / "h0_target_fingerprint.py"
        implementation.parent.mkdir(parents=True)
        shutil.copy2(ROOT / "scripts" / "h0_target_fingerprint.py", implementation)
        return root

    @staticmethod
    def refresh_hash(root: Path, filename: str) -> None:
        pack = root / live_pack.PACK_RELATIVE
        hashes_path = pack / "SHA256SUMS.json"
        hashes = json.loads(hashes_path.read_text(encoding="utf-8"))
        hashes["files"][filename] = hashlib.sha256((pack / filename).read_bytes()).hexdigest()
        hashes_path.write_text(
            json.dumps(hashes, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    def test_current_pack_is_valid_inert_and_four_staged(self) -> None:
        self.assertEqual(live_pack.validate_pack(ROOT), [])

    def test_changed_prompt_byte_fails_hash_binding(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self.copied_root(directory)
            prompt = root / live_pack.PACK_RELATIVE / "00-authority-and-target-preflight.md"
            prompt.write_text(prompt.read_text(encoding="utf-8") + "\nchanged\n", encoding="utf-8")
            errors = live_pack.validate_pack(root)
        self.assertTrue(any("byte hash mismatch" in error for error in errors))

    def test_stage_sequence_cannot_be_reordered(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self.copied_root(directory)
            manifest_path = root / live_pack.PACK_RELATIVE / "stage-manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["stages"][1], manifest["stages"][2] = (
                manifest["stages"][2],
                manifest["stages"][1],
            )
            manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
            self.refresh_hash(root, manifest_path.name)
            errors = live_pack.validate_pack(root)
        self.assertTrue(any("stage sequence" in error or "manifest" in error for error in errors))

    def test_pack_cannot_activate_operator_adapter(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self.copied_root(directory)
            manifest_path = root / live_pack.PACK_RELATIVE / "stage-manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["authority_effect"]["activates_operator_approval_adapter"] = True
            manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
            self.refresh_hash(root, manifest_path.name)
            errors = live_pack.validate_pack(root)
        self.assertTrue(any("grants authority" in error for error in errors))

    def test_apply_stage_must_remain_state_changing_and_human_authorized(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self.copied_root(directory)
            manifest_path = root / live_pack.PACK_RELATIVE / "stage-manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["stages"][2]["state_changing"] = False
            manifest["stages"][2]["requires_human_authorization"] = False
            manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
            self.refresh_hash(root, manifest_path.name)
            errors = live_pack.validate_pack(root)
        self.assertTrue(any("H0-ALV-02" in error and "manifest" in error for error in errors))

    def test_result_schema_cannot_allow_operator_adapter_activation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self.copied_root(directory)
            schema_path = root / live_pack.PACK_RELATIVE / "stage-result.schema.json"
            schema = json.loads(schema_path.read_text(encoding="utf-8"))
            schema["properties"]["safety"]["properties"][
                "operator_approval_adapter_activated"
            ] = {"type": "boolean"}
            schema_path.write_text(json.dumps(schema, indent=2) + "\n", encoding="utf-8")
            self.refresh_hash(root, schema_path.name)
            errors = live_pack.validate_pack(root)
        self.assertTrue(any("safety boundary widened" in error for error in errors))

    def test_operator_input_schema_cannot_allow_adapter_activation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self.copied_root(directory)
            schema_path = root / live_pack.PACK_RELATIVE / "operator-input.schema.json"
            schema = json.loads(schema_path.read_text(encoding="utf-8"))
            schema["properties"]["operator_approval_adapter"]["properties"][
                "activation_authorized"
            ] = {"type": "boolean"}
            schema_path.write_text(json.dumps(schema, indent=2) + "\n", encoding="utf-8")
            self.refresh_hash(root, schema_path.name)
            errors = live_pack.validate_pack(root)
        self.assertTrue(any("input schema permits adapter activation" in error for error in errors))

    def test_two_apply_command_and_disposable_scope_cannot_be_removed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self.copied_root(directory)
            prompt = root / live_pack.PACK_RELATIVE / "02-two-apply-idempotence.md"
            prompt.write_text(
                prompt.read_text(encoding="utf-8").replace(
                    "--environment-scope DISPOSABLE_TEST",
                    "--environment-scope OTHER",
                ),
                encoding="utf-8",
            )
            self.refresh_hash(root, prompt.name)
            errors = live_pack.validate_pack(root)
        self.assertTrue(any("H0-ALV-02" in error and "safeguard" in error for error in errors))

    def test_human_approval_prohibition_cannot_be_removed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self.copied_root(directory)
            prompt = root / live_pack.PACK_RELATIVE / "01-check-mode-and-diff-review.md"
            prompt.write_text(
                prompt.read_text(encoding="utf-8").replace(
                    "Do not create or modify a human approval file.",
                    "Handle approval as needed.",
                ),
                encoding="utf-8",
            )
            self.refresh_hash(root, prompt.name)
            errors = live_pack.validate_pack(root)
        self.assertTrue(any("H0-ALV-01" in error and "safeguard" in error for error in errors))

    def test_operator_input_cannot_preapprove_execution_or_review(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self.copied_root(directory)
            operator_path = root / live_pack.PACK_RELATIVE / "operator-input.template.json"
            operator = json.loads(operator_path.read_text(encoding="utf-8"))
            operator["authorization_reference"]["authorized"] = True
            operator["check_mode_review"]["accepted"] = True
            operator_path.write_text(json.dumps(operator, indent=2) + "\n", encoding="utf-8")
            self.refresh_hash(root, operator_path.name)
            errors = live_pack.validate_pack(root)
        self.assertTrue(any("pre-authorizes" in error for error in errors))
        self.assertTrue(any("pre-accepts" in error for error in errors))

    def test_target_fingerprint_cannot_claim_authorization_or_approval(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self.copied_root(directory)
            contract_path = root / live_pack.PACK_RELATIVE / "target-fingerprint-contract.json"
            contract = json.loads(contract_path.read_text(encoding="utf-8"))
            contract["status"] = "APPROVED"
            contract["authority_effect"]["authorizes_target"] = True
            contract_path.write_text(json.dumps(contract, indent=2) + "\n", encoding="utf-8")
            self.refresh_hash(root, contract_path.name)
            errors = live_pack.validate_pack(root)
        self.assertTrue(any("fingerprint" in error and "authority" in error for error in errors))
        self.assertTrue(any("bypasses procedure approval" in error for error in errors))

    def test_target_fingerprint_golden_vector_is_executable_and_hash_bound(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self.copied_root(directory)
            vectors_path = root / live_pack.PACK_RELATIVE / "target-fingerprint-test-vectors.json"
            vectors = json.loads(vectors_path.read_text(encoding="utf-8"))
            vectors["vectors"][0]["sha256"] = "0" * 64
            vectors_path.write_text(json.dumps(vectors, indent=2) + "\n", encoding="utf-8")
            self.refresh_hash(root, vectors_path.name)
            errors = live_pack.validate_pack(root)
        self.assertTrue(any("golden-vector SHA-256" in error for error in errors))

    def test_operator_assistance_chain_is_inert_and_hash_bound(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self.copied_root(directory)
            manifest_path = root / live_pack.PACK_RELATIVE / "stage-manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["operator_assistance"]["automatic_execution"] = True
            manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
            self.refresh_hash(root, manifest_path.name)
            errors = live_pack.validate_pack(root)
        self.assertTrue(any("operator-assistance manifest" in error for error in errors))

    def test_operator_assistance_cannot_treat_chat_as_approval(self) -> None:
        relative = "operator-assistance/00-repository-and-procedure-readiness.md"
        with tempfile.TemporaryDirectory() as directory:
            root = self.copied_root(directory)
            prompt = root / live_pack.PACK_RELATIVE / relative
            prompt.write_text(
                prompt.read_text(encoding="utf-8").replace(
                    "Do not accept chat text as that record.",
                    "Accept the conversation as approval.",
                ),
                encoding="utf-8",
            )
            self.refresh_hash(root, relative)
            errors = live_pack.validate_pack(root)
        self.assertTrue(any("H0-ALV-GUIDE-00" in error and "safeguard" in error for error in errors))

    def test_guest_guide_cannot_create_human_input(self) -> None:
        relative = "operator-assistance/01-guest-local-observation-and-target-decision.md"
        with tempfile.TemporaryDirectory() as directory:
            root = self.copied_root(directory)
            prompt = root / live_pack.PACK_RELATIVE / relative
            prompt.write_text(
                prompt.read_text(encoding="utf-8").replace(
                    "Do not create,\npopulate, or modify a human approval",
                    "Create and\npopulate a human approval",
                ),
                encoding="utf-8",
            )
            self.refresh_hash(root, relative)
            errors = live_pack.validate_pack(root)
        self.assertTrue(any("H0-ALV-GUIDE-01" in error and "safeguard" in error for error in errors))

    def test_assistance_result_schema_cannot_permit_unattended_success(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self.copied_root(directory)
            schema_path = root / live_pack.PACK_RELATIVE / "operator-assistance-result.schema.json"
            schema = json.loads(schema_path.read_text(encoding="utf-8"))
            schema["properties"]["outcome"]["enum"].append("PASS")
            schema_path.write_text(json.dumps(schema, indent=2) + "\n", encoding="utf-8")
            self.refresh_hash(root, schema_path.name)
            errors = live_pack.validate_pack(root)
        self.assertTrue(any("unattended success" in error for error in errors))

    def test_human_checkpoint_result_shape_is_schema_valid(self) -> None:
        schema = json.loads(
            (self.pack / "operator-assistance-result.schema.json").read_text(encoding="utf-8")
        )
        value = {
            "guide_id": "H0-ALV-GUIDE-00",
            "phase": "H0_PREPARATION",
            "outcome": "HUMAN_ACTION_REQUIRED",
            "summary": "Repository checks passed; deliberate guest-local entry is required.",
            "authority_effect": False,
            "automated_checks": [],
            "target_observation": None,
            "human_checkpoint": {
                "required": True,
                "checkpoint_id": "LOCAL_GUEST_SESSION_REQUIRED",
                "human_action": "Enter the approved local session and invoke H0-ALV-GUIDE-01.",
                "why_human_required": "Automation cannot choose or enter the target guest.",
                "required_inputs": ["Attributable procedure-approval reference"],
                "resume_with": "H0-ALV-GUIDE-01",
            },
            "safety": {
                "live_target_observed": False,
                "ansible_playbook_executed": False,
                "operator_input_created_or_modified_by_agent": False,
                "human_authorization_created_or_inferred_by_agent": False,
                "operator_approval_adapter_activated": False,
                "controller_activated": False,
                "h0_t02_executed": False,
                "host_transport_modified": False,
                "network_controls_modified": False,
                "protected_artifacts_modified": False,
                "git_commit_merge_or_push": False,
                "automatic_next_prompt_started": False,
            },
            "next_guide": "H0-ALV-GUIDE-01",
            "next_stage": None,
        }
        self.assertEqual(list(Draft202012Validator(schema).iter_errors(value)), [])
        invalid = dict(value)
        invalid["next_stage"] = "H0-ALV-00"
        self.assertNotEqual(list(Draft202012Validator(schema).iter_errors(invalid)), [])


if __name__ == "__main__":
    unittest.main()
