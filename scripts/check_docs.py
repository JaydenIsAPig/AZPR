#!/usr/bin/env python3
"""Validate AZ Permit Radar documentation governance without third-party packages."""

from __future__ import annotations

import json
import re
import sys
from datetime import date
from pathlib import Path
from typing import Any
from urllib.parse import unquote


ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
CURRENT = DOCS / "current"
LEGACY = DOCS / "legacy"
LOGS = DOCS / "logs"
SCHEMA_PATH = DOCS / "schema" / "business-data.schema.json"

FAMILIES = {
    "project-structure": ".md",
    "backend-structure": ".md",
    "business-logic": ".md",
    "business-data": ".json",
    "frontend-design": ".md",
}
VERSION_PATTERN = re.compile(r"^[1-9][0-9]*\.[0-9]+$")
LINK_PATTERN = re.compile(r"(?<!!)\[[^\]]+\]\(([^)]+)\)")


def fail(errors: list[str], message: str) -> None:
    errors.append(message)


def read_json(path: Path, errors: list[str]) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        fail(errors, f"{path.relative_to(ROOT)}: invalid JSON: {exc}")
        return None


def markdown_metadata(path: Path, errors: list[str]) -> dict[str, str]:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        fail(errors, f"{path.relative_to(ROOT)}: cannot read: {exc}")
        return {}
    if not lines or lines[0] != "---":
        fail(errors, f"{path.relative_to(ROOT)}: missing YAML-style metadata block")
        return {}
    metadata: dict[str, str] = {}
    for line in lines[1:]:
        if line == "---":
            return metadata
        if ":" not in line:
            fail(errors, f"{path.relative_to(ROOT)}: malformed metadata line: {line!r}")
            continue
        key, value = line.split(":", 1)
        metadata[key.strip()] = value.strip()
    fail(errors, f"{path.relative_to(ROOT)}: unclosed metadata block")
    return metadata


def current_metadata(path: Path, errors: list[str]) -> dict[str, Any]:
    data = read_json(path, errors) if path.suffix == ".json" else markdown_metadata(path, errors)
    return data if isinstance(data, dict) else {}


def validate_schema(instance: Any, schema: dict[str, Any], location: str, errors: list[str]) -> None:
    """Validate the JSON Schema keywords used by this repository's schema."""
    expected_type = schema.get("type")
    type_matches = {
        "object": isinstance(instance, dict),
        "array": isinstance(instance, list),
        "string": isinstance(instance, str),
        "integer": isinstance(instance, int) and not isinstance(instance, bool),
        "number": isinstance(instance, (int, float)) and not isinstance(instance, bool),
        "boolean": isinstance(instance, bool),
        "null": instance is None,
    }
    if expected_type and not type_matches.get(expected_type, False):
        fail(errors, f"{location}: expected {expected_type}, got {type(instance).__name__}")
        return

    if "const" in schema and instance != schema["const"]:
        fail(errors, f"{location}: expected constant {schema['const']!r}")
    if "enum" in schema and instance not in schema["enum"]:
        fail(errors, f"{location}: value {instance!r} is not in {schema['enum']!r}")

    if isinstance(instance, str):
        if len(instance) < schema.get("minLength", 0):
            fail(errors, f"{location}: string is shorter than minLength")
        pattern = schema.get("pattern")
        if pattern and not re.fullmatch(pattern, instance):
            fail(errors, f"{location}: value {instance!r} does not match {pattern!r}")
        if schema.get("format") == "date":
            try:
                date.fromisoformat(instance)
            except ValueError:
                fail(errors, f"{location}: value {instance!r} is not an ISO date")

    if isinstance(instance, list):
        if len(instance) < schema.get("minItems", 0):
            fail(errors, f"{location}: array has fewer than minItems")
        if schema.get("uniqueItems"):
            encoded = [json.dumps(item, sort_keys=True) for item in instance]
            if len(encoded) != len(set(encoded)):
                fail(errors, f"{location}: array items are not unique")
        item_schema = schema.get("items")
        if isinstance(item_schema, dict):
            for index, item in enumerate(instance):
                validate_schema(item, item_schema, f"{location}[{index}]", errors)

    if isinstance(instance, dict):
        required = schema.get("required", [])
        for key in required:
            if key not in instance:
                fail(errors, f"{location}: missing required property {key!r}")
        properties = schema.get("properties", {})
        if schema.get("additionalProperties") is False:
            for key in instance:
                if key not in properties:
                    fail(errors, f"{location}: unexpected property {key!r}")
        for key, subschema in properties.items():
            if key in instance:
                validate_schema(instance[key], subschema, f"{location}.{key}", errors)


