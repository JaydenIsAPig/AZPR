#!/usr/bin/env python3
"""Generate unapproved exact governing-policy artifacts from a DOCX.

The output canonical text is a deterministic supported-OOXML UTF-8 rendering. Unsupported normative structures cause a fail-closed error. It is
not approved by this tool. Approval records must bind the exact DOCX, manifest,
rendered bytes, and byte-span map with independent signatures.
"""
from __future__ import annotations
import argparse, hashlib, json, os, stat, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "trusted-controller"))
import secure_runtime as sr


def read_once(path: Path, limit: int = 32 * 1024 * 1024) -> bytes:
    path = path.expanduser().absolute()
    fd = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    try:
        before = os.fstat(fd)
        if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1 or before.st_size > limit:
            raise SystemExit(f"unsafe DOCX input: {path}")
        data = bytearray()
        while True:
            chunk = os.read(fd, 65536)
            if not chunk:
                break
            data.extend(chunk)
            if len(data) > limit:
                raise SystemExit("DOCX exceeds size limit")
        after = os.fstat(fd)
        if (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns) != (
            after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns
        ):
            raise SystemExit("DOCX changed while reading")
        return bytes(data)
    finally:
        os.close(fd)


def write_once(path: Path, data: bytes) -> None:
    path = path.expanduser().absolute()
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    for candidate in [path.parent, *path.parent.parents]:
        st = os.lstat(candidate)
        if stat.S_ISLNK(st.st_mode):
            raise SystemExit(f"symlinked output ancestor: {candidate}")
        if candidate == candidate.parent:
            break
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0), 0o600)
    try:
        view = memoryview(data)
        while view:
            view = view[os.write(fd, view):]
        os.fsync(fd)
    finally:
        os.close(fd)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--docx", required=True)
    parser.add_argument("--canonical-output", required=True)
    parser.add_argument("--source-manifest-output", required=True)
    parser.add_argument("--section-map-output", required=True)
    args = parser.parse_args()
    source = Path(args.docx)
    raw = read_once(source)
    try:
        manifest, canonical_bytes, section_map = sr.derive_docx_lossless_policy(raw, source.name)
    except sr.SecurityError as exc:
        raise SystemExit(str(exc)) from exc
    manifest_bytes = (json.dumps(manifest, indent=2, sort_keys=True) + "\n").encode("utf-8")
    section_map["source_manifest_sha256"] = hashlib.sha256(manifest_bytes).hexdigest()
    map_bytes = (json.dumps(section_map, indent=2, sort_keys=True) + "\n").encode("utf-8")
    write_once(Path(args.canonical_output), canonical_bytes)
    write_once(Path(args.source_manifest_output), manifest_bytes)
    write_once(Path(args.section_map_output), map_bytes)
    print(json.dumps({
        "source_sha256": manifest["source_document_sha256"],
        "canonical_sha256": manifest["canonical_policy_sha256"],
        "source_manifest_sha256": section_map["source_manifest_sha256"],
        "section_map_sha256": hashlib.sha256(map_bytes).hexdigest(),
        "source_units": manifest["unit_count"],
        "canonical_bytes": manifest["canonical_byte_length"],
        "render_algorithm": manifest["canonical_render_algorithm"],
        "feature_inventory": manifest["feature_inventory"],
        "warning": "Outputs preserve only explicitly supported OOXML and are unapproved; visual review plus independent policy-owner and security-approver signatures are still required.",
    }, indent=2))


if __name__ == "__main__":
    main()
