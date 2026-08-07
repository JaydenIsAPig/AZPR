#!/usr/bin/env python3
"""Offline, reviewer-owned, non-privileged release verifier for AZPR v10.1."""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
import os
import re
import shutil
import signal
import stat
import subprocess
import sys
import tempfile
import time
from pathlib import Path, PurePosixPath
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parent
MAX_OUTPUT = 8 * 1024 * 1024
PROMPT_SHA256 = "3b235cb7e33ca409241ff26523f60f8fee89cec524b3f09e91a69927a0aa4880"
CATALOG_KIND = "AZPR_V10_1_RELEASE_BLOCKING_TEST_CATALOG"


def fail(message: str) -> None:
    raise SystemExit(f"VERIFY V10.1 FAILED: {message}")


def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load(path: Path) -> dict:
    try:
        value = json.loads(Path(path).read_bytes())
    except Exception as exc:
        fail(f"invalid JSON {path}: {exc}")
    if not isinstance(value, dict):
        fail(f"JSON must be an object: {path}")
    return value


def inventory() -> dict[str, str]:
    return {p.relative_to(ROOT).as_posix(): sha(p) for p in sorted(ROOT.rglob("*")) if p.is_file()}


def reject_cache_or_unsafe_files() -> None:
    forbidden_names = {"__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache", "__MACOSX"}
    forbidden_suffixes = {".pyc", ".pyo", ".swp", ".tmp", ".bak"}
    for path in ROOT.rglob("*"):
        if any(part in forbidden_names for part in path.parts) or path.suffix in forbidden_suffixes or path.name.startswith("._"):
            fail(f"cache/platform/temporary artifact present: {path.relative_to(ROOT)}")
        if path.is_symlink():
            fail(f"symlink present in candidate: {path.relative_to(ROOT)}")
        if path.is_socket() or path.is_fifo() or path.is_block_device() or path.is_char_device():
            fail(f"special file present in candidate: {path.relative_to(ROOT)}")


def verify_safety() -> None:
    status = load(ROOT / "REMEDIATION-STATUS.json")
    decision = status.get("decision", {})
    expected = {
        "pre_autonomous_staging": "FAIL",
        "semi_autonomous_codex_staging_ready": False,
        "trusted_pre_autonomous_installation_ready": False,
        "safe_for_unattended_execution_now": False,
        "full_autonomous_pathway_viable": True,
    }
    for key, value in expected.items():
        if decision.get(key) != value:
            fail(f"readiness disposition changed: {key}")
    if decision.get("organization_release_signature_status") != "NOT_PROVIDED_UNSIGNED_DEVELOPMENT_CANDIDATE":
        fail("unsigned development status missing")
    if status.get("status") != "READY_FOR_INDEPENDENT_V10_1_SOURCE_REASSESSMENT":
        fail("v10.1 source-reassessment-only status missing")
    forbidden = [
        ROOT / "repository-overlay/automation/roadmap.json",
        ROOT / "repository-overlay/automation/roadmap.proposed.json",
        ROOT / "repository-overlay/automation/policy/AZPR-master-operating-prompt.md",
        ROOT / "repository-overlay/automation/policy/canonical-policy-section-map.json",
    ]
    for path in forbidden:
        if path.exists():
            fail(f"forbidden active policy/roadmap authority: {path.relative_to(ROOT)}")
    reject_cache_or_unsafe_files()


def verify_python() -> int:
    paths = sorted(ROOT.rglob("*.py"))
    for path in paths:
        try:
            source = path.read_text()
            compile(source, str(path), "exec")
            ast.parse(source, filename=str(path))
        except Exception as exc:
            fail(f"Python syntax error {path.relative_to(ROOT)}: {exc}")
    return len(paths)


def _walk_schema_bounds(value, path: str, issues: list[str]) -> None:
    if isinstance(value, dict):
        typ = value.get("type")
        types = set(typ) if isinstance(typ, list) else {typ} if isinstance(typ, str) else set()
        if "string" in types and not any(k in value for k in ("maxLength", "const", "enum", "pattern")):
            issues.append(path + " unbounded string")
        if "array" in types and "maxItems" not in value:
            issues.append(path + " unbounded array")
        if "object" in types and value.get("additionalProperties") is not False and "maxProperties" not in value:
            issues.append(path + " unbounded object")
        for key, item in value.items():
            _walk_schema_bounds(item, path + "/" + str(key), issues)
    elif isinstance(value, list):
        for index, item in enumerate(value):
            _walk_schema_bounds(item, path + "/" + str(index), issues)


