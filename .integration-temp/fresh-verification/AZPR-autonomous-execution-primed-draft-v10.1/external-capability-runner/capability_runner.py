#!/usr/bin/env python3
"""Human-operated external capability runner for AZPR.

This program is a separate trust boundary from Codex and the autonomous
controller. It accepts only signed, schema-valid plans/manifests/attestations,
re-probes the target immediately before apply, consumes the capability nonce
before side effects, invokes immutable allowlisted adapters without a shell,
and emits signed evidence.
"""
from __future__ import annotations

import argparse
import atexit
import hashlib
import json
import os
import resource
import secrets
import signal
import subprocess
import sys
import tempfile
import stat
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import jsonschema
from referencing import Registry, Resource

import secure_runtime as sr
import trusted_installation as ti

CONFIRMATION = "APPLY SIGNED AZPR CAPABILITY"
DEFAULT_INSTALLATION_MANIFEST = "/etc/azpr/external-runner-installation.json"
MAX_ADAPTER_OUTPUT_BYTES = 2 * 1024 * 1024


class RunnerError(RuntimeError):
    pass


def load_json(path: Path, *, max_bytes: int = 2 * 1024 * 1024) -> dict[str, Any]:
    try:
        sr.no_symlink_ancestors(path, allow_missing_leaf=False)
        flags=os.O_RDONLY|getattr(os,"O_NOFOLLOW",0);fd=os.open(path,flags)
        try:
            before=os.fstat(fd)
            if not stat.S_ISREG(before.st_mode) or before.st_nlink!=1 or before.st_size>max_bytes:
                raise RunnerError(f"Unsafe or oversized JSON: {path}")
            data=bytearray()
            while True:
                chunk=os.read(fd,65536)
                if not chunk:break
                data.extend(chunk)
                if len(data)>max_bytes:raise RunnerError(f"JSON exceeds size limit: {path}")
            after=os.fstat(fd)
            if (before.st_dev,before.st_ino,before.st_size,before.st_mtime_ns)!=(after.st_dev,after.st_ino,after.st_size,after.st_mtime_ns):
                raise RunnerError(f"JSON changed while being read: {path}")
        finally:os.close(fd)
        value=json.loads(bytes(data).decode("utf-8"))
    except (OSError,UnicodeDecodeError,json.JSONDecodeError) as exc:
        raise RunnerError(f"Invalid JSON: {path}") from exc
    if not isinstance(value, dict):raise RunnerError(f"Expected JSON object: {path}")
    return value


def schema_registry(schema_dir: Path) -> Registry:
    registry = Registry()
    for path in schema_dir.glob("*.json"):
        schema = load_json(path)
        identifier = schema.get("$id")
        if isinstance(identifier, str):
            registry = registry.with_resource(identifier, Resource.from_contents(schema))
    return registry


def validate(instance: Any, schema_path: Path, registry: Registry, label: str) -> None:
    schema = load_json(schema_path)
    validator = jsonschema.Draft202012Validator(
        schema,
        registry=registry,
        format_checker=jsonschema.FormatChecker(),
    )
    errors = sorted(validator.iter_errors(instance), key=lambda error: list(error.path))
    if errors:
        rendered = []
        for error in errors[:25]:
            path = ".".join(str(value) for value in error.absolute_path) or "$"
            rendered.append(f"{path}: {error.message}")
        raise RunnerError(f"{label} schema failure:\n- " + "\n- ".join(rendered))


def sha256_json(value: Any) -> str:
    return hashlib.sha256(sr.canonical_json_bytes(value)).hexdigest()


def strict_path(path_value: str, label: str) -> Path:
    path = Path(path_value).expanduser().absolute()
    try:
        sr.no_symlink_ancestors(path, allow_missing_leaf=False)
    except sr.SecurityError as exc:
        raise RunnerError(f"{label}: {exc}") from exc
    return path


def sanitized_adapter_env(temp_root: Path) -> dict[str, str]:
    try:
        return sr.minimal_child_env(
            runtime_dir=temp_root,
            executable_path="/usr/bin:/bin:/usr/local/bin",
            extra={"AZPR_EXTERNAL_RUNNER": "1"},
        )
    except sr.SecurityError as exc:
        raise RunnerError(str(exc)) from exc


