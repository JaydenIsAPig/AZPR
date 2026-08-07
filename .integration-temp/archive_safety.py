#!/usr/bin/env python3
"""Read-only ZIP safety validator for the AZPR v10.1 delivery chain."""

from __future__ import annotations

import argparse
import io
import json
import stat
import zipfile
from pathlib import PurePosixPath


def inspect_zip(label: str, payload: bytes) -> dict[str, object]:
    findings: list[dict[str, str]] = []
    members: list[dict[str, object]] = []
    with zipfile.ZipFile(io.BytesIO(payload)) as archive:
        names = [entry.filename for entry in archive.infolist()]
        seen: set[str] = set()
        for entry in archive.infolist():
            name = entry.filename
            path = PurePosixPath(name)
            mode = entry.external_attr >> 16
            file_type = stat.S_IFMT(mode)
            member_type = "directory" if entry.is_dir() else "regular"

            if name in seen:
                findings.append({"member": name, "reason": "duplicate_member"})
            seen.add(name)
            if not name or "\x00" in name:
                findings.append({"member": name, "reason": "empty_or_nul_path"})
            if name.startswith(("/", "\\")) or path.is_absolute():
                findings.append({"member": name, "reason": "absolute_path"})
            if "\\" in name:
                findings.append({"member": name, "reason": "backslash_path"})
            if any(part in {"", ".", ".."} for part in path.parts):
                findings.append({"member": name, "reason": "unsafe_path_component"})
            if path.parts and ":" in path.parts[0]:
                findings.append({"member": name, "reason": "drive_or_scheme_path"})
            if entry.flag_bits & 0x1:
                findings.append({"member": name, "reason": "encrypted_member"})

            if file_type == stat.S_IFLNK:
                member_type = "symlink"
                findings.append({"member": name, "reason": "symbolic_link"})
            elif file_type not in {0, stat.S_IFREG, stat.S_IFDIR}:
                member_type = f"special:{oct(file_type)}"
                findings.append({"member": name, "reason": "special_file"})
            elif entry.is_dir() and file_type == stat.S_IFREG:
                findings.append({"member": name, "reason": "directory_metadata_mismatch"})
            elif not entry.is_dir() and file_type == stat.S_IFDIR:
                findings.append({"member": name, "reason": "file_metadata_mismatch"})

            members.append(
                {
                    "name": name,
                    "type": member_type,
                    "size": entry.file_size,
                    "compressed_size": entry.compress_size,
                    "crc32": f"{entry.CRC:08x}",
                    "mode": oct(mode),
                }
            )

        archive.testzip()
        nested = []
        for name in names:
            if name.lower().endswith(".zip"):
                nested.append(inspect_zip(f"{label}!/{name}", archive.read(name)))

    return {
        "archive": label,
        "member_count": len(members),
        "safe": not findings,
        "findings": findings,
        "members": members,
        "nested_archives": nested,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("zip_path")
    args = parser.parse_args()
    with open(args.zip_path, "rb") as source:
        result = inspect_zip(args.zip_path, source.read())
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["safe"] and all(x["safe"] for x in result["nested_archives"]) else 1


if __name__ == "__main__":
    raise SystemExit(main())
