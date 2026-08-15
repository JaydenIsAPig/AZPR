#!/usr/bin/env python3
"""Fail-closed macOS operator-approval adapter for AZPR.

This module is inert source.  It never creates a key, enrolls an operator,
selects a host path, or activates controller execution.  A later host-owned
installation must provide an absolute helper path, trust record, and replay
ledger outside the repository before the adapter can be constructed.
"""

from __future__ import annotations

import base64
import binascii
import fcntl
import hashlib
import json
import os
import secrets
import selectors
import signal
import stat
import subprocess
import time
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Iterator, Mapping

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec

from automation import approval_manager


ASSERTION_FORMAT = "AZPR_OPERATOR_DECISION_ASSERTION_V1"
ASSERTION_KIND = "AZPR_OPERATOR_DECISION_ASSERTION"
ASSERTION_PURPOSE = "AZPR_OPERATOR_APPROVAL_DECISION_V1"
ASSERTION_ALGORITHM = "ECDSA_MESSAGE_X962_SHA256"
PUBLIC_KEY_ENCODING = "ANSI_X9_63_UNCOMPRESSED_P256"
REQUEST_KIND = "AZPR_OPERATOR_DECISION_REQUEST"
TERMINAL_KIND = "AZPR_OPERATOR_DECISION_TERMINAL"
TRUST_KIND = "AZPR_OPERATOR_AUTHENTICATOR_TRUST"
LEDGER_KIND = "AZPR_OPERATOR_APPROVAL_REPLAY_LEDGER"
HELPER_BUILD_ID = "AZPR_OPERATOR_APPROVAL_HELPER_V1"

MAX_TICKET_BYTES = 256 * 1024
MAX_REQUEST_BYTES = 384 * 1024
MAX_RESPONSE_BYTES = 64 * 1024
MAX_DIAGNOSTIC_BYTES = 16 * 1024
MAX_STRING_BYTES = 16 * 1024
DEFAULT_HELPER_TIMEOUT_SECONDS = 180
MAX_FUTURE_SKEW_SECONDS = 5

SIGNED_PAYLOAD_FIELDS = {
    "format_version",
    "record_kind",
    "purpose",
    "approval_id",
    "ticket_id",
    "ticket_sha256",
    "decision",
    "nonce",
    "requested_at",
    "decided_at",
    "expires_at",
    "authenticator_id",
    "authentication_event_id",
    "key_id",
}
ASSERTION_ENVELOPE_FIELDS = {
    "signed_payload",
    "signature_algorithm",
    "signature_base64",
    "public_key_sha256",
    "helper_build_id",
}
REQUEST_FIELDS = {
    "format_version",
    "record_kind",
    "ticket_base64",
    "nonce",
    "requested_at",
    "expires_at",
    "authenticator_id",
    "key_id",
    "preflight_result",
}
TERMINAL_FIELDS = {
    "format_version",
    "record_kind",
    "status",
    "reason_code",
    "helper_build_id",
}
TRUST_FIELDS = {
    "format_version",
    "record_kind",
    "authenticator_id",
    "helper_path",
    "approved_helper_sha256",
    "code_signing_designated_requirement",
    "helper_build_id",
    "helper_owner_uid",
    "helper_owner_gid",
    "helper_mode",
    "key_id",
    "public_key_encoding",
    "public_key_base64",
    "public_key_sha256",
    "authenticated_operator_subject",
    "allowed_roles",
    "status",
    "enrolled_at",
    "revoked_at",
}


class OperatorApprovalError(approval_manager.ApprovalError):
    """The native operator-approval boundary stopped safely."""


class OperatorApprovalTerminal(OperatorApprovalError):
    """The helper returned a non-authorizing terminal response."""

    def __init__(self, status: str, reason_code: str) -> None:
        super().__init__(f"operator decision ended without authority: {status}/{reason_code}")
        self.status = status
        self.reason_code = reason_code


def _strict_fields(value: Mapping[str, Any], expected: set[str], field: str) -> None:
    missing = sorted(expected - set(value))
    extra = sorted(set(value) - expected)
    if missing or extra:
        raise OperatorApprovalError(f"{field} field mismatch; missing={missing}, extra={extra}")


def _bounded_string(value: Any, field: str, *, maximum: int = 512) -> str:
    if not isinstance(value, str) or not value or len(value.encode("utf-8")) > maximum:
        raise OperatorApprovalError(f"{field} must be a non-empty bounded string")
    return value


def _reject_float(_: str) -> Any:
    raise OperatorApprovalError("floating-point values are forbidden in canonical records")


def _reject_constant(_: str) -> Any:
    raise OperatorApprovalError("non-finite numeric values are forbidden in canonical records")


def _object_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise OperatorApprovalError(f"duplicate JSON object key: {key}")
        result[key] = value
    return result


