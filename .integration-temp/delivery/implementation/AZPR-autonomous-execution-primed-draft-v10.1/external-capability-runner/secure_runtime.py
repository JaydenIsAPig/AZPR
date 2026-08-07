#!/usr/bin/env python3
"""Security primitives for the AZPR autonomous controller.

This module is intentionally independent from repository-controlled application
code. In production it must be installed with the trusted controller/runner,
not imported from an agent-writable working tree.
"""
from __future__ import annotations

import base64
import errno
import hashlib
import json
import os
import re
import secrets
import stat
import subprocess
import sys
import tempfile
import sqlite3
import shutil
import io
import zipfile
import unicodedata
from xml.etree import ElementTree as ET
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any, Iterable, Iterator, Sequence

try:
    import fcntl
except ImportError as exc:  # pragma: no cover - fail closed on unsupported OS
    raise RuntimeError("AZPR secure runtime requires POSIX file locking (fcntl).") from exc

try:
    import jsonschema
    from referencing import Registry, Resource
except ImportError as exc:  # pragma: no cover
    raise RuntimeError("AZPR requires jsonschema; schema validation is never optional.") from exc

try:
    from cryptography.exceptions import InvalidSignature
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric.ed25519 import (
        Ed25519PrivateKey,
        Ed25519PublicKey,
    )
except ImportError as exc:  # pragma: no cover
    raise RuntimeError("AZPR requires cryptography with Ed25519 support.") from exc

ZERO_HASH = "0" * 64
CONTROL_CHAR_RE = re.compile(r"[\x00-\x1f\x7f]")
HEX64_RE = re.compile(r"^[0-9a-f]{64}$")


class SecurityError(RuntimeError):
    """Fail-closed security policy violation."""