def verify_schemas() -> int:
    try:
        import jsonschema
    except ImportError:
        fail("jsonschema unavailable")
    schemas = {}
    issues: list[str] = []
    for path in sorted((ROOT / "repository-overlay/automation/schemas").glob("*.json")):
        schema = load(path)
        try:
            jsonschema.Draft202012Validator.check_schema(schema)
        except Exception as exc:
            fail(f"invalid schema {path.name}: {exc}")
        _walk_schema_bounds(schema, path.name, issues)
        schemas[path.name] = schema
    if issues:
        fail("unbounded/loose schemas: " + "; ".join(issues[:20]))
    required = {
        "host-qualification-roots-v10.schema.json",
        "host-root-anchor-identity-v10.schema.json",
        "external-receipt-signer-identity-v10.schema.json",
        "qualification-trust-manifest-v10.schema.json",
        "approved-probe-keyring-v10.schema.json",
        "probe-attestor-keyring-v10.schema.json",
        "probe-policy-v10.schema.json",
        "probe-service-identity-v10.schema.json",
        "probe-service-attestation-v10.schema.json",
        "probe-revocation-state-v10.schema.json",
        "probe-attestor-revocation-state-v10.schema.json",
        "qualification-probe-result-envelope-v10.schema.json",
        "qualification-probe-envelopes-manifest-v10.schema.json",
        "qualified-artifact-inputs-v10.schema.json",
        "cleanroom-qualification-input.schema.json",
        "cleanroom-qualification-receipt-v10.schema.json",
        "external-receipt-signing-request-v10.schema.json",
        "external-receipt-signing-response-v10.schema.json",
        "host-bootstrap-roots-v10.schema.json",
        "qualification-installation-authorization-v10.schema.json",
        "qualification-phase-transition-authorization-v10.schema.json",
    }
    if not required.issubset(schemas):
        fail(f"missing v10.1 schemas: {sorted(required-set(schemas))}")
    for name in required:
        if schemas[name].get("additionalProperties") is not False:
            fail(f"non-strict v10.1 schema: {name}")
    bindings = schemas["cleanroom-qualification-receipt-v10.schema.json"]["properties"]["artifact_bindings"]
    if len(bindings.get("required", [])) != 57 or set(bindings["required"]) != set(bindings["properties"]):
        fail("receipt does not require exact versioned 57-artifact set")
    inputs = schemas["cleanroom-qualification-input.schema.json"]
    forbidden = {
        "trusted_ancestor", "expected_trust_owner_uid", "minimum_trust_sequence",
        "external_signer_client", "external_signer_identity_sha256",
        "qualification_receipt_signing_public_key", "receipt_signing_key_id",
    }
    if forbidden.intersection(inputs.get("properties", {})):
        fail("qualification input schema permits caller trust-root selection")
    return len(schemas)


def verify_prompts() -> tuple[int, int, str]:
    numbered = sorted((ROOT / "repository-overlay/automation/numbered").glob("*.md"))
    appendices = sorted((ROOT / "repository-overlay/automation/appendices").glob("*.md"))
    if len(numbered) != 38 or len(appendices) != 3:
        fail("prompt count differs from 38 numbered plus 3 appendices")
    archive = ROOT / "markdown-prompts-autonomous-priming-draft.zip"
    if sha(archive) != PROMPT_SHA256:
        fail("embedded prompt archive bytes changed")
    expected = {p.relative_to(ROOT / "repository-overlay").as_posix(): p.read_bytes() for p in numbered + appendices}
    with ZipFile(archive) as zf:
        if len(zf.namelist()) != len(set(zf.namelist())) or set(zf.namelist()) != set(expected):
            fail("prompt archive inventory mismatch")
        for info in zf.infolist():
            path = PurePosixPath(info.filename)
            mode = (info.external_attr >> 16) & 0o170000
            if path.is_absolute() or ".." in path.parts or "\\" in info.filename or (mode and mode != stat.S_IFREG):
                fail(f"unsafe prompt archive member: {info.filename}")
            if zf.read(info.filename) != expected[info.filename]:
                fail(f"prompt byte mismatch: {info.filename}")
    return len(numbered), len(appendices), sha(archive)