def strict_canonical_loads(data: bytes, *, maximum_bytes: int) -> Any:
    """Parse exactly one canonical AZPR JSON value with duplicate detection."""

    if not isinstance(data, bytes) or not data or len(data) > maximum_bytes:
        raise OperatorApprovalError("canonical JSON input is empty or exceeds its byte limit")
    try:
        text = data.decode("utf-8", errors="strict")
    except UnicodeDecodeError as exc:
        raise OperatorApprovalError("canonical JSON input is not valid UTF-8") from exc
    try:
        value = json.loads(
            text,
            object_pairs_hook=_object_pairs,
            parse_float=_reject_float,
            parse_constant=_reject_constant,
        )
    except json.JSONDecodeError as exc:
        raise OperatorApprovalError(f"invalid canonical JSON: {exc}") from exc
    if approval_manager.canonical_bytes(value) != data:
        raise OperatorApprovalError("JSON input is not AZPR_CANONICAL_JSON_V1")
    _check_string_bounds(value)
    return value


def _check_string_bounds(value: Any, field: str = "$") -> None:
    if isinstance(value, str):
        if len(value.encode("utf-8")) > MAX_STRING_BYTES:
            raise OperatorApprovalError(f"{field} exceeds the canonical string limit")
        return
    if isinstance(value, list):
        for index, item in enumerate(value):
            _check_string_bounds(item, f"{field}[{index}]")
    elif isinstance(value, dict):
        for key, item in value.items():
            _check_string_bounds(key, f"{field}.<key>")
            _check_string_bounds(item, f"{field}.{key}")


def _decode_base64(value: Any, field: str, *, expected_length: int | None = None) -> bytes:
    text = _bounded_string(value, field, maximum=MAX_STRING_BYTES)
    try:
        decoded = base64.b64decode(text, validate=True)
    except (ValueError, binascii.Error) as exc:
        raise OperatorApprovalError(f"{field} must be strict base64") from exc
    if expected_length is not None and len(decoded) != expected_length:
        raise OperatorApprovalError(f"{field} has the wrong decoded length")
    return decoded


def _parse_utc(value: Any, field: str) -> datetime:
    text = _bounded_string(value, field, maximum=64)
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise OperatorApprovalError(f"{field} must be an ISO-8601 timestamp") from exc
    if parsed.utcoffset() is None:
        raise OperatorApprovalError(f"{field} must include a UTC offset")
    return parsed.astimezone(timezone.utc)


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _path_is_within(path: Path, parent: Path) -> bool:
    try:
        path.resolve().relative_to(parent.resolve())
        return True
    except ValueError:
        return False


@dataclass(frozen=True)
class TrustRecord:
    authenticator_id: str
    helper_path: Path
    approved_helper_sha256: str
    code_signing_designated_requirement: str | None
    helper_build_id: str
    helper_owner_uid: int
    helper_owner_gid: int
    helper_mode: int
    key_id: str
    public_key_bytes: bytes
    public_key_sha256: str
    authenticated_operator_subject: str
    allowed_roles: tuple[str, ...]
    status: str
    enrolled_at: str
    revoked_at: str | None


def load_trust_record(path: Path, *, repository_root: Path) -> TrustRecord:
    if not path.is_absolute() or _path_is_within(path, repository_root):
        raise OperatorApprovalError("trust record must be absolute and outside the repository")
    try:
        metadata = path.lstat()
        if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISREG(metadata.st_mode):
            raise OperatorApprovalError("trust record must be a regular non-symlink file")
        if metadata.st_uid not in {0, os.getuid()} or metadata.st_mode & 0o022:
            raise OperatorApprovalError("trust record ownership or permissions are unsafe")
        raw = path.read_bytes()
    except OSError as exc:
        raise OperatorApprovalError("host-owned trust record is unavailable") from exc
    value = strict_canonical_loads(raw, maximum_bytes=64 * 1024)
    if not isinstance(value, dict):
        raise OperatorApprovalError("trust record must be an object")
    _strict_fields(value, TRUST_FIELDS, "trust_record")
    if value["format_version"] != "1.0" or value["record_kind"] != TRUST_KIND:
        raise OperatorApprovalError("trust record identity is invalid")
    if value["status"] != "ACTIVE":
        raise OperatorApprovalError("trusted key is not ACTIVE")
    if value["public_key_encoding"] != PUBLIC_KEY_ENCODING:
        raise OperatorApprovalError("public key encoding is not the governed X9.63 encoding")
    helper_path_text = _bounded_string(value["helper_path"], "helper_path", maximum=4096)
    helper_path = Path(helper_path_text)
    if not helper_path.is_absolute() or _path_is_within(helper_path, repository_root):
        raise OperatorApprovalError("trusted helper path must be absolute and outside the repository")
    digest = _bounded_string(value["approved_helper_sha256"], "approved_helper_sha256", maximum=64)
    public_digest = _bounded_string(value["public_key_sha256"], "public_key_sha256", maximum=64)
    if not all(len(item) == 64 and all(ch in "0123456789abcdef" for ch in item) for item in (digest, public_digest)):
        raise OperatorApprovalError("trust record SHA-256 values are invalid")
    public_key = _decode_base64(value["public_key_base64"], "public_key_base64", expected_length=65)
    if public_key[0] != 0x04 or _sha256(public_key) != public_digest:
        raise OperatorApprovalError("trusted public key bytes or digest are invalid")
    if value["code_signing_designated_requirement"] is not None:
        _bounded_string(
            value["code_signing_designated_requirement"],
            "code_signing_designated_requirement",
            maximum=4096,
        )
    for field in ("helper_owner_uid", "helper_owner_gid", "helper_mode"):
        if not isinstance(value[field], int) or isinstance(value[field], bool) or value[field] < 0:
            raise OperatorApprovalError(f"{field} must be a non-negative integer")
    if (
        value["helper_mode"] > 0o777
        or value["helper_mode"] & 0o022
        or not value["helper_mode"] & 0o100
    ):
        raise OperatorApprovalError("helper_mode must be owner-executable without special or group/world-write bits")
    roles = value["allowed_roles"]
    if not isinstance(roles, list) or not roles or len(set(roles)) != len(roles):
        raise OperatorApprovalError("allowed_roles must be a unique non-empty array")
    role_values = tuple(_bounded_string(role, "allowed_roles[]", maximum=256) for role in roles)
    enrolled = _bounded_string(value["enrolled_at"], "enrolled_at", maximum=64)
    _parse_utc(enrolled, "enrolled_at")
    revoked_at = value["revoked_at"]
    if revoked_at is not None:
        _parse_utc(revoked_at, "revoked_at")
    helper_build_id = _bounded_string(value["helper_build_id"], "helper_build_id")
    if helper_build_id != HELPER_BUILD_ID:
        raise OperatorApprovalError("trusted helper build identity is unsupported")
    return TrustRecord(
        authenticator_id=_bounded_string(value["authenticator_id"], "authenticator_id"),
        helper_path=helper_path,
        approved_helper_sha256=digest,
        code_signing_designated_requirement=value["code_signing_designated_requirement"],
        helper_build_id=helper_build_id,
        helper_owner_uid=value["helper_owner_uid"],
        helper_owner_gid=value["helper_owner_gid"],
        helper_mode=value["helper_mode"],
        key_id=_bounded_string(value["key_id"], "key_id"),
        public_key_bytes=public_key,
        public_key_sha256=public_digest,
        authenticated_operator_subject=_bounded_string(
            value["authenticated_operator_subject"], "authenticated_operator_subject", maximum=1024
        ),
        allowed_roles=role_values,
        status=value["status"],
        enrolled_at=enrolled,
        revoked_at=revoked_at,
    )


