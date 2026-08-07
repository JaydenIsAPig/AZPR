#!/usr/bin/env python3
"""Rollback-resistant, globally serialized installer authorization transaction state.

This module is intentionally independent from installation side effects. Callers must
hold ``InstallerGlobalLock`` from before the first state read through activation and
final authorization completion.
"""
from __future__ import annotations

import base64
import fcntl
import hashlib
import json
import os
import stat
import subprocess
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from cryptography.hazmat.primitives import serialization
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey

ZERO = "0" * 64
MAX_RECORD_BYTES = 256 * 1024


def canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def sha_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def fsync_dir(path: Path) -> None:
    fd = os.open(path, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def atomic_write(path: Path, data: bytes, mode: int = 0o400) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".new", dir=path.parent)
    tmp = Path(tmp_name)
    try:
        os.fchmod(fd, mode)
        os.write(fd, data)
        os.fsync(fd)
        os.close(fd)
        fd = -1
        os.replace(tmp, path)
        fsync_dir(path.parent)
    finally:
        if fd >= 0:
            try:
                os.close(fd)
            except OSError:
                pass
        try:
            tmp.unlink()
        except FileNotFoundError:
            pass


def read_json(path: Path) -> dict[str, Any]:
    fd = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    try:
        st = os.fstat(fd)
        if not stat.S_ISREG(st.st_mode) or st.st_nlink != 1 or st.st_size > MAX_RECORD_BYTES:
            raise SystemExit(f"unsafe authorization state file: {path}")
        data = bytearray()
        while True:
            chunk = os.read(fd, 65536)
            if not chunk:
                break
            data.extend(chunk)
            if len(data) > MAX_RECORD_BYTES:
                raise SystemExit(f"authorization state file too large: {path}")
    finally:
        os.close(fd)
    try:
        value = json.loads(bytes(data))
    except Exception as exc:
        raise SystemExit(f"invalid authorization state JSON: {path}") from exc
    if not isinstance(value, dict):
        raise SystemExit(f"authorization state must be an object: {path}")
    return value


class InstallerGlobalLock:
    """Kernel-enforced exclusive installer lock.

    The lock file itself is not treated as installation authorization state. Kernel
    ownership means stale process locks disappear on process death; the on-disk file
    is retained only as a stable inode.
    """

    def __init__(self, path: Path):
        self.path = Path(path)
        self.fd: int | None = None

    def acquire(self) -> "InstallerGlobalLock":
        if self.fd is not None:
            raise SystemExit("installer global lock already acquired")
        self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        fd = os.open(
            self.path,
            os.O_RDWR | os.O_CREAT | getattr(os, "O_NOFOLLOW", 0),
            0o600,
        )
        st = os.fstat(fd)
        if not stat.S_ISREG(st.st_mode) or st.st_nlink != 1:
            os.close(fd)
            raise SystemExit("unsafe installer global lock inode")
        try:
            os.fchmod(fd, 0o600)
            if os.geteuid() == 0:
                os.fchown(fd, 0, 0)
            fcntl.flock(fd, fcntl.LOCK_EX)
        except BaseException:
            os.close(fd)
            raise
        self.fd = fd
        return self

    def release(self) -> None:
        if self.fd is None:
            return
        try:
            fcntl.flock(self.fd, fcntl.LOCK_UN)
        finally:
            os.close(self.fd)
            self.fd = None

    def __enter__(self) -> "InstallerGlobalLock":
        return self.acquire()

    def __exit__(self, exc_type, exc, tb) -> None:
        self.release()


@dataclass(frozen=True)
class AnchorHead:
    journal_id: str
    ledger_sequence: int
    authorization_sequence: int
    head_sha256: str

    @classmethod
    def genesis(cls, journal_id: str) -> "AnchorHead":
        return cls(journal_id, 0, 0, ZERO)

    def as_dict(self) -> dict[str, Any]:
        return {
            "journal_id": self.journal_id,
            "ledger_sequence": self.ledger_sequence,
            "authorization_sequence": self.authorization_sequence,
            "head_sha256": self.head_sha256,
        }


