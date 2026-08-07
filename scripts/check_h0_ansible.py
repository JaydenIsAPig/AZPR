#!/usr/bin/env python3
"""Fail-closed contract and optional runtime checks for H0 Ansible infrastructure."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import tempfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
ANSIBLE_ROOT = Path("infrastructure/ansible")
CONTRACT = ANSIBLE_ROOT / "h0-qualification-contract.json"
APPROVAL_TEMPLATE = Path(
    "docs/delivery-provenance/v10.1/validation/linux-validation-environment-approval.template.json"
)
RUNTIME_EVIDENCE = Path(
    "docs/delivery-provenance/v10.1/validation/ansible/ansible-runtime-manifest.json"
)
IDEMPOTENCE_EVIDENCE = Path(
    "docs/delivery-provenance/v10.1/validation/ansible/idempotence-result.json"
)
PREFLIGHT_EVIDENCE = Path(
    "docs/delivery-provenance/v10.1/validation/ansible/qualification-preflight.json"
)
MODULE_PATTERN = re.compile(r"^\s+(ansible\.[a-z0-9_.]+):", re.MULTILINE)
TASK_PATTERN = re.compile(r"^\s*- name:\s*(.+?)\s*$", re.MULTILINE)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def relative(path: Path) -> str:
    return path.as_posix()


def text_at(root: Path, path: Path, overrides: dict[str, str] | None) -> str:
    key = relative(path)
    if overrides and key in overrides:
        return overrides[key]
    return (root / path).read_text(encoding="utf-8")


def json_at(root: Path, path: Path, overrides: dict[str, str] | None) -> dict[str, Any]:
    value = json.loads(text_at(root, path, overrides))
    return value if isinstance(value, dict) else {}


def task_blocks(value: str) -> list[tuple[str, str]]:
    matches = list(TASK_PATTERN.finditer(value))
    blocks: list[tuple[str, str]] = []
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(value)
        blocks.append((match.group(1).strip('"\''), value[match.start():end]))
    return blocks


def validate(
    root: Path = ROOT,
    *,
    overrides: dict[str, str] | None = None,
) -> dict[str, Any]:
    errors: list[str] = []
    contract_path = root / CONTRACT
    if not contract_path.is_file() and not (overrides and relative(CONTRACT) in overrides):
        return {"valid": False, "preparation_complete": False, "errors": ["H0 Ansible contract is missing"]}
    try:
        contract = json_at(root, CONTRACT, overrides)
    except (OSError, ValueError) as error:
        return {"valid": False, "preparation_complete": False, "errors": [f"invalid H0 contract: {error}"]}

    if contract.get("format_version") != "1.0" or contract.get("contract_id") != "AZPR_H0_ANSIBLE_QUALIFICATION_INFRASTRUCTURE":
        errors.append("H0 Ansible contract identity mismatch")
    if contract.get("lifecycle_phase") != "H0_PREPARATION":
        errors.append("Ansible infrastructure escaped H0_PREPARATION")
    if contract.get("status") not in {"IMPLEMENTED_PENDING_LIVE_VALIDATION", "COMPLETE_EVIDENCE_BOUND"}:
        errors.append("H0 Ansible implementation status is invalid")
    authority = contract.get("authority_effect", {})
    if not authority or any(value is not False for value in authority.values()):
        errors.append("Ansible contract grants an authority effect")
    transport = contract.get("control_transport", {})
    if transport.get("model") != "OPERATOR_MEDIATED_LOCAL_CONNECTION_INSIDE_GUEST":
        errors.append("qualification transport is not the credential-free local-in-guest model")
    if transport.get("creates_credentials") is not False or transport.get("requires_unmanaged_ssh_key") is not False:
        errors.append("qualification transport may create or require unmanaged credentials")
    runtime = contract.get("runtime", {})
    if runtime != {"python": "3.12", "ansible_core": "2.21.2", "third_party_collections": []}:
        errors.append("pinned Ansible runtime contract drifted")

    required_files = {
        ANSIBLE_ROOT / "README.md",
        ANSIBLE_ROOT / "ansible.cfg",
        CONTRACT,
        ANSIBLE_ROOT / "requirements/requirements-ansible.in",
        ANSIBLE_ROOT / "requirements/requirements-ansible.lock",
        ANSIBLE_ROOT / "requirements/wheelhouse-manifest.json",
        ANSIBLE_ROOT / "inventories/qualification/README.md",
        ANSIBLE_ROOT / "inventories/qualification/hosts.example.yml",
        ANSIBLE_ROOT / "inventories/qualification/group_vars/all.yml",
        ANSIBLE_ROOT / "tests/README.md",
        ANSIBLE_ROOT / "tests/run_idempotence.py",
        APPROVAL_TEMPLATE,
    }
    required_files.update(ANSIBLE_ROOT / "playbooks" / name for name in contract.get("playbooks", []))
    required_files.update(
        ANSIBLE_ROOT / "roles" / name / "tasks/main.yml" for name in contract.get("roles", [])
    )
    for path in sorted(required_files):
        if not (root / path).is_file() and not (overrides and relative(path) in overrides):
            errors.append(f"required H0 artifact is missing: {relative(path)}")

    inventory_parent = root / ANSIBLE_ROOT / "inventories"
    if inventory_parent.is_dir():
        forbidden = set(contract.get("forbidden_inventory_names", []))
        present = {path.name for path in inventory_parent.iterdir() if path.is_dir()}
        if present != {"qualification"} or present & forbidden:
            errors.append(f"H0 inventory set must be qualification-only, found {sorted(present)}")
    try:
        hosts = json_at(root, ANSIBLE_ROOT / "inventories/qualification/hosts.example.yml", overrides)
        children = hosts.get("all", {}).get("children", {})
        host_values = children.get("qualification", {}).get("hosts", {})
        if set(children) != {"qualification"} or not host_values:
            errors.append("example inventory does not contain exactly one qualification group")
        if any(host.get("ansible_connection") != "local" for host in host_values.values()):
            errors.append("qualification inventory is not local-to-guest")
    except (OSError, ValueError) as error:
        errors.append(f"qualification inventory is not deterministic JSON/YAML: {error}")

    try:
        variables = json_at(root, ANSIBLE_ROOT / "inventories/qualification/group_vars/all.yml", overrides)
        if variables.get("azpr_environment_approval_state") != "PENDING_HUMAN_APPROVAL":
            errors.append("inventory fabricates or bypasses environment approval")
        if variables.get("azpr_environment_id") != "UNAPPROVED_H0_TEMPLATE":
            errors.append("inventory fabricates an approved environment identity")
        if variables.get("azpr_validation_root") != "/srv/azpr-validator":
            errors.append("bounded validation root drifted")
    except (OSError, ValueError) as error:
        errors.append(f"qualification variables are not deterministic JSON/YAML: {error}")

    yaml_paths = sorted((root / ANSIBLE_ROOT / "playbooks").glob("*.yml"))
    yaml_paths.extend(sorted((root / ANSIBLE_ROOT / "roles").glob("*/tasks/*.yml")))
    yaml_text = ""
    privileged_names: set[str] = set()
    forbidden_modules = set(contract.get("forbidden_modules", []))
    for absolute in yaml_paths:
        path = absolute.relative_to(root)
        value = text_at(root, path, overrides)
        yaml_text += value + "\n"
        modules = set(MODULE_PATTERN.findall(value))
        unqualified = sorted(module for module in modules if not module.startswith("ansible.builtin."))
        forbidden = sorted(modules & forbidden_modules)
        if unqualified:
            errors.append(f"{relative(path)} uses non-builtin modules: {unqualified}")
        if forbidden:
            errors.append(f"{relative(path)} uses forbidden modules: {forbidden}")
        if "/playbooks/" in f"/{relative(path)}" and "become: false" not in value:
            errors.append(f"{relative(path)} does not declare become: false")
        for name, block in task_blocks(value):
            if "become: true" in block:
                privileged_names.add(name)
                if "become_user: root" not in block or "azpr_privileged" not in block:
                    errors.append(f"privileged task lacks explicit root and azpr_privileged tag: {name}")

    if privileged_names != set(contract.get("privileged_tasks", [])):
        errors.append(
            f"privileged task allowlist differs: expected={sorted(contract.get('privileged_tasks', []))} actual={sorted(privileged_names)}"
        )
    for gate in contract.get("required_failure_gates", []):
        if gate not in yaml_text:
            errors.append(f"required failure gate is not implemented: {gate}")

    try:
        approval = json_at(root, APPROVAL_TEMPLATE, overrides)
        if approval.get("approved") is not False:
            errors.append("environment approval template is pre-approved")
        for field in ("approver_name", "approver_role", "approval_timestamp"):
            if approval.get(field) is not None:
                errors.append(f"environment approval template fabricates {field}")
    except (OSError, ValueError) as error:
        errors.append(f"environment approval template is invalid: {error}")

    evidence_errors: list[str] = []
    if contract.get("status") == "COMPLETE_EVIDENCE_BOUND":
        try:
            runtime_evidence = json_at(root, RUNTIME_EVIDENCE, overrides)
            if runtime_evidence.get("status") != "PASS" or runtime_evidence.get("ansible_core") != "2.21.2":
                evidence_errors.append("pinned Ansible runtime evidence is not PASS for 2.21.2")
        except (OSError, ValueError) as error:
            evidence_errors.append(f"Ansible runtime evidence is invalid: {error}")
        try:
            idempotence = json_at(root, IDEMPOTENCE_EVIDENCE, overrides)
            second = idempotence.get("second_apply", {}).get("recap", {})
            if idempotence.get("status") != "PASS" or second.get("changed") != 0 or second.get("failed") != 0 or second.get("unreachable") != 0:
                evidence_errors.append("idempotence evidence does not prove a zero-change second apply")
        except (OSError, ValueError) as error:
            evidence_errors.append(f"idempotence evidence is invalid: {error}")
        try:
            preflight = json_at(root, PREFLIGHT_EVIDENCE, overrides)
            if preflight.get("status") != "PASS" or preflight.get("qualification_effect") is not False:
                evidence_errors.append("qualification preflight evidence is not a non-authoritative PASS")
        except (OSError, ValueError) as error:
            evidence_errors.append(f"qualification preflight evidence is invalid: {error}")
    errors.extend(evidence_errors)
    complete = contract.get("status") == "COMPLETE_EVIDENCE_BOUND" and not errors
    return {
        "assessment": "AZPR_H0_ANSIBLE_CONTRACT",
        "valid": not errors,
        "preparation_complete": complete,
        "status": contract.get("status"),
        "roles": contract.get("roles", []),
        "playbooks": contract.get("playbooks", []),
        "privileged_tasks": sorted(privileged_names),
        "errors": errors,
    }


def runtime_checks(root: Path, bin_dir: Path) -> dict[str, Any]:
    ansible_playbook = bin_dir / "ansible-playbook"
    ansible_inventory = bin_dir / "ansible-inventory"
    errors: list[str] = []
    commands: list[dict[str, Any]] = []
    environment = dict(os.environ)
    environment.update(
        ANSIBLE_CONFIG=str(root / ANSIBLE_ROOT / "ansible.cfg"),
        ANSIBLE_NOCOLOR="1",
        PYTHONDONTWRITEBYTECODE="1",
    )
    inventory = root / ANSIBLE_ROOT / "inventories/qualification/hosts.example.yml"
    planned = [
        [str(ansible_inventory), "-i", str(inventory), "--list"],
        *[
            [str(ansible_playbook), "-i", str(inventory), str(playbook), "--syntax-check"]
            for playbook in sorted((root / ANSIBLE_ROOT / "playbooks").glob("*.yml"))
        ],
    ]
    for command in planned:
        if not Path(command[0]).is_file():
            errors.append(f"missing pinned Ansible executable: {command[0]}")
            continue
        result = subprocess.run(command, cwd=root, env=environment, text=True, capture_output=True, check=False)
        record = {
            "command": [Path(command[0]).name, *command[1:]],
            "exit_code": result.returncode,
            "stdout_sha256": hashlib.sha256(result.stdout.encode()).hexdigest(),
            "stderr_sha256": hashlib.sha256(result.stderr.encode()).hexdigest(),
        }
        commands.append(record)
        if result.returncode != 0:
            errors.append(f"Ansible runtime check failed: {' '.join(record['command'])}")
    return {"valid": not errors, "commands": commands, "errors": errors}


def atomic_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(value, handle, indent=2, sort_keys=True)
            handle.write("\n")
        os.replace(temporary, path)
    except BaseException:
        Path(temporary).unlink(missing_ok=True)
        raise


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ansible-bin-dir", type=Path)
    parser.add_argument("--require-complete", action="store_true")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = validate(ROOT)
    if args.ansible_bin_dir:
        result["runtime_checks"] = runtime_checks(ROOT, args.ansible_bin_dir.resolve())
        if not result["runtime_checks"]["valid"]:
            result["valid"] = False
            result["errors"].extend(result["runtime_checks"]["errors"])
    if args.require_complete and not result["preparation_complete"]:
        result["valid"] = False
        result["errors"].append("H0 Ansible preparation is not complete and evidence-bound")
    if args.output:
        atomic_json(args.output, result)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