class HelperIdentityVerifier:
    """Verify a fixed native helper before any invocation."""

    MACHO_MAGICS = {
        b"\xfe\xed\xfa\xcf",
        b"\xcf\xfa\xed\xfe",
        b"\xfe\xed\xfa\xce",
        b"\xce\xfa\xed\xfe",
        b"\xca\xfe\xba\xbe",
        b"\xbe\xba\xfe\xca",
        b"\xca\xfe\xba\xbf",
        b"\xbf\xba\xfe\xca",
    }

    def __init__(self, trust: TrustRecord) -> None:
        self.trust = trust

    def verify(self) -> None:
        path = self.trust.helper_path
        if not path.is_absolute():
            raise OperatorApprovalError("helper path is not absolute")
        try:
            metadata = path.lstat()
        except OSError as exc:
            raise OperatorApprovalError("trusted helper is unavailable") from exc
        if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISREG(metadata.st_mode):
            raise OperatorApprovalError("trusted helper must be a regular non-symlink file")
        if metadata.st_uid != self.trust.helper_owner_uid or metadata.st_gid != self.trust.helper_owner_gid:
            raise OperatorApprovalError("trusted helper ownership drifted")
        if stat.S_IMODE(metadata.st_mode) != self.trust.helper_mode:
            raise OperatorApprovalError("trusted helper permissions drifted")
        try:
            data = path.read_bytes()
        except OSError as exc:
            raise OperatorApprovalError("trusted helper cannot be read for hashing") from exc
        if len(data) < 4 or data[:4] not in self.MACHO_MAGICS:
            raise OperatorApprovalError("trusted helper is not a native Mach-O executable")
        if _sha256(data) != self.trust.approved_helper_sha256:
            raise OperatorApprovalError("trusted helper SHA-256 drifted")
        if self.trust.code_signing_designated_requirement is not None:
            argv = [
                "/usr/bin/codesign",
                "--verify",
                "--strict",
                f"-R={self.trust.code_signing_designated_requirement}",
                str(path),
            ]
            completed = subprocess.run(
                argv,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                env={"PATH": "/usr/bin:/bin", "LANG": "C", "LC_ALL": "C"},
                timeout=30,
                check=False,
                shell=False,
            )
            if completed.returncode != 0:
                raise OperatorApprovalError("trusted helper code signature or designated requirement failed")


