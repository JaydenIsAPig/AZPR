#!/usr/bin/env python3
"""Descriptor-relative trusted-file reads for v10 security roots."""
from __future__ import annotations

import json
import os
import stat
from dataclasses import dataclass
from pathlib import Path
from typing import Any

MAX_TRUSTED_FILE = 16 * 1024 * 1024


@dataclass(frozen=True)
class TrustedRead:
    data: bytes
    device: int
    inode: int
    size: int
    mode: int
    uid: int
    gid: int
    mtime_ns: int
    ctime_ns: int


def _require_primitives() -> None:
    required = ("O_NOFOLLOW", "O_DIRECTORY", "O_CLOEXEC")
    missing = [name for name in required if not hasattr(os, name)]
    if missing:
        raise SystemExit(f"trusted no-follow primitives unavailable: {','.join(missing)}")


def _check_dir(st: os.stat_result, path: Path, expected_owner_uid: int) -> None:
    if not stat.S_ISDIR(st.st_mode):
        raise SystemExit(f"trusted ancestor is not a directory: {path}")
    if st.st_uid != expected_owner_uid:
        raise SystemExit(f"trusted ancestor owner mismatch: {path}")
    if st.st_mode & 0o022:
        raise SystemExit(f"trusted ancestor is group/world writable: {path}")


def read_trusted_regular(
    path: Path,
    *,
    trusted_ancestor: Path,
    expected_owner_uid: int,
    max_bytes: int = MAX_TRUSTED_FILE,
    require_no_write_bits: bool = True,
    require_executable: bool = False,
) -> TrustedRead:
    """Read a trusted file without following links from an anchored directory FD.

    `trusted_ancestor` is an independently provisioned path anchor. Production
    bootstrap callers use `/etc`; unit tests use a private 0700/0500 directory.
    Every component from that anchor through the leaf is checked.
    """
    _require_primitives()
    path = Path(path).absolute()
    trusted_ancestor = Path(trusted_ancestor).absolute()
    try:
        relative = path.relative_to(trusted_ancestor)
    except ValueError as exc:
        raise SystemExit(f"trusted file escapes provisioned ancestor: {path}") from exc
    if not relative.parts:
        raise SystemExit("trusted file path must name a leaf")

    # Open the anchored directory through a no-follow component walk. Permission
    # enforcement starts at the provisioned anchor; production chooses /etc.
    root_fd = os.open("/", os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC)
    current_fd = root_fd
    opened: list[int] = []
    try:
        anchor_parts = trusted_ancestor.parts[1:]
        for component in anchor_parts:
            next_fd = os.open(
                component,
                os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC,
                dir_fd=current_fd,
            )
            opened.append(next_fd)
            if current_fd != root_fd:
                os.close(current_fd)
            current_fd = next_fd
        _check_dir(os.fstat(current_fd), trusted_ancestor, expected_owner_uid)

        walked = trusted_ancestor
        for component in relative.parts[:-1]:
            next_fd = os.open(
                component,
                os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC,
                dir_fd=current_fd,
            )
            os.close(current_fd)
            current_fd = next_fd
            walked = walked / component
            _check_dir(os.fstat(current_fd), walked, expected_owner_uid)

        leaf = relative.parts[-1]
        fd = os.open(leaf, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC, dir_fd=current_fd)
        try:
            before = os.fstat(fd)
            if not stat.S_ISREG(before.st_mode):
                raise SystemExit(f"trusted root is not a regular file: {path}")
            if before.st_nlink != 1:
                raise SystemExit(f"trusted root has multiple hard links: {path}")
            if before.st_uid != expected_owner_uid:
                raise SystemExit(f"trusted root owner mismatch: {path}")
            if require_no_write_bits and before.st_mode & 0o222:
                raise SystemExit(f"trusted root is writable: {path}")
            if require_executable and not before.st_mode & 0o111:
                raise SystemExit(f"trusted executable lacks execute permission: {path}")
            if before.st_size > max_bytes:
                raise SystemExit(f"trusted root exceeds size limit: {path}")
            chunks: list[bytes] = []
            total = 0
            while True:
                chunk = os.read(fd, 65536)
                if not chunk:
                    break
                total += len(chunk)
                if total > max_bytes:
                    raise SystemExit(f"trusted root exceeds read limit: {path}")
                chunks.append(chunk)
            after = os.fstat(fd)
            identity_before = (
                before.st_dev, before.st_ino, before.st_size, before.st_mode,
                before.st_uid, before.st_gid, before.st_mtime_ns, before.st_ctime_ns,
            )
            identity_after = (
                after.st_dev, after.st_ino, after.st_size, after.st_mode,
                after.st_uid, after.st_gid, after.st_mtime_ns, after.st_ctime_ns,
            )
            if identity_before != identity_after:
                raise SystemExit(f"trusted root changed during descriptor read: {path}")
            return TrustedRead(
                data=b"".join(chunks), device=before.st_dev, inode=before.st_ino,
                size=before.st_size, mode=before.st_mode, uid=before.st_uid,
                gid=before.st_gid, mtime_ns=before.st_mtime_ns, ctime_ns=before.st_ctime_ns,
            )
        finally:
            os.close(fd)
    except OSError as exc:
        raise SystemExit(f"trusted no-follow resolution failed for {path}: {exc}") from exc
    finally:
        try:
            if current_fd != root_fd:
                os.close(current_fd)
        except OSError:
            pass
        try:
            os.close(root_fd)
        except OSError:
            pass


def load_trusted_json(path: Path, **kwargs: Any) -> tuple[dict[str, Any], TrustedRead]:
    result = read_trusted_regular(path, **kwargs)
    try:
        value = json.loads(result.data)
    except Exception as exc:
        raise SystemExit(f"invalid trusted JSON: {path}") from exc
    if not isinstance(value, dict):
        raise SystemExit(f"trusted JSON must be an object: {path}")
    return value, result