DOCX_NS={"w":"http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
def derive_docx_source_manifest(raw:bytes,source_name:str)->dict[str,Any]:
    """Derive stable paragraph units from the exact governing DOCX bytes."""
    try:
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            xml=archive.read("word/document.xml")
    except Exception as exc:
        raise SecurityError("governing policy source is not a valid DOCX") from exc
    try:root=ET.fromstring(xml)
    except ET.ParseError as exc:raise SecurityError("governing policy DOCX XML is invalid") from exc
    units=[]
    for paragraph in root.findall(".//w:body/w:p",DOCX_NS):
        text="".join((node.text or "") for node in paragraph.findall(".//w:t",DOCX_NS)).strip()
        if not text:continue
        style_node=paragraph.find("./w:pPr/w:pStyle",DOCX_NS)
        style=style_node.attrib.get("{%s}val"%DOCX_NS["w"],"") if style_node is not None else ""
        normalized=unicodedata.normalize("NFKC"," ".join(text.split()))
        ordinal=len(units)+1
        units.append({"unit_id":f"p{ordinal:06d}","ordinal":ordinal,"style":style[:200],"text_sha256":sha256_bytes(text.encode("utf-8")),"normalized_text_sha256":sha256_bytes(normalized.encode("utf-8"))})
    if not units:raise SecurityError("governing policy DOCX has no nonempty paragraph units")
    return {"format_version":"1.0","algorithm":"AZPR_DOCX_PARAGRAPH_UNITS_V1","source_document_name":source_name,"source_document_sha256":sha256_bytes(raw),"unit_count":len(units),"unit_chain_sha256":sha256_bytes(canonical_json_bytes(units)),"units":units}


def canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def parse_utc(value: str, label: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (TypeError, ValueError) as exc:
        raise SecurityError(f"{label} must be an ISO-8601 timestamp.") from exc
    if parsed.tzinfo is None:
        raise SecurityError(f"{label} must include a timezone.")
    return parsed.astimezone(timezone.utc)


def validate_json(instance: Any, schema_path: Path, *, label: str) -> None:
    if not schema_path.is_file() or schema_path.is_symlink():
        raise SecurityError(f"Required schema is missing or unsafe: {schema_path}")
    try:
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SecurityError(f"Invalid schema {schema_path}: {exc}") from exc
    registry = Registry()
    for candidate in schema_path.parent.glob("*.json"):
        try:
            sibling = json.loads(candidate.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        identifier = sibling.get("$id") if isinstance(sibling, dict) else None
        if isinstance(identifier, str):
            registry = registry.with_resource(identifier, Resource.from_contents(sibling))
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
        raise SecurityError(f"{label} failed schema validation:\n- " + "\n- ".join(rendered))


def ensure_no_control_chars(value: str, label: str) -> None:
    if CONTROL_CHAR_RE.search(value):
        raise SecurityError(f"{label} contains a control character and is rejected.")


def safe_relative_path(value: str, label: str = "path") -> str:
    ensure_no_control_chars(value, label)
    if "\\" in value:
        raise SecurityError(f"{label} must use POSIX separators.")
    path = PurePosixPath(value)
    if path.is_absolute() or not value or any(part in {"", ".", ".."} for part in path.parts):
        raise SecurityError(f"{label} must be a normalized repository-relative path: {value!r}")
    return path.as_posix()


def no_symlink_ancestors(path: Path, *, allow_missing_leaf: bool = True) -> None:
    absolute = path.absolute()
    parts = absolute.parts
    cursor = Path(parts[0])
    for index, part in enumerate(parts[1:], start=1):
        cursor = cursor / part
        is_leaf = index == len(parts) - 1
        try:
            info = os.lstat(cursor)
        except FileNotFoundError:
            if allow_missing_leaf or not is_leaf:
                continue
            raise SecurityError(f"Required path does not exist: {cursor}")
        if stat.S_ISLNK(info.st_mode):
            raise SecurityError(f"Symlink ancestry is forbidden for trusted path: {cursor}")


def secure_mkdir(path: Path, mode: int = 0o700) -> None:
    no_symlink_ancestors(path, allow_missing_leaf=True)
    path.mkdir(parents=True, exist_ok=True)
    no_symlink_ancestors(path, allow_missing_leaf=False)
    os.chmod(path, mode)
    info = os.stat(path)
    if not stat.S_ISDIR(info.st_mode):
        raise SecurityError(f"Expected directory: {path}")
    if info.st_mode & 0o077:
        raise SecurityError(f"Trusted directory must be owner-only (0700): {path}")


def secure_write_bytes(
    path: Path,
    data: bytes,
    mode: int = 0o600,
    *,
    create_once: bool = False,
) -> None:
    """Write a trusted external file without following symlinks.

    ``create_once`` is mandatory for immutable records and evidence. Existing
    regular files are never silently replaced in that mode.
    """
    secure_mkdir(path.parent)
    no_symlink_ancestors(path, allow_missing_leaf=True)
    flags = os.O_WRONLY | os.O_CREAT
    flags |= os.O_EXCL if create_once else os.O_TRUNC
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    fd = os.open(path, flags, mode)
    try:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
            raise SecurityError(f"Trusted output must be a single-link regular file: {path}")
        os.fchmod(fd, mode)
        view = memoryview(data)
        while view:
            written = os.write(fd, view)
            view = view[written:]
        os.fsync(fd)
    finally:
        os.close(fd)
    directory_fd = os.open(path.parent, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
    try:
        os.fsync(directory_fd)
    finally:
        os.close(directory_fd)


def secure_repo_write_bytes(
    repo_root: Path,
    relative_path: str,
    data: bytes,
    *,
    mode: int = 0o644,
    create_once: bool = False,
) -> None:
    """Descriptor-relative repository write with no-follow semantics.

    Every path segment is opened relative to a trusted repository descriptor.
    Symlinks, hard-linked leaves, devices, FIFOs, and sockets are rejected at
    the moment of the write rather than only during an earlier preflight.
    """
    normalized = safe_relative_path(relative_path, "controller output path")
    root = repo_root.resolve(strict=True)
    root_fd = os.open(root, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
    current_fd = root_fd
    opened: list[int] = []
    try:
        parts = PurePosixPath(normalized).parts
        for part in parts[:-1]:
            flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)
            if hasattr(os, "O_NOFOLLOW"):
                flags |= os.O_NOFOLLOW
            try:
                next_fd = os.open(part, flags, dir_fd=current_fd)
            except FileNotFoundError:
                os.mkdir(part, 0o755, dir_fd=current_fd)
                next_fd = os.open(part, flags, dir_fd=current_fd)
            except OSError as exc:
                raise SecurityError(f"Unsafe controller output ancestor: {part}") from exc
            info = os.fstat(next_fd)
            if not stat.S_ISDIR(info.st_mode):
                raise SecurityError(f"Controller output ancestor is not a directory: {part}")
            opened.append(next_fd)
            current_fd = next_fd
        leaf_flags = os.O_WRONLY | os.O_CREAT
        leaf_flags |= os.O_EXCL if create_once else os.O_TRUNC
        if hasattr(os, "O_NOFOLLOW"):
            leaf_flags |= os.O_NOFOLLOW
        fd = os.open(parts[-1], leaf_flags, mode, dir_fd=current_fd)
        try:
            info = os.fstat(fd)
            if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
                raise SecurityError(f"Controller output leaf must be a single-link regular file: {normalized}")
            os.fchmod(fd, mode)
            view = memoryview(data)
            while view:
                written = os.write(fd, view)
                view = view[written:]
            os.fsync(fd)
        finally:
            os.close(fd)
        os.fsync(current_fd)
    finally:
        for fd in reversed(opened):
            os.close(fd)
        os.close(root_fd)


def secure_repo_write_json(
    repo_root: Path, relative_path: str, value: Any, *, create_once: bool = False
) -> None:
    secure_repo_write_bytes(
        repo_root,
        relative_path,
        json.dumps(value, indent=2, ensure_ascii=False).encode("utf-8") + b"\n",
        create_once=create_once,
    )

def secure_write_json(
    path: Path, value: Any, mode: int = 0o600, *, create_once: bool = False
) -> None:
    secure_write_bytes(
        path,
        json.dumps(value, indent=2, ensure_ascii=False).encode("utf-8") + b"\n",
        mode,
        create_once=create_once,
    )


def runtime_root_for(repo_root: Path, configured: str | None = None) -> Path:
    raw = configured or os.environ.get("AZPR_RUNTIME_ROOT")
    if not raw:
        raise SecurityError(
            "AZPR_RUNTIME_ROOT (or controller.config runtime_root) is required and must be outside the repository."
        )
    runtime = Path(raw).expanduser().absolute()
    no_symlink_ancestors(runtime, allow_missing_leaf=True)
    repo = repo_root.resolve()
    try:
        runtime.resolve(strict=False).relative_to(repo)
    except ValueError:
        pass
    else:
        raise SecurityError("Runtime root must be outside the agent/validator workspace.")
    secure_mkdir(runtime)
    return runtime


def load_private_key(path: Path) -> Ed25519PrivateKey:
    no_symlink_ancestors(path, allow_missing_leaf=False)
    info = os.stat(path)
    if info.st_mode & 0o077:
        raise SecurityError(f"Private key permissions must be 0600: {path}")
    data = path.read_bytes()
    try:
        key = serialization.load_pem_private_key(data, password=None)
    except Exception as exc:
        raise SecurityError(f"Could not load Ed25519 private key: {path}") from exc
    if not isinstance(key, Ed25519PrivateKey):
        raise SecurityError(f"Private key is not Ed25519: {path}")
    return key


def load_public_key(path: Path) -> Ed25519PublicKey:
    no_symlink_ancestors(path, allow_missing_leaf=False)
    data = path.read_bytes()
    try:
        key = serialization.load_pem_public_key(data)
    except Exception as exc:
        raise SecurityError(f"Could not load Ed25519 public key: {path}") from exc
    if not isinstance(key, Ed25519PublicKey):
        raise SecurityError(f"Public key is not Ed25519: {path}")
    return key


def ed25519_sign(private_key_path: Path, value: Any) -> str:
    signature = load_private_key(private_key_path).sign(canonical_json_bytes(value))
    return base64.b64encode(signature).decode("ascii")


def ed25519_verify(public_key: Ed25519PublicKey, value: Any, signature_b64: str) -> bool:
    try:
        signature = base64.b64decode(signature_b64, validate=True)
        public_key.verify(signature, canonical_json_bytes(value))
        return True
    except (ValueError, InvalidSignature):
        return False


@dataclass(frozen=True)
class SignerRecord:
    key_id: str
    signer_id: str
    roles: frozenset[str]
    public_key: Ed25519PublicKey
    revoked_at: datetime | None


def load_public_keyring(path: Path) -> dict[str, SignerRecord]:
    no_symlink_ancestors(path, allow_missing_leaf=False)
    flags=os.O_RDONLY|getattr(os,"O_NOFOLLOW",0);fd=os.open(path,flags)
    try:
        before=os.fstat(fd)
        if not stat.S_ISREG(before.st_mode) or before.st_nlink!=1 or before.st_size>1024*1024:
            raise SecurityError(f"Unsafe public keyring: {path}")
        data=bytearray()
        while True:
            chunk=os.read(fd,65536)
            if not chunk: break
            data.extend(chunk)
            if len(data)>1024*1024: raise SecurityError("Public keyring exceeds size limit")
        after=os.fstat(fd)
        if (before.st_dev,before.st_ino,before.st_size,before.st_mtime_ns)!=(after.st_dev,after.st_ino,after.st_size,after.st_mtime_ns):
            raise SecurityError("Public keyring changed during read")
    finally: os.close(fd)
    try:
        payload=json.loads(bytes(data).decode("utf-8"))
    except (UnicodeDecodeError,json.JSONDecodeError) as exc:
        raise SecurityError(f"Invalid public keyring: {path}") from exc
    if not isinstance(payload, dict) or payload.get("format_version") != "1.0":
        raise SecurityError("Public keyring must be a format_version 1.0 object.")
    entries = payload.get("keys")
    if not isinstance(entries, list) or not entries:
        raise SecurityError("Public keyring must contain at least one key.")
    result: dict[str, SignerRecord] = {}
    signer_ids: set[str] = set()
    key_fingerprints: set[str] = set()
    for item in entries:
        if not isinstance(item, dict):
            raise SecurityError("Public keyring entries must be objects.")
        key_id = item.get("key_id")
        signer_id = item.get("signer_id")
        roles = item.get("roles")
        pem = item.get("public_key_pem")
        if not all(isinstance(v, str) and v for v in (key_id, signer_id, pem)):
            raise SecurityError("Public keyring entries require key_id, signer_id, and public_key_pem.")
        if key_id in result:
            raise SecurityError(f"Duplicate public key ID: {key_id}")
        if signer_id in signer_ids:
            raise SecurityError(f"Duplicate signer identity: {signer_id}")
        if not isinstance(roles, list) or not roles or not all(isinstance(v, str) and v for v in roles):
            raise SecurityError(f"Key {key_id} must list non-empty signer roles.")
        try:
            key = serialization.load_pem_public_key(pem.encode("utf-8"))
        except Exception as exc:
            raise SecurityError(f"Invalid public key PEM for {key_id}.") from exc
        if not isinstance(key, Ed25519PublicKey):
            raise SecurityError(f"Key {key_id} is not Ed25519.")
        fingerprint = sha256_bytes(key.public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw))
        if fingerprint in key_fingerprints:
            raise SecurityError("Duplicate Ed25519 public-key material is not allowed under multiple identities.")
        signer_ids.add(signer_id)
        key_fingerprints.add(fingerprint)
        revoked = item.get("revoked_at")
        result[key_id] = SignerRecord(
            key_id=key_id,
            signer_id=signer_id,
            roles=frozenset(roles),
            public_key=key,
            revoked_at=parse_utc(revoked, f"keyring.{key_id}.revoked_at") if revoked else None,
        )
    return result


def unsigned_document(payload: dict[str, Any]) -> dict[str, Any]:
    result = dict(payload)
    result.pop("signatures", None)
    return result


def verify_signatures(
    payload: dict[str, Any],
    *,
    keyring: dict[str, SignerRecord],
    required_key_ids: Iterable[str],
    required_signer_ids: Iterable[str],
    required_roles: Iterable[str],
    min_signers: int,
    now: datetime | None = None,
) -> set[str]:
    if min_signers < 1:
        raise SecurityError("Signature quorum must be at least one.")
    signatures = payload.get("signatures")
    if not isinstance(signatures, list) or not signatures:
        raise SecurityError("Signed document has no signatures.")
    message = unsigned_document(payload)
    valid_key_ids: set[str] = set()
    valid_signer_ids: set[str] = set()
    valid_roles: set[str] = set()
    signer_roles: dict[str, set[str]] = {}
    current = now or datetime.now(timezone.utc)
    for item in signatures:
        if not isinstance(item, dict):
            continue
        key_id = item.get("key_id")
        signature = item.get("ed25519")
        record = keyring.get(key_id) if isinstance(key_id, str) else None
        if record is None or not isinstance(signature, str):
            continue
        if record.revoked_at is not None and record.revoked_at <= current:
            continue
        if ed25519_verify(record.public_key, message, signature):
            valid_key_ids.add(record.key_id)
            valid_signer_ids.add(record.signer_id)
            valid_roles.update(record.roles)
            signer_roles.setdefault(record.signer_id, set()).update(record.roles)
    required_keys = set(required_key_ids)
    required_signers = set(required_signer_ids)
    required_role_set = set(required_roles)
    if not required_keys.issubset(valid_key_ids):
        raise SecurityError(f"Missing required signing keys: {sorted(required_keys - valid_key_ids)}")
    if not required_signers.issubset(valid_signer_ids):
        raise SecurityError(f"Missing required signer identities: {sorted(required_signers - valid_signer_ids)}")
    if not required_role_set.issubset(valid_roles):
        raise SecurityError(f"Missing required signer roles: {sorted(required_role_set - valid_roles)}")

    # Sensitive role coverage requires a distinct signer identity for every role.
    # This prevents one dual-role key plus an unrelated signer from satisfying a
    # nominal separation-of-duties policy.
    roles = sorted(required_role_set)
    def assign(index: int, used: set[str]) -> bool:
        if index >= len(roles):
            return True
        role = roles[index]
        for signer_id, available in signer_roles.items():
            if signer_id not in used and role in available:
                used.add(signer_id)
                if assign(index + 1, used):
                    return True
                used.remove(signer_id)
        return False
    if roles and not assign(0, set()):
        raise SecurityError("Required signer roles cannot be assigned to distinct signer identities.")
    if len(valid_signer_ids) < min_signers:
        raise SecurityError(
            f"Distinct signer quorum not met: {len(valid_signer_ids)}/{min_signers}."
        )
    return valid_signer_ids


class SignedJournal:
    """Append-only Ed25519-signed hash-chain journal."""

    def __init__(
        self,
        path: Path,
        *,
        signing_private_key_path: Path | None,
        verification_public_key_path: Path,
        signer_key_id: str,
    ) -> None:
        self.path = path
        self.signing_private_key_path = signing_private_key_path
        self.verification_public_key_path = verification_public_key_path
        self.signer_key_id = signer_key_id
        secure_mkdir(path.parent)
        no_symlink_ancestors(path, allow_missing_leaf=True)

    def _anchor_payload(self, records: list[dict[str, Any]]) -> dict[str, Any]:
        return {
            "journal_id": sha256_bytes(str(self.path.absolute()).encode("utf-8")),
            "sequence": len(records),
            "head_sha256": sha256_bytes(canonical_json_bytes(records[-1])) if records else ZERO_HASH,
        }

    def _anchor(self, operation: str, records: list[dict[str, Any]]) -> None:
        command = os.environ.get("AZPR_JOURNAL_ANCHOR_COMMAND")
        required = os.environ.get("AZPR_REQUIRE_JOURNAL_ANCHOR") == "1"
        if not command:
            if required:
                raise SecurityError("External journal anchoring is required but not configured.")
            return
        helper = Path(command).absolute()
        no_symlink_ancestors(helper, allow_missing_leaf=False)
        info = os.stat(helper)
        if not stat.S_ISREG(info.st_mode) or info.st_mode & 0o022:
            raise SecurityError("Journal anchor helper must be a non-writable regular file.")
        payload = canonical_json_bytes(self._anchor_payload(records))
        completed = subprocess.run(
            [str(helper), operation], input=payload, capture_output=True,
            env={"PATH":"/usr/bin:/bin","HOME":"/nonexistent","LANG":"C.UTF-8","LC_ALL":"C.UTF-8"},
            timeout=30, check=False,
        )
        if completed.returncode != 0:
            raise SecurityError(f"External journal anchor {operation} failed.")

    def _read_locked(self, handle: Any) -> list[dict[str, Any]]:
        handle.seek(0)
        lines = handle.read().splitlines()
        records: list[dict[str, Any]] = []
        public_key = load_public_key(self.verification_public_key_path)
        previous_hash = ZERO_HASH
        expected_sequence = 1
        for line_number, raw in enumerate(lines, start=1):
            if not raw.strip():
                continue
            try:
                record = json.loads(raw)
            except json.JSONDecodeError as exc:
                raise SecurityError(f"Corrupt signed journal at line {line_number}.") from exc
            if not isinstance(record, dict):
                raise SecurityError(f"Invalid signed journal record at line {line_number}.")
            signature = record.get("signature")
            unsigned = dict(record)
            unsigned.pop("signature", None)
            if record.get("sequence") != expected_sequence:
                raise SecurityError("Signed journal sequence is not continuous.")
            if record.get("previous_hash") != previous_hash:
                raise SecurityError("Signed journal hash chain is broken.")
            if record.get("signer_key_id") != self.signer_key_id:
                raise SecurityError("Signed journal signer key ID mismatch.")
            if not isinstance(signature, str) or not ed25519_verify(public_key, unsigned, signature):
                raise SecurityError("Signed journal signature verification failed.")
            previous_hash = sha256_bytes(canonical_json_bytes(record))
            expected_sequence += 1
            records.append(record)
        return records

    def read_all(self) -> list[dict[str, Any]]:
        secure_mkdir(self.path.parent)
        flags = os.O_RDWR | os.O_CREAT
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        fd = os.open(self.path, flags, 0o600)
        try:
            os.fchmod(fd, 0o600)
            with os.fdopen(fd, "r+", encoding="utf-8", closefd=False) as handle:
                fcntl.flock(handle.fileno(), fcntl.LOCK_SH)
                try:
                    records = self._read_locked(handle)
                    self._anchor("verify", records)
                    return records
                finally:
                    fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        finally:
            os.close(fd)

    def append(self, event_type: str, payload: dict[str, Any], *, run_id: str) -> dict[str, Any]:
        ensure_no_control_chars(event_type, "event_type")
        ensure_no_control_chars(run_id, "run_id")
        if self.signing_private_key_path is None:
            raise SecurityError("Signed journal is read-only because no signing key is configured.")
        secure_mkdir(self.path.parent)
        flags = os.O_RDWR | os.O_CREAT
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        fd = os.open(self.path, flags, 0o600)
        try:
            os.fchmod(fd, 0o600)
            with os.fdopen(fd, "r+", encoding="utf-8", closefd=False) as handle:
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
                try:
                    records = self._read_locked(handle)
                    previous_hash = (
                        sha256_bytes(canonical_json_bytes(records[-1])) if records else ZERO_HASH
                    )
                    unsigned = {
                        "format_version": "1.0",
                        "sequence": len(records) + 1,
                        "previous_hash": previous_hash,
                        "event_type": event_type,
                        "created_at": utc_now(),
                        "run_id": run_id,
                        "signer_key_id": self.signer_key_id,
                        "payload": payload,
                    }
                    record = dict(unsigned)
                    record["signature"] = ed25519_sign(self.signing_private_key_path, unsigned)
                    handle.seek(0, os.SEEK_END)
                    handle.write(json.dumps(record, sort_keys=True, ensure_ascii=False) + "\n")
                    handle.flush()
                    os.fsync(handle.fileno())
                    self._anchor("publish", [*records, record])
                    return record
                finally:
                    fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        finally:
            os.close(fd)


    def head(self) -> dict[str, Any]:
        records = self.read_all()
        return {
            "sequence": len(records),
            "record_sha256": sha256_bytes(canonical_json_bytes(records[-1])) if records else ZERO_HASH,
        }

    def append_unique(
        self,
        event_type: str,
        payload: dict[str, Any],
        *,
        unique_field: str,
        unique_value: str,
        run_id: str,
    ) -> dict[str, Any]:
        """Atomically verify the chain, test uniqueness, and append under one lock."""
        ensure_no_control_chars(unique_value, unique_field)
        if self.signing_private_key_path is None:
            raise SecurityError("Signed journal is read-only because no signing key is configured.")
        secure_mkdir(self.path.parent)
        flags = os.O_RDWR | os.O_CREAT
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        fd = os.open(self.path, flags, 0o600)
        try:
            os.fchmod(fd, 0o600)
            with os.fdopen(fd, "r+", encoding="utf-8", closefd=False) as handle:
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
                try:
                    records = self._read_locked(handle)
                    for record in records:
                        existing = record.get("payload")
                        if isinstance(existing, dict) and existing.get(unique_field) == unique_value:
                            raise SecurityError(f"{unique_field} was already consumed.")
                    previous_hash = sha256_bytes(canonical_json_bytes(records[-1])) if records else ZERO_HASH
                    unsigned = {
                        "format_version": "1.0",
                        "sequence": len(records) + 1,
                        "previous_hash": previous_hash,
                        "event_type": event_type,
                        "created_at": utc_now(),
                        "run_id": run_id,
                        "signer_key_id": self.signer_key_id,
                        "payload": payload,
                    }
                    record = dict(unsigned)
                    record["signature"] = ed25519_sign(self.signing_private_key_path, unsigned)
                    handle.seek(0, os.SEEK_END)
                    handle.write(json.dumps(record, sort_keys=True, ensure_ascii=False) + "\n")
                    handle.flush()
                    os.fsync(handle.fileno())
                    directory_fd = os.open(self.path.parent, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
                    try:
                        os.fsync(directory_fd)
                    finally:
                        os.close(directory_fd)
                    self._anchor("publish", [*records, record])
                    return record
                finally:
                    fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        finally:
            os.close(fd)


class StateStore:
    """Reconstructible controller state backed by a signed journal.

    A cache may be written for diagnostics, but it is never authoritative.
    """

    def __init__(self, runtime_root: Path, *, private_key: Path | None, public_key: Path, key_id: str) -> None:
        self.runtime_root = runtime_root
        self.journal = SignedJournal(
            runtime_root / "journals" / "controller-state.jsonl",
            signing_private_key_path=private_key,
            verification_public_key_path=public_key,
            signer_key_id=key_id,
        )
        self.cache = runtime_root / "cache" / "state.json"

    def load(self, default: dict[str, Any]) -> dict[str, Any]:
        records = self.journal.read_all()
        state = dict(default)
        for record in records:
            if record.get("event_type") == "STATE_SNAPSHOT":
                payload = record.get("payload")
                if not isinstance(payload, dict) or not isinstance(payload.get("state"), dict):
                    raise SecurityError("Invalid state snapshot journal record.")
                state = dict(default)
                state.update(payload["state"])
        return state

    def save(self, state: dict[str, Any], *, run_id: str) -> None:
        self.journal.append("STATE_SNAPSHOT", {"state": state}, run_id=run_id)
        secure_write_json(self.cache, state)


class NonceLedger:
    """Atomic one-use ledger.

    SQLite provides a cross-process uniqueness constraint. The signed journal is
    retained as auditable evidence; both writes occur while the database holds an
    IMMEDIATE transaction, and a failed journal append rolls the transaction back.
    """

    def __init__(self, runtime_root: Path, *, private_key: Path, public_key: Path, key_id: str) -> None:
        self.root = runtime_root / "nonce-ledger"
        secure_mkdir(self.root)
        self.db_path = self.root / "nonces.sqlite3"
        self.journal = SignedJournal(
            runtime_root / "journals" / "consumed-nonces.jsonl",
            signing_private_key_path=private_key,
            verification_public_key_path=public_key,
            signer_key_id=key_id,
        )
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        no_symlink_ancestors(self.db_path, allow_missing_leaf=True)
        connection = sqlite3.connect(self.db_path, timeout=30, isolation_level=None)
        try:
            connection.execute("PRAGMA journal_mode=WAL")
            connection.execute("PRAGMA synchronous=FULL")
            connection.execute("PRAGMA foreign_keys=ON")
            return connection
        except Exception:
            connection.close()
            raise

    def _initialize(self) -> None:
        connection = self._connect()
        try:
            connection.execute(
                "CREATE TABLE IF NOT EXISTS consumed_nonce ("
                "nonce TEXT PRIMARY KEY, document_id TEXT NOT NULL, purpose TEXT NOT NULL,"
                "run_id TEXT NOT NULL, consumed_at TEXT NOT NULL, journal_sequence INTEGER NOT NULL)"
            )
        finally:
            connection.close()
        os.chmod(self.db_path, 0o600)

    def consumed(self) -> set[str]:
        journal_values: set[str] = set()
        for record in self.journal.read_all():
            if record.get("event_type") == "NONCE_CONSUMED":
                payload = record.get("payload")
                if isinstance(payload, dict) and isinstance(payload.get("nonce"), str):
                    journal_values.add(payload["nonce"])
        connection = self._connect()
        try:
            rows = connection.execute("SELECT nonce FROM consumed_nonce").fetchall()
        finally:
            connection.close()
        database_values = {str(row[0]) for row in rows}
        if journal_values != database_values:
            raise SecurityError("Nonce database and signed journal disagree.")
        return database_values

    def consume(self, nonce: str, *, document_id: str, purpose: str, run_id: str) -> None:
        ensure_no_control_chars(nonce, "nonce")
        if len(nonce) < 16:
            raise SecurityError("Nonce must contain at least 16 characters.")
        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            try:
                connection.execute(
                    "INSERT INTO consumed_nonce(nonce, document_id, purpose, run_id, consumed_at, journal_sequence) "
                    "VALUES (?, ?, ?, ?, ?, -1)",
                    (nonce, document_id, purpose, run_id, utc_now()),
                )
            except sqlite3.IntegrityError as exc:
                connection.execute("ROLLBACK")
                raise SecurityError("Nonce was already consumed.") from exc
            record = self.journal.append_unique(
                "NONCE_CONSUMED",
                {"nonce": nonce, "document_id": document_id, "purpose": purpose},
                unique_field="nonce",
                unique_value=nonce,
                run_id=run_id,
            )
            connection.execute(
                "UPDATE consumed_nonce SET journal_sequence=? WHERE nonce=?",
                (int(record["sequence"]), nonce),
            )
            connection.execute("COMMIT")
        except Exception:
            try:
                connection.execute("ROLLBACK")
            except sqlite3.Error:
                pass
            raise
        finally:
            connection.close()
        directory_fd = os.open(self.root, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)


def split_nul_paths(raw: bytes, *, label: str) -> list[str]:
    if not raw:
        return []
    if not raw.endswith(b"\0"):
        raise SecurityError(f"{label} did not return NUL-terminated output.")
    result: list[str] = []
    for index, item in enumerate(raw[:-1].split(b"\0")):
        try:
            value = item.decode("utf-8", errors="strict")
        except UnicodeDecodeError as exc:
            raise SecurityError(f"{label} returned a non-UTF-8 filename at index {index}.") from exc
        result.append(safe_relative_path(value, f"{label}[{index}]"))
    return result


def trusted_git_binary() -> str:
    value = os.environ.get("AZPR_TRUSTED_GIT", "/usr/bin/git")
    path = Path(value)
    if not path.is_absolute():
        raise SecurityError("AZPR_TRUSTED_GIT must be an absolute path.")
    no_symlink_ancestors(path, allow_missing_leaf=False)
    info = os.stat(path)
    if not stat.S_ISREG(info.st_mode) or info.st_mode & 0o022:
        raise SecurityError("Trusted Git binary must be a non-writable regular file.")
    return str(path)


def secure_git_env() -> dict[str, str]:
    return {
        "PATH": "/usr/bin:/bin",
        "HOME": "/nonexistent",
        "LANG": "C.UTF-8",
        "LC_ALL": "C.UTF-8",
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_CONFIG_SYSTEM": "/dev/null",
        "GIT_CONFIG_GLOBAL": "/dev/null",
        "GIT_TERMINAL_PROMPT": "0",
        "GIT_PAGER": "cat",
        "GIT_EDITOR": "true",
        "GIT_SEQUENCE_EDITOR": "true",
        "GIT_OPTIONAL_LOCKS": "0",
    }


def secure_git_argv(argv: Sequence[str]) -> list[str]:
    return [
        trusted_git_binary(),
        "-c", "core.hooksPath=/dev/null",
        "-c", "core.fsmonitor=false",
        "-c", "core.pager=cat",
        "-c", "commit.gpgSign=false",
        "-c", "tag.gpgSign=false",
        "-c", "credential.helper=",
        "-c", "advice.detachedHead=false",
        *argv,
    ]


def assert_safe_git_configuration(root: Path) -> None:
    completed = subprocess.run(
        secure_git_argv(["config", "--local", "--null", "--list"]),
        cwd=root, capture_output=True, env=secure_git_env(), check=False,
    )
    if completed.returncode != 0:
        raise SecurityError("Unable to inspect repository Git configuration safely.")
    forbidden_prefixes = (
        "filter.", "include.", "includeif.", "credential.", "url.",
        "core.hookspath", "core.fsmonitor", "gpg.", "commit.gpgsign",
        "tag.gpgsign", "diff.external", "difftool.", "mergetool.",
        "core.excludesfile", "core.attributesfile", "core.worktree",
        "core.sshcommand", "extensions.worktreeconfig", "remote.",
    )
    for raw in completed.stdout.split(b"\0"):
        if not raw:
            continue
        key = raw.split(b"\n", 1)[0].decode("utf-8", "replace").lower()
        if key.startswith(forbidden_prefixes):
            raise SecurityError(f"Unsafe repository Git configuration is forbidden: {key}")


def secure_git_run(root: Path, argv: Sequence[str], *, input_bytes: bytes | None = None) -> subprocess.CompletedProcess[bytes]:
    assert_safe_git_configuration(root)
    return subprocess.run(
        secure_git_argv(argv), cwd=root, input=input_bytes, capture_output=True,
        env=secure_git_env(), check=False,
    )


def _git_bytes(root: Path, argv: Sequence[str]) -> bytes:
    completed = secure_git_run(root, argv)
    if completed.returncode != 0:
        raise SecurityError(
            f"Git command failed: {argv!r}\n{completed.stderr.decode('utf-8', errors='replace')[-2000:]}"
        )
    return completed.stdout


def git_changed_paths(root: Path) -> list[str]:
    """Return changed paths using NUL-delimited, no-rename Git output.

    Disabling rename detection makes both deletion and addition paths visible and
    avoids parsing human-oriented "old -> new" syntax.
    """
    paths: set[str] = set()
    commands = (
        ["diff", "--name-only", "-z", "--no-renames"],
        ["diff", "--cached", "--name-only", "-z", "--no-renames"],
        ["ls-files", "--others", "--exclude-standard", "-z"],
    )
    for argv in commands:
        paths.update(split_nul_paths(_git_bytes(root, argv), label="git " + " ".join(argv)))
    return sorted(paths)


def _glob_to_regex(pattern: str) -> re.Pattern[str]:
    pattern = safe_relative_path(pattern, "path pattern")
    pieces: list[str] = ["^"]
    index = 0
    while index < len(pattern):
        char = pattern[index]
        if char == "*":
            if index + 1 < len(pattern) and pattern[index + 1] == "*":
                index += 2
                if index < len(pattern) and pattern[index] == "/":
                    index += 1
                    pieces.append("(?:.*/)?")
                else:
                    pieces.append(".*")
                continue
            pieces.append("[^/]*")
        elif char == "?":
            pieces.append("[^/]")
        elif char == "[":
            end = pattern.find("]", index + 1)
            if end < 0:
                pieces.append("\\[")
            else:
                content = pattern[index + 1 : end]
                if not content or "/" in content:
                    raise SecurityError(f"Invalid path character class: {pattern!r}")
                pieces.append("[" + re.escape(content) + "]")
                index = end
        else:
            pieces.append(re.escape(char))
        index += 1
    pieces.append("$")
    return re.compile("".join(pieces))


def path_matches(path: str, patterns: Iterable[str]) -> bool:
    normalized = safe_relative_path(path)
    return any(_glob_to_regex(pattern).fullmatch(normalized) is not None for pattern in patterns)


def is_exact_path_pattern(pattern: str) -> bool:
    safe_relative_path(pattern, "path pattern")
    return not any(token in pattern for token in ("*", "?", "[", "]"))


def tracked_paths(root: Path) -> list[str]:
    return split_nul_paths(_git_bytes(root, ["ls-files", "-z"]), label="git ls-files")


def validate_path_scope(
    root: Path,
    patterns: Iterable[str],
    *,
    max_tracked_matches: int,
    exact_only: bool = False,
) -> dict[str, int]:
    pattern_list = list(patterns)
    if not pattern_list:
        return {}
    tracked = tracked_paths(root)
    result: dict[str, int] = {}
    for pattern in pattern_list:
        safe_relative_path(pattern, "allowed path pattern")
        if exact_only and not is_exact_path_pattern(pattern):
            raise SecurityError(f"Only exact paths are allowed here: {pattern}")
        count = sum(1 for path in tracked if path_matches(path, [pattern]))
        result[pattern] = count
        if count > max_tracked_matches:
            raise SecurityError(
                f"Allowed path pattern {pattern!r} matches {count} tracked files, exceeding budget {max_tracked_matches}."
            )
    return result


def repository_topology_preflight(root: Path, writable_patterns: Iterable[str]) -> None:
    root = root.resolve()
    no_symlink_ancestors(root, allow_missing_leaf=False)
    # Git submodules are explicit filesystem boundaries.
    raw_stage = _git_bytes(root, ["ls-files", "--stage", "-z"])
    for item in raw_stage.split(b"\0"):
        if item.startswith(b"160000 "):
            raise SecurityError("Git submodules are forbidden in an autonomous writable worktree.")
    for current, dirs, files in os.walk(root, topdown=True, followlinks=False):
        current_path = Path(current)
        rel_dir = current_path.relative_to(root).as_posix()
        if rel_dir == ".git" or rel_dir.startswith(".git/"):
            dirs[:] = []
            continue
        if current_path != root and (current_path / ".git").exists():
            raise SecurityError(f"Nested Git repository is forbidden: {current_path}")
        for name in list(dirs) + list(files):
            candidate = current_path / name
            rel = candidate.relative_to(root).as_posix()
            info = os.lstat(candidate)
            if stat.S_ISLNK(info.st_mode):
                if path_matches(rel, writable_patterns):
                    raise SecurityError(f"Writable symlink is forbidden: {rel}")
                continue
            if stat.S_ISREG(info.st_mode) and info.st_nlink > 1 and path_matches(rel, writable_patterns):
                raise SecurityError(f"Writable hard-linked file is forbidden: {rel}")
            if name == ".git" and candidate != root / ".git":
                raise SecurityError(f"Nested repository marker is forbidden: {rel}")


def tree_digest(root: Path) -> str:
    """Content and topology digest excluding .git metadata."""
    digest = hashlib.sha256()
    for current, dirs, files in os.walk(root, topdown=True, followlinks=False):
        current_path = Path(current)
        rel_dir = current_path.relative_to(root).as_posix()
        dirs[:] = sorted(d for d in dirs if not (rel_dir == "." and d == ".git"))
        for name in sorted(files):
            path = current_path / name
            rel = path.relative_to(root).as_posix()
            info = os.lstat(path)
            digest.update(rel.encode("utf-8") + b"\0")
            digest.update(str(stat.S_IFMT(info.st_mode)).encode("ascii") + b"\0")
            if stat.S_ISREG(info.st_mode):
                digest.update(sha256_file(path).encode("ascii"))
            elif stat.S_ISLNK(info.st_mode):
                digest.update(os.readlink(path).encode("utf-8"))
            digest.update(b"\0")
    return digest.hexdigest()


_SECRET_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"(?i)(authorization:\s*bearer\s+)[A-Za-z0-9._~+/=-]+"), r"\1[REDACTED]"),
    (re.compile(r"\bAKIA[0-9A-Z]{16}\b"), "[REDACTED_AWS_KEY]"),
    (re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}\b"), "[REDACTED_GITHUB_TOKEN]"),
    (re.compile(r"(?i)\b(token|secret|password|passwd|api[_-]?key|private[_-]?key)\s*[:=]\s*([^\s,;]+)"), r"\1=[REDACTED]"),
    (re.compile(r"(?<!\d)(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}(?!\d)"), "[REDACTED_PHONE]"),
)


def redact_text(value: str, *, max_chars: int = 200_000) -> str:
    value = value.replace("\x00", "[NUL]")
    value = "".join(char if char in "\n\r\t" or ord(char) >= 32 else "�" for char in value)
    for pattern, replacement in _SECRET_PATTERNS:
        value = pattern.sub(replacement, value)
    if len(value) > max_chars:
        value = value[:max_chars] + "\n[TRUNCATED BY CONTROLLER]\n"
    return value


def minimal_child_env(
    *,
    runtime_dir: Path,
    executable_path: str,
    codex_home: str | None = None,
    extra: dict[str, str] | None = None,
) -> dict[str, str]:
    secure_mkdir(runtime_dir)
    home = runtime_dir / "home"
    tmp = runtime_dir / "tmp"
    secure_mkdir(home)
    secure_mkdir(tmp)
    env = {
        "PATH": executable_path,
        "HOME": str(home),
        "TMPDIR": str(tmp),
        "LANG": "C.UTF-8",
        "LC_ALL": "C.UTF-8",
        "PYTHONDONTWRITEBYTECODE": "1",
        "NO_PROXY": "*",
        "no_proxy": "*",
    }
    if codex_home:
        codex_path = Path(codex_home).expanduser().absolute()
        no_symlink_ancestors(codex_path, allow_missing_leaf=False)
        env["CODEX_HOME"] = str(codex_path)
    if extra:
        forbidden = ("SECRET", "TOKEN", "PASSWORD", "PASSWD", "PRIVATE", "CREDENTIAL", "APPROVAL", "SIGNING")
        for key, value in extra.items():
            if any(token in key.upper() for token in forbidden):
                raise SecurityError(f"Refusing to expose sensitive environment variable to child: {key}")
            ensure_no_control_chars(key, "environment name")
            ensure_no_control_chars(value, f"environment {key}")
            env[key] = value
    return env


def sign_manifest(payload: dict[str, Any], *, private_key_path: Path, key_id: str) -> dict[str, Any]:
    unsigned = dict(payload)
    unsigned.pop("signature", None)
    unsigned["signer_key_id"] = key_id
    result = dict(unsigned)
    result["signature"] = ed25519_sign(private_key_path, unsigned)
    return result


def verify_manifest(payload: dict[str, Any], *, public_key_path: Path, key_id: str) -> None:
    if payload.get("signer_key_id") != key_id:
        raise SecurityError("Signed manifest key ID mismatch.")
    signature = payload.get("signature")
    unsigned = dict(payload)
    unsigned.pop("signature", None)
    if not isinstance(signature, str) or not ed25519_verify(load_public_key(public_key_path), unsigned, signature):
        raise SecurityError("Signed manifest verification failed.")


def write_signed_manifest(
    path: Path,
    payload: dict[str, Any],
    *,
    private_key_path: Path,
    key_id: str,
) -> dict[str, Any]:
    signed = sign_manifest(payload, private_key_path=private_key_path, key_id=key_id)
    secure_write_json(path, signed)
    return signed

# ---------------------------------------------------------------------------
# Finalized security overrides (v4)
# ---------------------------------------------------------------------------

import selectors as _selectors
import time as _time
import trusted_installation as _ti

MAX_CONTROLLER_OUTPUT_BYTES = 2 * 1024 * 1024
MAX_JSON_INPUT_BYTES = 2 * 1024 * 1024


def installed_trust() -> _ti.TrustedInstallation:
    try:
        return _ti.load_installation()
    except _ti.InstallationError as exc:
        raise SecurityError(str(exc)) from exc


def runtime_root_for(repo_root: Path, configured: str | None = None) -> Path:
    """Resolve runtime root; production ignores caller-provided values."""
    if _ti.production_mode():
        value = installed_trust().directory("runtime_root")
    else:
        raw = configured or os.environ.get("AZPR_RUNTIME_ROOT")
        if not raw:
            raise SecurityError("development runtime_root is required")
        value = Path(raw).expanduser().absolute()
    repo = repo_root.resolve()
    try:
        value.resolve().relative_to(repo)
    except ValueError:
        pass
    else:
        raise SecurityError("runtime root must remain outside the repository")
    secure_mkdir(value)
    return value


def trusted_git_binary() -> str:
    if _ti.production_mode():
        return str(installed_trust().component("git_binary"))
    value = os.environ.get("AZPR_TRUSTED_GIT", "/usr/bin/git")
    path = Path(value).absolute()
    no_symlink_ancestors(path, allow_missing_leaf=False)
    info = os.stat(path)
    if not stat.S_ISREG(info.st_mode) or info.st_mode & 0o022:
        raise SecurityError("Trusted Git binary must be a non-writable regular file.")
    return str(path)


def _anchor_helper_path() -> Path | None:
    if _ti.production_mode():
        return installed_trust().component("anchor_helper")
    command = os.environ.get("AZPR_JOURNAL_ANCHOR_COMMAND")
    return Path(command).absolute() if command else None


def _anchor_required() -> bool:
    return _ti.production_mode() or os.environ.get("AZPR_REQUIRE_JOURNAL_ANCHOR") == "1"


def _invoke_anchor(operation: str, payload: dict[str, Any]) -> None:
    helper = _anchor_helper_path()
    if helper is None:
        if _anchor_required():
            raise SecurityError("mandatory external journal anchor is unavailable")
        return
    no_symlink_ancestors(helper, allow_missing_leaf=False)
    st = os.stat(helper)
    if not stat.S_ISREG(st.st_mode) or st.st_mode & 0o022:
        raise SecurityError("journal anchor helper is unsafe")
    argv = [str(helper), operation]
    # The bundled anchor is a clean-room Python reference. Production launchers
    # always use the root-installed executable pinned by the installation
    # manifest; only non-production source-tree verification may invoke a .py
    # helper through the current trusted interpreter so ZIP extractors that do
    # not preserve Unix execute bits cannot change test behavior.
    if not _ti.production_mode() and helper.suffix == ".py":
        argv = [sys.executable, str(helper), operation]
    rc, _stdout, _stderr, _duration = run_bounded_process(
        argv, cwd=helper.parent, input_bytes=canonical_json_bytes(payload),
        env={"PATH":"/usr/bin:/bin","HOME":"/nonexistent","LANG":"C.UTF-8","LC_ALL":"C.UTF-8"},
        timeout_seconds=30, stdout_limit=64*1024, stderr_limit=64*1024,
    )
    if rc != 0:
        raise SecurityError(f"external journal anchor {operation} failed")
    if _stdout.strip():
        try:
            receipt=json.loads(_stdout.decode("utf-8"))
        except Exception as exc:
            raise SecurityError("external journal anchor returned invalid receipt JSON") from exc
        if not isinstance(receipt,dict):
            raise SecurityError("external journal anchor receipt must be an object")
    else:
        receipt={"operation":operation,"journal_id":payload["journal_id"],"sequence":payload["sequence"],"head_sha256":payload["head_sha256"]}
    if receipt.get("sequence")!=payload["sequence"] or receipt.get("head_sha256")!=payload["head_sha256"] or receipt.get("journal_id")!=payload["journal_id"]:
        raise SecurityError("external journal anchor receipt does not acknowledge the exact published head")
    return receipt


def _signed_journal_anchor(self: SignedJournal, operation: str, records: list[dict[str, Any]]) -> None:
    _invoke_anchor(operation, self._anchor_payload(records))

SignedJournal._anchor = _signed_journal_anchor  # type: ignore[assignment]


def run_bounded_process(
    argv: Sequence[str], *, cwd: Path, input_bytes: bytes | None = None,
    timeout_seconds: int = 900, env: dict[str,str] | None = None,
    stdout_limit: int = MAX_CONTROLLER_OUTPUT_BYTES,
    stderr_limit: int = MAX_CONTROLLER_OUTPUT_BYTES,
    run_as_uid: int | None = None, run_as_gid: int | None = None,
) -> tuple[int, bytes, bytes, float]:
    """Stream child output into bounded buffers and kill the process group on overflow."""
    if input_bytes is not None and len(input_bytes) > MAX_JSON_INPUT_BYTES:
        raise SecurityError("child input exceeds bounded size")
    start = _time.monotonic()
    process = subprocess.Popen(
        list(argv), cwd=cwd, stdin=subprocess.PIPE if input_bytes is not None else subprocess.DEVNULL,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env, start_new_session=True,
        user=run_as_uid, group=run_as_gid, extra_groups=[] if run_as_uid is not None else None,
    )
    if input_bytes is not None:
        assert process.stdin is not None
        process.stdin.write(input_bytes); process.stdin.close()
    assert process.stdout is not None and process.stderr is not None
    for stream in (process.stdout, process.stderr): os.set_blocking(stream.fileno(), False)
    selector = _selectors.DefaultSelector()
    selector.register(process.stdout, _selectors.EVENT_READ, ("stdout", stdout_limit))
    selector.register(process.stderr, _selectors.EVENT_READ, ("stderr", stderr_limit))
    buffers={"stdout":bytearray(),"stderr":bytearray()}
    deadline=start+timeout_seconds
    try:
        while selector.get_map():
            if _time.monotonic() > deadline:
                raise TimeoutError("child process timeout")
            for key,_ in selector.select(timeout=0.1):
                name,limit=key.data
                chunk=os.read(key.fd, 65536)
                if not chunk:
                    selector.unregister(key.fileobj); continue
                buffers[name].extend(chunk)
                if len(buffers[name]) > limit:
                    raise SecurityError(f"child {name} exceeded {limit} bytes")
            if process.poll() is not None and not selector.get_map(): break
        rc=process.wait(timeout=max(1,int(deadline-_time.monotonic())))
    except (TimeoutError, SecurityError, subprocess.TimeoutExpired):
        try: os.killpg(process.pid, 9)
        except ProcessLookupError: pass
        process.wait(timeout=10)
        raise
    finally:
        selector.close()
        for stream in (process.stdout, process.stderr):
            try:
                if stream is not None: stream.close()
            except OSError:
                pass
    return rc,bytes(buffers['stdout']),bytes(buffers['stderr']),_time.monotonic()-start


class DurableEventStore:
    """Single authoritative signed SQLite event store with recoverable anchoring.

    The event is durably committed as PENDING before anchor publication. A failed
    or interrupted anchor never makes a nonce reusable; recovery republishes the
    pending signed head and marks it ANCHORED.
    """
    def __init__(self, path: Path, *, private_key: Path | None, public_key: Path, key_id: str, store_id: str):
        self.path=path; self.private_key=private_key; self.public_key=public_key; self.key_id=key_id; self.store_id=store_id
        secure_mkdir(path.parent); no_symlink_ancestors(path,allow_missing_leaf=True); self._initialize()
    def _connect(self):
        conn=sqlite3.connect(self.path,timeout=30,isolation_level=None)
        conn.execute('PRAGMA journal_mode=WAL'); conn.execute('PRAGMA synchronous=FULL'); conn.execute('PRAGMA foreign_keys=ON')
        return conn
    def _initialize(self):
        c=self._connect()
        try:
            c.execute('CREATE TABLE IF NOT EXISTS event(seq INTEGER PRIMARY KEY, record_json TEXT NOT NULL, record_sha256 TEXT NOT NULL UNIQUE, anchor_status TEXT NOT NULL CHECK(anchor_status IN (\'PENDING\',\'ANCHORED\')), anchor_receipt_json TEXT)')
            columns={row[1] for row in c.execute('PRAGMA table_info(event)').fetchall()}
            if 'anchor_receipt_json' not in columns: c.execute('ALTER TABLE event ADD COLUMN anchor_receipt_json TEXT')
        finally:c.close()
        os.chmod(self.path,0o600)
    def _records_tx(self,c):
        rows=c.execute('SELECT record_json FROM event ORDER BY seq').fetchall(); records=[]; prev=ZERO_HASH; pub=load_public_key(self.public_key)
        for expected,(raw,) in enumerate(rows,1):
            record=json.loads(raw); sig=record.get('signature'); unsigned=dict(record); unsigned.pop('signature',None)
            if record.get('sequence')!=expected or record.get('previous_hash')!=prev or record.get('signer_key_id')!=self.key_id or not isinstance(sig,str) or not ed25519_verify(pub,unsigned,sig):
                raise SecurityError('durable event store chain verification failed')
            prev=sha256_bytes(canonical_json_bytes(record)); records.append(record)
        return records
    def _payload(self,records):
        return {'journal_id':sha256_bytes(self.store_id.encode()),'sequence':len(records),'head_sha256':sha256_bytes(canonical_json_bytes(records[-1])) if records else ZERO_HASH}
    def recover(self):
        lock_path=self.path.with_name(self.path.name+'.anchor.lock')
        lock_fd=os.open(lock_path,os.O_RDWR|os.O_CREAT|getattr(os,'O_NOFOLLOW',0),0o600)
        try:
            fcntl.flock(lock_fd,fcntl.LOCK_EX)
            while True:
                c=self._connect()
                try:
                    c.execute('BEGIN IMMEDIATE'); records=self._records_tx(c)
                    pending=c.execute("SELECT COUNT(*) FROM event WHERE anchor_status='PENDING'").fetchone()[0]
                    payload=self._payload(records); c.execute('COMMIT')
                except Exception:
                    try:c.execute('ROLLBACK')
                    except sqlite3.Error:pass
                    raise
                finally:c.close()
                if not pending:
                    _invoke_anchor('verify',payload)
                    return
                receipt=_invoke_anchor('publish',payload)
                published_sequence=payload['sequence']; published_head=payload['head_sha256']
                c=self._connect()
                try:
                    c.execute('BEGIN IMMEDIATE'); current=self._records_tx(c)
                    if len(current)<published_sequence or sha256_bytes(canonical_json_bytes(current[published_sequence-1]))!=published_head:
                        raise SecurityError('event store changed incompatibly while acknowledging anchor publication')
                    c.execute("UPDATE event SET anchor_status='ANCHORED',anchor_receipt_json=? WHERE anchor_status='PENDING' AND seq<=?",(json.dumps(receipt,sort_keys=True,separators=(',',':')),published_sequence))
                    c.execute('COMMIT')
                except Exception:
                    try:c.execute('ROLLBACK')
                    except sqlite3.Error:pass
                    raise
                finally:c.close()
        finally:
            try:fcntl.flock(lock_fd,fcntl.LOCK_UN)
            finally:os.close(lock_fd)
    def append_with(self,event_type:str,payload:dict[str,Any],*,run_id:str,transaction_callback=None):
        if self.private_key is None: raise SecurityError('event store is read-only')
        c=self._connect()
        try:
            c.execute('BEGIN IMMEDIATE'); records=self._records_tx(c)
            if transaction_callback is not None: transaction_callback(c)
            prev=sha256_bytes(canonical_json_bytes(records[-1])) if records else ZERO_HASH
            unsigned={'format_version':'1.0','sequence':len(records)+1,'previous_hash':prev,'event_type':event_type,'created_at':utc_now(),'run_id':run_id,'signer_key_id':self.key_id,'payload':payload}
            record=dict(unsigned); record['signature']=ed25519_sign(self.private_key,unsigned); raw=json.dumps(record,sort_keys=True,ensure_ascii=False); rh=sha256_bytes(canonical_json_bytes(record))
            c.execute('INSERT INTO event(seq,record_json,record_sha256,anchor_status) VALUES(?,?,?,\'PENDING\')',(record['sequence'],raw,rh)); c.execute('COMMIT')
        except Exception:
            try:c.execute('ROLLBACK')
            except sqlite3.Error:pass
            raise
        finally:c.close()
        # A failure here leaves the signed event pending but authoritative. Recovery is safe.
        self.recover(); return record
    def append(self,event_type,payload,*,run_id): return self.append_with(event_type,payload,run_id=run_id)
    def read_all(self):
        self.recover(); c=self._connect()
        try:return self._records_tx(c)
        finally:c.close()
    def head(self):
        records=self.read_all(); return {'sequence':len(records),'record_sha256':sha256_bytes(canonical_json_bytes(records[-1])) if records else ZERO_HASH}


class StateStore:
    def __init__(self,runtime_root:Path,*,private_key:Path|None,public_key:Path,key_id:str):
        self.runtime_root=runtime_root; self.store=DurableEventStore(runtime_root/'state'/'state.sqlite3',private_key=private_key,public_key=public_key,key_id=key_id,store_id='controller-state'); self.journal=self.store; self.cache=runtime_root/'cache'/'state.json'
    def load(self,default):
        state=dict(default)
        for record in self.store.read_all():
            if record.get('event_type')=='STATE_SNAPSHOT':
                p=record.get('payload');
                if not isinstance(p,dict) or not isinstance(p.get('state'),dict): raise SecurityError('invalid state snapshot')
                state=dict(default); state.update(p['state'])
        return state
    def save(self,state,*,run_id):
        self.store.append('STATE_SNAPSHOT',{'state':state},run_id=run_id); secure_write_json(self.cache,state)


class NonceLedger:
    def __init__(self,runtime_root:Path,*,private_key:Path,public_key:Path,key_id:str):
        self.root=runtime_root/'nonce-ledger'; secure_mkdir(self.root)
        self.store=DurableEventStore(self.root/'ledger.sqlite3',private_key=private_key,public_key=public_key,key_id=key_id,store_id='nonce-ledger'); self.journal=self.store
        c=self.store._connect()
        try:c.execute('CREATE TABLE IF NOT EXISTS consumed_nonce(nonce TEXT PRIMARY KEY,document_id TEXT NOT NULL,purpose TEXT NOT NULL,run_id TEXT NOT NULL,consumed_at TEXT NOT NULL)')
        finally:c.close()
    def consumed(self):
        self.store.recover(); c=self.store._connect()
        try:return {str(r[0]) for r in c.execute('SELECT nonce FROM consumed_nonce').fetchall()}
        finally:c.close()
    def consume(self,nonce:str,*,document_id:str,purpose:str,run_id:str):
        ensure_no_control_chars(nonce,'nonce')
        if len(nonce)<16: raise SecurityError('Nonce must contain at least 16 characters.')
        def insert(c):
            try:c.execute('INSERT INTO consumed_nonce VALUES(?,?,?,?,?)',(nonce,document_id,purpose,run_id,utc_now()))
            except sqlite3.IntegrityError as exc: raise SecurityError('Nonce was already consumed.') from exc
        return self.store.append_with('NONCE_CONSUMED',{'nonce':nonce,'document_id':document_id,'purpose':purpose},run_id=run_id,transaction_callback=insert)


def git_diff_metrics(root: Path, *, byte_limit: int) -> dict[str, int]:
    """Measure the actual binary patch plus non-ignored untracked bytes."""
    env=secure_git_env(); argv=secure_git_argv(["diff","--binary","--full-index","--no-ext-diff","HEAD","--"])
    try:
        _rc, patch, stderr, _duration=run_bounded_process(argv,cwd=root,timeout_seconds=120,env=env,stdout_limit=byte_limit+1,stderr_limit=256*1024)
    except SecurityError as exc:
        raise SecurityError("actual diff exceeds the configured byte budget") from exc
    untracked=split_nul_paths(_git_bytes(root,["ls-files","--others","--exclude-standard","-z"]),label="git untracked")
    untracked_bytes=0
    for rel in untracked:
        path=root/rel; no_symlink_ancestors(path,allow_missing_leaf=False); st=os.lstat(path)
        if not stat.S_ISREG(st.st_mode) or st.st_nlink!=1: raise SecurityError(f"unsafe untracked diff input: {rel}")
        untracked_bytes += st.st_size + len(rel.encode("utf-8")) + 1
        if len(patch)+untracked_bytes>byte_limit: raise SecurityError("actual diff exceeds the configured byte budget")
    return {"patch_bytes":len(patch),"untracked_bytes":untracked_bytes,"total_bytes":len(patch)+untracked_bytes}

# ---------------------------------------------------------------------------
# v6 repository-boundary overrides
# ---------------------------------------------------------------------------

MAX_GIT_METADATA_FILES = 200_000
MAX_GIT_METADATA_BYTES = 2 * 1024 * 1024 * 1024


def _raw_git_output(root: Path, argv: Sequence[str]) -> bytes:
    completed = subprocess.run(
        secure_git_argv(argv), cwd=root, capture_output=True,
        env=secure_git_env(), check=False,
    )
    if completed.returncode != 0:
        raise SecurityError(
            f"Unable to inspect Git administrative metadata: {argv!r}: "
            + completed.stderr.decode("utf-8", "replace")[-2000:]
        )
    return completed.stdout


def git_admin_roots(root: Path) -> list[Path]:
    """Return the worktree and common Git administrative roots.

    The repository-visible .git marker is included separately by the inventory.
    Production callers must keep every returned path controller-owned and
    inaccessible for writes by the agent identity.
    """
    repo = root.resolve()
    values: list[Path] = []
    for argv in (["rev-parse", "--absolute-git-dir"], ["rev-parse", "--git-common-dir"]):
        raw = _raw_git_output(repo, argv).decode("utf-8", "strict").strip()
        if not raw:
            raise SecurityError("Git returned an empty administrative path.")
        path = Path(raw)
        if not path.is_absolute():
            path = (repo / path).resolve()
        else:
            path = path.resolve()
        if path not in values:
            values.append(path)
    return values


def _metadata_entries(root: Path) -> list[Path]:
    entries: list[Path] = []
    marker = root.resolve() / ".git"
    if marker.exists() or marker.is_symlink():
        entries.append(marker)
    for admin in git_admin_roots(root):
        if not admin.exists():
            raise SecurityError(f"Git administrative root is missing: {admin}")
        entries.append(admin)
        for current, dirs, files in os.walk(admin, topdown=True, followlinks=False):
            current_path = Path(current)
            dirs[:] = sorted(dirs)
            entries.extend(current_path / name for name in dirs)
            entries.extend(current_path / name for name in sorted(files))
            if len(entries) > MAX_GIT_METADATA_FILES:
                raise SecurityError("Git administrative metadata exceeds the file-count limit.")
    # The marker can equal the worktree admin root. Dedupe by absolute spelling;
    # do not resolve symlinks because symlinks are themselves forbidden metadata.
    unique: dict[str, Path] = {}
    for path in entries:
        unique[str(path.absolute())] = path.absolute()
    return [unique[key] for key in sorted(unique)]


def git_metadata_inventory(root: Path) -> dict[str, Any]:
    """Cryptographically inventory all Git administrative metadata.

    This deliberately includes index, refs, config, info/exclude, attributes,
    hooks, worktree metadata, alternates, logs and object metadata rather than
    relying on a short denylist.
    """
    rows: list[dict[str, Any]] = []
    total = 0
    for path in _metadata_entries(root):
        st = os.lstat(path)
        kind = stat.S_IFMT(st.st_mode)
        row: dict[str, Any] = {
            "path": str(path),
            "mode": format(st.st_mode & 0o7777, "o"),
            "uid": st.st_uid,
            "gid": st.st_gid,
            "kind": kind,
            "nlink": st.st_nlink,
        }
        if stat.S_ISLNK(st.st_mode):
            row["target"] = os.readlink(path)
        elif stat.S_ISREG(st.st_mode):
            total += st.st_size
            if total > MAX_GIT_METADATA_BYTES:
                raise SecurityError("Git administrative metadata exceeds the byte limit.")
            row["size"] = st.st_size
            row["sha256"] = sha256_file(path)
        elif not stat.S_ISDIR(st.st_mode):
            raise SecurityError(f"Unsupported Git administrative entry type: {path}")
        rows.append(row)
    return {
        "format_version": "1.0",
        "entry_count": len(rows),
        "total_regular_bytes": total,
        "entries": rows,
        "sha256": sha256_bytes(canonical_json_bytes(rows)),
    }


def verify_git_metadata_inventory(root: Path, expected: dict[str, Any]) -> None:
    actual = git_metadata_inventory(root)
    if actual.get("sha256") != expected.get("sha256") or actual.get("entries") != expected.get("entries"):
        raise SecurityError("Git administrative metadata changed during the controlled agent run.")


_IDENTITY_WRITABLE_PROBE = r"""
import json, os, stat, sys
payload = json.load(sys.stdin)
os.setgroups([])
os.setgid(int(payload['gid']))
os.setuid(int(payload['uid']))
failure = ''
for raw in payload['paths']:
    path = raw
    try:
        st = os.lstat(path)
        if stat.S_ISDIR(st.st_mode):
            probe = os.path.join(path, f'.azpr-agent-write-probe-{os.getpid()}')
            fd = os.open(probe, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, 'O_NOFOLLOW', 0), 0o600)
            os.close(fd)
            os.unlink(probe)
            failure = path
            break
        if stat.S_ISREG(st.st_mode):
            fd = os.open(path, os.O_WRONLY | getattr(os, 'O_NOFOLLOW', 0))
            os.close(fd)
            failure = path
            break
    except (PermissionError, FileNotFoundError, IsADirectoryError, OSError):
        continue
print(failure)
"""


def _identity_writable_path(paths: Sequence[Path], uid: int, gid: int) -> str | None:
    """Return the first path writable by an exact dropped identity.

    The access probe runs in a fresh Python process and drops identity before
    touching any candidate. This avoids unsafe fork-from-multithreaded-runtime
    behavior while still exercising ACL and supplementary-group boundaries.
    """
    if os.geteuid() != 0:
        raise SecurityError("Identity access probes require the root controller identity.")
    payload = json.dumps({'uid': uid, 'gid': gid, 'paths': [str(path) for path in paths]}, separators=(',', ':'))
    executable = str(Path(sys.executable).resolve())
    try:
        result = subprocess.run(
            [executable, '-I', '-c', _IDENTITY_WRITABLE_PROBE],
            input=payload,
            cwd='/',
            env={'PATH':'/usr/bin:/bin','PYTHONDONTWRITEBYTECODE':'1','LANG':'C.UTF-8','LC_ALL':'C.UTF-8'},
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise SecurityError("Agent-identity write-denial probe failed.") from exc
    if result.returncode != 0:
        raise SecurityError("Agent-identity write-denial probe failed.")
    value = result.stdout.rstrip('\n')
    if '\n' in value or len(value.encode('utf-8', 'replace')) > 8192:
        raise SecurityError("Agent-identity write-denial probe returned invalid output.")
    return value or None


def assert_git_metadata_protected(root: Path, *, agent_uid: int, agent_gid: int, owner_uid: int = 0) -> dict[str, Any]:
    entries = _metadata_entries(root)
    for path in entries:
        st = os.lstat(path)
        if stat.S_ISLNK(st.st_mode):
            raise SecurityError(f"Symlinked Git administrative metadata is forbidden: {path}")
        if st.st_uid != owner_uid:
            raise SecurityError(f"Git administrative metadata is not controller-owned: {path}")
        if st.st_mode & 0o022:
            raise SecurityError(f"Git administrative metadata is group/other writable: {path}")
        if stat.S_ISREG(st.st_mode) and st.st_nlink != 1:
            raise SecurityError(f"Hard-linked Git administrative file is forbidden: {path}")
    writable = _identity_writable_path(entries, agent_uid, agent_gid)
    if writable:
        raise SecurityError(f"Configured agent identity can write Git administrative metadata: {writable}")
    return git_metadata_inventory(root)


def filesystem_worktree_paths(root: Path) -> list[str]:
    """Inventory every non-Git-admin worktree entry without ignore semantics."""
    repo = root.resolve()
    values: set[str] = set()
    for current, dirs, files in os.walk(repo, topdown=True, followlinks=False):
        current_path = Path(current)
        rel_dir = current_path.relative_to(repo).as_posix()
        # Only the repository's own .git marker is excluded. Nested repository
        # markers are surfaced and pruned so they cannot hide a subtree.
        if current_path == repo:
            if ".git" in dirs:
                dirs.remove(".git")
            if ".git" in files:
                files.remove(".git")
        else:
            if ".git" in dirs:
                marker = current_path / ".git"
                values.add(marker.relative_to(repo).as_posix())
                dirs.remove(".git")
            if ".git" in files:
                values.add((current_path / ".git").relative_to(repo).as_posix())
                files.remove(".git")
        dirs[:] = sorted(dirs)
        for name in sorted(files):
            rel = (current_path / name).relative_to(repo).as_posix()
            safe_relative_path(rel, "worktree path")
            values.add(rel)
        # os.walk lists symlinked directories in dirs but does not traverse them.
        for name in list(dirs):
            candidate = current_path / name
            try:
                if stat.S_ISLNK(os.lstat(candidate).st_mode):
                    values.add(candidate.relative_to(repo).as_posix())
                    dirs.remove(name)
            except FileNotFoundError:
                values.add(candidate.relative_to(repo).as_posix())
    return sorted(values)


def complete_worktree_paths(root: Path) -> list[str]:
    """Return tracked changes plus all untracked/ignored filesystem paths."""
    tracked = set(tracked_paths(root))
    changed: set[str] = set()
    for argv in (
        ["diff", "--name-only", "-z", "--no-renames"],
        ["diff", "--cached", "--name-only", "-z", "--no-renames"],
    ):
        changed.update(split_nul_paths(_git_bytes(root, argv), label="git " + " ".join(argv)))
    for rel in filesystem_worktree_paths(root):
        if rel not in tracked:
            changed.add(rel)
    return sorted(changed)


def git_changed_paths(root: Path) -> list[str]:
    """v6 override: ignore metadata can no longer hide changed paths."""
    return complete_worktree_paths(root)


def git_diff_metrics(root: Path, *, byte_limit: int) -> dict[str, int]:
    """Measure tracked binary patch plus every untracked/ignored artifact."""
    env = secure_git_env()
    argv = secure_git_argv(["diff", "--binary", "--full-index", "--no-ext-diff", "HEAD", "--"])
    try:
        _rc, patch, _stderr, _duration = run_bounded_process(
            argv, cwd=root, timeout_seconds=120, env=env,
            stdout_limit=byte_limit + 1, stderr_limit=256 * 1024,
        )
    except SecurityError as exc:
        raise SecurityError("actual diff exceeds the configured byte budget") from exc
    tracked = set(tracked_paths(root))
    untracked = [path for path in filesystem_worktree_paths(root) if path not in tracked]
    untracked_bytes = 0
    for rel in untracked:
        path = root / rel
        no_symlink_ancestors(path, allow_missing_leaf=False)
        st = os.lstat(path)
        if stat.S_ISREG(st.st_mode):
            if st.st_nlink != 1:
                raise SecurityError(f"unsafe untracked diff input: {rel}")
            size = st.st_size
        elif stat.S_ISLNK(st.st_mode):
            size = len(os.readlink(path).encode("utf-8"))
        else:
            raise SecurityError(f"unsupported untracked diff input: {rel}")
        untracked_bytes += size + len(rel.encode("utf-8")) + 1
        if len(patch) + untracked_bytes > byte_limit:
            raise SecurityError("actual diff exceeds the configured byte budget")
    return {
        "patch_bytes": len(patch),
        "untracked_bytes": untracked_bytes,
        "total_bytes": len(patch) + untracked_bytes,
    }

# ---------------------------------------------------------------------------
# v6 exact governing-policy rendering
# ---------------------------------------------------------------------------

DOCX_CANONICAL_RENDER_ALGORITHM = "AZPR_DOCX_PARAGRAPH_TEXT_UTF8_V2"


def derive_docx_lossless_policy(raw: bytes, source_name: str) -> tuple[dict[str, Any], bytes, dict[str, Any]]:
    """Derive the only admissible Markdown/text authority from exact DOCX text.

    The exact DOCX hash remains authoritative. The deterministic UTF-8 render is
    accepted only when every byte equals this algorithm's output; no semantic
    substitution, condensation, reordering, or expansion is permitted.
    """
    try:
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            xml = archive.read("word/document.xml")
    except Exception as exc:
        raise SecurityError("governing policy source is not a valid DOCX") from exc
    try:
        root = ET.fromstring(xml)
    except ET.ParseError as exc:
        raise SecurityError("governing policy DOCX XML is invalid") from exc
    paragraphs: list[tuple[str, str]] = []
    for paragraph in root.findall(".//w:body/w:p", DOCX_NS):
        text = "".join((node.text or "") for node in paragraph.findall(".//w:t", DOCX_NS))
        if not text.strip():
            continue
        style_node = paragraph.find("./w:pPr/w:pStyle", DOCX_NS)
        style = style_node.attrib.get("{%s}val" % DOCX_NS["w"], "") if style_node is not None else ""
        paragraphs.append((text, style[:200]))
    if not paragraphs:
        raise SecurityError("governing policy DOCX has no nonempty paragraph units")
    chunks: list[bytes] = []
    units: list[dict[str, Any]] = []
    mappings: list[dict[str, Any]] = []
    offset = 0
    for index, (text, style) in enumerate(paragraphs, start=1):
        text_bytes = text.encode("utf-8")
        separator = b"\n" if index == len(paragraphs) else b"\n\n"
        span = text_bytes + separator
        start = offset
        text_end = start + len(text_bytes)
        end = start + len(span)
        unit_id = f"p{index:06d}"
        normalized = unicodedata.normalize("NFKC", " ".join(text.split()))
        unit = {
            "unit_id": unit_id,
            "ordinal": index,
            "style": style,
            "text_sha256": sha256_bytes(text_bytes),
            "normalized_text_sha256": sha256_bytes(normalized.encode("utf-8")),
            "text_length_bytes": len(text_bytes),
            "canonical_start_byte": start,
            "canonical_text_end_byte": text_end,
            "canonical_end_byte": end,
            "canonical_text_sha256": sha256_bytes(text_bytes),
            "canonical_span_sha256": sha256_bytes(span),
        }
        units.append(unit)
        mappings.append({
            "mapping_id": f"m{index:06d}",
            "source_unit_id": unit_id,
            "canonical_start_byte": start,
            "canonical_text_end_byte": text_end,
            "canonical_end_byte": end,
            "source_text_sha256": unit["text_sha256"],
            "canonical_text_sha256": unit["canonical_text_sha256"],
            "canonical_span_sha256": unit["canonical_span_sha256"],
            "review_status": "EXACT",
        })
        chunks.append(span)
        offset = end
    canonical_bytes = b"".join(chunks)
    manifest = {
        "format_version": "2.0",
        "algorithm": "AZPR_DOCX_PARAGRAPH_UNITS_V2",
        "canonical_render_algorithm": DOCX_CANONICAL_RENDER_ALGORITHM,
        "source_document_name": source_name,
        "source_document_sha256": sha256_bytes(raw),
        "canonical_policy_sha256": sha256_bytes(canonical_bytes),
        "canonical_byte_length": len(canonical_bytes),
        "unit_count": len(units),
        "unit_chain_sha256": sha256_bytes(canonical_json_bytes(units)),
        "units": units,
    }
    section_map = {
        "format_version": "3.0",
        "algorithm": DOCX_CANONICAL_RENDER_ALGORITHM,
        "source_document_name": source_name,
        "source_document_sha256": manifest["source_document_sha256"],
        "source_manifest_sha256": "",  # Filled by the output tool after canonical JSON serialization.
        "canonical_policy_sha256": manifest["canonical_policy_sha256"],
        "canonical_byte_length": len(canonical_bytes),
        "source_unit_count": len(units),
        "mappings": mappings,
    }
    return manifest, canonical_bytes, section_map


def verify_lossless_canonical_policy(
    source_raw: bytes,
    source_name: str,
    source_manifest: dict[str, Any],
    canonical_bytes: bytes,
    section_map: dict[str, Any],
    *,
    source_manifest_sha256: str | None = None,
) -> None:
    derived_manifest, derived_canonical, derived_map = derive_docx_lossless_policy(source_raw, source_name)
    if source_manifest != derived_manifest:
        raise SecurityError("canonical source manifest is not the deterministic v2 manifest of the governing DOCX")
    if canonical_bytes != derived_canonical:
        raise SecurityError("canonical policy is not the exact deterministic rendering of the governing DOCX")
    expected_map = dict(derived_map)
    expected_map["source_manifest_sha256"] = source_manifest_sha256 or section_map.get("source_manifest_sha256")
    if section_map != expected_map:
        raise SecurityError("canonical section map is not the exact byte-span map of the governing DOCX rendering")

# ---------------------------------------------------------------------------
# v7 pre-autonomous execution-boundary closures
# ---------------------------------------------------------------------------

DOCX_CANONICAL_RENDER_ALGORITHM = "AZPR_DOCX_SUPPORTED_OOXML_UTF8_V3"
MAX_WORKTREE_LEDGER_FILES = 200_000
MAX_WORKTREE_LEDGER_BYTES = 2 * 1024 * 1024 * 1024
MAX_AGENT_RESULT_BYTES = 2 * 1024 * 1024

@dataclass(frozen=True)
class AgentRunSurface:
    handoff_root: Path
    run_dir: Path
    home: Path
    tmp: Path
    output_dir: Path
    output_path: Path
    agent_uid: int
    agent_gid: int


def _ensure_directory_metadata(path: Path, *, uid: int, gid: int, mode: int) -> None:
    st=os.lstat(path)
    if stat.S_ISLNK(st.st_mode) or not stat.S_ISDIR(st.st_mode):
        raise SecurityError(f"unsafe directory: {path}")
    if st.st_uid != uid or st.st_gid != gid or (st.st_mode & 0o777) != mode:
        raise SecurityError(f"directory metadata mismatch: {path}")


def validate_agent_handoff_root(path: Path) -> Path:
    path=path.absolute()
    no_symlink_ancestors(path,allow_missing_leaf=False)
    st=os.lstat(path)
    if not stat.S_ISDIR(st.st_mode) or st.st_uid != 0 or st.st_gid != 0:
        raise SecurityError("agent handoff root must be a root-owned directory")
    if (st.st_mode & 0o777) != 0o711:
        raise SecurityError("agent handoff root must use exact mode 0711")
    return path


def create_agent_run_surface(handoff_root: Path, *, agent_uid: int, agent_gid: int, run_token: str | None = None) -> AgentRunSurface:
    if os.geteuid()!=0:
        raise SecurityError("agent run surfaces must be created by the root controller")
    if agent_uid<=0 or agent_gid<=0:
        raise SecurityError("agent run surface requires an explicit non-root UID/GID")
    root=validate_agent_handoff_root(handoff_root)
    token=run_token or secrets.token_hex(24)
    if not re.fullmatch(r"[A-Za-z0-9._-]{16,160}",token):
        raise SecurityError("invalid agent run token")
    run_dir=root/("run-"+token)
    try:
        os.mkdir(run_dir,0o700)
    except FileExistsError as exc:
        raise SecurityError("agent run surface collision") from exc
    os.chown(run_dir,agent_uid,agent_gid);os.chmod(run_dir,0o700)
    children=[]
    try:
        for name in ("home","tmp","output"):
            child=run_dir/name
            os.mkdir(child,0o700);os.chown(child,agent_uid,agent_gid);os.chmod(child,0o700)
            children.append(child)
        surface=AgentRunSurface(root,run_dir,children[0],children[1],children[2],children[2]/"result.json",agent_uid,agent_gid)
        _ensure_directory_metadata(run_dir,uid=agent_uid,gid=agent_gid,mode=0o700)
        for child in children:_ensure_directory_metadata(child,uid=agent_uid,gid=agent_gid,mode=0o700)
        return surface
    except BaseException:
        try:os.chown(run_dir,0,0);shutil.rmtree(run_dir,ignore_errors=True)
        except OSError:pass
        raise


def agent_surface_env(surface: AgentRunSurface, *, executable_path: str, codex_home: str | None = None, extra: dict[str,str] | None = None) -> dict[str,str]:
    for path in (surface.run_dir,surface.home,surface.tmp,surface.output_dir):
        _ensure_directory_metadata(path,uid=surface.agent_uid,gid=surface.agent_gid,mode=0o700)
    env={
        "PATH":executable_path,"HOME":str(surface.home),"TMPDIR":str(surface.tmp),
        "LANG":"C.UTF-8","LC_ALL":"C.UTF-8","PYTHONDONTWRITEBYTECODE":"1",
        "NO_PROXY":"*","no_proxy":"*","UMASK":"077",
    }
    if codex_home:
        cp=Path(codex_home).expanduser().absolute();no_symlink_ancestors(cp,allow_missing_leaf=False);env["CODEX_HOME"]=str(cp)
    if extra:
        forbidden=("SECRET","TOKEN","PASSWORD","PASSWD","PRIVATE","CREDENTIAL","APPROVAL","SIGNING")
        for key,value in extra.items():
            if any(token in key.upper() for token in forbidden):raise SecurityError(f"Refusing to expose sensitive environment variable to child: {key}")
            ensure_no_control_chars(key,"environment name");ensure_no_control_chars(value,f"environment {key}");env[key]=value
    return env


def import_agent_result(surface: AgentRunSurface, controller_output: Path, *, max_bytes: int = MAX_AGENT_RESULT_BYTES) -> bytes:
    path=surface.output_path
    before=os.lstat(path)
    if stat.S_ISLNK(before.st_mode) or not stat.S_ISREG(before.st_mode) or before.st_nlink!=1:
        raise SecurityError("agent result must be a single-link regular file")
    if before.st_uid!=surface.agent_uid or before.st_gid!=surface.agent_gid:
        raise SecurityError("agent result ownership mismatch")
    if before.st_size<=0 or before.st_size>max_bytes:
        raise SecurityError("agent result size is outside the allowed bounds")
    if before.st_mode & 0o022:
        raise SecurityError("agent result is writable by group/other")
    fd=os.open(path,os.O_RDONLY|getattr(os,"O_NOFOLLOW",0))
    try:
        opened=os.fstat(fd)
        if (before.st_dev,before.st_ino)!=(opened.st_dev,opened.st_ino):raise SecurityError("agent result identity changed before open")
        data=bytearray()
        while True:
            chunk=os.read(fd,65536)
            if not chunk:break
            data.extend(chunk)
            if len(data)>max_bytes:raise SecurityError("agent result exceeded the import limit")
        after=os.fstat(fd)
        if (opened.st_dev,opened.st_ino,opened.st_size,opened.st_mtime_ns)!=(after.st_dev,after.st_ino,after.st_size,after.st_mtime_ns):
            raise SecurityError("agent result changed during import")
        current=os.lstat(path)
        if stat.S_ISLNK(current.st_mode) or (current.st_dev,current.st_ino)!=(after.st_dev,after.st_ino):
            raise SecurityError("agent result pathname changed during import")
    finally:os.close(fd)
    secure_write_bytes(controller_output,bytes(data),mode=0o600,create_once=True)
    return bytes(data)


def _remove_tree_nofollow(path: Path) -> None:
    st=os.lstat(path)
    if stat.S_ISLNK(st.st_mode) or stat.S_ISREG(st.st_mode):os.unlink(path);return
    if not stat.S_ISDIR(st.st_mode):raise SecurityError(f"unsupported cleanup entry: {path}")
    with os.scandir(path) as entries:
        names=[entry.name for entry in entries]
    for name in names:_remove_tree_nofollow(path/name)
    os.rmdir(path)


def destroy_agent_run_surface(surface: AgentRunSurface) -> None:
    root=validate_agent_handoff_root(surface.handoff_root)
    try:surface.run_dir.relative_to(root)
    except ValueError as exc:raise SecurityError("agent run surface escaped its handoff root") from exc
    quarantine=root/(".quarantine-"+secrets.token_hex(24))
    os.rename(surface.run_dir,quarantine)
    os.chown(quarantine,0,0);os.chmod(quarantine,0o700)
    _remove_tree_nofollow(quarantine)
    if surface.run_dir.exists() or surface.run_dir.is_symlink():raise SecurityError("agent run surface cleanup failed")


def _git_config_values(root: Path, pattern: str) -> list[str]:
    completed=subprocess.run(secure_git_argv(["config","--get-regexp",pattern]),cwd=root,capture_output=True,env=secure_git_env(),check=False)
    if completed.returncode not in (0,1):raise SecurityError("unable to inspect Git semantic configuration")
    return completed.stdout.decode("utf-8","replace").splitlines()


def repository_topology_preflight(root: Path, writable_patterns: Iterable[str]) -> None:
    """Reject every unsupported Git semantic boundary before any stage side effect."""
    repo=root.resolve();no_symlink_ancestors(repo,allow_missing_leaf=False)
    marker=repo/".git"
    st=os.lstat(marker)
    if not stat.S_ISDIR(st.st_mode) or stat.S_ISLNK(st.st_mode):
        raise SecurityError("linked worktrees and .git indirection files are forbidden")
    admins=git_admin_roots(repo)
    expected=marker.resolve()
    if len(admins)!=1 or admins[0]!=expected:
        raise SecurityError("separate Git worktree/common administrative roots are forbidden")
    shallow=_raw_git_output(repo,["rev-parse","--is-shallow-repository"]).decode().strip().lower()
    if shallow!="false":raise SecurityError("shallow repositories are forbidden")
    forbidden_paths=[
        marker/"info/grafts",marker/"objects/info/alternates",marker/"objects/info/http-alternates",
        marker/"shallow",marker/"commondir",marker/"gitdir",
    ]
    for candidate in forbidden_paths:
        if candidate.exists() or candidate.is_symlink():raise SecurityError(f"unsupported Git semantic override is present: {candidate.relative_to(marker)}")
    replace_root=marker/"refs/replace"
    if replace_root.exists() and any(replace_root.rglob("*")):
        raise SecurityError("Git replace refs are forbidden")
    for candidate in (marker/"objects/pack").glob("*.promisor") if (marker/"objects/pack").exists() else ():
        raise SecurityError(f"partial-clone promisor state is forbidden: {candidate.name}")
    if _git_config_values(repo,r"^(extensions\.partialclone|remote\..*\.promisor|core\.alternateRefsCommand|core\.repositoryFormatVersion)$"):
        # repositoryFormatVersion=0 is ordinary; inspect it separately.
        lines=_git_config_values(repo,r"^(extensions\.partialclone|remote\..*\.promisor|core\.alternateRefsCommand)$")
        if lines:raise SecurityError("partial-clone/promisor/alternate Git configuration is forbidden")
    raw_stage=_git_bytes(repo,["ls-files","--stage","-z"])
    for item in raw_stage.split(b"\0"):
        if item.startswith(b"160000 "):raise SecurityError("Git submodules/gitlinks are forbidden")
    if (repo/".gitmodules").exists() or (repo/".gitmodules").is_symlink():raise SecurityError(".gitmodules is forbidden")
    allowed_top={"HEAD","config","description","index","packed-refs","branches","hooks","info","logs","objects","refs","COMMIT_EDITMSG","ORIG_HEAD","FETCH_HEAD"}
    for child in marker.iterdir():
        if child.name not in allowed_top and not child.name.endswith(".lock"):
            raise SecurityError(f"unexpected Git administrative top-level entry: {child.name}")
    info=marker/"info"
    if info.exists():
        allowed_info={"exclude","attributes","refs"}
        for child in info.iterdir():
            if child.name not in allowed_info:raise SecurityError(f"unsupported Git info entry: {child.name}")
    for current,dirs,files in os.walk(repo,topdown=True,followlinks=False):
        current_path=Path(current)
        if current_path==repo:
            if ".git" in dirs:dirs.remove(".git")
            if ".git" in files:files.remove(".git")
        elif ".git" in dirs or ".git" in files:
            raise SecurityError(f"nested Git administrative boundary is forbidden: {current_path}")
        for name in list(dirs)+list(files):
            candidate=current_path/name;rel=candidate.relative_to(repo).as_posix();info_st=os.lstat(candidate)
            if stat.S_ISLNK(info_st.st_mode) and path_matches(rel,writable_patterns):raise SecurityError(f"Writable symlink is forbidden: {rel}")
            if stat.S_ISREG(info_st.st_mode) and info_st.st_nlink>1 and path_matches(rel,writable_patterns):raise SecurityError(f"Writable hard-linked file is forbidden: {rel}")


def worktree_identity_inventory(root: Path) -> dict[str,Any]:
    repo=root.resolve();rows=[];total=0
    for current,dirs,files in os.walk(repo,topdown=True,followlinks=False):
        cp=Path(current)
        if cp==repo and ".git" in dirs:dirs.remove(".git")
        dirs[:]=sorted(dirs)
        names=sorted(dirs)+sorted(files)
        for name in names:
            path=cp/name;rel=path.relative_to(repo).as_posix();st=os.lstat(path)
            row={"path":rel,"kind":stat.S_IFMT(st.st_mode),"mode":st.st_mode&0o7777,"uid":st.st_uid,"gid":st.st_gid,"dev":st.st_dev,"ino":st.st_ino,"nlink":st.st_nlink}
            if stat.S_ISREG(st.st_mode):
                total+=st.st_size
                if total>MAX_WORKTREE_LEDGER_BYTES:raise SecurityError("worktree ledger exceeds byte limit")
                row.update({"size":st.st_size,"sha256":sha256_file(path)})
            elif stat.S_ISLNK(st.st_mode):row["target"]=os.readlink(path)
            elif not stat.S_ISDIR(st.st_mode):raise SecurityError(f"unsupported worktree entry type: {rel}")
            rows.append(row)
            if len(rows)>MAX_WORKTREE_LEDGER_FILES:raise SecurityError("worktree ledger exceeds file-count limit")
    semantic=[{k:v for k,v in row.items() if k not in {"dev","ino"}} for row in rows]
    return {"format_version":"1.0","entry_count":len(rows),"total_regular_bytes":total,"entries":rows,"semantic_sha256":sha256_bytes(canonical_json_bytes(semantic))}


def cleanup_worktree_to_baseline(root: Path, baseline: dict[str,Any]) -> dict[str,Any]:
    repo=root.resolve();expected={row["path"]:row for row in baseline.get("entries",[]) if isinstance(row,dict) and isinstance(row.get("path"),str)}
    current=worktree_identity_inventory(repo);actual={row["path"]:row for row in current["entries"]}
    # Baseline content/type/ownership must already have been restored by Git reset.
    for rel,row in expected.items():
        now=actual.get(rel)
        if now is None:raise SecurityError(f"baseline path is missing after reset: {rel}")
        for key in ("kind","mode","uid","gid","nlink","size","sha256","target"):
            if row.get(key)!=now.get(key):raise SecurityError(f"baseline path identity was not restored: {rel}:{key}")
    created=sorted(set(actual)-set(expected),key=lambda value:(value.count("/"),len(value)),reverse=True)
    for rel in created:
        path=repo/safe_relative_path(rel,"stage-created path")
        st=os.lstat(path);captured=actual[rel]
        if (st.st_dev,st.st_ino,stat.S_IFMT(st.st_mode))!=(captured["dev"],captured["ino"],captured["kind"]):
            raise SecurityError(f"stage-created path changed before cleanup: {rel}")
        if stat.S_ISDIR(st.st_mode):os.rmdir(path)
        elif stat.S_ISREG(st.st_mode) or stat.S_ISLNK(st.st_mode):os.unlink(path)
        else:raise SecurityError(f"unsupported stage-created cleanup type: {rel}")
    final=worktree_identity_inventory(repo)
    expected_semantic=baseline.get("semantic_sha256")
    if final.get("semantic_sha256")!=expected_semantic:
        raise SecurityError("post-cleanup worktree does not equal the pre-stage baseline")
    return {"removed_paths":created,"final_semantic_sha256":final["semantic_sha256"]}


_UNSUPPORTED_DOCX_TAGS={
    "tbl","txbxContent","fldSimple","fldChar","instrText","footnoteReference","endnoteReference",
    "commentReference","ins","del","moveFrom","moveTo","altChunk","object","pict","drawing","sdt",
}

def _local_name(tag: str) -> str:return tag.rsplit("}",1)[-1]

def _render_docx_paragraph(paragraph: ET.Element) -> tuple[str,dict[str,int]]:
    counts={"text_nodes":0,"tabs":0,"breaks":0}
    pieces=[]
    for node in paragraph.iter():
        name=_local_name(node.tag)
        if name in _UNSUPPORTED_DOCX_TAGS:raise SecurityError(f"unsupported normative DOCX feature: {name}")
        if name=="numPr":raise SecurityError("Word automatic numbering is unsupported; render must fail closed")
        if name=="t":pieces.append(node.text or "");counts["text_nodes"]+=1
        elif name=="tab":pieces.append("\t");counts["tabs"]+=1
        elif name in {"br","cr"}:pieces.append("\n");counts["breaks"]+=1
        elif name=="noBreakHyphen":pieces.append("‑")
        elif name=="softHyphen":pieces.append("\u00ad")
    return "".join(pieces),counts


def _docx_supported_parts(archive: zipfile.ZipFile) -> tuple[ET.Element,dict[str,Any]]:
    names=archive.namelist()
    if len(names)!=len(set(names)):raise SecurityError("DOCX contains duplicate ZIP members")
    for name in names:
        pp=PurePosixPath(name)
        if pp.is_absolute() or ".." in pp.parts or "\\" in name:raise SecurityError("DOCX contains unsafe member paths")
    try:document=ET.fromstring(archive.read("word/document.xml"))
    except (KeyError,ET.ParseError) as exc:raise SecurityError("governing policy DOCX XML is invalid") from exc
    unsupported_parts=[]
    for name in names:
        lower=name.lower()
        if not lower.startswith("word/") or not lower.endswith(".xml") or lower=="word/document.xml":continue
        if any(token in lower for token in ("header","footer","footnote","endnote","comments","glossary","people","document2")):
            try:part=ET.fromstring(archive.read(name))
            except ET.ParseError as exc:raise SecurityError(f"invalid DOCX part: {name}") from exc
            visible=[]
            for node in part.iter():
                lname=_local_name(node.tag)
                if lname=="t" and (node.text or ""):visible.append(node.text or "")
                elif lname in {"tab","br","cr"}:visible.append(lname)
            if visible:unsupported_parts.append(name)
    if unsupported_parts:raise SecurityError("unsupported normative DOCX parts are nonempty: "+", ".join(sorted(unsupported_parts)))
    return document,{"package_member_count":len(names),"unsupported_features":[],"unsupported_normative_parts":[]}


def derive_docx_lossless_policy(raw: bytes, source_name: str) -> tuple[dict[str,Any],bytes,dict[str,Any]]:
    try:
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:root,feature_inventory=_docx_supported_parts(archive)
    except SecurityError:raise
    except Exception as exc:raise SecurityError("governing policy source is not a valid DOCX") from exc
    body=root.find(".//w:body",DOCX_NS)
    if body is None:raise SecurityError("governing policy DOCX has no body")
    paragraphs=[];totals={"paragraphs":0,"text_nodes":0,"tabs":0,"breaks":0}
    for child in list(body):
        lname=_local_name(child.tag)
        if lname=="sectPr":continue
        if lname!="p":raise SecurityError(f"unsupported top-level DOCX body feature: {lname}")
        text,counts=_render_docx_paragraph(child)
        if text=="":continue
        style_node=child.find("./w:pPr/w:pStyle",DOCX_NS)
        style=style_node.attrib.get("{%s}val"%DOCX_NS["w"],"") if style_node is not None else ""
        paragraphs.append((text,style[:200],counts));totals["paragraphs"]+=1
        for key in ("text_nodes","tabs","breaks"):totals[key]+=counts[key]
    if not paragraphs:raise SecurityError("governing policy DOCX has no nonempty paragraph units")
    chunks=[];units=[];mappings=[];offset=0
    for index,(text,style,counts) in enumerate(paragraphs,1):
        tb=text.encode("utf-8");sep=b"\n" if index==len(paragraphs) else b"\n\n";span=tb+sep
        start=offset;text_end=start+len(tb);end=start+len(span);uid=f"p{index:06d}"
        normalized=unicodedata.normalize("NFKC",text)
        unit={"unit_id":uid,"ordinal":index,"style":style,"text_sha256":sha256_bytes(tb),"normalized_text_sha256":sha256_bytes(normalized.encode()),"text_length_bytes":len(tb),"tab_count":counts["tabs"],"break_count":counts["breaks"],"canonical_start_byte":start,"canonical_text_end_byte":text_end,"canonical_end_byte":end,"canonical_text_sha256":sha256_bytes(tb),"canonical_span_sha256":sha256_bytes(span)}
        units.append(unit);mappings.append({"mapping_id":f"m{index:06d}","source_unit_id":uid,"canonical_start_byte":start,"canonical_text_end_byte":text_end,"canonical_end_byte":end,"source_text_sha256":unit["text_sha256"],"canonical_text_sha256":unit["canonical_text_sha256"],"canonical_span_sha256":unit["canonical_span_sha256"],"review_status":"EXACT_SUPPORTED_OOXML"});chunks.append(span);offset=end
    canonical=b"".join(chunks)
    features={**feature_inventory,**totals,"rendered_tab_count":totals["tabs"],"rendered_break_count":totals["breaks"]}
    manifest={"format_version":"3.0","algorithm":"AZPR_DOCX_SUPPORTED_OOXML_UNITS_V3","canonical_render_algorithm":DOCX_CANONICAL_RENDER_ALGORITHM,"source_document_name":source_name,"source_document_sha256":sha256_bytes(raw),"canonical_policy_sha256":sha256_bytes(canonical),"canonical_byte_length":len(canonical),"unit_count":len(units),"unit_chain_sha256":sha256_bytes(canonical_json_bytes(units)),"feature_inventory":features,"units":units}
    section={"format_version":"4.0","algorithm":DOCX_CANONICAL_RENDER_ALGORITHM,"source_document_name":source_name,"source_document_sha256":manifest["source_document_sha256"],"source_manifest_sha256":"","canonical_policy_sha256":manifest["canonical_policy_sha256"],"canonical_byte_length":len(canonical),"source_unit_count":len(units),"feature_inventory_sha256":sha256_bytes(canonical_json_bytes(features)),"mappings":mappings}
    return manifest,canonical,section


def verify_lossless_canonical_policy(source_raw: bytes,source_name: str,source_manifest: dict[str,Any],canonical_bytes: bytes,section_map: dict[str,Any],*,source_manifest_sha256: str|None=None)->None:
    dm,dc,ds=derive_docx_lossless_policy(source_raw,source_name)
    if source_manifest!=dm:raise SecurityError("canonical source manifest is not the deterministic v3 supported-OOXML manifest")
    if canonical_bytes!=dc:raise SecurityError("canonical policy is not the exact supported-OOXML rendering")
    expected=dict(ds);expected["source_manifest_sha256"]=source_manifest_sha256 or section_map.get("source_manifest_sha256")
    if section_map!=expected:raise SecurityError("canonical section map is not the exact v3 byte-span map")

# ---------------------------------------------------------------------------
# V8 execution-unit containment and duplex I/O overrides
# ---------------------------------------------------------------------------
import signal as _signal

@dataclass
class _ExecutionUnit:
    token: str
    def wrap(self, argv: Sequence[str], barrier_read_fd: int) -> list[str]:
        return [sys.executable, str(Path(__file__).with_name('process_gate.py')), '--barrier-fd', str(barrier_read_fd), '--', *map(str,argv)]
    def attach(self,pid:int)->None:pass
    def terminate_and_wait_empty(self,deadline:float)->None:raise NotImplementedError
    def close(self)->None:pass

class _ProcessMarkerExecutionUnit(_ExecutionUnit):
    """Black-box development containment; production never accepts this backend."""
    def _members(self)->list[int]:
        needle=(f'AZPR_EXECUTION_UNIT_TOKEN={self.token}').encode();out=[]
        for entry in Path('/proc').iterdir():
            if not entry.name.isdigit():continue
            try:
                if needle in (entry/'environ').read_bytes().split(b'\0'):out.append(int(entry.name))
            except (FileNotFoundError,PermissionError,ProcessLookupError,OSError):continue
        return out
    def terminate_and_wait_empty(self,deadline:float)->None:
        while True:
            members=[pid for pid in self._members() if pid!=os.getpid()]
            if not members:return
            for pid in members:
                try:os.kill(pid,_signal.SIGKILL)
                except ProcessLookupError:pass
            if _time.monotonic()>=deadline:raise SecurityError(f'execution unit did not empty; remaining={members[:16]}')
            _time.sleep(0.02)

class _CgroupV2ExecutionUnit(_ExecutionUnit):
    requires_privileged_gate=True
    def __init__(self,token:str,profile:dict[str,Any],root:Path,gate:Path,python_binary:Path):
        super().__init__(token);self.profile=profile;self.root=root;self.gate=gate;self.python=python_binary;self.path=root/('run-'+token)
        validate_cgroup_v2_root(root)
        try:self.path.mkdir(mode=0o755)
        except FileExistsError as exc:raise SecurityError('execution cgroup collision') from exc
        for name,value in [('pids.max',str(profile['pids_max'])),('memory.max',str(profile['memory_max_bytes'])),('cpu.max',profile['cpu_max'])]:
            _write_cgroup_control(self.path/name,value)
    def wrap(self,argv:Sequence[str],barrier_read_fd:int)->list[str]:
        return [str(self.python),str(self.gate),'--barrier-fd',str(barrier_read_fd),'--production-isolation','--uid',str(self.profile['agent_uid']),'--gid',str(self.profile['agent_gid']),'--',*map(str,argv)]
    def attach(self,pid:int)->None:
        _write_cgroup_control(self.path/'cgroup.procs',str(pid))
        if pid not in _read_cgroup_pids(self.path):raise SecurityError('child was not attached to the run cgroup')
    def terminate_and_wait_empty(self,deadline:float)->None:
        kill=self.path/'cgroup.kill'
        if kill.exists():_write_cgroup_control(kill,'1')
        else:
            for pid in _read_cgroup_pids(self.path):
                try:os.kill(pid,_signal.SIGKILL)
                except ProcessLookupError:pass
        while _read_cgroup_pids(self.path):
            if _time.monotonic()>=deadline:raise SecurityError('run cgroup could not be proven empty')
            _time.sleep(0.02)
    def close(self)->None:
        try:self.path.rmdir()
        except OSError as exc:raise SecurityError('empty execution cgroup could not be removed') from exc

def _write_cgroup_control(path:Path,value:str)->None:
    fd=os.open(path,os.O_WRONLY|getattr(os,'O_NOFOLLOW',0))
    try:
        raw=(value+'\n').encode();view=memoryview(raw)
        while view:view=view[os.write(fd,view):]
    finally:os.close(fd)

def _read_cgroup_pids(path:Path)->list[int]:
    try:return [int(x) for x in (path/'cgroup.procs').read_text().split()]
    except FileNotFoundError:return []

def validate_cgroup_v2_root(root:Path)->Path:
    root=root.absolute();no_symlink_ancestors(root,allow_missing_leaf=False)
    st=os.lstat(root)
    if not stat.S_ISDIR(st.st_mode) or st.st_uid!=0 or st.st_mode&0o022:raise SecurityError('agent cgroup root must be root-owned and non-writable')
    if not (root/'cgroup.controllers').exists() and not (root.parent/'cgroup.controllers').exists():raise SecurityError('agent cgroup root is not cgroup v2')
    return root

def _load_v8_execution_unit()->_ExecutionUnit:
    token=secrets.token_hex(24)
    if _ti.production_mode():
        inst=installed_trust();profile_path=inst.component('agent_execution_profile');profile=json.loads(profile_path.read_text())
        schema=inst.component('schema:agent-execution-profile.schema.json');validate_json(profile,schema,label='agent execution profile')
        if profile.get('process_gate_sha256')!=sha256_file(inst.component('process_gate')):raise SecurityError('agent execution profile process-gate mismatch')
        if profile.get('host_id')!=inst.data.get('host_id'):raise SecurityError('agent execution profile host mismatch')
        if not (profile.get('pid_namespace_required') and profile.get('mount_namespace_required') and profile.get('network_namespace_mode')=='DENY_ALL'):raise SecurityError('production execution profile must require PID/mount/network namespaces')
        return _CgroupV2ExecutionUnit(token,profile,inst.directory('agent_cgroup_root'),inst.component('process_gate'),inst.component('python_binary'))
    if os.environ.get('AZPR_EXPLICIT_TEST_MODE')!='1':raise SecurityError('agent execution requires production cgroup containment')
    return _ProcessMarkerExecutionUnit(token)

def _kill_process_group(pid:int)->None:
    try:os.killpg(pid,_signal.SIGKILL)
    except ProcessLookupError:pass

def run_bounded_process(
    argv: Sequence[str], *, cwd: Path, input_bytes: bytes | None = None,
    timeout_seconds: int = 900, env: dict[str,str] | None = None,
    stdout_limit: int = MAX_CONTROLLER_OUTPUT_BYTES,
    stderr_limit: int = MAX_CONTROLLER_OUTPUT_BYTES,
    run_as_uid: int | None = None, run_as_gid: int | None = None,
) -> tuple[int, bytes, bytes, float]:
    """One deadline for duplex transfer, execution-unit teardown, and pipe drain.

    Agent executions are released through a trusted barrier only after their PID
    is attached to the dedicated execution unit.  Every completion path proves
    that the complete unit is empty before returning any result.
    """
    if input_bytes is not None and len(input_bytes)>MAX_JSON_INPUT_BYTES:raise SecurityError('child input exceeds bounded size')
    if timeout_seconds<=0:raise SecurityError('child timeout must be positive')
    start=_time.monotonic();deadline=start+timeout_seconds;unit=_load_v8_execution_unit() if run_as_uid is not None else None
    barrier_r=barrier_w=None;process=None;selector=_selectors.DefaultSelector();buffers={'stdout':bytearray(),'stderr':bytearray()};input_view=memoryview(input_bytes or b'')
    child_env=dict(env or {})
    if unit is not None:child_env['AZPR_EXECUTION_UNIT_TOKEN']=unit.token
    try:
        command=list(map(str,argv));pass_fds=()
        if unit is not None:
            barrier_r,barrier_w=os.pipe2(getattr(os,'O_CLOEXEC',0));os.set_inheritable(barrier_r,True);command=unit.wrap(command,barrier_r);pass_fds=(barrier_r,)
        gate_is_privileged=bool(unit is not None and getattr(unit,'requires_privileged_gate',False))
        process=subprocess.Popen(command,cwd=cwd,stdin=subprocess.PIPE if input_bytes is not None else subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.PIPE,env=child_env,start_new_session=True,user=None if gate_is_privileged else run_as_uid,group=None if gate_is_privileged else run_as_gid,extra_groups=None if gate_is_privileged else ([] if run_as_uid is not None else None),pass_fds=pass_fds)
        if barrier_r is not None:os.close(barrier_r);barrier_r=None
        if unit is not None:
            unit.attach(process.pid);os.write(barrier_w,b'G');os.close(barrier_w);barrier_w=None
        assert process.stdout is not None and process.stderr is not None
        for stream in (process.stdout,process.stderr):os.set_blocking(stream.fileno(),False)
        selector.register(process.stdout,_selectors.EVENT_READ,('stdout',stdout_limit));selector.register(process.stderr,_selectors.EVENT_READ,('stderr',stderr_limit))
        if input_bytes is not None:
            assert process.stdin is not None;os.set_blocking(process.stdin.fileno(),False);selector.register(process.stdin,_selectors.EVENT_WRITE,('stdin',len(input_view)))
        main_exited=False;rc=None;unit_emptied=unit is None
        while selector.get_map() or not main_exited or not unit_emptied:
            now=_time.monotonic()
            if now>=deadline:raise TimeoutError('child process total deadline exceeded')
            if not main_exited:
                polled=process.poll()
                if polled is not None:
                    rc=polled;main_exited=True
                    if process.stdin is not None:
                        try:selector.unregister(process.stdin)
                        except Exception:pass
                        try:process.stdin.close()
                        except OSError:pass
                    if unit is not None:
                        unit.terminate_and_wait_empty(deadline);unit_emptied=True
                    else:_kill_process_group(process.pid)
            events=selector.select(timeout=min(0.05,max(0.0,deadline-_time.monotonic())))
            for key,mask in events:
                name,limit=key.data
                if name=='stdin':
                    if not input_view:
                        selector.unregister(key.fileobj);key.fileobj.close();continue
                    try:written=os.write(key.fd,input_view[:65536])
                    except BrokenPipeError:
                        selector.unregister(key.fileobj);key.fileobj.close();input_view=input_view[len(input_view):];continue
                    input_view=input_view[written:]
                    if not input_view:
                        selector.unregister(key.fileobj);key.fileobj.close()
                    continue
                try:chunk=os.read(key.fd,65536)
                except BlockingIOError:continue
                if not chunk:
                    selector.unregister(key.fileobj);key.fileobj.close();continue
                buffers[name].extend(chunk)
                if len(buffers[name])>limit:raise SecurityError(f'child {name} exceeded {limit} bytes')
            if main_exited and unit_emptied and not selector.get_map():break
        if rc is None:rc=process.wait(timeout=max(0.01,deadline-_time.monotonic()))
        if unit is not None and not unit_emptied:raise SecurityError('execution unit emptiness was not proven')
        return int(rc),bytes(buffers['stdout']),bytes(buffers['stderr']),_time.monotonic()-start
    except BaseException:
        if process is not None:
            _kill_process_group(process.pid)
            if unit is not None:
                try:unit.terminate_and_wait_empty(deadline)
                except BaseException:pass
            try:process.wait(timeout=max(0.01,min(5,deadline-_time.monotonic())))
            except BaseException:pass
        raise
    finally:
        if barrier_r is not None:
            try:os.close(barrier_r)
            except OSError:pass
        if barrier_w is not None:
            try:os.close(barrier_w)
            except OSError:pass
        selector.close()
        if unit is not None:
            try:unit.close()
            except SecurityError:
                if sys.exc_info()[0] is None:raise

# ---------------------------------------------------------------------------
# V8 quota-controlled agent surface overrides
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class AgentRunSurface:
    handoff_root: Path
    run_dir: Path
    home: Path
    tmp: Path
    output_dir: Path
    output_path: Path
    cache: Path
    work: Path
    agent_uid: int
    agent_gid: int
    quota: dict[str,Any]
    mounted_tmpfs: bool
    sealed: bool=False

def _quota_profile()->dict[str,Any]:
    if _ti.production_mode():
        inst=installed_trust();path=inst.component('handoff_quota_profile');value=json.loads(path.read_text());validate_json(value,inst.component('schema:handoff-quota-profile.schema.json'),label='handoff quota profile');return value
    # Non-production source tests use the same bounded defaults; production always loads the signed installed profile.
    return {'format_version':'1.0','profile_id':'v8-test-quota','filesystem_type':'tmpfs','mount_options':['nodev','nosuid','noexec','mode=0700'],'max_bytes':64*1024*1024,'max_inodes':4096,'max_entries':4096,'max_file_bytes':8*1024*1024,'max_depth':32,'max_path_length':1024,'cleanup_max_entries':8192,'cleanup_timeout_seconds':10}

def _mountinfo_for(path:Path)->dict[str,Any]|None:
    target=str(path.resolve());best=None
    try:lines=Path('/proc/self/mountinfo').read_text().splitlines()
    except OSError:return None
    for line in lines:
        parts=line.split();sep=parts.index('-');mountpoint=parts[4].replace('\\040',' ')
        try:Path(target).relative_to(mountpoint)
        except ValueError:continue
        if best is None or len(mountpoint)>len(best['mountpoint']):best={'mountpoint':mountpoint,'mount_options':parts[5].split(','),'fs_type':parts[sep+1],'super_options':parts[sep+3].split(',')}
    return best

def _mount_run_tmpfs(run_dir:Path,quota:dict[str,Any],uid:int,gid:int)->None:
    inst=installed_trust();mount=inst.component('mount_binary')
    options=set(quota['mount_options'])|{f"size={quota['max_bytes']}",f"nr_inodes={quota['max_inodes']}",f'uid={uid}',f'gid={gid}','mode=0700'}
    command=[str(mount),'-t','tmpfs','-o',','.join(sorted(options)),'tmpfs',str(run_dir)]
    rc,out,err,_=run_bounded_process(command,cwd=run_dir,timeout_seconds=30,env={'PATH':'/usr/bin:/bin','HOME':'/nonexistent','LANG':'C.UTF-8','LC_ALL':'C.UTF-8'},stdout_limit=65536,stderr_limit=65536)
    if rc!=0:raise SecurityError('failed to mount quota-controlled agent tmpfs: '+err.decode('utf-8','replace')[-1000:])
    info=_mountinfo_for(run_dir)
    if not info or Path(info['mountpoint'])!=run_dir.resolve() or info['fs_type']!='tmpfs':raise SecurityError('agent run surface is not an exact tmpfs mount')

def _unmount_run_tmpfs(run_dir:Path)->None:
    inst=installed_trust();umount=inst.component('umount_binary')
    rc,_out,err,_=run_bounded_process([str(umount),str(run_dir)],cwd=run_dir.parent,timeout_seconds=30,env={'PATH':'/usr/bin:/bin','HOME':'/nonexistent','LANG':'C.UTF-8','LC_ALL':'C.UTF-8'},stdout_limit=65536,stderr_limit=65536)
    if rc!=0:raise SecurityError('failed to unmount agent run surface: '+err.decode('utf-8','replace')[-1000:])

def create_agent_run_surface(handoff_root:Path,*,agent_uid:int,agent_gid:int,run_token:str|None=None)->AgentRunSurface:
    if os.geteuid()!=0:raise SecurityError('agent run surfaces must be created by the root controller')
    if agent_uid<=0 or agent_gid<=0:raise SecurityError('agent run surface requires explicit non-root identity')
    root=validate_agent_handoff_root(handoff_root);quota=_quota_profile();token=run_token or secrets.token_hex(24)
    if not re.fullmatch(r'[A-Za-z0-9._-]{16,160}',token):raise SecurityError('invalid agent run token')
    run_dir=root/('run-'+token);os.mkdir(run_dir,0o700);os.chown(run_dir,0,0);mounted=False
    try:
        if _ti.production_mode():_mount_run_tmpfs(run_dir,quota,agent_uid,agent_gid);mounted=True
        else:os.chown(run_dir,agent_uid,agent_gid)
        children=[]
        for name in ('home','tmp','output','cache','work'):
            child=run_dir/name;os.mkdir(child,0o700);os.chown(child,agent_uid,agent_gid);os.chmod(child,0o700);children.append(child)
        return AgentRunSurface(root,run_dir,children[0],children[1],children[2],children[2]/'result.json',children[3],children[4],agent_uid,agent_gid,quota,mounted,False)
    except BaseException:
        if mounted:
            try:_unmount_run_tmpfs(run_dir)
            except BaseException:pass
        try:os.chown(run_dir,0,0);shutil.rmtree(run_dir,ignore_errors=True)
        except OSError:pass
        raise

def agent_surface_env(surface:AgentRunSurface,*,executable_path:str,codex_home:str|None=None,extra:dict[str,str]|None=None)->dict[str,str]:
    env={'PATH':executable_path,'HOME':str(surface.home),'TMPDIR':str(surface.tmp),'XDG_CACHE_HOME':str(surface.cache),'AZPR_AGENT_WORK':str(surface.work),'AZPR_RLIMIT_FSIZE':str(surface.quota['max_file_bytes']),'AZPR_RLIMIT_NOFILE':'1024','LANG':'C.UTF-8','LC_ALL':'C.UTF-8','PYTHONDONTWRITEBYTECODE':'1','NO_PROXY':'*','no_proxy':'*','UMASK':'077'}
    if codex_home:
        cp=Path(codex_home).absolute();no_symlink_ancestors(cp,allow_missing_leaf=False);env['CODEX_HOME']=str(cp)
    if extra:
        forbidden=('SECRET','TOKEN','PASSWORD','PASSWD','PRIVATE','CREDENTIAL','APPROVAL','SIGNING')
        for k,v in extra.items():
            if any(t in k.upper() for t in forbidden):raise SecurityError(f'Refusing sensitive environment variable: {k}')
            ensure_no_control_chars(k,'environment name');ensure_no_control_chars(v,f'environment {k}');env[k]=v
    return env

def _quota_scan(root:Path,quota:dict[str,Any],deadline:float)->dict[str,int]:
    count=0;allocated=0;max_depth=0
    stack=[(root,0)]
    while stack:
        if _time.monotonic()>deadline:raise SecurityError('agent surface inventory exceeded cleanup deadline')
        path,depth=stack.pop();st=os.lstat(path);count+=1;allocated+=st.st_blocks*512;max_depth=max(max_depth,depth)
        if count>quota['cleanup_max_entries'] or count>quota['max_entries']:raise SecurityError('agent surface entry budget exceeded')
        if allocated>quota['max_bytes']:raise SecurityError('agent surface allocated-byte budget exceeded')
        if depth>quota['max_depth'] or len(str(path))>quota['max_path_length']:raise SecurityError('agent surface path/depth budget exceeded')
        if stat.S_ISREG(st.st_mode) and st.st_size>quota['max_file_bytes']:raise SecurityError('agent surface file-size budget exceeded')
        if stat.S_ISDIR(st.st_mode):
            with os.scandir(path) as it:
                for e in it:stack.append((path/e.name,depth+1))
        elif not (stat.S_ISREG(st.st_mode) or stat.S_ISLNK(st.st_mode)):raise SecurityError('agent surface contains forbidden special file')
    return {'entries':count,'allocated_bytes':allocated,'max_depth':max_depth}

def seal_agent_run_surface(surface:AgentRunSurface)->AgentRunSurface:
    deadline=_time.monotonic()+surface.quota['cleanup_timeout_seconds'];_quota_scan(surface.run_dir,surface.quota,deadline)
    # Revocation happens by making the complete tree unreachable to the agent UID.
    os.chown(surface.run_dir,0,0);os.chmod(surface.run_dir,0o700)
    return AgentRunSurface(**{**surface.__dict__,'sealed':True})

def destroy_agent_run_surface(surface:AgentRunSurface)->None:
    root=validate_agent_handoff_root(surface.handoff_root)
    try:surface.run_dir.relative_to(root)
    except ValueError as exc:raise SecurityError('agent run surface escaped its handoff root') from exc
    deadline=_time.monotonic()+surface.quota['cleanup_timeout_seconds']
    if not surface.sealed:
        try:surface=seal_agent_run_surface(surface)
        except FileNotFoundError:return
    _quota_scan(surface.run_dir,surface.quota,deadline)
    if surface.mounted_tmpfs:_unmount_run_tmpfs(surface.run_dir)
    quarantine=root/('.quarantine-'+secrets.token_hex(24));os.rename(surface.run_dir,quarantine);os.chown(quarantine,0,0);os.chmod(quarantine,0o700)
    _remove_tree_nofollow(quarantine)
    if surface.run_dir.exists() or surface.run_dir.is_symlink():raise SecurityError('agent run surface cleanup failed')

# Development-only complete-tree backend: Linux child-subreaper semantics avoid
# reliance on /proc/<other-uid>/environ, which may be hidden by host policy.
class _ProcessMarkerExecutionUnit(_ExecutionUnit):
    def __init__(self,token:str):
        super().__init__(token);self.root_pid=None;self.baseline=set(_direct_children(os.getpid()))
        import ctypes
        libc=ctypes.CDLL(None,use_errno=True)
        if libc.prctl(36,1,0,0,0)!=0:raise SecurityError('unable to enable child-subreaper test containment')
    def attach(self,pid:int)->None:self.root_pid=pid
    def _members(self)->set[int]:
        members=set();stack=[]
        if self.root_pid and Path(f'/proc/{self.root_pid}').exists():stack.append(self.root_pid)
        stack.extend(pid for pid in _direct_children(os.getpid()) if pid not in self.baseline)
        while stack:
            pid=stack.pop()
            if pid in members:continue
            members.add(pid);stack.extend(_direct_children(pid))
        return members
    def terminate_and_wait_empty(self,deadline:float)->None:
        empty_streak=0
        while True:
            while True:
                try:pid,_=os.waitpid(-1,os.WNOHANG)
                except ChildProcessError:break
                if pid<=0:break
            members={p for p in self._members() if p!=os.getpid()}
            if not members:
                empty_streak+=1
                if empty_streak>=4:return
                if _time.monotonic()>=deadline:raise SecurityError('subreaper stabilization exceeded deadline')
                _time.sleep(0.05);continue
            empty_streak=0
            for pid in sorted(members,reverse=True):
                try:os.kill(pid,_signal.SIGKILL)
                except ProcessLookupError:pass
            while True:
                try:pid,_=os.waitpid(-1,os.WNOHANG)
                except ChildProcessError:break
                if pid<=0:break
            if _time.monotonic()>=deadline:raise SecurityError(f'subreaper execution unit did not empty: {sorted(members)[:16]}')
            _time.sleep(0.02)

def _direct_children(pid:int)->list[int]:
    try:return [int(x) for x in Path(f'/proc/{pid}/task/{pid}/children').read_text().split()]
    except (FileNotFoundError,PermissionError,OSError,ValueError):return []

# Some hardened kernels omit /proc/<pid>/task/<pid>/children.  The development
# harness therefore derives the child graph from universally readable status
# metadata. Production uses cgroup.procs and never relies on this fallback.
def _direct_children(pid:int)->list[int]:
    out=[]
    for entry in Path('/proc').iterdir():
        if not entry.name.isdigit():continue
        try:
            ppid=None
            for line in (entry/'status').read_text().splitlines():
                if line.startswith('PPid:'):ppid=int(line.split(':',1)[1]);break
            if ppid==pid:out.append(int(entry.name))
        except (FileNotFoundError,PermissionError,OSError,ValueError):continue
    return out