def _limits() -> None:
    resource.setrlimit(resource.RLIMIT_CPU, (300, 300))
    resource.setrlimit(resource.RLIMIT_FSIZE, (MAX_ADAPTER_OUTPUT_BYTES, MAX_ADAPTER_OUTPUT_BYTES))
    resource.setrlimit(resource.RLIMIT_NOFILE, (256, 256))
    if hasattr(resource, "RLIMIT_NPROC"):
        resource.setrlimit(resource.RLIMIT_NPROC, (64, 64))
    if hasattr(resource, "RLIMIT_AS"):
        resource.setrlimit(resource.RLIMIT_AS, (2 * 1024**3, 2 * 1024**3))


def _read_bounded(path: Path, limit: int) -> str:
    size = path.stat().st_size
    if size > limit:
        raise RunnerError(f"Child output exceeded {limit} bytes.")
    return path.read_text(encoding="utf-8", errors="replace")


def invoke_adapter(
    adapter_fd: int,
    mode: str,
    payload: dict[str, Any],
    *,
    timeout: int,
    temp_root: Path,
    request_schema: Path | None = None,
    response_schema: Path | None = None,
    registry: Registry | None = None,
) -> dict[str, Any]:
    if request_schema is not None and registry is not None:
        validate(payload, request_schema, registry, f"adapter {mode} request")
    executable = f"/proc/self/fd/{adapter_fd}"
    stdout_path = temp_root / f"adapter-{mode}-{secrets.token_hex(8)}.stdout"
    stderr_path = temp_root / f"adapter-{mode}-{secrets.token_hex(8)}.stderr"
    with stdout_path.open("wb") as stdout_handle, stderr_path.open("wb") as stderr_handle:
        process = subprocess.Popen(
            [executable, mode],
            cwd=temp_root,
            stdin=subprocess.PIPE,
            stdout=stdout_handle,
            stderr=stderr_handle,
            env=sanitized_adapter_env(temp_root / f"env-{mode}-{secrets.token_hex(6)}"),
            start_new_session=True,
            preexec_fn=_limits,
            pass_fds=(adapter_fd,),
        )
        try:
            process.communicate(
                input=json.dumps(payload, sort_keys=True).encode("utf-8"), timeout=timeout
            )
        except subprocess.TimeoutExpired as exc:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            process.wait(timeout=10)
            raise RunnerError(f"Adapter {mode} timed out and was killed.") from exc
    stdout = _read_bounded(stdout_path, MAX_ADAPTER_OUTPUT_BYTES)
    stderr = _read_bounded(stderr_path, MAX_ADAPTER_OUTPUT_BYTES)
    stdout_path.unlink(missing_ok=True)
    stderr_path.unlink(missing_ok=True)
    if process.returncode != 0:
        raise RunnerError(
            f"Adapter {mode} failed with exit {process.returncode}: "
            + sr.redact_text(stderr[-2000:])
        )
    try:
        value = json.loads(stdout)
    except json.JSONDecodeError as exc:
        raise RunnerError(f"Adapter {mode} returned invalid JSON.") from exc
    if not isinstance(value, dict):
        raise RunnerError(f"Adapter {mode} must return a JSON object.")
    if response_schema is not None and registry is not None:
        validate(value, response_schema, registry, f"adapter {mode} response")
    return value


def _verify_root_owned_path(path: Path, *, development_mode: bool) -> None:
    current = path.absolute()
    immediate = {current, current.parent}
    for candidate in [current, *current.parents]:
        info = os.lstat(candidate)
        if stat.S_ISLNK(info.st_mode):
            raise RunnerError(f"External runner trust path is symlinked: {candidate}")
        if (not development_mode or candidate in immediate) and info.st_mode & 0o022:
            raise RunnerError(f"External runner trust path is writable: {candidate}")
        if not development_mode and info.st_uid != 0:
            raise RunnerError(f"Production trust path must be root-owned: {candidate}")
        if candidate == candidate.parent:
            break


def _sha256_fd(fd: int) -> str:
    digest = hashlib.sha256()
    os.lseek(fd, 0, os.SEEK_SET)
    while True:
        chunk = os.read(fd, 1024 * 1024)
        if not chunk:
            break
        digest.update(chunk)
    os.lseek(fd, 0, os.SEEK_SET)
    return digest.hexdigest()