class AnchorClient:
    """Strict compare-and-publish client for a rollback-resistant external anchor."""

    def __init__(self, command: str, journal_id: str, timeout_seconds: int = 30):
        self.command = command
        self.journal_id = journal_id
        self.timeout_seconds = timeout_seconds

    def _run(self, operation: str, payload: dict[str, Any]) -> dict[str, Any]:
        proc = subprocess.run(
            [self.command, operation],
            input=json.dumps(payload, sort_keys=True),
            text=True,
            capture_output=True,
            timeout=self.timeout_seconds,
            env={"PATH": "/usr/bin:/bin", "LANG": "C", "LC_ALL": "C"},
        )
        if proc.returncode != 0:
            raise SystemExit(f"authorization anchor {operation} failed closed")
        try:
            value = json.loads(proc.stdout)
        except Exception as exc:
            raise SystemExit("authorization anchor returned invalid JSON") from exc
        if not isinstance(value, dict):
            raise SystemExit("authorization anchor response must be an object")
        return value

    def read_head(self) -> AnchorHead:
        value = self._run("read", {"journal_id": self.journal_id})
        expected = {"journal_id", "ledger_sequence", "authorization_sequence", "head_sha256"}
        if set(value) != expected or value["journal_id"] != self.journal_id:
            raise SystemExit("authorization anchor head identity mismatch")
        head = AnchorHead(
            journal_id=value["journal_id"],
            ledger_sequence=int(value["ledger_sequence"]),
            authorization_sequence=int(value["authorization_sequence"]),
            head_sha256=str(value["head_sha256"]),
        )
        if head.ledger_sequence < 0 or head.authorization_sequence < 0:
            raise SystemExit("authorization anchor sequence is negative")
        if len(head.head_sha256) != 64 or any(c not in "0123456789abcdef" for c in head.head_sha256):
            raise SystemExit("authorization anchor head hash is invalid")
        return head

    def compare_and_publish(self, previous: AnchorHead, new: AnchorHead) -> dict[str, Any]:
        payload = {
            "journal_id": self.journal_id,
            "expected_previous": previous.as_dict(),
            "new_head": new.as_dict(),
        }
        receipt = self._run("compare-and-publish", payload)
        if receipt.get("accepted") is not True:
            raise SystemExit("authorization anchor rejected head transition")
        if receipt.get("journal_id") != self.journal_id:
            raise SystemExit("authorization anchor receipt journal mismatch")
        if receipt.get("previous_head_sha256") != previous.head_sha256:
            raise SystemExit("authorization anchor receipt previous-head mismatch")
        if receipt.get("new_head_sha256") != new.head_sha256:
            raise SystemExit("authorization anchor receipt new-head mismatch")
        if int(receipt.get("ledger_sequence", -1)) != new.ledger_sequence:
            raise SystemExit("authorization anchor receipt sequence mismatch")
        return receipt


