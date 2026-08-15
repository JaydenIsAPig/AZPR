#!/usr/bin/env python3
"""Observe, calculate, and validate the proposed H0 live-target fingerprint."""

from __future__ import annotations

import argparse
import hashlib
import hmac
import importlib.util
import json
import os
import pwd
import re
import shlex
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping

ROOT = Path(__file__).resolve().parents[1]
PACK = ROOT / "automation" / "integration" / "v10.1" / "h0-ansible-live-stages"
CONTRACT_PATH = PACK / "target-fingerprint-contract.json"
OPERATOR_SCHEMA_PATH = PACK / "operator-input.schema.json"
CONTRACT_ID = "AZPR_H0_TARGET_FINGERPRINT_V1"
CANONICALIZATION_ID = "AZPR_H0_TARGET_FINGERPRINT_CANONICAL_JSON_V1"
FIELD_ORDER = (
    "target_id",
    "machine_id",
    "operating_system_id",
    "operating_system_version_id",
    "architecture",
    "reviewer_name",
    "reviewer_uid",
    "reviewer_gid",
    "reviewer_home",
)
MEMBER_ORDER = ("contract_id", *FIELD_ORDER)
ASCII_WHITESPACE = " \t\r\n\f\v"
TARGET_ID_PATTERN = re.compile(r"^[a-z0-9](?:[a-z0-9.-]{0,198}[a-z0-9])?$")
MACHINE_ID_PATTERN = re.compile(r"^[0-9a-f]{32}$")
DIGEST_PATTERN = re.compile(r"^[0-9a-f]{64}$")