def validate_current_documents(errors: list[str]) -> dict[str, Path]:
    resolved: dict[str, Path] = {}
    marked_current: dict[str, list[Path]] = {family: [] for family in FAMILIES}
    for path in sorted(CURRENT.iterdir()):
        if not path.is_file() or path.suffix not in {".md", ".json"}:
            continue
        metadata = current_metadata(path, errors)
        document_id = metadata.get("document_id")
        if document_id not in FAMILIES:
            fail(errors, f"{path.relative_to(ROOT)}: unknown or missing document_id")
            continue
        if metadata.get("document_status") == "current":
            marked_current[document_id].append(path)

    for family, extension in FAMILIES.items():
        if len(marked_current[family]) != 1:
            locations = ", ".join(str(path.relative_to(ROOT)) for path in marked_current[family]) or "none"
            fail(errors, f"{family}: expected exactly one file marked current; found {locations}")
        candidates = sorted(CURRENT.glob(f"{family}-v*{extension}"))
        if len(candidates) != 1:
            fail(errors, f"docs/current: expected exactly one {family} file, found {len(candidates)}")
            continue
        path = candidates[0]
        metadata = current_metadata(path, errors)
        version = str(metadata.get("version", ""))
        expected_name = f"{family}-v{version}{extension}"
        if metadata.get("document_id") != family:
            fail(errors, f"{path.relative_to(ROOT)}: document_id must be {family!r}")
        if not VERSION_PATTERN.fullmatch(version):
            fail(errors, f"{path.relative_to(ROOT)}: invalid major.minor version {version!r}")
        if path.name != expected_name:
            fail(errors, f"{path.relative_to(ROOT)}: filename must be {expected_name!r}")
        if metadata.get("document_status") != "current":
            fail(errors, f"{path.relative_to(ROOT)}: document_status must be 'current'")
        if metadata.get("implementation_status") not in {
            "implemented", "partially implemented", "planned", "proposed"
        }:
            fail(errors, f"{path.relative_to(ROOT)}: invalid implementation_status")
        log_path = LOGS / f"{family}-log-v{version}.md"
        if not log_path.is_file():
            fail(errors, f"{path.relative_to(ROOT)}: missing corresponding log {log_path.relative_to(ROOT)}")
        resolved[family] = path

    for path in sorted(LEGACY.rglob("*")):
        if not path.is_file() or path.suffix not in {".md", ".json"} or path.name == "README.md":
            continue
        if any(path.name.startswith(f"{family}-v") for family in FAMILIES):
            metadata = current_metadata(path, errors)
            if metadata.get("document_status") == "current":
                fail(errors, f"{path.relative_to(ROOT)}: legacy document is incorrectly marked current")
    return resolved


def validate_business_data(path: Path, errors: list[str]) -> None:
    instance = read_json(path, errors)
    schema = read_json(SCHEMA_PATH, errors)
    if isinstance(instance, dict) and isinstance(schema, dict):
        validate_schema(instance, schema, "business-data", errors)
        for related in instance.get("related_documents", []):
            target = CURRENT / related
            if not target.is_file():
                fail(errors, f"{path.relative_to(ROOT)}: missing related document {related!r}")


def validate_markdown_links(errors: list[str]) -> None:
    for path in sorted(ROOT.rglob("*.md")):
        if ".git" in path.parts:
            continue
        text = path.read_text(encoding="utf-8")
        for raw_target in LINK_PATTERN.findall(text):
            target = raw_target.strip().split(maxsplit=1)[0].strip("<>")
            if not target or target.startswith(("#", "http://", "https://", "mailto:")):
                continue
            target = unquote(target.split("#", 1)[0])
            resolved = (path.parent / target).resolve()
            try:
                resolved.relative_to(ROOT)
            except ValueError:
                fail(errors, f"{path.relative_to(ROOT)}: link escapes repository: {raw_target!r}")
                continue
            if not resolved.exists():
                fail(errors, f"{path.relative_to(ROOT)}: broken local link {raw_target!r}")


def main() -> int:
    errors: list[str] = []
    required_dirs = [CURRENT, LOGS, LEGACY, DOCS / "adr", DOCS / "audits", DOCS / "runbooks"]
    for path in required_dirs:
        if not path.is_dir():
            fail(errors, f"{path.relative_to(ROOT)}: required directory is missing")

    current = validate_current_documents(errors)
    business_data = current.get("business-data")
    if business_data:
        validate_business_data(business_data, errors)
    validate_markdown_links(errors)

    if errors:
        print("Documentation validation failed:", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1
    print("Documentation validation passed: 5 current families, unique current status, schema, logs, and local links.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