class NativeHelperProcess:
    """Invoke the already verified helper with a bounded canonical protocol."""

    def __init__(self, trust: TrustRecord, *, timeout_seconds: int = DEFAULT_HELPER_TIMEOUT_SECONDS) -> None:
        if timeout_seconds <= 0 or timeout_seconds > 600:
            raise OperatorApprovalError("helper timeout is outside the allowed range")
        self.trust = trust
        self.timeout_seconds = timeout_seconds

    def invoke(self, request_bytes: bytes) -> bytes:
        if len(request_bytes) > MAX_REQUEST_BYTES:
            raise OperatorApprovalError("helper request exceeds the byte limit")
        HelperIdentityVerifier(self.trust).verify()
        completed = _run_bounded_subprocess(
            [str(self.trust.helper_path)],
            input_bytes=request_bytes,
            cwd="/",
            env={"PATH": "/usr/bin:/bin", "LANG": "C", "LC_ALL": "C"},
            timeout_seconds=self.timeout_seconds,
            stdout_limit=MAX_RESPONSE_BYTES,
            stderr_limit=MAX_DIAGNOSTIC_BYTES,
        )
        if completed.returncode < 0:
            raise OperatorApprovalTerminal("ERROR", "HELPER_SIGNAL_EXIT")
        if completed.returncode != 0:
            raise OperatorApprovalTerminal("ERROR", f"HELPER_EXIT_{completed.returncode}")
        return completed.stdout


@dataclass(frozen=True)
class _BoundedProcessResult:
    returncode: int
    stdout: bytes
    stderr: bytes


def _terminate_process_group(process: subprocess.Popen[bytes]) -> None:
    if process.poll() is None:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except (OSError, ProcessLookupError):
            process.kill()
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait()


def _run_bounded_subprocess(
    argv: list[str],
    *,
    input_bytes: bytes,
    cwd: str,
    env: Mapping[str, str],
    timeout_seconds: int,
    stdout_limit: int,
    stderr_limit: int,
) -> _BoundedProcessResult:
    """Run one argv without a shell while never buffering beyond fixed limits."""

    try:
        process = subprocess.Popen(
            argv,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=cwd,
            env=dict(env),
            shell=False,
            start_new_session=True,
            bufsize=0,
        )
    except OSError as exc:
        raise OperatorApprovalTerminal("ERROR", "HELPER_LAUNCH_FAILED") from exc
    if process.stdin is None or process.stdout is None or process.stderr is None:
        _terminate_process_group(process)
        raise OperatorApprovalTerminal("ERROR", "HELPER_PIPE_SETUP_FAILED")

    streams = selectors.DefaultSelector()
    buffers = {"stdout": bytearray(), "stderr": bytearray()}
    limits = {"stdout": stdout_limit, "stderr": stderr_limit}
    input_offset = 0
    for stream in (process.stdin, process.stdout, process.stderr):
        os.set_blocking(stream.fileno(), False)
    streams.register(process.stdin, selectors.EVENT_WRITE, "stdin")
    streams.register(process.stdout, selectors.EVENT_READ, "stdout")
    streams.register(process.stderr, selectors.EVENT_READ, "stderr")
    deadline = time.monotonic() + timeout_seconds

    try:
        while streams.get_map():
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise OperatorApprovalTerminal("TIMED_OUT", "HELPER_TIMEOUT")
            for key, _ in streams.select(min(0.1, remaining)):
                stream = key.fileobj
                name = key.data
                if name == "stdin":
                    try:
                        written = os.write(stream.fileno(), input_bytes[input_offset : input_offset + 64 * 1024])
                        input_offset += written
                    except BrokenPipeError:
                        input_offset = len(input_bytes)
                    if input_offset == len(input_bytes):
                        streams.unregister(stream)
                        stream.close()
                    continue

                chunk = os.read(stream.fileno(), min(8192, limits[name] + 1 - len(buffers[name])))
                if not chunk:
                    streams.unregister(stream)
                    stream.close()
                    continue
                buffers[name].extend(chunk)
                if len(buffers[name]) > limits[name]:
                    raise OperatorApprovalError("helper output exceeded its byte limit")
        remaining = max(0.001, deadline - time.monotonic())
        returncode = process.wait(timeout=remaining)
    except subprocess.TimeoutExpired as exc:
        _terminate_process_group(process)
        raise OperatorApprovalTerminal("TIMED_OUT", "HELPER_TIMEOUT") from exc
    except OSError as exc:
        _terminate_process_group(process)
        raise OperatorApprovalTerminal("ERROR", "HELPER_PROCESS_IO_FAILED") from exc
    except OperatorApprovalError:
        _terminate_process_group(process)
        raise
    finally:
        streams.close()
        for stream in (process.stdin, process.stdout, process.stderr):
            if stream is not None and not stream.closed:
                stream.close()

    return _BoundedProcessResult(returncode, bytes(buffers["stdout"]), bytes(buffers["stderr"]))


@dataclass(frozen=True)
class PendingChallenge:
    approval_id: str
    ticket_id: str
    ticket_sha256: str
    nonce: str
    requested_at: str
    expires_at: str
    authenticator_id: str
    key_id: str


