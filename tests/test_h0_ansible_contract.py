import importlib.util
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[1]
SCRIPT = ROOT / "scripts" / "check_h0_ansible.py"
SPEC = importlib.util.spec_from_file_location("h0_ansible", SCRIPT)
assert SPEC and SPEC.loader
h0_ansible = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(h0_ansible)


class H0AnsibleContractTests(unittest.TestCase):
    contract_path = "infrastructure/ansible/h0-qualification-contract.json"
    variables_path = "infrastructure/ansible/inventories/qualification/group_vars/all.yml"
    hosts_path = "infrastructure/ansible/inventories/qualification/hosts.example.yml"
    baseline_path = "infrastructure/ansible/roles/azpr_validator_baseline/tasks/main.yml"
    preflight_path = "infrastructure/ansible/playbooks/qualification-preflight.yml"
    approval_path = (
        "docs/delivery-provenance/v10.1/validation/"
        "linux-validation-environment-approval.template.json"
    )

    def read(self, path: str) -> str:
        return (ROOT / path).read_text(encoding="utf-8")

    def validate(self, path: str, value: str):
        return h0_ansible.validate(ROOT, overrides={path: value})

    def test_current_h0_ansible_contract_is_valid(self) -> None:
        result = h0_ansible.validate(ROOT)
        self.assertEqual(result["errors"], [])
        self.assertTrue(result["valid"])

    def test_ansible_cannot_receive_qualification_authority(self) -> None:
        contract = json.loads(self.read(self.contract_path))
        contract["authority_effect"]["qualifies_environment"] = True
        result = self.validate(self.contract_path, json.dumps(contract))
        self.assertFalse(result["valid"])
        self.assertTrue(any("authority effect" in error for error in result["errors"]))

    def test_inventory_cannot_fabricate_environment_approval(self) -> None:
        variables = json.loads(self.read(self.variables_path))
        variables["azpr_environment_approval_state"] = "HUMAN_APPROVED"
        variables["azpr_environment_id"] = "fabricated"
        result = self.validate(self.variables_path, json.dumps(variables))
        self.assertFalse(result["valid"])
        self.assertTrue(any("approval" in error for error in result["errors"]))

    def test_production_inventory_cannot_be_hidden_in_example(self) -> None:
        hosts = json.loads(self.read(self.hosts_path))
        hosts["all"]["children"]["production"] = {"hosts": {}}
        result = self.validate(self.hosts_path, json.dumps(hosts))
        self.assertFalse(result["valid"])
        self.assertTrue(any("exactly one qualification" in error for error in result["errors"]))

    def test_forbidden_command_module_fails_closed(self) -> None:
        value = self.read(self.preflight_path) + "\n    - name: unsafe\n      ansible.builtin.command: whoami\n"
        result = self.validate(self.preflight_path, value)
        self.assertFalse(result["valid"])
        self.assertTrue(any("forbidden modules" in error for error in result["errors"]))

    def test_missing_failure_gate_fails_closed(self) -> None:
        value = self.read(self.preflight_path).replace("UNSUPPORTED_ARCHITECTURE", "ARCH_FAILURE")
        baseline = self.read(self.baseline_path).replace("UNSUPPORTED_ARCHITECTURE", "ARCH_FAILURE")
        result = h0_ansible.validate(
            ROOT,
            overrides={self.preflight_path: value, self.baseline_path: baseline},
        )
        self.assertFalse(result["valid"])
        self.assertTrue(any("UNSUPPORTED_ARCHITECTURE" in error for error in result["errors"]))

    def test_privileged_task_requires_explicit_tag(self) -> None:
        value = self.read(self.baseline_path).replace("    - azpr_privileged\n    - azpr_packages", "    - azpr_packages")
        result = self.validate(self.baseline_path, value)
        self.assertFalse(result["valid"])
        self.assertTrue(any("azpr_privileged" in error for error in result["errors"]))

    def test_approval_template_cannot_be_prepopulated(self) -> None:
        approval = json.loads(self.read(self.approval_path))
        approval["approved"] = True
        approval["approver_name"] = "fabricated"
        result = self.validate(self.approval_path, json.dumps(approval))
        self.assertFalse(result["valid"])
        self.assertTrue(any("pre-approved" in error for error in result["errors"]))


if __name__ == "__main__":
    unittest.main()