def adapter_catalog(config: dict[str, Any], *, development_mode: bool, trusted: Any | None = None) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    production = ti.production_mode()
    if production and trusted is None:
        raise RunnerError("Production adapter resolution requires the verified installation manifest.")
    for item in config["adapters"]:
        if production:
            component_name = item.get("component")
            if not isinstance(component_name, str) or not component_name:
                raise RunnerError(f"Production adapter is not manifest-component bound: {item.get('name')}")
            manifest_component = item.get("manifest_component")
            if not isinstance(manifest_component, str) or not manifest_component:
                raise RunnerError(f"Production adapter lacks a manifest component: {item.get('name')}")
            try:
                path = trusted.component(component_name)
                manifest_path = trusted.component(manifest_component)
            except ti.InstallationError as exc:
                raise RunnerError(str(exc)) from exc
            try:
                manifest_raw = manifest_path.read_bytes()
                if len(manifest_raw) > 1024 * 1024:
                    raise RunnerError("Adapter installation manifest exceeds size limit")
                adapter_manifest = json.loads(manifest_raw)
            except (OSError, json.JSONDecodeError) as exc:
                raise RunnerError("Adapter installation manifest is invalid") from exc
            expected_manifest = {
                "format_version": "1.0", "adapter_name": item.get("name"),
                "executable_component": component_name, "executable_sha256": item.get("sha256"),
                "allowed_operations": item.get("allowed_operations"),
            }
            for key, value in expected_manifest.items():
                if adapter_manifest.get(key) != value:
                    raise RunnerError(f"Adapter installation manifest mismatch: {item.get('name')}:{key}")
            if adapter_manifest.get("idempotency_key_required") is not True:
                raise RunnerError("Production adapter must require idempotency keys")
            if adapter_manifest.get("execution_mode") not in {"DRY_RUN_ONLY", "ISOLATED_TEST_TARGET_ONLY", "LIVE_REQUIRES_SEPARATE_SIGNED_TARGET_ATTESTATION"}:
                raise RunnerError("Adapter execution mode is invalid")
        else:
            path = strict_path(item["path"], f"adapter {item['name']}")
            _verify_root_owned_path(path, development_mode=development_mode)
        flags = os.O_RDONLY
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        fd = os.open(path, flags)
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_mode & 0o022:
            os.close(fd)
            raise RunnerError(f"Adapter must be an immutable regular file: {item['name']}")
        if _sha256_fd(fd) != item["sha256"]:
            os.close(fd)
            raise RunnerError(f"Adapter hash mismatch: {item['name']}")
        result[item["name"]] = {**item, "path": str(path), "fd": fd, "device": info.st_dev, "inode": info.st_ino, "installation_manifest": adapter_manifest if production else None}
    return result

def close_catalog(catalog: dict[str, dict[str, Any]]) -> None:
    for item in catalog.values():
        fd = item.get("fd")
        if isinstance(fd, int):
            try:
                os.close(fd)
            except OSError:
                pass


def verify_signed_document(
    payload: dict[str, Any],
    keyring: dict[str, sr.SignerRecord],
    *,
    min_signers: int,
    required_roles: list[str],
) -> None:
    try:
        sr.verify_signatures(
            payload,
            keyring=keyring,
            required_key_ids=[],
            required_signer_ids=[],
            required_roles=required_roles,
            min_signers=min_signers,
        )
    except sr.SecurityError as exc:
        raise RunnerError(str(exc)) from exc