class ApprovalReplayLedger:
    """Locked, atomic, host-owned one-attempt nonce state."""

    def __init__(self, path: Path, *, repository_root: Path) -> None:
        if not path.is_absolute() or _path_is_within(path, repository_root):
            raise OperatorApprovalError("replay ledger must be absolute and outside the repository")
        if not path.parent.is_dir() or path.parent.is_symlink():
            raise OperatorApprovalError("replay ledger parent must be an existing non-symlink directory")
        parent_metadata = path.parent.stat()
        if parent_metadata.st_uid not in {0, os.getuid()} or parent_metadata.st_mode & 0o022:
            raise OperatorApprovalError("replay ledger parent ownership or permissions are unsafe")
        self.path = path
        self.lock_path = path.with_name(path.name + ".lock")

    @contextmanager
    def _locked(self) -> Iterator[None]:
        flags = os.O_RDWR | os.O_CREAT | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
        descriptor = os.open(self.lock_path, flags, 0o600)
        try:
            metadata = os.fstat(descriptor)
            if not stat.S_ISREG(metadata.st_mode) or metadata.st_uid != os.getuid():
                raise OperatorApprovalError("replay ledger lock ownership or type is unsafe")
            os.fchmod(descriptor, 0o600)
            fcntl.flock(descriptor, fcntl.LOCK_EX)
            yield
        finally:
            fcntl.flock(descriptor, fcntl.LOCK_UN)
            os.close(descriptor)

    def _empty(self) -> dict[str, Any]:
        return {"format_version": "1.0", "record_kind": LEDGER_KIND, "challenges": {}}

    def _read(self) -> dict[str, Any]:
        if not self.path.exists():
            return self._empty()
        metadata = self.path.lstat()
        if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISREG(metadata.st_mode):
            raise OperatorApprovalError("replay ledger must be a regular non-symlink file")
        if metadata.st_uid != os.getuid() or stat.S_IMODE(metadata.st_mode) != 0o600:
            raise OperatorApprovalError("replay ledger ownership or permissions are unsafe")
        value = strict_canonical_loads(self.path.read_bytes(), maximum_bytes=2 * 1024 * 1024)
        if not isinstance(value, dict) or set(value) != {"format_version", "record_kind", "challenges"}:
            raise OperatorApprovalError("replay ledger structure is invalid")
        if value["format_version"] != "1.0" or value["record_kind"] != LEDGER_KIND:
            raise OperatorApprovalError("replay ledger identity is invalid")
        if not isinstance(value["challenges"], dict):
            raise OperatorApprovalError("replay ledger challenges are invalid")
        return value

    def _write(self, value: Mapping[str, Any]) -> None:
        data = approval_manager.canonical_bytes(dict(value))
        temporary = self.path.with_name(f".{self.path.name}.{secrets.token_hex(8)}.tmp")
        descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        try:
            with os.fdopen(descriptor, "wb", closefd=True) as handle:
                handle.write(data)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, self.path)
            directory = os.open(self.path.parent, os.O_RDONLY)
            try:
                os.fsync(directory)
            finally:
                os.close(directory)
        finally:
            if temporary.exists():
                temporary.unlink()

    def register(self, challenge: PendingChallenge) -> None:
        with self._locked():
            value = self._read()
            challenges = value["challenges"]
            if challenge.nonce in challenges:
                raise OperatorApprovalError("authorization nonce already exists")
            challenges[challenge.nonce] = {
                "approval_id": challenge.approval_id,
                "ticket_id": challenge.ticket_id,
                "ticket_sha256": challenge.ticket_sha256,
                "requested_at": challenge.requested_at,
                "expires_at": challenge.expires_at,
                "authenticator_id": challenge.authenticator_id,
                "key_id": challenge.key_id,
                "state": "PENDING",
                "assertion_sha256": None,
                "run_id": None,
                "claimed_actions": [],
                "terminal_reason": None,
            }
            self._write(value)

    def mark_verified(self, challenge: PendingChallenge, assertion_sha256: str) -> None:
        with self._locked():
            value = self._read()
            record = value["challenges"].get(challenge.nonce)
            if not isinstance(record, dict) or record.get("state") != "PENDING":
                raise OperatorApprovalError("authorization nonce is absent or no longer pending")
            self._assert_binding(record, challenge)
            record["state"] = "VERIFIED"
            record["assertion_sha256"] = assertion_sha256
            self._write(value)

    def mark_terminal(self, challenge: PendingChallenge, reason: str) -> None:
        with self._locked():
            value = self._read()
            record = value["challenges"].get(challenge.nonce)
            if not isinstance(record, dict) or record.get("state") != "PENDING":
                raise OperatorApprovalError("authorization nonce is absent or no longer pending")
            self._assert_binding(record, challenge)
            record["state"] = "TERMINAL"
            record["terminal_reason"] = _bounded_string(reason, "terminal_reason")
            self._write(value)

    def claim_action(
        self,
        challenge: PendingChallenge,
        *,
        assertion_sha256: str,
        run_id: str,
        action_id: str,
    ) -> None:
        with self._locked():
            value = self._read()
            record = value["challenges"].get(challenge.nonce)
            if not isinstance(record, dict) or record.get("state") not in {"VERIFIED", "CONSUMED"}:
                raise OperatorApprovalError("authorization nonce is not available for execution")
            self._assert_binding(record, challenge)
            if record.get("assertion_sha256") != assertion_sha256:
                raise OperatorApprovalError("authorization assertion changed before execution")
            if record["state"] == "VERIFIED":
                record["state"] = "CONSUMED"
                record["run_id"] = _bounded_string(run_id, "run_id")
            elif record.get("run_id") != run_id:
                raise OperatorApprovalError("consumed authorization cannot be replayed by another run")
            claimed = record.get("claimed_actions")
            if not isinstance(claimed, list) or action_id in claimed:
                raise OperatorApprovalError("material action was already claimed")
            claimed.append(_bounded_string(action_id, "action_id"))
            self._write(value)

    @staticmethod
    def _assert_binding(record: Mapping[str, Any], challenge: PendingChallenge) -> None:
        for field in (
            "approval_id",
            "ticket_id",
            "ticket_sha256",
            "requested_at",
            "expires_at",
            "authenticator_id",
            "key_id",
        ):
            if record.get(field) != getattr(challenge, field):
                raise OperatorApprovalError("stored challenge binding drifted")