def verify_current_documents() -> int:
    index = load(ROOT / "CURRENT-DOCUMENT-INDEX.json")
    rows = index.get("documents")
    if index.get("format_version") != "1.1" or index.get("candidate_version") != "v10.1":
        fail("current-document index version mismatch")
    if not isinstance(rows, list) or not rows:
        fail("current-document index is missing")
    categories = set()
    for row in rows:
        if not isinstance(row, dict) or set(row) != {"category", "path", "sha256", "version", "status"}:
            fail("current-document index row shape mismatch")
        if row["category"] in categories:
            fail(f"multiple current documents for category {row['category']}")
        categories.add(row["category"])
        path = ROOT / row["path"]
        if not path.is_file() or sha(path) != row["sha256"]:
            fail(f"current-document hash/path mismatch: {row['category']}")
        if row["version"] != "v10.1" or row["status"] != "CURRENT":
            fail(f"stale current-document label: {row['category']}")
    return len(rows)


def secure_temp_root() -> Path:
    base = Path(os.environ.get("TMPDIR") or tempfile.gettempdir()).absolute()
    temp = Path(tempfile.mkdtemp(prefix="azpr-v10-1-reviewer-", dir=base))
    os.chmod(temp, 0o700)
    st = temp.stat()
    if st.st_uid != os.geteuid() or stat.S_IMODE(st.st_mode) != 0o700:
        fail("reviewer-owned temporary root invariant failed")
    return temp