def load_installation_manifest(path: Path, *, development_mode: bool) -> tuple[dict[str, Any], Path, Path]:
    _verify_root_owned_path(path, development_mode=development_mode)
    installation = load_json(path)
    if installation.get("format_version") != "1.0":
        raise RunnerError("Unsupported external runner installation manifest.")
    if sr.sha256_file(Path(__file__).resolve()) != installation.get("launcher_sha256"):
        raise RunnerError("External capability runner hash does not match the installed trust manifest.")
    config_path = strict_path(installation["config_path"], "installed runner config")
    schema_dir = strict_path(installation["schema_dir"], "installed schema directory")
    _verify_root_owned_path(config_path, development_mode=development_mode)
    _verify_root_owned_path(schema_dir, development_mode=development_mode)
    if sr.sha256_file(config_path) != installation["config_sha256"]:
        raise RunnerError("Installed runner config hash mismatch.")
    schema_hashes = installation.get("schema_hashes", {})
    if not isinstance(schema_hashes, dict) or not schema_hashes:
        raise RunnerError("Installation manifest must pin every schema hash.")
    for name, expected in schema_hashes.items():
        path_value = schema_dir / name
        if sr.sha256_file(path_value) != expected:
            raise RunnerError(f"Installed schema hash mismatch: {name}")
    return installation, config_path, schema_dir


