import hashlib
import importlib.util
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).parents[1]
RUNNER_PATH = ROOT / "infrastructure" / "ansible" / "tests" / "run_idempotence.py"
CHECKER_PATH = ROOT / "scripts" / "check_h0_ansible.py"


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


runner = load_module("h0_idempotence_runner", RUNNER_PATH)
checker = load_module("h0_ansible_checker_live_paths", CHECKER_PATH)


def ansible_result(
    *,
    exit_code: int = 0,
    ok: int = 4,
    changed: int = 0,
    unreachable: int = 0,
    failed: int = 0,
):
    return {
        "command": ["ansible-playbook", "fixture.yml"],
        "exit_code": exit_code,
        "recap": {
            "ok": ok,
            "changed": changed,
            "unreachable": unreachable,
            "failed": failed,
        },
        "stdout_sha256": "0" * 64,
        "stderr_sha256": "1" * 64,
    }


class H0IdempotenceResultTests(unittest.TestCase):
    def passing_records(self):
        return (
            ansible_result(changed=0),
            ansible_result(changed=3),
            ansible_result(changed=0),
        )

    def test_successful_result_construction_uses_real_false(self) -> None:
        evidence, passed = runner.build_evidence("DISPOSABLE_TEST", *self.passing_records())
        self.assertTrue(passed)
        self.assertEqual(evidence["status"], "PASS")
        self.assertIs(evidence["qualification_effect"], False)
        self.assertEqual(evidence["second_apply"]["recap"]["changed"], 0)
        json.dumps(evidence)

    def test_every_phase_fails_on_nonzero_missing_or_bad_recap(self) -> None:
        mutations = {
            "nonzero": lambda value: {**value, "exit_code": 2},
            "missing_recap": lambda value: {**value, "recap": None},
            "failed": lambda value: {**value, "recap": {**value["recap"], "failed": 1}},
            "unreachable": lambda value: {
                **value,
                "recap": {**value["recap"], "unreachable": 1},
            },
        }
        for phase in range(3):
            for label, mutate in mutations.items():
                with self.subTest(phase=phase, condition=label):
                    records = list(self.passing_records())
                    records[phase] = mutate(records[phase])
                    evidence, passed = runner.build_evidence("DISPOSABLE_TEST", *records)
                    self.assertFalse(passed)
                    self.assertEqual(evidence["status"], "FAIL")

    def test_second_apply_fails_every_negative_idempotence_condition(self) -> None:
        for field in ("changed", "unreachable", "failed"):
            with self.subTest(field=field):
                records = list(self.passing_records())
                records[2] = ansible_result(**{field: 1})
                _evidence, passed = runner.build_evidence("DISPOSABLE_TEST", *records)
                self.assertFalse(passed)

    def test_missing_recap_fields_fail_closed(self) -> None:
        for field in ("ok", "changed", "unreachable", "failed"):
            with self.subTest(field=field):
                records = list(self.passing_records())
                del records[2]["recap"][field]
                _evidence, passed = runner.build_evidence("DISPOSABLE_TEST", *records)
                self.assertFalse(passed)

    def test_atomic_output_replaces_once_and_leaves_no_temporary_file(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "idempotence-result.json"
            evidence, _passed = runner.build_evidence("DISPOSABLE_TEST", *self.passing_records())
            with mock.patch.object(runner.os, "replace", wraps=os.replace) as replace:
                runner.atomic_json(output, evidence)
            replace.assert_called_once()
            temporary, destination = replace.call_args.args
            self.assertEqual(Path(destination), output)
            self.assertEqual(Path(temporary).parent, output.parent)
            self.assertEqual(json.loads(output.read_text(encoding="utf-8")), evidence)
            self.assertEqual(list(output.parent.glob(f".{output.name}.*")), [])

    def test_atomic_output_cleans_up_after_serialization_failure(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "idempotence-result.json"
            with mock.patch.object(runner.json, "dump", side_effect=ValueError("fixture")):
                with self.assertRaises(ValueError):
                    runner.atomic_json(output, {"status": "FAIL"})
            self.assertFalse(output.exists())
            self.assertEqual(list(output.parent.iterdir()), [])

    def test_run_hashes_output_without_retaining_secret_values(self) -> None:
        secret = "AZPR_TEST_CREDENTIAL_VALUE_MUST_NOT_APPEAR"
        with tempfile.TemporaryDirectory() as directory:
            executable = Path(directory) / "fake-ansible"
            executable.write_text(
                "#!/bin/sh\n"
                f"printf '%s\\n' '{secret}'\n"
                f"printf '%s\\n' '{secret}' >&2\n"
                "printf '%s\\n' 'azpr-validator : ok=4 changed=0 unreachable=0 failed=0'\n",
                encoding="utf-8",
            )
            executable.chmod(0o700)
            result = runner.run([str(executable)], dict(os.environ))
        serialized = json.dumps(result, sort_keys=True)
        self.assertNotIn(secret, serialized)
        self.assertNotIn("stdout", result)
        self.assertNotIn("stderr", result)
        self.assertEqual(
            result["stderr_sha256"],
            hashlib.sha256(f"{secret}\n".encode("utf-8")).hexdigest(),
        )


class H0ReviewerAndFailureGateTests(unittest.TestCase):
    variables_path = "infrastructure/ansible/inventories/qualification/group_vars/all.yml"
    preflight_path = "infrastructure/ansible/playbooks/qualification-preflight.yml"
    baseline_path = "infrastructure/ansible/roles/azpr_validator_baseline/tasks/main.yml"
    runtime_path = "infrastructure/ansible/roles/azpr_validator_runtime/tasks/main.yml"
    filesystem_path = "infrastructure/ansible/roles/azpr_validator_filesystem/tasks/main.yml"
    isolation_path = "infrastructure/ansible/roles/azpr_validator_isolation/tasks/main.yml"
    seal_path = "infrastructure/ansible/playbooks/qualification-seal.yml"
    reset_path = "infrastructure/ansible/playbooks/qualification-reset.yml"

    def read(self, path: str) -> str:
        return (ROOT / path).read_text(encoding="utf-8")

    def test_reviewer_username_ids_passwd_home_and_generated_home_agree(self) -> None:
        variables = json.loads(self.read(self.variables_path))
        self.assertEqual(
            (
                variables["azpr_reviewer_name"],
                variables["azpr_reviewer_uid"],
                variables["azpr_reviewer_gid"],
            ),
            ("ubuntu", 1000, 1000),
        )
        for path in (self.preflight_path, self.baseline_path, self.seal_path):
            value = self.read(path)
            self.assertIn("getent_passwd[azpr_reviewer_name][1]", value)
            self.assertIn("getent_passwd[azpr_reviewer_name][2]", value)
            self.assertIn("getent_passwd[azpr_reviewer_name][4]", value)
        isolation = self.read(self.isolation_path)
        self.assertIn("HOME={{ getent_passwd[azpr_reviewer_name][4] }}", isolation)
        self.assertNotIn("HOME=/home/oai", isolation)
        self.assertIn("generated verifier HOME", self.read(self.seal_path))

    def test_reset_is_bounded_and_preserves_approved_inputs(self) -> None:
        variables = json.loads(self.read(self.variables_path))
        reset = self.read(self.reset_path)
        self.assertEqual(variables["azpr_validation_root"], "/srv/azpr-validator")
        self.assertEqual(variables["azpr_approved_inputs_root"], "/srv/azpr-approved-inputs")
        self.assertIn("azpr_approved_inputs_root == '/srv/azpr-approved-inputs'", reset)
        self.assertIn('path: "/srv/azpr-validator"', reset)
        self.assertIn("state: absent", reset)
        self.assertNotIn('path: "/srv/azpr-approved-inputs"', reset)

    def test_reset_target_mutation_fails_the_contract(self) -> None:
        reset = self.read(self.reset_path).replace(
            'path: "/srv/azpr-validator"',
            'path: "/srv/azpr-approved-inputs"',
        )
        result = checker.validate(ROOT, overrides={self.reset_path: reset})
        self.assertFalse(result["valid"])
        self.assertTrue(any("preserve approved inputs" in error for error in result["errors"]))

    def test_live_failure_conditions_are_contract_enforced(self) -> None:
        cases = {
            "CANDIDATE_HASH_MISMATCH": [self.preflight_path],
            "PROMPT_HASH_MISMATCH": [self.preflight_path],
            "MISSING_OFFLINE_DEPENDENCY": [self.preflight_path, self.runtime_path],
            "WRONG_DEPENDENCY_HASH": [self.runtime_path],
            "UNEXPECTED_CREDENTIAL_ENVIRONMENT": [self.isolation_path, self.seal_path],
            "WRITABLE_CANDIDATE_TREE": [self.filesystem_path, self.seal_path],
            "UNEXPECTED_NETWORK_STATE": [self.seal_path],
            "RESET_OUTSIDE_BOUNDED_ROOT": [self.reset_path],
        }
        for gate, paths in cases.items():
            with self.subTest(gate=gate):
                overrides = {
                    path: self.read(path).replace(gate, "REMOVED_FAILURE_IDENTIFIER")
                    for path in paths
                }
                result = checker.validate(ROOT, overrides=overrides)
                self.assertFalse(result["valid"])
                self.assertTrue(
                    any(f"required failure gate is not implemented: {gate}" == error for error in result["errors"]),
                    result["errors"],
                )


if __name__ == "__main__":
    unittest.main()