@dataclass(frozen=True)
class VerifiedOperatorAssertion:
    envelope: dict[str, Any]
    challenge: PendingChallenge
    authentication: approval_manager.VerifiedAuthentication
    decision: str
    assertion_sha256: str


class OperatorAssertionVerifier:
    def __init__(self, trust: TrustRecord) -> None:
        self.trust = trust

    def verify(
        self,
        response_bytes: bytes,
        *,
        challenge: PendingChallenge,
        ticket: Mapping[str, Any],
        now: str,
    ) -> VerifiedOperatorAssertion:
        value = strict_canonical_loads(response_bytes, maximum_bytes=MAX_RESPONSE_BYTES)
        if not isinstance(value, dict):
            raise OperatorApprovalError("helper response must be an object")
        if value.get("record_kind") == TERMINAL_KIND:
            _strict_fields(value, TERMINAL_FIELDS, "terminal_response")
            if value["format_version"] != "1.0" or value["helper_build_id"] != self.trust.helper_build_id:
                raise OperatorApprovalError("terminal helper identity is invalid")
            status = _bounded_string(value["status"], "status")
            if status not in {"CANCELED", "TIMED_OUT", "AUTHENTICATION_FAILED", "UNAVAILABLE", "ERROR"}:
                raise OperatorApprovalError("terminal response status is invalid")
            raise OperatorApprovalTerminal(status, _bounded_string(value["reason_code"], "reason_code"))
        _strict_fields(value, ASSERTION_ENVELOPE_FIELDS, "assertion")
        payload = value["signed_payload"]
        if not isinstance(payload, dict):
            raise OperatorApprovalError("signed_payload must be an object")
        _strict_fields(payload, SIGNED_PAYLOAD_FIELDS, "signed_payload")
        constants = {
            "format_version": "1.0",
            "record_kind": ASSERTION_KIND,
            "purpose": ASSERTION_PURPOSE,
        }
        if any(payload[field] != expected for field, expected in constants.items()):
            raise OperatorApprovalError("signed payload identity is invalid")
        if value["signature_algorithm"] != ASSERTION_ALGORITHM:
            raise OperatorApprovalError("signature algorithm is invalid")
        if value["public_key_sha256"] != self.trust.public_key_sha256:
            raise OperatorApprovalError("assertion public-key digest is untrusted")
        if value["helper_build_id"] != self.trust.helper_build_id:
            raise OperatorApprovalError("helper build identity drifted")
        expected = {
            "approval_id": challenge.approval_id,
            "ticket_id": challenge.ticket_id,
            "ticket_sha256": challenge.ticket_sha256,
            "nonce": challenge.nonce,
            "requested_at": challenge.requested_at,
            "expires_at": challenge.expires_at,
            "authenticator_id": challenge.authenticator_id,
            "key_id": challenge.key_id,
        }
        for field, expected_value in expected.items():
            if payload[field] != expected_value:
                raise OperatorApprovalError(f"signed payload {field} does not match the pending challenge")
        if payload["approval_id"] != ticket.get("approval_id") or payload["ticket_id"] != ticket.get("ticket_id"):
            raise OperatorApprovalError("signed payload targets a different ticket")
        if payload["decision"] not in {"APPROVED", "REJECTED"}:
            raise OperatorApprovalError("signed decision is invalid")
        _bounded_string(payload["authentication_event_id"], "authentication_event_id")
        requested = _parse_utc(payload["requested_at"], "requested_at")
        decided = _parse_utc(payload["decided_at"], "decided_at")
        expires = _parse_utc(payload["expires_at"], "expires_at")
        current = _parse_utc(now, "now")
        if decided < requested or decided > current + timedelta(seconds=MAX_FUTURE_SKEW_SECONDS):
            raise OperatorApprovalError("decision timestamp is outside the allowed window")
        if current >= expires or expires <= decided:
            raise OperatorApprovalError("operator assertion is expired or has invalid validity")
        maximum = timedelta(seconds=int(ticket["validity"]["maximum_duration_seconds"]))
        if expires > requested + maximum:
            raise OperatorApprovalError("operator assertion validity exceeds the ticket policy")
        signature = _decode_base64(value["signature_base64"], "signature_base64")
        try:
            public_key = ec.EllipticCurvePublicKey.from_encoded_point(ec.SECP256R1(), self.trust.public_key_bytes)
            public_key.verify(
                signature,
                approval_manager.canonical_bytes(payload),
                ec.ECDSA(hashes.SHA256()),
            )
        except (ValueError, InvalidSignature) as exc:
            raise OperatorApprovalError("operator assertion signature verification failed") from exc
        role = self._authorized_role(ticket)
        authentication = approval_manager.VerifiedAuthentication(
            subject=self.trust.authenticated_operator_subject,
            role=role,
            authenticator_id=self.trust.authenticator_id,
            authentication_event_id=payload["authentication_event_id"],
            authenticated_at=payload["decided_at"],
            ticket_digest_challenge=challenge.ticket_sha256,
        )
        return VerifiedOperatorAssertion(
            envelope=value,
            challenge=challenge,
            authentication=authentication,
            decision=payload["decision"],
            assertion_sha256=_sha256(response_bytes),
        )

    def _authorized_role(self, ticket: Mapping[str, Any]) -> str:
        ticket_roles = ticket.get("authentication_policy", {}).get("allowed_roles", [])
        common = sorted(set(ticket_roles).intersection(self.trust.allowed_roles))
        if len(common) != 1:
            raise OperatorApprovalError("trusted operator role is absent or ambiguous for this ticket")
        return common[0]


