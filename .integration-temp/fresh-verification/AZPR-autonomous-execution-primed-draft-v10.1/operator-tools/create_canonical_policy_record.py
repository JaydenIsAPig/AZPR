#!/usr/bin/env python3
"""Create an unsigned canonical-policy record after exact-byte verification."""
from __future__ import annotations
import argparse, hashlib, json, os, stat, sys
from datetime import datetime, timezone, timedelta
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "trusted-controller"))
import secure_runtime as sr


def read_once(path: Path, limit: int = 32 * 1024 * 1024) -> bytes:
    path = path.expanduser().absolute()
    fd = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    try:
        before = os.fstat(fd)
        if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1 or before.st_size > limit:
            raise SystemExit(f"unsafe input: {path}")
        data = bytearray()
        while True:
            chunk = os.read(fd, 65536)
            if not chunk:
                break
            data.extend(chunk)
            if len(data) > limit:
                raise SystemExit(f"input too large: {path}")
        after = os.fstat(fd)
        if (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns) != (
            after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns
        ):
            raise SystemExit(f"input changed: {path}")
        return bytes(data)
    finally:
        os.close(fd)


def write_once(path: Path, data: bytes) -> None:
    path = path.absolute()
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0), 0o600)
    try:
        view = memoryview(data)
        while view:
            view = view[os.write(fd, view):]
        os.fsync(fd)
    finally:
        os.close(fd)


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True)
    parser.add_argument("--source-manifest", required=True)
    parser.add_argument("--canonical", required=True)
    parser.add_argument("--section-map", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--valid-days", type=int, default=365)
    parser.add_argument("--review-statement", required=True)
    args = parser.parse_args()
    source = Path(args.source)
    source_bytes = read_once(source)
    manifest_bytes = read_once(Path(args.source_manifest))
    canonical_bytes = read_once(Path(args.canonical))
    map_bytes = read_once(Path(args.section_map))
    try:
        manifest = json.loads(manifest_bytes)
        mapping = json.loads(map_bytes)
    except Exception as exc:
        raise SystemExit("manifest or section map invalid JSON") from exc
    try:
        sr.verify_lossless_canonical_policy(
            source_bytes, source.name, manifest, canonical_bytes, mapping,
            source_manifest_sha256=sha(manifest_bytes),
        )
    except sr.SecurityError as exc:
        raise SystemExit(str(exc)) from exc
    now = datetime.now(timezone.utc)
    value = {
        "format_version": "4.0",
        "record_id": "policy-" + os.urandom(16).hex(),
        "source_document_name": source.name,
        "source_document_sha256": sha(source_bytes),
        "source_manifest_sha256": sha(manifest_bytes),
        "canonical_policy_sha256": sha(canonical_bytes),
        "section_map_sha256": sha(map_bytes),
        "feature_inventory_sha256": mapping["feature_inventory_sha256"],
        "canonical_render_algorithm": sr.DOCX_CANONICAL_RENDER_ALGORITHM,
        "source_unit_count": manifest["unit_count"],
        "mapped_source_unit_count": len(mapping["mappings"]),
        "canonical_byte_length": len(canonical_bytes),
        "completeness_statement": "EXACT_SUPPORTED_OOXML_RENDER_VERIFIED",
        "unsupported_feature_count": len(manifest["feature_inventory"]["unsupported_features"]) + len(manifest["feature_inventory"]["unsupported_normative_parts"]),
        "review_statement": args.review_statement,
        "approved_at": now.isoformat(),
        "expires_at": (now + timedelta(days=args.valid_days)).isoformat(),
        "signatures": [],
    }
    write_once(Path(args.output), (json.dumps(value, indent=2, sort_keys=True) + "\n").encode("utf-8"))
    print(Path(args.output).absolute())


if __name__ == "__main__":
    main()