class AuthorizationTransactionStore:
    """Signed, hash-chained, externally anchored authorization state machine."""

    def __init__(
        self,
        root: Path,
        anchor_command: str,
        signing_private_key: Path,
        signing_key_id: str,
        journal_id: str,
    ):
        self.root = Path(root)
        self.records = self.root / "records"
        self.head_path = self.root / "HEAD.json"
        self.pending_path = self.root / "PENDING.json"
        self.anchor_receipts = self.root / "anchor-receipts"
        self.anchor = AnchorClient(anchor_command, journal_id)
        self.journal_id = journal_id
        self.signing_key_id = signing_key_id
        raw = Path(signing_private_key).read_bytes()
        key = serialization.load_pem_private_key(raw, password=None)
        if not isinstance(key, Ed25519PrivateKey):
            raise SystemExit("authorization transaction signing key is not Ed25519")
        self.private_key = key
        self.public_key: Ed25519PublicKey = key.public_key()

    def _local_head(self) -> AnchorHead:
        if not self.head_path.exists():
            return AnchorHead.genesis(self.journal_id)
        value = read_json(self.head_path)
        expected = {"journal_id", "ledger_sequence", "authorization_sequence", "head_sha256"}
        if set(value) != expected:
            raise SystemExit("local authorization head is malformed")
        return AnchorHead(
            journal_id=str(value["journal_id"]),
            ledger_sequence=int(value["ledger_sequence"]),
            authorization_sequence=int(value["authorization_sequence"]),
            head_sha256=str(value["head_sha256"]),
        )

    def _write_head(self, head: AnchorHead) -> None:
        atomic_write(self.head_path, (json.dumps(head.as_dict(), indent=2, sort_keys=True) + "\n").encode())

    def _record_path(self, ledger_sequence: int) -> Path:
        return self.records / f"{ledger_sequence:020d}.json"

    def _iter_records(self) -> list[dict[str, Any]]:
        if not self.records.exists():
            return []
        rows = []
        for path in sorted(self.records.glob("*.json")):
            rows.append(read_json(path))
        return rows

    def _sign_record(self, unsigned: dict[str, Any]) -> dict[str, Any]:
        record = dict(unsigned)
        record["signer_key_id"] = self.signing_key_id
        record["signature"] = base64.b64encode(self.private_key.sign(canonical(record))).decode()
        return record

    def _verify_record(self, record: dict[str, Any]) -> None:
        unsigned = dict(record)
        signature = unsigned.pop("signature", None)
        if unsigned.get("signer_key_id") != self.signing_key_id:
            raise SystemExit("authorization record signer identity mismatch")
        try:
            self.public_key.verify(base64.b64decode(str(signature), validate=True), canonical(unsigned))
        except (InvalidSignature, ValueError, TypeError) as exc:
            raise SystemExit("authorization record signature invalid") from exc

    def _audit_records(self, head: AnchorHead) -> None:
        records = self._iter_records()
        if len(records) != head.ledger_sequence:
            raise SystemExit("authorization record count does not match anchored ledger sequence")
        previous_hash = ZERO
        current_authorization_sequence = 0
        open_reservations: set[str] = set()
        for expected_ledger, record in enumerate(records, start=1):
            self._verify_record(record)
            if int(record.get("ledger_sequence", -1)) != expected_ledger:
                raise SystemExit("authorization ledger sequence gap or duplicate")
            if record.get("journal_id") != self.journal_id or record.get("previous_head_sha256") != previous_hash:
                raise SystemExit("authorization record hash-chain mismatch")
            kind = record.get("record_kind")
            seq = int(record.get("authorization_sequence", -1))
            auth_id = str(record.get("authorization_id", ""))
            if kind == "RESERVATION":
                if seq != current_authorization_sequence + 1 or auth_id in open_reservations:
                    raise SystemExit("authorization reservation monotonicity/uniqueness violation")
                current_authorization_sequence = seq
                open_reservations.add(auth_id)
            elif kind == "COMPLETION":
                if seq != current_authorization_sequence or auth_id not in open_reservations:
                    raise SystemExit("authorization completion lacks current reservation")
                open_reservations.remove(auth_id)
            else:
                raise SystemExit("unknown authorization record kind")
            previous_hash = self._record_hash(record)
        if previous_hash != head.head_sha256 or current_authorization_sequence != head.authorization_sequence:
            raise SystemExit("authorization ledger terminal state differs from anchored head")

    def _record_hash(self, record: dict[str, Any]) -> str:
        return sha_bytes(canonical(record))

    def _reconcile_heads(self) -> AnchorHead:
        local = self._local_head()
        remote = self.anchor.read_head()
        if local != remote:
            raise SystemExit(
                "authorization ledger/anchor mismatch; local deletion, truncation, stale restore, or rollback detected"
            )
        self._audit_records(local)
        return local

    def recover(self) -> str:
        """Resolve an interrupted compare-and-publish transaction deterministically."""
        local = self._local_head()
        remote = self.anchor.read_head()
        if not self.pending_path.exists():
            if local != remote:
                raise SystemExit("authorization state rollback detected without recoverable pending record")
            self._audit_records(local)
            return "NO_PENDING_TRANSACTION"
        pending = read_json(self.pending_path)
        record = pending.get("record")
        new_head_value = pending.get("new_head")
        previous_value = pending.get("previous_head")
        if not isinstance(record, dict) or not isinstance(new_head_value, dict) or not isinstance(previous_value, dict):
            raise SystemExit("authorization pending transaction is malformed")
        previous = AnchorHead(**previous_value)
        new = AnchorHead(**new_head_value)
        self._audit_records(local)
        if local == previous and remote == previous:
            self.pending_path.unlink()
            fsync_dir(self.root)
            return "ROLLED_BACK_UNANCHORED_PENDING_TRANSACTION"
        if local == previous and remote == new:
            self.records.mkdir(parents=True, exist_ok=True, mode=0o700)
            record_path = self._record_path(new.ledger_sequence)
            if record_path.exists():
                if read_json(record_path) != record:
                    raise SystemExit("authorization recovery record collision")
            else:
                atomic_write(record_path, (json.dumps(record, indent=2, sort_keys=True) + "\n").encode())
            self._write_head(new)
            self.pending_path.unlink()
            fsync_dir(self.root)
            return "COMPLETED_ANCHORED_PENDING_TRANSACTION"
        if local == new and remote == new:
            self.pending_path.unlink()
            fsync_dir(self.root)
            return "CLEANED_COMPLETED_PENDING_MARKER"
        raise SystemExit("authorization pending transaction cannot be reconciled with local and remote heads")

    def _commit_record(self, unsigned: dict[str, Any], authorization_sequence: int) -> dict[str, Any]:
        previous = self._reconcile_heads()
        ledger_sequence = previous.ledger_sequence + 1
        unsigned = dict(unsigned)
        unsigned.update(
            {
                "format_version": "2.0",
                "journal_id": self.journal_id,
                "ledger_sequence": ledger_sequence,
                "previous_head_sha256": previous.head_sha256,
                "recorded_at": datetime.now(timezone.utc).isoformat(),
            }
        )
        record = self._sign_record(unsigned)
        record_hash = self._record_hash(record)
        new = AnchorHead(
            journal_id=self.journal_id,
            ledger_sequence=ledger_sequence,
            authorization_sequence=authorization_sequence,
            head_sha256=record_hash,
        )
        pending = {
            "format_version": "1.0",
            "previous_head": previous.as_dict(),
            "new_head": new.as_dict(),
            "record": record,
        }
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        atomic_write(self.pending_path, (json.dumps(pending, indent=2, sort_keys=True) + "\n").encode(), 0o600)
        anchor_receipt = self.anchor.compare_and_publish(previous, new)
        # The anchored head commits exactly the immutable signed record. Transport
        # receipts are retained separately so they cannot alter the committed hash.
        self.records.mkdir(parents=True, exist_ok=True, mode=0o700)
        atomic_write(
            self._record_path(ledger_sequence),
            (json.dumps(record, indent=2, sort_keys=True) + "\n").encode(),
        )
        self.anchor_receipts.mkdir(parents=True, exist_ok=True, mode=0o700)
        atomic_write(
            self.anchor_receipts / f"{ledger_sequence:020d}.json",
            (json.dumps(anchor_receipt, indent=2, sort_keys=True) + "\n").encode(),
        )
        self._write_head(new)
        self.pending_path.unlink()
        fsync_dir(self.root)
        return record

    def reserve(self, authorization: dict[str, Any], authorization_sha256: str) -> dict[str, Any]:
        self.recover()
        head = self._reconcile_heads()
        requested_sequence = int(authorization["sequence"])
        if requested_sequence != head.authorization_sequence + 1:
            raise SystemExit("qualification authorization sequence is not the exact next monotonic value")
        for row in self._iter_records():
            if row.get("authorization_id") == authorization["authorization_id"]:
                raise SystemExit("qualification authorization ID replay detected")
            if row.get("nonce") == authorization["nonce"]:
                raise SystemExit("qualification authorization nonce replay detected")
            if row.get("authorization_sequence") == requested_sequence and row.get("record_kind") == "RESERVATION":
                raise SystemExit("qualification authorization sequence replay detected")
        return self._commit_record(
            {
                "record_kind": "RESERVATION",
                "authorization_id": authorization["authorization_id"],
                "authorization_sha256": authorization_sha256,
                "nonce": authorization["nonce"],
                "authorization_sequence": requested_sequence,
                "status": "RESERVED",
                "installation_id": None,
                "failure_sha256": None,
            },
            requested_sequence,
        )

    def complete(
        self,
        reservation: dict[str, Any],
        status: str,
        installation_id: str | None = None,
        failure: str | None = None,
    ) -> dict[str, Any]:
        if status not in {"CONSUMED", "FAILED_CONSUMED"}:
            raise SystemExit("invalid authorization completion status")
        self.recover()
        head = self._reconcile_heads()
        sequence = int(reservation["authorization_sequence"])
        if head.authorization_sequence != sequence:
            raise SystemExit("authorization completion does not match current anchored authorization sequence")
        completed = [
            r
            for r in self._iter_records()
            if r.get("record_kind") == "COMPLETION"
            and r.get("authorization_id") == reservation["authorization_id"]
        ]
        if completed:
            raise SystemExit("authorization already completed")
        return self._commit_record(
            {
                "record_kind": "COMPLETION",
                "authorization_id": reservation["authorization_id"],
                "authorization_sha256": reservation["authorization_sha256"],
                "nonce": reservation["nonce"],
                "authorization_sequence": sequence,
                "status": status,
                "installation_id": installation_id,
                "failure_sha256": sha_bytes(str(failure).encode()) if failure else None,
                "reservation_head_sha256": sha_bytes(canonical(reservation)),
            },
            sequence,
        )