def _challenge_from_payload(payload: Mapping[str, Any]) -> PendingChallenge:
    return PendingChallenge(
        approval_id=payload["approval_id"],
        ticket_id=payload["ticket_id"],
        ticket_sha256=payload["ticket_sha256"],
        nonce=payload["nonce"],
        requested_at=payload["requested_at"],
        expires_at=payload["expires_at"],
        authenticator_id=payload["authenticator_id"],
        key_id=payload["key_id"],
    )


def build_operator_decision_record(
    verified: VerifiedOperatorAssertion,
) -> dict[str, Any]:
    payload = verified.envelope["signed_payload"]
    authentication = verified.authentication
    return {
        "format_version": "1.0",
        "record_kind": "AZPR_APPROVAL_DECISION",
        "approval_id": payload["approval_id"],
        "ticket_id": payload["ticket_id"],
        "ticket_sha256": payload["ticket_sha256"],
        "decision": payload["decision"],
        "decided_at": payload["decided_at"],
        "expires_at": payload["expires_at"],
        "authenticated_actor": {
            "subject": authentication.subject,
            "role": authentication.role,
        },
        "authentication_binding": {
            "authenticator_id": authentication.authenticator_id,
            "authentication_event_id": authentication.authentication_event_id,
            "authenticated_at": authentication.authenticated_at,
            "ticket_digest_challenge": authentication.ticket_digest_challenge,
        },
        "operator_assertion": verified.envelope,
    }