def run_group(command: list[str], *, env: dict[str, str], timeout: int, label: str) -> tuple[int, str, str, float]:
    started = time.monotonic()
    with tempfile.TemporaryFile() as stdout, tempfile.TemporaryFile() as stderr:
        proc = subprocess.Popen(command, cwd=ROOT, env=env, stdout=stdout, stderr=stderr, start_new_session=True)
        timed_out = False
        try:
            proc.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            timed_out = True
            try:
                os.killpg(proc.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            proc.wait(timeout=10)
        # A descendant that remains in the original process group is a release failure.
        group_leaked = False
        if not timed_out:
            time.sleep(0.02)
            try:
                os.killpg(proc.pid, 0)
            except ProcessLookupError:
                pass
            else:
                group_leaked = True
                try:
                    os.killpg(proc.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
        stdout.seek(0)
        stderr.seek(0)
        out = stdout.read(MAX_OUTPUT + 1)
        err = stderr.read(MAX_OUTPUT + 1)
    if len(out) > MAX_OUTPUT or len(err) > MAX_OUTPUT:
        fail(f"{label} output limit exceeded")
    if timed_out:
        fail(f"{label} timed out")
    if group_leaked:
        fail(f"{label} leaked a descendant in its process group")
    return proc.returncode, out.decode("utf-8", "replace"), err.decode("utf-8", "replace"), time.monotonic() - started


def pytest_environment(temp_root: Path) -> dict[str, str]:
    base_env = {
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
        "HOME": str(temp_root / "home"),
        "TMPDIR": str(temp_root / "tmp"),
        "XDG_CONFIG_HOME": str(temp_root / "xdg"),
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTHONHASHSEED": "0",
        "PYTHONNOUSERSITE": "1",
        "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1",
        "GIT_CONFIG_NOSYSTEM": "1",
        "LANG": "C.UTF-8",
        "LC_ALL": "C.UTF-8",
    }
    for name in ("home", "tmp", "xdg"):
        path = temp_root / name
        path.mkdir(mode=0o700, exist_ok=True)
    return base_env


def collect_nodes(*, env: dict[str, str]) -> list[str]:
    rc, out, err, _ = run_group(
        [sys.executable, "-m", "pytest", "--collect-only", "-q", "-p", "no:cacheprovider"],
        env=env,
        timeout=90,
        label="complete pytest collection",
    )
    if rc != 0:
        print(out)
        print(err, file=sys.stderr)
        fail("complete pytest collection failed")
    nodes = [line.strip() for line in out.splitlines() if "::" in line and not line.startswith(" ")]
    if not nodes or len(nodes) != len(set(nodes)):
        fail("pytest collection is empty or contains duplicate node IDs")
    return nodes


def run_catalog(temp_root: Path) -> tuple[list[dict], int]:
    catalog = load(ROOT / "V10-RELEASE-TEST-CATALOG.json")
    rows = catalog.get("tests")
    if catalog.get("catalog_kind") != CATALOG_KIND or catalog.get("format_version") != "2.1" or not isinstance(rows, list):
        fail("release-test catalog invalid")
    if catalog.get("test_count") != len(rows):
        fail("release-test catalog count invalid")
    base_env = pytest_environment(temp_root)
    collected = collect_nodes(env=base_env)
    catalog_nodes = [row.get("node") for row in rows if isinstance(row, dict)]
    if catalog.get("collected_test_count") != len(collected) or set(catalog_nodes) != set(collected) or len(catalog_nodes) != len(collected):
        missing = sorted(set(collected) - set(catalog_nodes))
        extra = sorted(set(catalog_nodes) - set(collected))
        fail(f"release catalog does not cover complete collected suite; missing={missing[:10]} extra={extra[:10]}")
    results = []
    seen_ids = set()
    for row in rows:
        if not isinstance(row, dict) or set(row) != {"id", "node", "category", "security_critical"}:
            fail("release-test catalog row shape invalid")
        if row["id"] in seen_ids:
            fail("release-test catalog duplicate ID")
        if row["security_critical"] is not True:
            fail(f"unselected/non-blocking test in complete release catalog: {row['id']}")
        seen_ids.add(row["id"])
        rc, out, err, duration = run_group(
            [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", row["node"]],
            env=base_env,
            timeout=60,
            label=row["id"],
        )
        if rc != 0 or not re.search(r"\b1 passed\b", out + err):
            print(out)
            print(err, file=sys.stderr)
            fail(f"release-blocking test failed: {row['id']} exit={rc}")
        results.append({
            "test_id": row["id"], "node": row["node"], "category": row["category"],
            "status": "PASS", "duration_seconds": round(duration, 4),
        })
    return results, len(collected)


def verify_manifest() -> int:
    manifest = load(ROOT / "SHA256SUMS.json")
    if (
        manifest.get("format_version") != "1.1"
        or manifest.get("algorithm") != "SHA-256"
        or manifest.get("bundle_name") != "AZPR-autonomous-execution-primed-draft-v10.1"
        or manifest.get("bundle_type") != "implementation"
        or manifest.get("excludes") != ["SHA256SUMS.json"]
    ):
        fail("internal manifest metadata invalid")
    entries = {p.relative_to(ROOT).as_posix() for p in ROOT.rglob("*") if p.is_file() and p.name != "SHA256SUMS.json"}
    declared = manifest.get("entries")
    if not isinstance(declared, dict) or set(declared) != entries:
        fail(f"internal manifest inventory mismatch missing={sorted(entries-set(declared or {}))[:10]} extra={sorted(set(declared or {})-entries)[:10]}")
    if manifest.get("expected_inventory_count") != len(declared):
        fail("internal manifest count mismatch")
    for relative, digest in declared.items():
        if not re.fullmatch(r"[0-9a-f]{64}", str(digest)) or sha(ROOT / relative) != digest:
            fail(f"internal manifest hash mismatch: {relative}")
    return len(declared)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--fresh-extraction", action="store_true")
    args = parser.parse_args()
    if os.geteuid() == 0:
        fail("release verifier must run as a dedicated unprivileged reviewer")
    before = inventory()
    temp_root = secure_temp_root()
    try:
        verify_safety()
        python_files = verify_python()
        schemas = verify_schemas()
        numbered, appendices, prompt_hash = verify_prompts()
        current_documents = verify_current_documents()
        tests, collected_count = run_catalog(temp_root)
        manifest_entries = verify_manifest()
        reject_cache_or_unsafe_files()
        after = inventory()
        if before != after:
            changed = [name for name in sorted(set(before) | set(after)) if before.get(name) != after.get(name)]
            fail(f"source tree changed during verification: {changed[:20]}")
        output = {
            "status": "PASS_READY_FOR_INDEPENDENT_V10_1_SOURCE_REASSESSMENT",
            "candidate_version": "v10.1",
            "fresh_extraction_invocation": args.fresh_extraction,
            "pre_autonomous_staging": "FAIL",
            "semi_autonomous_codex_staging_ready": False,
            "trusted_pre_autonomous_installation_ready": False,
            "safe_for_unattended_execution_now": False,
            "full_autonomous_pathway_viable": True,
            "organization_release_signature_status": "NOT_PROVIDED_UNSIGNED_DEVELOPMENT_CANDIDATE",
            "manifest_entries_verified": manifest_entries,
            "python_files_compiled": python_files,
            "schemas_verified": schemas,
            "numbered_prompts_verified": numbered,
            "appendices_verified": appendices,
            "prompt_zip_sha256": prompt_hash,
            "current_documents_verified": current_documents,
            "collected_tests_verified": collected_count,
            "release_tests_passed": len(tests),
            "test_execution": tests,
            "environment": {
                "effective_uid": os.geteuid(),
                "reviewer_temp_mode": "0700",
                "root_state_required": False,
                "credential_environment_inherited": False,
                "network_required": False,
                "source_tree_mutation_detected": False,
            },
        }
        print(json.dumps(output, indent=2, sort_keys=True))
    finally:
        shutil.rmtree(temp_root, ignore_errors=True)


if __name__ == "__main__":
    main()