def main() -> int:
    if not ti.production_mode() and os.environ.get("AZPR_EXPLICIT_TEST_MODE") != "1":
        raise RunnerError("Direct source-tree capability runner execution is disabled; use the verified installed launcher.")
    parser = argparse.ArgumentParser()
    parser.add_argument("--installation-manifest")
    parser.add_argument("--development-mode", action="store_true", help="Allows a non-system installation manifest for synthetic testing only.")
    parser.add_argument("--plan", required=True)
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--target-attestation", required=True)
    parser.add_argument("--operation-ticket", required=True)
    parser.add_argument("--evidence-dir", required=True)
    parser.add_argument("--confirm", required=True)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--timeout", type=int, default=600)
    args = parser.parse_args()
    if args.confirm != CONFIRMATION:
        raise RunnerError("Exact human confirmation phrase is required.")
    if ti.production_mode():
        if args.installation_manifest or args.development_mode:
            raise RunnerError("Production mode rejects caller-selected installation trust roots.")
        try:
            trusted = ti.load_installation()
            config_path = trusted.component("external_runner_config")
            schema_dir = trusted.directory("schema_dir")
        except ti.InstallationError as exc:
            raise RunnerError(str(exc)) from exc
        config = load_json(config_path)
    else:
        installation_value = args.installation_manifest or DEFAULT_INSTALLATION_MANIFEST
        installation_path = strict_path(installation_value, "external runner installation manifest")
        installation, config_path, schema_dir = load_installation_manifest(installation_path, development_mode=True)
        config = load_json(config_path)
    registry = schema_registry(schema_dir)
    validate(config, schema_dir / "external-runner-config.schema.json", registry, "runner config")
    if ti.production_mode():
        expected_components = {
            "approval_keyring_component": "approval_keyring",
            "evidence_private_key_component": "evidence_private_key",
            "evidence_public_key_component": "evidence_public_key",
            "controller_runtime_public_key_component": "runtime_public_key",
        }
        if config.get("format_version") != "2.0":
            raise RunnerError("Production external-runner config must be installer-generated format 2.0.")
        for field, expected in expected_components.items():
            if config.get(field) != expected:
                raise RunnerError(f"Production external-runner trust component mismatch: {field}")
        if config.get("nonce_ledger_directory") != "external_runner_runtime":
            raise RunnerError("Production nonce ledger must use the manifest-pinned directory.")
        if config.get("controller_runtime_key_id") != trusted.data.get("runtime_signing_key_id"):
            raise RunnerError("Production controller runtime key ID is not installation-bound.")
        if config.get("evidence_key_id") != trusted.data.get("evidence_key_id"):
            raise RunnerError("Production evidence key ID is not installation-bound.")
    plan = load_json(strict_path(args.plan, "plan"))
    manifest = load_json(strict_path(args.manifest, "capability manifest"))
    attestation = load_json(strict_path(args.target_attestation, "target attestation"))
    ticket = load_json(strict_path(args.operation_ticket, "operation registration ticket"))
    validate(plan, schema_dir / "deployment-plan.schema.json", registry, "plan")
    validate(manifest, schema_dir / "capability-manifest.schema.json", registry, "capability manifest")
    validate(attestation, schema_dir / "target-attestation.schema.json", registry, "target attestation")
    validate(ticket, schema_dir / "operation-registration.schema.json", registry, "operation registration ticket")
    if ti.production_mode():
        trusted = ti.load_installation()
        controller_public_key = trusted.component("runtime_public_key")
        controller_key_id = str(trusted.data.get("runtime_signing_key_id", "azpr-controller-runtime"))
    else:
        controller_public_key = strict_path(config["controller_runtime_public_key_path"], "controller runtime public key")
        controller_key_id = str(config.get("controller_runtime_key_id", "azpr-controller-runtime-development"))
    try:
        sr.verify_manifest(ticket, public_key_path=controller_public_key, key_id=controller_key_id)
    except sr.SecurityError as exc:
        raise RunnerError(f"operation ticket signature failed: {exc}") from exc
    plan_hash = sha256_json(plan)
    manifest_hash = sha256_json(manifest)
    attestation_hash = sha256_json(attestation)
    if manifest["plan_sha256"] != plan_hash:
        raise RunnerError("Capability manifest is not bound to the exact plan.")
    if manifest.get("target_attestation_sha256") != attestation_hash:
        raise RunnerError("Capability manifest is not bound to the exact target attestation.")
    if manifest["environment"] != plan["environment"] or manifest["target"] != plan["target"]:
        raise RunnerError("Plan and capability target/environment mismatch.")
    if attestation["target"] != plan["target"]:
        raise RunnerError("Target attestation does not match the plan target.")
    target_hash = sha256_json(plan["target"])
    operations_hash = sha256_json(plan["actions"])
    ticket_checks = {
        "registration": manifest.get("operation_registration_id") == ticket.get("registration_id"),
        "stage": plan.get("stage_id") == ticket.get("stage_id") == manifest.get("stage_id"),
        "environment": plan.get("environment") == ticket.get("environment") == manifest.get("environment"),
        "repository": plan.get("repository_id") == ticket.get("repository_id"),
        "commit": plan.get("created_from_commit") == ticket.get("source_commit") == manifest.get("source_commit"),
        "tree": plan.get("created_from_tree") == ticket.get("source_tree") == manifest.get("source_tree"),
        "plan": ticket.get("plan_sha256") == plan_hash,
        "manifest": ticket.get("capability_manifest_sha256") == manifest_hash,
        "attestation": ticket.get("target_attestation_sha256") == attestation_hash,
        "target": ticket.get("target_sha256") == target_hash == manifest.get("target_sha256"),
        "operations": ticket.get("operations_sha256") == operations_hash == manifest.get("operations_sha256"),
        "nonce": ticket.get("capability_nonce") == manifest.get("nonce"),
        "policy": ticket.get("controller_policy_identity_sha256") == manifest.get("controller_policy_identity_sha256"),
    }
    failed = [name for name, ok in ticket_checks.items() if not ok]
    if failed:
        raise RunnerError(f"operation ticket binding mismatch: {failed}")
    now = datetime.now(timezone.utc)
    issued = sr.parse_utc(manifest["issued_at"], "manifest.issued_at")
    expires = sr.parse_utc(manifest["expires_at"], "manifest.expires_at")
    attestation_expires = sr.parse_utc(attestation["expires_at"], "attestation.expires_at")
    if issued > now or expires <= now or attestation_expires <= now:
        raise RunnerError("Manifest or target attestation is outside its validity window.")
    if ti.production_mode():
        keyring_path = trusted.component("approval_keyring")
    else:
        keyring_path = strict_path(config["approval_keyring_path"], "approval keyring")
    keyring = sr.load_public_keyring(keyring_path)
    verify_signed_document(manifest, keyring, min_signers=2, required_roles=["operator", "security-approver"])
    verify_signed_document(attestation, keyring, min_signers=1, required_roles=["target-attestor"])
    catalog = adapter_catalog(config, development_mode=args.development_mode, trusted=(trusted if ti.production_mode() else None))
    atexit.register(close_catalog, catalog)
    actions_by_key = {(item["adapter"], item["operation"]): item for item in manifest["actions"]}
    if len(actions_by_key) != len(plan["actions"]):
        raise RunnerError("Plan and capability action counts differ.")
    preflights: list[dict[str, Any]] = []
    with tempfile.TemporaryDirectory(prefix="azpr-capability-runner-") as temporary:
        temp_root = Path(temporary)
        for action in plan["actions"]:
            adapter = catalog.get(action["adapter"])
            if adapter is None or action["operation"] not in adapter["allowed_operations"]:
                raise RunnerError(f"Adapter or operation is not allowlisted: {action['adapter']}:{action['operation']}")
            if attestation.get("adapter_hashes", {}).get(action["adapter"]) != adapter["sha256"]:
                raise RunnerError(f"Target attestation is not bound to the exact adapter hash: {action['adapter']}")
            manifest_action = actions_by_key.get((action["adapter"], action["operation"]))
            if manifest_action is None or manifest_action["parameters_sha256"] != sha256_json(action["parameters"]):
                raise RunnerError("Capability action is not bound to exact parameters.")
            probe = invoke_adapter(
                adapter["fd"],
                "probe",
                {"target": plan["target"], "operation": action["operation"], "parameters": action["parameters"]},
                timeout=min(args.timeout, 300),
                temp_root=temp_root,
                request_schema=schema_dir / "adapter-request.schema.json",
                response_schema=schema_dir / "adapter-response.schema.json",
                registry=registry,
            )
            if probe.get("target") != plan["target"]:
                raise RunnerError("Live account/project/region identity differs from the signed target.")
            if probe.get("drift_sha256") != attestation["drift_sha256"]:
                raise RunnerError("Live drift differs from the signed target attestation.")
            if probe.get("safe_to_apply") is not True:
                raise RunnerError("Adapter preflight did not authorize apply.")
            preflights.append(probe)
        if args.dry_run:
            print(json.dumps({"status": "DRY_RUN_PASS", "plan_sha256": plan_hash, "preflights": preflights}, indent=2))
            return 0
        if ti.production_mode():
            trusted = ti.load_installation()
            private_key = trusted.component("evidence_private_key")
            public_key = trusted.component("evidence_public_key")
            ledger_root = trusted.directory("external_runner_runtime")
        else:
            private_key = strict_path(config["evidence_private_key_path"], "evidence private key")
            public_key = strict_path(config["evidence_public_key_path"], "evidence public key")
            ledger_root = Path(config["nonce_ledger_root"]).absolute()
        try:
            sr.secure_mkdir(ledger_root)
            ledger = sr.NonceLedger(
                ledger_root,
                private_key=private_key,
                public_key=public_key,
                key_id=config["evidence_key_id"],
            )
            # Consume before any side effect. Failure after this point requires a new signed manifest.
            ledger.consume(
                manifest["nonce"],
                document_id=manifest["manifest_id"],
                purpose=f"external-apply:{plan['plan_id']}",
                run_id=f"apply-{secrets.token_hex(16)}",
            )
        except sr.SecurityError as exc:
            raise RunnerError(str(exc)) from exc
        started = sr.utc_now()
        adapter_results: list[dict[str, Any]] = []
        overall_status = "APPLY_COMPLETE"
        error_summary: str | None = None
        active_action: dict[str, Any] | None = None
        active_probe: dict[str, Any] | None = None
        try:
            for action in plan["actions"]:
                active_action = action
                adapter = catalog[action["adapter"]]
                # The adapter is executed through the already verified descriptor,
                # eliminating pathname replacement between hash and execution.
                active_probe = invoke_adapter(
                    adapter["fd"],
                    "probe",
                    {"target": plan["target"], "operation": action["operation"], "parameters": action["parameters"]},
                    timeout=min(args.timeout, 300),
                    temp_root=temp_root,
                )
                if active_probe.get("target") != plan["target"]:
                    raise RunnerError("Live target identity changed immediately before apply.")
                if active_probe.get("drift_sha256") != attestation["drift_sha256"]:
                    raise RunnerError("Live drift changed immediately before apply.")
                if active_probe.get("safe_to_apply") is not True:
                    raise RunnerError("Immediate pre-apply probe did not authorize apply.")
                result = invoke_adapter(
                    adapter["fd"],
                    "apply",
                    {
                        "target": plan["target"],
                        "operation": action["operation"],
                        "parameters": action["parameters"],
                        "constraints": plan["constraints"],
                        "preflight": active_probe,
                    },
                    timeout=args.timeout,
                    temp_root=temp_root,
                    request_schema=schema_dir / "adapter-request.schema.json",
                    response_schema=schema_dir / "adapter-response.schema.json",
                    registry=registry,
                )
                status = result.get("status")
                if status not in {"APPLIED", "NO_CHANGE", "FAILED", "ROLLED_BACK"}:
                    raise RunnerError("Adapter returned invalid apply status.")
                adapter_results.append(
                    {
                        "adapter": action["adapter"],
                        "operation": action["operation"],
                        "status": status,
                        "preflight_sha256": sha256_json(active_probe),
                        "result_sha256": sha256_json(result),
                    }
                )
                if status == "FAILED":
                    raise RunnerError("External apply failed; execute the separately signed rollback plan.")
                if status == "ROLLED_BACK":
                    overall_status = "APPLY_ROLLED_BACK"
                    raise RunnerError("External action rolled back and is not a completed apply.")
        except (RunnerError, sr.SecurityError) as exc:
            error_summary = sr.redact_text(str(exc), max_chars=4000)
            completed_side_effect = any(item["status"] == "APPLIED" for item in adapter_results)
            if overall_status != "APPLY_ROLLED_BACK":
                overall_status = "PARTIAL_APPLY" if completed_side_effect else "APPLY_FAILED"
            if active_action is not None and not any(
                item["adapter"] == active_action["adapter"] and item["operation"] == active_action["operation"]
                for item in adapter_results
            ):
                adapter_results.append(
                    {
                        "adapter": active_action["adapter"],
                        "operation": active_action["operation"],
                        "status": "FAILED",
                        "preflight_sha256": sha256_json(active_probe or {}),
                        "result_sha256": sr.sha256_bytes(error_summary.encode("utf-8")),
                    }
                )
        evidence = {
            "format_version": "1.0",
            "evidence_id": f"evidence-{secrets.token_hex(12)}",
            "operation_registration_id": ticket["registration_id"],
            "stage_id": ticket["stage_id"],
            "evidence_for_stage_id": ticket["evidence_for_stage_id"],
            "environment": ticket["environment"],
            "repository_id": ticket["repository_id"],
            "source_commit": ticket["source_commit"],
            "source_tree": ticket["source_tree"],
            "target_sha256": ticket["target_sha256"],
            "operations_sha256": ticket["operations_sha256"],
            "capability_nonce": ticket["capability_nonce"],
            "controller_policy_identity_sha256": ticket["controller_policy_identity_sha256"],
            "overall_status": overall_status,
            "plan_sha256": plan_hash,
            "capability_manifest_sha256": manifest_hash,
            "target_attestation_sha256": attestation_hash,
            "started_at": started,
            "completed_at": sr.utc_now(),
            "target": plan["target"],
            "adapter_results": adapter_results,
            "rollback_ready": bool(plan.get("rollback", {}).get("steps")),
            "output_hashes": {},
        }
        if error_summary is not None:
            evidence["error_summary"] = error_summary
        signed = sr.sign_manifest(evidence, private_key_path=private_key, key_id=(str(trusted.data.get("evidence_key_id", "azpr-external-evidence")) if ti.production_mode() else config["evidence_key_id"]))
        validate(signed, schema_dir / "evidence.schema.json", registry, "signed evidence")
        try:
            sr.verify_manifest(signed, public_key_path=public_key, key_id=(str(trusted.data.get("evidence_key_id", "azpr-external-evidence")) if ti.production_mode() else config["evidence_key_id"]))
            evidence_dir = Path(args.evidence_dir).expanduser().absolute()
            sr.secure_mkdir(evidence_dir)
            content_hash = sr.sha256_bytes(sr.canonical_json_bytes(signed))
            evidence_path = evidence_dir / f"{content_hash}.json"
            sr.secure_write_json(evidence_path, signed, create_once=True)
        except sr.SecurityError as exc:
            raise RunnerError(str(exc)) from exc
        close_catalog(catalog)
        if error_summary is not None:
            raise RunnerError(
                f"External apply did not complete; signed immutable evidence: {evidence_path}"
            )
        print(json.dumps({"status": overall_status, "evidence": str(evidence_path), "sha256": content_hash}, indent=2))
        return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (RunnerError, sr.SecurityError) as exc:
        print(f"CAPABILITY RUNNER BLOCKED: {exc}", file=sys.stderr)
        raise SystemExit(2)