class OperatorApprovalService:
    """Coordinate pending challenges without granting execution by itself."""

    def __init__(
        self,
        *,
        repository_root: Path,
        trust_record_path: Path,
        replay_ledger_path: Path,
        timeout_seconds: int = DEFAULT_HELPER_TIMEOUT_SECONDS,
        now: Callable[[], datetime] | None = None,
    ) -> None:
        self.repository_root = repository_root.resolve()
        self.trust_record_path = trust_record_path
        self.ledger = ApprovalReplayLedger(replay_ledger_path, repository_root=self.repository_root)
        self.timeout_seconds = timeout_seconds
        self.now = now or (lambda: datetime.now(timezone.utc))

    def _trust(self) -> TrustRecord:
        return load_trust_record(self.trust_record_path, repository_root=self.repository_root)

    def begin_challenge(
        self,
        *,
        manifest_path: Path,
        ticket_path: Path,
        review_path: Path,
        preflight_result: str,
    ) -> tuple[PendingChallenge, bytes, dict[str, Any], TrustRecord]:
        if preflight_result != "PASS":
            raise OperatorApprovalError("preflight must PASS before the approval helper opens")
        ticket_sha256 = approval_manager.validate_ticket_artifacts(
            self.repository_root, manifest_path, ticket_path, review_path
        )
        ticket_bytes = ticket_path.read_bytes()
        if len(ticket_bytes) > MAX_TICKET_BYTES:
            raise OperatorApprovalError("canonical ticket exceeds the helper input limit")
        ticket = approval_manager.load_canonical_object(ticket_path)
        trust = self._trust()
        HelperIdentityVerifier(trust).verify()
        requested = self.now().astimezone(timezone.utc)
        maximum = timedelta(seconds=int(ticket["validity"]["maximum_duration_seconds"]))
        expires = requested + maximum
        nonce = base64.urlsafe_b64encode(secrets.token_bytes(32)).rstrip(b"=").decode("ascii")
        challenge = PendingChallenge(
            approval_id=ticket["approval_id"],
            ticket_id=ticket["ticket_id"],
            ticket_sha256=ticket_sha256,
            nonce=nonce,
            requested_at=requested.isoformat().replace("+00:00", "Z"),
            expires_at=expires.isoformat().replace("+00:00", "Z"),
            authenticator_id=trust.authenticator_id,
            key_id=trust.key_id,
        )
        self.ledger.register(challenge)
        request = {
            "format_version": "1.0",
            "record_kind": REQUEST_KIND,
            "ticket_base64": base64.b64encode(ticket_bytes).decode("ascii"),
            "nonce": challenge.nonce,
            "requested_at": challenge.requested_at,
            "expires_at": challenge.expires_at,
            "authenticator_id": challenge.authenticator_id,
            "key_id": challenge.key_id,
            "preflight_result": preflight_result,
        }
        request_bytes = approval_manager.canonical_bytes(request)
        if len(request_bytes) > MAX_REQUEST_BYTES:
            raise OperatorApprovalError("canonical helper request exceeds its limit")
        return challenge, request_bytes, ticket, trust

    def request_decision(
        self,
        *,
        manifest_path: Path,
        ticket_path: Path,
        review_path: Path,
        decision_path: Path,
        preflight_result: str,
    ) -> dict[str, Any]:
        challenge, request, ticket, trust = self.begin_challenge(
            manifest_path=manifest_path,
            ticket_path=ticket_path,
            review_path=review_path,
            preflight_result=preflight_result,
        )
        try:
            response = NativeHelperProcess(trust, timeout_seconds=self.timeout_seconds).invoke(request)
            verified = OperatorAssertionVerifier(trust).verify(
                response,
                challenge=challenge,
                ticket=ticket,
                now=self.now().astimezone(timezone.utc).isoformat(),
            )
        except OperatorApprovalTerminal as exc:
            self.ledger.mark_terminal(challenge, f"{exc.status}:{exc.reason_code}")
            raise
        if verified.decision == "REJECTED":
            self.ledger.mark_terminal(challenge, "SIGNED_REJECTION")
        else:
            self.ledger.mark_verified(challenge, verified.assertion_sha256)
        decision = build_operator_decision_record(verified)
        approval_manager.write_canonical(decision_path, decision)
        return decision

    def authorize_material_action(
        self,
        *,
        manifest_path: Path,
        ticket_path: Path,
        review_path: Path,
        decision_path: Path,
        observed_targets: Mapping[str, Any],
        run_id: str,
        action_id: str,
        now: str,
    ) -> dict[str, Any]:
        approval_manager.validate_ticket_artifacts(
            self.repository_root, manifest_path, ticket_path, review_path
        )
        ticket = approval_manager.load_canonical_object(ticket_path)
        decision = approval_manager.load_canonical_object(decision_path)
        if decision.get("decision") != "APPROVED":
            raise OperatorApprovalError("a rejected decision cannot authorize execution")
        envelope = decision.get("operator_assertion")
        if not isinstance(envelope, dict):
            raise OperatorApprovalError("decision does not retain the operator assertion")
        response = approval_manager.canonical_bytes(envelope)
        payload = envelope.get("signed_payload")
        if not isinstance(payload, dict):
            raise OperatorApprovalError("decision assertion payload is invalid")
        challenge = _challenge_from_payload(payload)
        trust = self._trust()
        verified = OperatorAssertionVerifier(trust).verify(
            response, challenge=challenge, ticket=ticket, now=now
        )
        if build_operator_decision_record(verified) != decision:
            raise OperatorApprovalError("decision artifact drifted after assertion verification")
        expected_targets = {item["action_id"]: item["target"] for item in ticket["actions"]}
        if dict(observed_targets) != expected_targets:
            raise OperatorApprovalError("observed execution targets drifted")
        if action_id not in expected_targets:
            raise OperatorApprovalError("material action is outside the ticket")
        self.ledger.claim_action(
            challenge,
            assertion_sha256=verified.assertion_sha256,
            run_id=run_id,
            action_id=action_id,
        )
        authorization = approval_manager.authorize_execution(
            root=self.repository_root,
            manifest_path=manifest_path,
            ticket_path=ticket_path,
            review_path=review_path,
            decision_path=decision_path,
            observed_targets=observed_targets,
            authentication_verifier=lambda _: verified.authentication,
            now=now,
        )
        return {**authorization, "run_id": run_id, "material_action_id": action_id}


def validate_helper_request(data: bytes) -> dict[str, Any]:
    """Shared protocol validator used by Python golden tests."""

    value = strict_canonical_loads(data, maximum_bytes=MAX_REQUEST_BYTES)
    if not isinstance(value, dict):
        raise OperatorApprovalError("helper request must be an object")
    _strict_fields(value, REQUEST_FIELDS, "helper_request")
    if value["format_version"] != "1.0" or value["record_kind"] != REQUEST_KIND:
        raise OperatorApprovalError("helper request identity is invalid")
    ticket = _decode_base64(value["ticket_base64"], "ticket_base64")
    strict_canonical_loads(ticket, maximum_bytes=MAX_TICKET_BYTES)
    if value["preflight_result"] not in {"PASS", "FAIL", "NOT_RUN"}:
        raise OperatorApprovalError("preflight_result is invalid")
    nonce = _bounded_string(value["nonce"], "nonce")
    nonce_alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_"
    if len(nonce) != 43 or any(character not in nonce_alphabet for character in nonce):
        raise OperatorApprovalError("nonce must encode exactly 256 bits as unpadded base64url")
    for field in ("authenticator_id", "key_id"):
        _bounded_string(value[field], field)
    _parse_utc(value["requested_at"], "requested_at")
    _parse_utc(value["expires_at"], "expires_at")
    return value