class TargetFingerprintError(ValueError):
    """A fail-closed, safe-to-report fingerprint error."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


def _ascii_string(value: Any, field: str, *, lowercase: bool = False) -> str:
    if not isinstance(value, str):
        raise TargetFingerprintError(f"INVALID_{field.upper()}")
    normalized = value.strip(ASCII_WHITESPACE)
    try:
        normalized.encode("ascii")
    except UnicodeEncodeError as exc:
        raise TargetFingerprintError(f"INVALID_{field.upper()}") from exc
    return normalized.lower() if lowercase else normalized


def _unsigned_integer(value: Any, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise TargetFingerprintError(f"INVALID_{field.upper()}")
    return value


def normalize_identity(value: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise TargetFingerprintError("INVALID_TARGET_IDENTITY")
    if set(value) != set(FIELD_ORDER):
        raise TargetFingerprintError("TARGET_IDENTITY_FIELD_SET_MISMATCH")

    normalized: dict[str, Any] = {
        "target_id": _ascii_string(value["target_id"], "target_id", lowercase=True),
        "machine_id": _ascii_string(value["machine_id"], "machine_id", lowercase=True),
        "operating_system_id": _ascii_string(
            value["operating_system_id"], "operating_system_id", lowercase=True
        ),
        "operating_system_version_id": _ascii_string(
            value["operating_system_version_id"], "operating_system_version_id"
        ),
        "architecture": _ascii_string(value["architecture"], "architecture", lowercase=True),
        "reviewer_name": _ascii_string(value["reviewer_name"], "reviewer_name", lowercase=True),
        "reviewer_uid": _unsigned_integer(value["reviewer_uid"], "reviewer_uid"),
        "reviewer_gid": _unsigned_integer(value["reviewer_gid"], "reviewer_gid"),
        "reviewer_home": _ascii_string(value["reviewer_home"], "reviewer_home"),
    }

    if not TARGET_ID_PATTERN.fullmatch(normalized["target_id"]):
        raise TargetFingerprintError("INVALID_TARGET_ID")
    if (
        not MACHINE_ID_PATTERN.fullmatch(normalized["machine_id"])
        or normalized["machine_id"] == "0" * 32
    ):
        raise TargetFingerprintError("INVALID_MACHINE_ID")
    required = {
        "operating_system_id": "ubuntu",
        "operating_system_version_id": "24.04",
        "architecture": "aarch64",
        "reviewer_name": "ubuntu",
        "reviewer_uid": 1000,
        "reviewer_gid": 1000,
        "reviewer_home": "/home/ubuntu",
    }
    for field, expected in required.items():
        if normalized[field] != expected:
            raise TargetFingerprintError(f"UNSUPPORTED_{field.upper()}")
    return {field: normalized[field] for field in FIELD_ORDER}


def canonical_bytes(value: Mapping[str, Any]) -> bytes:
    identity = normalize_identity(value)
    payload = {"contract_id": CONTRACT_ID}
    payload.update(identity)
    if tuple(payload) != MEMBER_ORDER:
        raise TargetFingerprintError("CANONICAL_MEMBER_ORDER_MISMATCH")
    return json.dumps(
        payload,
        ensure_ascii=True,
        allow_nan=False,
        separators=(",", ":"),
    ).encode("utf-8")


def fingerprint(value: Mapping[str, Any]) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def compare_fingerprint(value: Mapping[str, Any], expected_sha256: str) -> tuple[str, bool]:
    if not isinstance(expected_sha256, str) or not DIGEST_PATTERN.fullmatch(expected_sha256):
        raise TargetFingerprintError("INVALID_EXPECTED_TARGET_FINGERPRINT")
    observed = fingerprint(value)
    return observed, hmac.compare_digest(bytes.fromhex(observed), bytes.fromhex(expected_sha256))


def parse_os_release(path: Path) -> dict[str, str]:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise TargetFingerprintError("TARGET_IDENTITY_FIELD_UNAVAILABLE") from exc
    values: dict[str, str] = {}
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, raw = stripped.split("=", 1)
        if key not in {"ID", "VERSION_ID"}:
            continue
        if key in values:
            raise TargetFingerprintError("INVALID_OS_RELEASE")
        try:
            tokens = shlex.split(raw, comments=False, posix=True)
        except ValueError as exc:
            raise TargetFingerprintError("INVALID_OS_RELEASE") from exc
        if len(tokens) != 1:
            raise TargetFingerprintError("INVALID_OS_RELEASE")
        values[key] = tokens[0]
    if set(values) != {"ID", "VERSION_ID"}:
        raise TargetFingerprintError("TARGET_IDENTITY_FIELD_UNAVAILABLE")
    return values


def observe_identity(
    *,
    machine_id_path: Path = Path("/etc/machine-id"),
    hostname_path: Path = Path("/proc/sys/kernel/hostname"),
    os_release_path: Path = Path("/etc/os-release"),
    uname: Callable[[], Any] = os.uname,
    passwd_lookup: Callable[[str], Any] = pwd.getpwnam,
) -> dict[str, Any]:
    try:
        target_id = hostname_path.read_text(encoding="ascii")
        machine_id = machine_id_path.read_text(encoding="ascii")
        system = uname()
        reviewer = passwd_lookup("ubuntu")
    except (KeyError, OSError, UnicodeError) as exc:
        raise TargetFingerprintError("TARGET_IDENTITY_FIELD_UNAVAILABLE") from exc
    os_release = parse_os_release(os_release_path)
    return normalize_identity(
        {
            "target_id": target_id,
            "machine_id": machine_id,
            "operating_system_id": os_release["ID"],
            "operating_system_version_id": os_release["VERSION_ID"],
            "architecture": system.machine,
            "reviewer_name": reviewer.pw_name,
            "reviewer_uid": reviewer.pw_uid,
            "reviewer_gid": reviewer.pw_gid,
            "reviewer_home": reviewer.pw_dir,
        }
    )


def _load_object(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise TargetFingerprintError("INVALID_JSON_INPUT") from exc
    if not isinstance(value, dict):
        raise TargetFingerprintError("INVALID_JSON_INPUT")
    return value


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    try:
        with path.open("rb") as handle:
            for block in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(block)
    except OSError as exc:
        raise TargetFingerprintError("FINGERPRINT_CONTRACT_UNAVAILABLE") from exc
    return digest.hexdigest()


def _timestamp(value: Any) -> datetime:
    if not isinstance(value, str):
        raise TargetFingerprintError("INVALID_AUTHORIZATION_TIMESTAMP")
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00" if value.endswith("Z") else value)
    except ValueError as exc:
        raise TargetFingerprintError("INVALID_AUTHORIZATION_TIMESTAMP") from exc
    if parsed.utcoffset() is None:
        raise TargetFingerprintError("INVALID_AUTHORIZATION_TIMESTAMP")
    return parsed.astimezone(timezone.utc)


def operator_input_format_checker() -> Any:
    from jsonschema import FormatChecker

    checker = FormatChecker()

    @checker.checks("date-time", raises=(TypeError, ValueError))
    def is_date_time(value: object) -> bool:
        if not isinstance(value, str):
            return True
        _timestamp(value)
        return True

    return checker


def _procedure_approval_status(repository_root: Path = ROOT) -> Any:
    module_path = repository_root / "automation" / "procedure_approval.py"
    name = "azpr_h0_target_procedure_approval"
    spec = importlib.util.spec_from_file_location(name, module_path)
    if spec is None or spec.loader is None:
        raise TargetFingerprintError("PROCEDURE_APPROVAL_CHANNEL_UNAVAILABLE")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    try:
        spec.loader.exec_module(module)
        return module.assess_repository_channel(repository_root)
    except Exception as exc:
        raise TargetFingerprintError("PROCEDURE_APPROVAL_CHANNEL_INVALID") from exc
    finally:
        sys.modules.pop(name, None)


def validate_operator_input(
    input_path: Path,
    *,
    schema_path: Path = OPERATOR_SCHEMA_PATH,
    contract_path: Path = CONTRACT_PATH,
    now: datetime | None = None,
    procedure_approval_check: Callable[[], Any] | None = None,
) -> dict[str, Any]:
    value = _load_object(input_path)
    schema = _load_object(schema_path)
    try:
        from jsonschema import Draft202012Validator

        Draft202012Validator.check_schema(schema)
        issues = sorted(
            Draft202012Validator(
                schema, format_checker=operator_input_format_checker()
            ).iter_errors(value),
            key=lambda issue: list(issue.absolute_path),
        )
    except Exception as exc:
        raise TargetFingerprintError("OPERATOR_INPUT_SCHEMA_INVALID") from exc
    if issues:
        raise TargetFingerprintError("OPERATOR_INPUT_SCHEMA_MISMATCH")
    if value.get("status") != "SUPPLIED_REFERENCE_NOT_APPROVAL":
        raise TargetFingerprintError("OPERATOR_INPUT_NOT_SUPPLIED_REFERENCE")

    target = value["target"]
    identity = {field: target[field] for field in FIELD_ORDER}
    normalized = normalize_identity(identity)
    if identity != normalized:
        raise TargetFingerprintError("TARGET_IDENTITY_NOT_NORMALIZED")
    calculated = fingerprint(identity)
    target_digest = target["target_fingerprint_sha256"]
    if not isinstance(target_digest, str) or not hmac.compare_digest(calculated, target_digest):
        raise TargetFingerprintError("TARGET_FINGERPRINT_MISMATCH")
    if target["disposable_target_confirmed"] is not True:
        raise TargetFingerprintError("DISPOSABLE_TARGET_NOT_CONFIRMED")
    if target["local_guest_session_confirmed"] is not True:
        raise TargetFingerprintError("LOCAL_GUEST_SESSION_NOT_CONFIRMED")

    authorization = value["authorization_reference"]
    if authorization["authorized"] is not True:
        raise TargetFingerprintError("EXACT_TARGET_AUTHORIZATION_MISSING")
    if authorization["fingerprint_procedure_approved"] is not True:
        raise TargetFingerprintError("FINGERPRINT_PROCEDURE_APPROVAL_MISSING")
    if "H0-ALV-00" not in authorization["allowed_stage_ids"]:
        raise TargetFingerprintError("H0_ALV_00_AUTHORIZATION_MISSING")
    authorization_digest = authorization["target_fingerprint_sha256"]
    if not isinstance(authorization_digest, str) or not hmac.compare_digest(
        calculated, authorization_digest
    ):
        raise TargetFingerprintError("AUTHORIZATION_TARGET_FINGERPRINT_MISMATCH")
    contract_sha256 = _sha256_file(contract_path)
    authorization_contract_digest = authorization["target_fingerprint_contract_sha256"]
    if not isinstance(authorization_contract_digest, str) or not hmac.compare_digest(
        contract_sha256, authorization_contract_digest
    ):
        raise TargetFingerprintError("AUTHORIZATION_FINGERPRINT_CONTRACT_MISMATCH")
    procedure_status = (
        procedure_approval_check()
        if procedure_approval_check is not None
        else _procedure_approval_status(ROOT)
    )
    if getattr(procedure_status, "approved", False) is not True:
        raise TargetFingerprintError("FINGERPRINT_PROCEDURE_APPROVAL_MISSING")
    procedure_digest = getattr(procedure_status, "procedure_sha256", None)
    if not isinstance(procedure_digest, str) or not hmac.compare_digest(
        procedure_digest, contract_sha256
    ):
        raise TargetFingerprintError("PROCEDURE_APPROVAL_CONTRACT_MISMATCH")
    approval_reference = getattr(procedure_status, "approval_reference", None)
    if authorization["reference"] != approval_reference:
        raise TargetFingerprintError("PROCEDURE_APPROVAL_REFERENCE_MISMATCH")

    authorized_at = _timestamp(authorization["authorized_at"])
    expires_at = _timestamp(authorization["expires_at"])
    observed_now = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    if authorized_at > observed_now or expires_at <= observed_now or expires_at <= authorized_at:
        raise TargetFingerprintError("AUTHORIZATION_WINDOW_INVALID")
    return {
        "authority_effect": False,
        "authorization_reference_valid": True,
        "fingerprint_contract_sha256": contract_sha256,
        "operator_approval_adapter_active": False,
        "schema_draft": "2020-12",
        "target_fingerprint_sha256": calculated,
    }


def _fingerprint_result(identity: Mapping[str, Any], expected: str | None) -> tuple[dict[str, Any], int]:
    normalized = normalize_identity(identity)
    calculated = fingerprint(normalized)
    matches = None
    if expected is not None:
        _observed, matches = compare_fingerprint(normalized, expected)
    result = {
        "authority_effect": False,
        "canonicalization": CANONICALIZATION_ID,
        "contract_id": CONTRACT_ID,
        "identity": normalized,
        "matches_expected": matches,
        "status": "PASS" if matches is not False else "BLOCKED",
        "target_fingerprint_sha256": calculated,
    }
    return result, 0 if matches is not False else 2


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    observe = subparsers.add_parser("observe", help="Observe the fixed identity fields locally")
    observe.add_argument("--expected-sha256")

    calculate = subparsers.add_parser("calculate", help="Calculate from a JSON identity fixture")
    calculate.add_argument("--input", required=True, type=Path)
    calculate.add_argument("--expected-sha256")

    validate = subparsers.add_parser(
        "validate-operator-input",
        help="Validate the human-supplied operator reference without displaying its contents",
    )
    validate.add_argument("--input", required=True, type=Path)
    validate.add_argument("--schema", type=Path, default=OPERATOR_SCHEMA_PATH)
    validate.add_argument("--contract", type=Path, default=CONTRACT_PATH)
    args = parser.parse_args(argv)

    try:
        if args.command == "observe":
            result, exit_code = _fingerprint_result(observe_identity(), args.expected_sha256)
        elif args.command == "calculate":
            result, exit_code = _fingerprint_result(_load_object(args.input), args.expected_sha256)
        else:
            result = validate_operator_input(
                args.input,
                schema_path=args.schema,
                contract_path=args.contract,
            )
            result = {"status": "PASS", **result}
            exit_code = 0
    except TargetFingerprintError as exc:
        result = {
            "authority_effect": False,
            "error_codes": [exc.code],
            "operator_approval_adapter_active": False,
            "status": "BLOCKED",
        }
        exit_code = 2
    print(json.dumps(result, indent=2, sort_keys=True))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
