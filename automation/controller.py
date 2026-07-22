#!/usr/bin/env python3
"""Safe local orchestration for the AZ Permit Radar Codex prompt roadmap.

Design goals:
- one bounded stage per run;
- controller-owned branches, validation, documentation records, and commits;
- read-only formal audits whose reports are written by the controller;
- mandatory merge reconciliation before the next stage;
- Appendix A only for explicitly authorized audit corrections;
- Appendices B and C hard-locked and never part of normal execution.

The script uses only Python's standard library. The optional ``jsonschema``
package is used when present, but equivalent project-specific validation is
always performed even when it is absent.
"""

from __future__ import annotations

import argparse
import fnmatch
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import textwrap
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Sequence


CONTROLLER_VERSION = "1.0.0"
PROMOTE_CONFIRMATION = "PROMOTE ROADMAP"
ABANDON_CONFIRMATION = "ABANDON ACTIVE STAGE"
APPENDIX_B_CONFIRMATION = "ENABLE CONTROLLED SMS CANARY"
APPENDIX_C_CONFIRMATION = "AUDIT CONTROLLED SMS CANARY"

EFFORT_MAP = {
    "Light": "low",
    "Medium": "medium",
    "High": "high",
    "Extra High": "xhigh",
    "Ultra": "xhigh",
}

VALID_STAGE_KINDS = {
    "implementation",
    "documentation",
    "decision_gate",
    "audit",
    "release_gate",
}
VALID_OUTCOMES = {
    "COMPLETED",
    "PASS",
    "PASS_WITH_REQUIRED_CORRECTIONS",
    "BLOCKED",
    "APPROVAL_REQUIRED",
    "FAILED",
}
AUDIT_OUTCOMES = {"PASS", "PASS_WITH_REQUIRED_CORRECTIONS", "BLOCKED"}


class ControllerError(RuntimeError):
    """A safe stop raised by controller policy or local state."""


@dataclass(frozen=True)
class CommandResult:
    argv: list[str]
    returncode: int
    stdout: str
    stderr: str
    duration_seconds: float


# ---------------------------------------------------------------------------
# Generic helpers
# ---------------------------------------------------------------------------


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def slugify(value: str, max_length: int = 60) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return (slug[:max_length].rstrip("-") or "stage")


def load_json(path: Path) -> dict[str, Any]:
    try:
        with path.open("r", encoding="utf-8") as handle:
            value = json.load(handle)
    except FileNotFoundError as exc:
        raise ControllerError(f"Required file does not exist: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ControllerError(f"Invalid JSON in {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ControllerError(f"Expected a JSON object in {path}.")
    return value


def save_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8") as handle:
        json.dump(value, handle, indent=2, sort_keys=False)
        handle.write("\n")
    temporary.replace(path)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def run_process(
    argv: Sequence[str],
    *,
    cwd: Path,
    input_text: str | None = None,
    timeout_seconds: int | None = None,
    check: bool = False,
) -> CommandResult:
    import time

    start = time.monotonic()
    try:
        completed = subprocess.run(
            list(argv),
            cwd=cwd,
            input=input_text,
            text=True,
            capture_output=True,
            timeout=timeout_seconds,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise ControllerError(
            f"Command timed out after {timeout_seconds} seconds: {list(argv)!r}"
        ) from exc
    duration = time.monotonic() - start
    result = CommandResult(
        argv=list(argv),
        returncode=completed.returncode,
        stdout=completed.stdout,
        stderr=completed.stderr,
        duration_seconds=duration,
    )
    if check and result.returncode != 0:
        raise ControllerError(
            "Command failed:\n"
            f"  argv: {result.argv!r}\n"
            f"  exit: {result.returncode}\n"
            f"  stdout:\n{result.stdout[-4000:]}\n"
            f"  stderr:\n{result.stderr[-4000:]}"
        )
    return result


def repo_root_from(start: Path) -> Path:
    result = run_process(
        ["git", "rev-parse", "--show-toplevel"], cwd=start, check=True
    )
    return Path(result.stdout.strip()).resolve()


def git(root: Path, *args: str, check: bool = True) -> str:
    result = run_process(["git", *args], cwd=root, check=check)
    return result.stdout.strip()


def current_branch(root: Path) -> str:
    return git(root, "branch", "--show-current")


def current_commit(root: Path) -> str:
    return git(root, "rev-parse", "HEAD")


def git_is_ancestor(root: Path, ancestor: str, descendant: str = "HEAD") -> bool:
    result = run_process(
        ["git", "merge-base", "--is-ancestor", ancestor, descendant], cwd=root
    )
    return result.returncode == 0


def clean_status(root: Path) -> str:
    return git(root, "status", "--porcelain=v1", "--untracked-files=all")


def require_clean(root: Path, reason: str) -> None:
    status = clean_status(root)
    if status:
        raise ControllerError(
            f"A clean working tree is required {reason}.\n\nCurrent changes:\n{status}"
        )


def changed_paths(root: Path) -> list[str]:
    output = git(root, "status", "--porcelain=v1", "--untracked-files=all")
    paths: list[str] = []
    for line in output.splitlines():
        if len(line) < 4:
            continue
        value = line[3:]
        if " -> " in value:
            value = value.split(" -> ", 1)[1]
        value = value.strip().strip('"')
        if value:
            paths.append(value.replace("\\", "/"))
    return sorted(set(paths))


def path_matches(path: str, patterns: Iterable[str]) -> bool:
    normalized = path.replace("\\", "/")
    return any(fnmatch.fnmatchcase(normalized, pattern) for pattern in patterns)


def parse_front_matter(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        raise ControllerError(f"Prompt lacks YAML-like front matter: {path}")
    end = text.find("\n---\n", 4)
    if end < 0:
        raise ControllerError(f"Prompt front matter is not closed: {path}")
    values: dict[str, Any] = {}
    for raw_line in text[4:end].splitlines():
        if not raw_line.strip() or raw_line.lstrip().startswith("#"):
            continue
        if ":" not in raw_line:
            raise ControllerError(f"Invalid front matter line in {path}: {raw_line}")
        key, raw_value = raw_line.split(":", 1)
        key = key.strip()
        raw_value = raw_value.strip()
        if raw_value in {"true", "false"}:
            value: Any = raw_value == "true"
        else:
            try:
                value = json.loads(raw_value)
            except json.JSONDecodeError:
                value = raw_value
        values[key] = value
    return values


def prompt_body(path: Path) -> str:
    text = path.read_text(encoding="utf-8")
    if text.startswith("---\n"):
        end = text.find("\n---\n", 4)
        if end < 0:
            raise ControllerError(f"Prompt front matter is not closed: {path}")
        text = text[end + 5 :]
    body = text.strip()
    if "BEGIN PROMPT" not in body or "END PROMPT" not in body:
        raise ControllerError(
            f"Prompt must contain BEGIN PROMPT and END PROMPT boundaries: {path}"
        )
    return body


# ---------------------------------------------------------------------------
# Repository paths and state
# ---------------------------------------------------------------------------


def paths(root: Path) -> dict[str, Path]:
    automation = root / "automation"
    runtime = root / ".codex-loop"
    return {
        "automation": automation,
        "config": automation / "controller.config.json",
        "roadmap": automation / "roadmap.json",
        "roadmap_proposed": automation / "roadmap.proposed.json",
        "roadmap_schema": automation / "roadmap.schema.json",
        "result_schema": automation / "result.schema.json",
        "generator_prompt": automation / "roadmap-generator-prompt.md",
        "generator_report": automation / "reports" / "roadmap-generation-report.md",
        "runtime": runtime,
        "state": runtime / "state.json",
        "results": runtime / "results",
        "logs": runtime / "logs",
        "audits_index": root / "docs" / "audits" / "index.json",
        "current_status": root / "docs" / "automation" / "current-status.md",
        "run_history": root / "docs" / "automation" / "run-history",
    }


def default_state() -> dict[str, Any]:
    return {
        "controller_version": CONTROLLER_VERSION,
        "roadmap_version": None,
        "completed_numbered_stages": [],
        "latest_formal_audit": None,
        "pending_correction": None,
        "pending_audit_rerun": None,
        "blocked": None,
        "pending_merge": None,
        "active_uncommitted": None,
        "approval_pending": None,
        "audit_rerun_counts": {},
        "appendix_history": [],
        "last_stop": None,
        "updated_at": utc_now(),
    }


def load_state(root: Path) -> dict[str, Any]:
    state_path = paths(root)["state"]
    if not state_path.exists():
        return default_state()
    state = load_json(state_path)
    merged = default_state()
    merged.update(state)
    return merged


def save_state(root: Path, state: dict[str, Any]) -> None:
    state["controller_version"] = CONTROLLER_VERSION
    state["updated_at"] = utc_now()
    save_json(paths(root)["state"], state)


def load_config(root: Path) -> dict[str, Any]:
    return load_json(paths(root)["config"])


def load_roadmap(root: Path, proposed: bool = False) -> dict[str, Any]:
    key = "roadmap_proposed" if proposed else "roadmap"
    return load_json(paths(root)[key])


# ---------------------------------------------------------------------------
# Roadmap validation
# ---------------------------------------------------------------------------


def optional_jsonschema_validation(instance: dict[str, Any], schema_path: Path) -> list[str]:
    try:
        import jsonschema  # type: ignore
    except ImportError:
        return []
    schema = load_json(schema_path)
    validator = jsonschema.Draft202012Validator(schema)
    return [error.message for error in sorted(validator.iter_errors(instance), key=str)]


def validate_command_spec(command: dict[str, Any], config: dict[str, Any], label: str) -> list[str]:
    errors: list[str] = []
    argv = command.get("argv")
    if not isinstance(argv, list) or not argv or not all(isinstance(v, str) and v for v in argv):
        return [f"{label}: argv must be a non-empty array of strings."]
    executable = Path(argv[0]).name
    allowed = set(config.get("allowed_validation_executables", []))
    if executable not in allowed:
        errors.append(
            f"{label}: validation executable {executable!r} is not in "
            "controller.config.json allowed_validation_executables."
        )
    timeout = command.get("timeout_seconds", 900)
    if not isinstance(timeout, int) or timeout < 1 or timeout > 7200:
        errors.append(f"{label}: timeout_seconds must be between 1 and 7200.")
    return errors


def validate_roadmap(root: Path, roadmap: dict[str, Any]) -> tuple[list[str], list[str]]:
    config = load_config(root)
    errors: list[str] = []
    warnings: list[str] = []

    errors.extend(optional_jsonschema_validation(roadmap, paths(root)["roadmap_schema"]))

    if roadmap.get("format_version") != "1.0":
        errors.append("format_version must equal '1.0'.")
    if not isinstance(roadmap.get("roadmap_version"), str) or not roadmap.get("roadmap_version"):
        errors.append("roadmap_version must be a non-empty string.")

    stages = roadmap.get("stages")
    if not isinstance(stages, list) or not stages:
        errors.append("stages must be a non-empty array.")
        return errors, warnings

    numbered_dir = root / "automation" / "numbered"
    prompt_files = sorted(
        str(path.relative_to(root)).replace("\\", "/")
        for path in numbered_dir.glob("*.md")
    )
    represented: list[str] = []
    seen_ids: set[str] = set()
    seen_sequences: set[int] = set()

    for index, stage in enumerate(stages, start=1):
        label = f"stages[{index - 1}]"
        if not isinstance(stage, dict):
            errors.append(f"{label} must be an object.")
            continue
        stage_id = stage.get("id")
        sequence = stage.get("sequence")
        if not isinstance(stage_id, str) or not re.fullmatch(r"\d{3}", stage_id):
            errors.append(f"{label}.id must be a three-digit string.")
        elif stage_id in seen_ids:
            errors.append(f"Duplicate stage id: {stage_id}")
        else:
            seen_ids.add(stage_id)
        if not isinstance(sequence, int) or sequence < 1:
            errors.append(f"{label}.sequence must be a positive integer.")
        elif sequence in seen_sequences:
            errors.append(f"Duplicate sequence: {sequence}")
        else:
            seen_sequences.add(sequence)
        if isinstance(stage_id, str) and isinstance(sequence, int):
            if stage_id != f"{sequence:03d}":
                errors.append(f"{label}: id {stage_id} does not match sequence {sequence}.")

        prompt_file = stage.get("prompt_file")
        if not isinstance(prompt_file, str) or not prompt_file.startswith("automation/numbered/"):
            errors.append(f"{label}.prompt_file must be under automation/numbered/.")
        else:
            represented.append(prompt_file)
            prompt_path = root / prompt_file
            if not prompt_path.is_file():
                errors.append(f"{label}: missing prompt file {prompt_file}.")
            else:
                try:
                    meta = parse_front_matter(prompt_path)
                    prompt_body(prompt_path)
                except ControllerError as exc:
                    errors.append(str(exc))
                    meta = {}
                expected_effort = meta.get("effort_label")
                if expected_effort and stage.get("effort_label") != expected_effort:
                    errors.append(
                        f"{label}: effort_label {stage.get('effort_label')!r} does not "
                        f"match prompt metadata {expected_effort!r}."
                    )
                if meta.get("prompt_id") and stage_id != meta.get("prompt_id"):
                    errors.append(f"{label}: stage id does not match prompt metadata.")

        effort = stage.get("effort_label")
        reasoning = stage.get("reasoning_effort")
        if effort not in EFFORT_MAP:
            errors.append(f"{label}.effort_label must be one of {list(EFFORT_MAP)}.")
        elif reasoning != EFFORT_MAP[effort]:
            errors.append(
                f"{label}.reasoning_effort must be {EFFORT_MAP[effort]!r} for {effort!r}."
            )

        kind = stage.get("kind")
        if kind not in VALID_STAGE_KINDS:
            errors.append(f"{label}.kind is invalid: {kind!r}.")
        sandbox = stage.get("sandbox")
        if sandbox not in {"read-only", "workspace-write"}:
            errors.append(f"{label}.sandbox must be read-only or workspace-write.")
        if kind in {"audit", "release_gate"} and sandbox != "read-only":
            errors.append(f"{label}: formal audit/release gate must use read-only sandbox.")

        prereqs = stage.get("prerequisites", [])
        if not isinstance(prereqs, list) or not all(isinstance(v, str) for v in prereqs):
            errors.append(f"{label}.prerequisites must be an array of stage ids.")
        else:
            for prerequisite in prereqs:
                if prerequisite not in seen_ids:
                    errors.append(
                        f"{label}: prerequisite {prerequisite!r} must refer to an earlier stage."
                    )
                elif isinstance(sequence, int) and int(prerequisite) >= sequence:
                    errors.append(
                        f"{label}: prerequisite {prerequisite!r} is not earlier than sequence {sequence}."
                    )

        for key in ("context_files", "allowed_change_paths", "forbidden_change_paths"):
            value = stage.get(key)
            if not isinstance(value, list) or not all(isinstance(v, str) and v for v in value):
                errors.append(f"{label}.{key} must be an array of non-empty strings.")

        validation = stage.get("validation", {})
        commands = validation.get("commands", []) if isinstance(validation, dict) else None
        if not isinstance(commands, list):
            errors.append(f"{label}.validation.commands must be an array.")
        else:
            for command_index, command in enumerate(commands):
                if not isinstance(command, dict):
                    errors.append(f"{label}.validation.commands[{command_index}] must be an object.")
                else:
                    errors.extend(
                        validate_command_spec(
                            command,
                            config,
                            f"{label}.validation.commands[{command_index}]",
                        )
                    )

        commit = stage.get("commit", {})
        allowed_outcomes = commit.get("allowed_outcomes", []) if isinstance(commit, dict) else []
        if not isinstance(allowed_outcomes, list) or not all(v in VALID_OUTCOMES for v in allowed_outcomes):
            errors.append(f"{label}.commit.allowed_outcomes contains invalid values.")
        if kind in {"audit", "release_gate"}:
            if not set(AUDIT_OUTCOMES).issubset(set(allowed_outcomes)):
                errors.append(
                    f"{label}: audits must commit PASS, PASS_WITH_REQUIRED_CORRECTIONS, and BLOCKED reports."
                )
            audit = stage.get("audit", {})
            if not isinstance(audit, dict) or audit.get("formal") is not True:
                errors.append(f"{label}: audit.formal must be true.")

    expected_sequences = list(range(1, len(stages) + 1))
    if sorted(seen_sequences) != expected_sequences:
        errors.append(
            f"Stage sequences must be continuous from 1 to {len(stages)}; got {sorted(seen_sequences)}."
        )
    if sorted(represented) != prompt_files:
        missing = sorted(set(prompt_files) - set(represented))
        extra = sorted(set(represented) - set(prompt_files))
        if missing:
            errors.append(f"Numbered prompt files omitted from roadmap: {missing}")
        if extra:
            errors.append(f"Roadmap references unexpected numbered prompt files: {extra}")
    if len(represented) != len(set(represented)):
        errors.append("Each numbered prompt file must be represented exactly once.")

    appendices = roadmap.get("appendices")
    if not isinstance(appendices, dict) or set(appendices) != {"A", "B", "C"}:
        errors.append("appendices must contain exactly A, B, and C.")
    else:
        for letter in ("A", "B", "C"):
            item = appendices[letter]
            label = f"appendices.{letter}"
            if not isinstance(item, dict):
                errors.append(f"{label} must be an object.")
                continue
            prompt_file = item.get("prompt_file")
            if not isinstance(prompt_file, str) or not prompt_file.startswith("automation/appendices/"):
                errors.append(f"{label}.prompt_file must be under automation/appendices/.")
            elif not (root / prompt_file).is_file():
                errors.append(f"{label}: missing prompt file {prompt_file}.")
            if item.get("normal_execution_eligible") is not False:
                errors.append(f"{label}.normal_execution_eligible must be false.")
            if letter in {"B", "C"}:
                if item.get("requires_explicit_invocation") is not True:
                    errors.append(f"{label}.requires_explicit_invocation must be true.")
                hard_lock = item.get("hard_lock", {})
                if not isinstance(hard_lock, dict) or hard_lock.get("enabled_by_default") is not False:
                    errors.append(f"{label}.hard_lock.enabled_by_default must be false.")

    if roadmap.get("normal_execution", {}).get("include_appendix_b") is not False:
        errors.append("normal_execution.include_appendix_b must be false.")
    if roadmap.get("normal_execution", {}).get("include_appendix_c") is not False:
        errors.append("normal_execution.include_appendix_c must be false.")

    if not errors:
        if len(stages) > 50:
            warnings.append("Roadmap contains more than 50 stages; verify that scope remains narrow.")
        if any("**" in p for stage in stages for p in stage.get("allowed_change_paths", [])):
            warnings.append(
                "One or more stages use broad ** allowed-change patterns. Review them carefully before promotion."
            )
    return errors, warnings


# ---------------------------------------------------------------------------
# Setup, roadmap generation, and promotion
# ---------------------------------------------------------------------------


def cmd_setup(root: Path) -> None:
    p = paths(root)
    for key in ("runtime", "results", "logs", "run_history"):
        p[key].mkdir(parents=True, exist_ok=True)
    if not p["state"].exists():
        save_state(root, default_state())

    gitignore = root / ".gitignore"
    existing = gitignore.read_text(encoding="utf-8") if gitignore.exists() else ""
    line = ".codex-loop/"
    if line not in {v.strip() for v in existing.splitlines()}:
        with gitignore.open("a", encoding="utf-8") as handle:
            if existing and not existing.endswith("\n"):
                handle.write("\n")
            handle.write("\n# Local Codex autonomous-loop runtime\n.codex-loop/\n")
        print("Added .codex-loop/ to .gitignore.")

    if shutil.which("codex") is None:
        print("WARNING: 'codex' was not found on PATH. Install/authenticate Codex CLI before running stages.")
    else:
        version = run_process(["codex", "--version"], cwd=root)
        print(f"Codex CLI: {version.stdout.strip() or version.stderr.strip()}")

    print("Setup complete.")
    print("Next: python3 automation/controller.py generate-roadmap")


def codex_command(
    root: Path,
    *,
    sandbox: str,
    reasoning_effort: str,
    schema_path: Path,
    output_path: Path,
) -> list[str]:
    return [
        "codex",
        "exec",
        "--ephemeral",
        "--sandbox",
        sandbox,
        "-c",
        'approval_policy="never"',
        "-c",
        f'model_reasoning_effort="{reasoning_effort}"',
        "-c",
        "sandbox_workspace_write.network_access=false",
        "--output-schema",
        str(schema_path),
        "--output-last-message",
        str(output_path),
        "-",
    ]


def invoke_codex_with_fallback(
    root: Path,
    *,
    prompt: str,
    sandbox: str,
    reasoning_effort: str,
    schema_path: Path,
    output_path: Path,
    log_path: Path,
    timeout_seconds: int,
    allow_xhigh_fallback: bool,
) -> dict[str, Any]:
    if shutil.which("codex") is None:
        raise ControllerError("Codex CLI is not installed or not on PATH.")

    efforts = [reasoning_effort]
    if reasoning_effort == "xhigh" and allow_xhigh_fallback:
        efforts.append("high")

    last_result: CommandResult | None = None
    for attempt, effort in enumerate(efforts, start=1):
        if output_path.exists():
            output_path.unlink()
        command = codex_command(
            root,
            sandbox=sandbox,
            reasoning_effort=effort,
            schema_path=schema_path,
            output_path=output_path,
        )
        result = run_process(
            command,
            cwd=root,
            input_text=prompt,
            timeout_seconds=timeout_seconds,
        )
        last_result = result
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with log_path.open("a", encoding="utf-8") as handle:
            handle.write(f"\n=== Codex attempt {attempt}; effort={effort} ===\n")
            handle.write(f"exit={result.returncode}; duration={result.duration_seconds:.2f}s\n")
            handle.write("--- stdout ---\n")
            handle.write(result.stdout)
            handle.write("\n--- stderr ---\n")
            handle.write(result.stderr)
            handle.write("\n")
        if result.returncode == 0 and output_path.exists():
            return load_json(output_path)
        combined = (result.stdout + "\n" + result.stderr).lower()
        if effort != "xhigh" or not any(token in combined for token in ("xhigh", "reasoning", "effort")):
            break

    assert last_result is not None
    raise ControllerError(
        "Codex execution failed. See the log for details:\n"
        f"  {log_path}\n"
        f"  exit: {last_result.returncode}\n"
        f"  stderr tail: {last_result.stderr[-2000:]}"
    )


def cmd_generate_roadmap(root: Path) -> None:
    require_clean(root, "before roadmap generation")
    config = load_config(root)
    p = paths(root)
    generator = p["generator_prompt"].read_text(encoding="utf-8")
    context = textwrap.dedent(
        f"""
        CONTROLLER-SUPPLIED FACTS
        - Repository root: {root}
        - Numbered prompt directory: automation/numbered/
        - Appendix prompt directory: automation/appendices/
        - Output must conform exactly to automation/roadmap.schema.json.
        - Do not execute, edit, or simulate any numbered prompt.
        - Appendix B and Appendix C must not appear in the numbered stages array and must remain hard-locked.
        - Return only the roadmap JSON object.
        """
    ).strip()
    prompt = f"{generator.strip()}\n\n{context}\n"
    output = p["runtime"] / "generated-roadmap.json"
    log = p["logs"] / "roadmap-generation.log"
    roadmap = invoke_codex_with_fallback(
        root,
        prompt=prompt,
        sandbox="read-only",
        reasoning_effort="xhigh",
        schema_path=p["roadmap_schema"],
        output_path=output,
        log_path=log,
        timeout_seconds=int(config.get("codex_timeout_seconds", 7200)),
        allow_xhigh_fallback=bool(config.get("xhigh_fallback_to_high", True)),
    )
    if clean_status(root):
        raise ControllerError("Roadmap generation was read-only but the working tree changed.")
    errors, warnings = validate_roadmap(root, roadmap)
    save_json(p["roadmap_proposed"], roadmap)
    report_lines = [
        "# Roadmap Generation Report",
        "",
        f"Generated: {utc_now()}",
        f"Controller version: {CONTROLLER_VERSION}",
        f"Proposed roadmap SHA-256: {sha256_file(p['roadmap_proposed'])}",
        f"Numbered stages: {len(roadmap.get('stages', []))}",
        "Appendix B included in normal execution: NO",
        "Appendix C included in normal execution: NO",
        "",
        "## Validation Result",
        "",
        "PASS" if not errors else "BLOCKED",
        "",
    ]
    if errors:
        report_lines += ["## Errors", ""] + [f"- {value}" for value in errors] + [""]
    if warnings:
        report_lines += ["## Warnings", ""] + [f"- {value}" for value in warnings] + [""]
    report_lines += [
        "## Required Human Action",
        "",
        "Review automation/roadmap.proposed.json against every prompt file and the governing documents.",
        "Do not promote it while any validation error or unresolved dependency concern remains.",
        "",
    ]
    p["generator_report"].parent.mkdir(parents=True, exist_ok=True)
    p["generator_report"].write_text("\n".join(report_lines), encoding="utf-8")
    print(f"Wrote proposal: {p['roadmap_proposed'].relative_to(root)}")
    print(f"Wrote report:   {p['generator_report'].relative_to(root)}")
    if errors:
        raise ControllerError("Proposed roadmap failed validation; review the generation report.")
    print("Proposal validates. Review it, then promote with:")
    print(f'python3 automation/controller.py promote-roadmap --confirm "{PROMOTE_CONFIRMATION}"')


def cmd_validate_roadmap(root: Path, file_path: str | None) -> None:
    target = Path(file_path).resolve() if file_path else paths(root)["roadmap_proposed"]
    roadmap = load_json(target)
    errors, warnings = validate_roadmap(root, roadmap)
    for warning in warnings:
        print(f"WARNING: {warning}")
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        raise ControllerError(f"Roadmap validation failed with {len(errors)} error(s).")
    print(f"Roadmap validation PASS: {target}")


def cmd_promote_roadmap(root: Path, confirmation: str) -> None:
    if confirmation != PROMOTE_CONFIRMATION:
        raise ControllerError(f"Confirmation must exactly equal: {PROMOTE_CONFIRMATION}")
    p = paths(root)
    roadmap = load_roadmap(root, proposed=True)
    errors, warnings = validate_roadmap(root, roadmap)
    if errors:
        raise ControllerError("Cannot promote an invalid roadmap:\n- " + "\n- ".join(errors))
    for warning in warnings:
        print(f"WARNING: {warning}")
    shutil.copy2(p["roadmap_proposed"], p["roadmap"])
    print(f"Promoted {p['roadmap_proposed'].relative_to(root)} to {p['roadmap'].relative_to(root)}.")
    print("Review the diff and commit the controller bundle and active roadmap manually.")
    print("The first autonomous stage will refuse to run until the repository is clean.")


# ---------------------------------------------------------------------------
# Eligibility and stage selection
# ---------------------------------------------------------------------------


def roadmap_stage(roadmap: dict[str, Any], stage_id: str) -> dict[str, Any]:
    for stage in roadmap.get("stages", []):
        if stage.get("id") == stage_id:
            return stage
    raise ControllerError(f"Roadmap has no numbered stage {stage_id}.")


def next_incomplete_stage(roadmap: dict[str, Any], state: dict[str, Any]) -> dict[str, Any] | None:
    completed = set(state.get("completed_numbered_stages", []))
    for stage in sorted(roadmap["stages"], key=lambda item: item["sequence"]):
        if stage["id"] not in completed:
            return stage
    return None


def approvals_satisfied(root: Path, files: list[str]) -> tuple[bool, list[str]]:
    missing: list[str] = []
    for value in files:
        path = root / value
        if not path.is_file():
            missing.append(value)
            continue
        try:
            payload = load_json(path)
        except ControllerError:
            missing.append(f"{value} (invalid JSON)")
            continue
        if payload.get("approved") is not True:
            missing.append(f"{value} (approved is not true)")
    return not missing, missing


def check_stage_eligibility(
    root: Path,
    roadmap: dict[str, Any],
    state: dict[str, Any],
    stage: dict[str, Any],
    *,
    rerun: bool,
) -> None:
    if state.get("pending_merge"):
        raise ControllerError("A completed stage is awaiting merge reconciliation.")
    if state.get("active_uncommitted"):
        raise ControllerError("An uncommitted stage branch requires human review.")
    if state.get("blocked") and not rerun:
        raise ControllerError(f"Progression is blocked: {state['blocked']}")

    completed = set(state.get("completed_numbered_stages", []))
    if not rerun:
        missing_prereqs = [value for value in stage.get("prerequisites", []) if value not in completed]
        if missing_prereqs:
            raise ControllerError(
                f"Stage {stage['id']} prerequisites are incomplete: {missing_prereqs}"
            )

    gate = stage.get("audit_gate", {})
    mode = gate.get("mode", "none")
    if mode == "latest_formal":
        latest = state.get("latest_formal_audit")
        allowed = gate.get("allowed_outcomes", ["PASS"])
        if not latest or latest.get("outcome") not in allowed:
            raise ControllerError(
                f"Stage {stage['id']} requires latest audit outcome in {allowed}; "
                f"current is {latest.get('outcome') if latest else None}."
            )
    elif mode not in {"none", None}:
        raise ControllerError(f"Unsupported audit gate mode: {mode}")

    human = stage.get("human_approval", {})
    approval_files = human.get("approval_files", []) if human.get("required_before_run") else []
    ok, missing = approvals_satisfied(root, approval_files)
    if not ok:
        raise ControllerError(
            f"Stage {stage['id']} requires approved files: {missing}"
        )


def select_normal_action(
    roadmap: dict[str, Any], state: dict[str, Any], requested_stage: str | None
) -> tuple[str, dict[str, Any], bool]:
    if state.get("pending_correction"):
        appendix = roadmap["appendices"]["A"]
        return "appendix_A", appendix, False
    if state.get("pending_audit_rerun"):
        stage_id = state["pending_audit_rerun"]["stage_id"]
        return "numbered", roadmap_stage(roadmap, stage_id), True
    if requested_stage:
        stage = roadmap_stage(roadmap, requested_stage.zfill(3))
        expected = next_incomplete_stage(roadmap, state)
        if expected and stage["id"] != expected["id"]:
            raise ControllerError(
                f"Requested stage {stage['id']} is not the next eligible stage; expected {expected['id']}."
            )
        return "numbered", stage, False
    stage = next_incomplete_stage(roadmap, state)
    if stage is None:
        raise ControllerError(
            "The numbered roadmap is complete. Normal execution stops here. "
            "Appendices B and C remain locked and are never launched automatically."
        )
    return "numbered", stage, False


# ---------------------------------------------------------------------------
# Stage execution
# ---------------------------------------------------------------------------


def stage_branch_name(config: dict[str, Any], action: str, stage: dict[str, Any], state: dict[str, Any], rerun: bool) -> str:
    prefix = config.get("branch_prefix", "automation")
    if action == "appendix_A":
        audit_id = state["pending_correction"]["audit_stage_id"]
        count = int(state.get("audit_rerun_counts", {}).get(audit_id, 0)) + 1
        return f"{prefix}/appendix-a-{audit_id}-correction-{count}"
    if action in {"appendix_B", "appendix_C"}:
        return f"{prefix}/appendix-{action[-1].lower()}-{slugify(stage['title'])}"
    suffix = ""
    if rerun:
        count = int(state.get("audit_rerun_counts", {}).get(stage["id"], 0)) + 1
        suffix = f"-rerun-{count}"
    return f"{prefix}/stage-{stage['id']}-{slugify(stage['title'])}{suffix}"


def build_stage_prompt(
    root: Path,
    roadmap: dict[str, Any],
    state: dict[str, Any],
    action: str,
    stage: dict[str, Any],
    audited_commit: str,
    rerun: bool,
) -> str:
    prompt_path = root / stage["prompt_file"]
    body = prompt_body(prompt_path)
    latest = state.get("latest_formal_audit")
    context_lines = "\n".join(f"- {value}" for value in stage.get("context_files", [])) or "- None listed"
    correction_text = ""
    if action == "appendix_A":
        correction = state["pending_correction"]
        correction_text = "\nAUTHORIZED CORRECTIONS\n" + json.dumps(
            correction.get("corrections", []), indent=2
        )
    if rerun:
        correction_text += "\nAUDIT RERUN\nThis is a mandatory rerun of the same formal audit after Appendix A corrections."

    ultra = ""
    if stage.get("effort_label") == "Ultra":
        ultra = textwrap.dedent(
            """
            ULTRA-STAGE SAFEGUARDS
            - Use the full relevant evidence set; do not approve by sampling only convenient files.
            - Explicitly reconcile code, tests, migrations, ADRs, runbooks, governed documents, and inherited audit findings.
            - Do not broaden scope merely because additional work is visible.
            - Stop rather than infer a security-sensitive, provider, destructive, source-access, or deployment decision.
            """
        ).strip()

    envelope = f"""
AUTONOMOUS CONTROLLER ENVELOPE
Controller version: {CONTROLLER_VERSION}
Action: {action}
Stage id: {stage.get('id', stage.get('appendix_id'))}
Stage title: {stage['title']}
Stage kind: {stage['kind']}
Human effort label: {stage['effort_label']}
Codex reasoning effort: {stage['reasoning_effort']}
Audited/starting commit: {audited_commit}
Roadmap version: {roadmap['roadmap_version']}

MANDATORY RULES
- Read AGENTS.md before acting.
- Execute only this one prompt. Never begin a later numbered prompt or another appendix.
- Inspect the listed context and the repository before editing.
- The controller, not Codex, owns branches, independent validation, documentation run records, and Git commits.
- Do not run git commit, git push, git merge, git reset, git clean, or destructive Git commands.
- Do not edit .git/, .codex-loop/, automation/controller.py, automation/controller.config.json,
  automation/result.schema.json, automation/roadmap.schema.json, or automation/roadmap.json.
- Do not use network access. Return APPROVAL_REQUIRED when network/provider action or a consequential decision is needed.
- Do not weaken tests, suppress failures, or edit unrelated code.
- Return a final JSON object conforming exactly to automation/result.schema.json.
- A formal audit is read-only. Put its complete immutable report in audit.report_markdown.
- Audit outcomes are exactly PASS, PASS_WITH_REQUIRED_CORRECTIONS, or BLOCKED.
- PASS_WITH_REQUIRED_CORRECTIONS may authorize Appendix A only through structured correction entries.
- BLOCKED never launches Appendix A automatically.
- Appendices B and C are outside normal execution. Do not invoke or prepare their activation.

REQUIRED CONTEXT
{context_lines}

LATEST FORMAL AUDIT
{json.dumps(latest, indent=2) if latest else 'None recorded by controller.'}

{ultra}
{correction_text}

PROMPT FILE CONTENT
{body}
"""
    return envelope.strip() + "\n"


def allowed_controller_paths(action: str, stage: dict[str, Any], audited_commit: str) -> list[str]:
    values = ["docs/automation/current-status.md", "docs/automation/run-history/**"]
    if stage["kind"] in {"audit", "release_gate"} or action == "appendix_C":
        values += ["docs/audits/**"]
    return values


def enforce_change_paths(
    root: Path,
    config: dict[str, Any],
    stage: dict[str, Any],
    action: str,
    audited_commit: str,
) -> list[str]:
    changed = changed_paths(root)
    global_forbidden = config.get("global_forbidden_change_paths", [])
    stage_forbidden = stage.get("forbidden_change_paths", [])
    forbidden = list(global_forbidden) + list(stage_forbidden)
    violations = [path for path in changed if path_matches(path, forbidden)]
    if violations:
        raise ControllerError(f"Forbidden files changed: {violations}")

    allowed = list(stage.get("allowed_change_paths", [])) + allowed_controller_paths(
        action, stage, audited_commit
    )
    if allowed:
        outside = [path for path in changed if not path_matches(path, allowed)]
        if outside:
            raise ControllerError(
                "Changes fall outside the stage's allowed paths:\n- " + "\n- ".join(outside)
            )
    return changed


def validate_result_for_stage(result: dict[str, Any], stage: dict[str, Any], action: str) -> None:
    outcome = result.get("outcome")
    if outcome not in VALID_OUTCOMES:
        raise ControllerError(f"Codex returned invalid outcome: {outcome!r}")
    expected_id = stage.get("id", stage.get("appendix_id"))
    if result.get("stage_id") != expected_id:
        raise ControllerError(
            f"Codex result stage_id {result.get('stage_id')!r} does not match {expected_id!r}."
        )
    is_audit = stage["kind"] in {"audit", "release_gate"} or action == "appendix_C"
    audit = result.get("audit", {})
    if is_audit:
        if outcome not in AUDIT_OUTCOMES:
            raise ControllerError(f"Formal audit returned non-audit outcome {outcome!r}.")
        if audit.get("is_audit") is not True or audit.get("verdict") != outcome:
            raise ControllerError("Audit result fields do not match the formal audit outcome.")
        if not str(audit.get("report_markdown", "")).strip():
            raise ControllerError("Formal audit did not supply audit.report_markdown.")
    else:
        if outcome in AUDIT_OUTCOMES:
            raise ControllerError("Non-audit stage returned an audit-only outcome.")


def audit_report_path(root: Path, stage: dict[str, Any], audited_commit: str, rerun_count: int) -> Path:
    suffix = f"-rerun-{rerun_count}" if rerun_count else ""
    filename = (
        f"stage-{stage.get('id', stage.get('appendix_id')).lower()}-"
        f"{slugify(stage['title'])}-{audited_commit[:12]}{suffix}.md"
    )
    return root / "docs" / "audits" / filename


def write_audit_artifacts(
    root: Path,
    stage: dict[str, Any],
    result: dict[str, Any],
    audited_commit: str,
    rerun_count: int,
) -> str:
    report_path = audit_report_path(root, stage, audited_commit, rerun_count)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report = str(result["audit"]["report_markdown"]).rstrip() + "\n"
    report_path.write_text(report, encoding="utf-8")

    index_path = paths(root)["audits_index"]
    if index_path.exists():
        index = load_json(index_path)
    else:
        index = {"format_version": "1.0", "audits": []}
    entry = {
        "stage_id": stage.get("id", stage.get("appendix_id")),
        "title": stage["title"],
        "outcome": result["outcome"],
        "audited_commit": audited_commit,
        "report_file": str(report_path.relative_to(root)).replace("\\", "/"),
        "created_at": utc_now(),
        "corrections": result.get("corrections", []),
    }
    index.setdefault("audits", []).append(entry)
    save_json(index_path, index)
    return entry["report_file"]


def run_validation_commands(
    root: Path,
    config: dict[str, Any],
    stage: dict[str, Any],
    run_label: str,
) -> list[dict[str, Any]]:
    commands: list[dict[str, Any]] = []
    commands.extend(stage.get("validation", {}).get("commands", []))
    for check in config.get("structural_checks", []):
        if_exists = check.get("if_exists")
        if if_exists and not (root / if_exists).exists():
            continue
        commands.append(check)

    records: list[dict[str, Any]] = []
    for index, command in enumerate(commands, start=1):
        errors = validate_command_spec(command, config, f"runtime command {index}")
        if errors:
            raise ControllerError("\n".join(errors))
        argv = command["argv"]
        timeout = int(command.get("timeout_seconds", 900))
        result = run_process(argv, cwd=root, timeout_seconds=timeout)
        record = {
            "name": command.get("name", " ".join(argv)),
            "argv": argv,
            "returncode": result.returncode,
            "duration_seconds": round(result.duration_seconds, 3),
            "stdout_tail": result.stdout[-4000:],
            "stderr_tail": result.stderr[-4000:],
        }
        records.append(record)
        log_path = paths(root)["logs"] / f"{run_label}-validation-{index:02d}.log"
        log_path.write_text(
            f"argv={argv!r}\nexit={result.returncode}\n\nSTDOUT\n{result.stdout}\n\nSTDERR\n{result.stderr}\n",
            encoding="utf-8",
        )
        if result.returncode != 0:
            raise ControllerError(
                f"Independent validation failed: {argv!r}\nSee {log_path.relative_to(root)}"
            )
    return records


def write_run_records(
    root: Path,
    roadmap: dict[str, Any],
    stage: dict[str, Any],
    action: str,
    result: dict[str, Any],
    audited_commit: str,
    validation_records: list[dict[str, Any]],
    audit_file: str | None,
    branch: str,
) -> str:
    identifier = stage.get("id", stage.get("appendix_id"))
    filename = f"{datetime.now().strftime('%Y%m%d-%H%M%S')}-{action.lower()}-{str(identifier).lower()}.md"
    history_path = paths(root)["run_history"] / filename
    history_path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        f"# Autonomous Run - {action} {identifier}",
        "",
        f"- Timestamp: {utc_now()}",
        f"- Roadmap version: {roadmap['roadmap_version']}",
        f"- Stage: {stage['title']}",
        f"- Branch: {branch}",
        f"- Starting commit: {audited_commit}",
        f"- Outcome: {result['outcome']}",
        f"- Audit file: {audit_file or 'Not applicable'}",
        "",
        "## Summary",
        "",
        str(result.get("summary", "")),
        "",
        "## Independent Controller Validation",
        "",
    ]
    if validation_records:
        for record in validation_records:
            lines.append(
                f"- PASS - `{record['argv']}` ({record['duration_seconds']} seconds)"
            )
    else:
        lines.append("- No executable validation commands were configured for this read-only result.")
    lines += [
        "",
        "## Remaining Risks",
        "",
    ]
    risks = result.get("remaining_risks", [])
    lines += [f"- {value}" for value in risks] if risks else ["- None reported."]
    lines.append("")
    history_path.write_text("\n".join(lines), encoding="utf-8")

    status_path = paths(root)["current_status"]
    status = [
        "# AZ Permit Radar Autonomous Execution Status",
        "",
        f"Updated: {utc_now()}",
        f"Roadmap version: {roadmap['roadmap_version']}",
        f"Latest prepared action: {action} {identifier} - {stage['title']}",
        f"Prepared outcome: {result['outcome']}",
        f"Prepared branch: {branch}",
        "State: awaiting human review and merge reconciliation",
        "",
        "The local controller state in `.codex-loop/state.json` is authoritative for the next local action.",
        "This file is a committed human-readable handoff and does not authorize bypassing audit or approval gates.",
        "",
    ]
    status_path.parent.mkdir(parents=True, exist_ok=True)
    status_path.write_text("\n".join(status), encoding="utf-8")
    return str(history_path.relative_to(root)).replace("\\", "/")


def commit_stage(
    root: Path,
    stage: dict[str, Any],
    action: str,
    result: dict[str, Any],
) -> str:
    git(root, "add", "--all")
    message_template = stage.get("commit", {}).get(
        "message_template", "Stage {id}: {title}"
    )
    identifier = stage.get("id", stage.get("appendix_id"))
    message = message_template.format(id=identifier, title=stage["title"], outcome=result["outcome"])
    git(root, "commit", "-m", message)
    return current_commit(root)


def execute_action(
    root: Path,
    *,
    action: str,
    stage: dict[str, Any],
    rerun: bool,
) -> None:
    config = load_config(root)
    roadmap = load_roadmap(root)
    state = load_state(root)
    base_branch = config.get("base_branch", roadmap.get("base_branch", "main"))

    if current_branch(root) != base_branch:
        raise ControllerError(
            f"Start stages from base branch {base_branch!r}; current branch is {current_branch(root)!r}."
        )
    require_clean(root, "before creating a stage branch")

    if action == "numbered":
        check_stage_eligibility(root, roadmap, state, stage, rerun=rerun)
    branch = stage_branch_name(config, action, stage, state, rerun)
    existing = git(root, "branch", "--list", branch)
    if existing:
        raise ControllerError(
            f"Branch {branch!r} already exists. Merge/delete it or update local state before retrying."
        )

    audited_commit = current_commit(root)
    git(root, "switch", "-c", branch)
    run_id = f"{action.lower()}-{stage.get('id', stage.get('appendix_id')).lower()}-{audited_commit[:8]}"
    result_path = paths(root)["results"] / f"{run_id}.json"
    log_path = paths(root)["logs"] / f"{run_id}-codex.log"

    try:
        prompt = build_stage_prompt(
            root, roadmap, state, action, stage, audited_commit, rerun
        )
        result = invoke_codex_with_fallback(
            root,
            prompt=prompt,
            sandbox=stage["sandbox"],
            reasoning_effort=stage["reasoning_effort"],
            schema_path=paths(root)["result_schema"],
            output_path=result_path,
            log_path=log_path,
            timeout_seconds=int(stage.get("codex_timeout_seconds", config.get("codex_timeout_seconds", 7200))),
            allow_xhigh_fallback=bool(config.get("xhigh_fallback_to_high", True)),
        )
        validate_result_for_stage(result, stage, action)

        is_audit = stage["kind"] in {"audit", "release_gate"} or action == "appendix_C"
        if is_audit and clean_status(root):
            raise ControllerError("A read-only audit changed repository files before controller report creation.")

        allowed_outcomes = set(stage.get("commit", {}).get("allowed_outcomes", []))
        if result["outcome"] not in allowed_outcomes:
            status = clean_status(root)
            state["last_stop"] = {
                "action": action,
                "stage_id": stage.get("id", stage.get("appendix_id")),
                "outcome": result["outcome"],
                "summary": result.get("summary"),
                "branch": branch,
                "created_at": utc_now(),
            }
            if status:
                state["active_uncommitted"] = state["last_stop"]
                save_state(root, state)
                raise ControllerError(
                    "Codex returned a non-committable outcome and left changes. "
                    f"Review branch {branch!r} manually; no commit was created."
                )
            git(root, "switch", base_branch)
            git(root, "branch", "-D", branch)
            if result["outcome"] == "APPROVAL_REQUIRED":
                state["approval_pending"] = result.get("approval")
            if result["outcome"] == "BLOCKED":
                state["blocked"] = result.get("summary")
            save_state(root, state)
            print(json.dumps(result, indent=2))
            return

        audit_file: str | None = None
        rerun_count = 0
        if rerun:
            rerun_count = int(state.get("audit_rerun_counts", {}).get(stage["id"], 0)) + 1
        if is_audit:
            audit_file = write_audit_artifacts(
                root, stage, result, audited_commit, rerun_count
            )

        validation_records = run_validation_commands(root, config, stage, run_id)
        run_history_file = write_run_records(
            root,
            roadmap,
            stage,
            action,
            result,
            audited_commit,
            validation_records,
            audit_file,
            branch,
        )
        changed = enforce_change_paths(root, config, stage, action, audited_commit)
        if not changed:
            raise ControllerError("Stage produced no committable repository changes.")

        # Final whitespace/merge-marker check after controller-created records.
        diff_check = run_process(["git", "diff", "--check"], cwd=root)
        if diff_check.returncode != 0:
            raise ControllerError(f"git diff --check failed:\n{diff_check.stdout}\n{diff_check.stderr}")

        commit_hash = commit_stage(root, stage, action, result)
        if clean_status(root):
            raise ControllerError("Controller commit completed but working tree is still dirty.")

        pending = {
            "action": action,
            "stage_id": stage.get("id", stage.get("appendix_id")),
            "title": stage["title"],
            "kind": stage["kind"],
            "outcome": result["outcome"],
            "branch": branch,
            "commit_hash": commit_hash,
            "starting_commit": audited_commit,
            "audit_file": audit_file,
            "corrections": result.get("corrections", []),
            "approval": result.get("approval"),
            "run_history_file": run_history_file,
            "rerun": rerun,
            "rerun_count": rerun_count,
            "created_at": utc_now(),
        }
        state["roadmap_version"] = roadmap["roadmap_version"]
        state["pending_merge"] = pending
        state["active_uncommitted"] = None
        save_state(root, state)
        print(json.dumps(result, indent=2))
        print("\nStage committed on an isolated branch.")
        print(f"Branch: {branch}")
        print(f"Commit: {commit_hash}")
        print("Review the diff, merge the branch into the base branch, return to the base branch, then run:")
        print("python3 automation/controller.py reconcile")
    except Exception:
        # Preserve branch and files for inspection. State records the active branch.
        state = load_state(root)
        state["active_uncommitted"] = {
            "action": action,
            "stage_id": stage.get("id", stage.get("appendix_id")),
            "branch": branch,
            "starting_commit": audited_commit,
            "created_at": utc_now(),
            "note": "Execution stopped before a controller-owned commit. Inspect this branch manually.",
        }
        save_state(root, state)
        raise


def cmd_run(root: Path, requested_stage: str | None) -> None:
    roadmap = load_roadmap(root)
    errors, warnings = validate_roadmap(root, roadmap)
    if errors:
        raise ControllerError("Active roadmap is invalid:\n- " + "\n- ".join(errors))
    for warning in warnings:
        print(f"WARNING: {warning}")
    state = load_state(root)
    if state.get("pending_merge"):
        raise ControllerError("A stage commit is awaiting merge. Run reconcile after merging it.")
    action, stage, rerun = select_normal_action(roadmap, state, requested_stage)
    if action == "appendix_A":
        execute_action(root, action=action, stage=stage, rerun=False)
    else:
        execute_action(root, action="numbered", stage=stage, rerun=rerun)


# ---------------------------------------------------------------------------
# Reconciliation and locked appendices
# ---------------------------------------------------------------------------


def cmd_reconcile(root: Path, delete_branch: bool) -> None:
    config = load_config(root)
    roadmap = load_roadmap(root)
    state = load_state(root)
    pending = state.get("pending_merge")
    if not pending:
        raise ControllerError("No stage commit is awaiting merge reconciliation.")
    base_branch = config.get("base_branch", roadmap.get("base_branch", "main"))
    if current_branch(root) != base_branch:
        raise ControllerError(f"Switch to base branch {base_branch!r} before reconciliation.")
    require_clean(root, "before merge reconciliation")
    if not git_is_ancestor(root, pending["commit_hash"], "HEAD"):
        raise ControllerError(
            f"Commit {pending['commit_hash']} is not in {base_branch}. Merge it before reconciliation."
        )

    action = pending["action"]
    outcome = pending["outcome"]
    stage_id = pending["stage_id"]

    if action == "numbered":
        completed = state.setdefault("completed_numbered_stages", [])
        if stage_id not in completed:
            completed.append(stage_id)
            completed.sort()
        stage = roadmap_stage(roadmap, stage_id)
        if stage["kind"] in {"audit", "release_gate"}:
            latest = {
                "stage_id": stage_id,
                "title": pending["title"],
                "outcome": outcome,
                "audited_commit": pending["starting_commit"],
                "report_file": pending.get("audit_file"),
                "corrections": pending.get("corrections", []),
                "report_commit": pending["commit_hash"],
                "reconciled_at": utc_now(),
            }
            state["latest_formal_audit"] = latest
            if pending.get("rerun"):
                counts = state.setdefault("audit_rerun_counts", {})
                counts[stage_id] = int(counts.get(stage_id, 0)) + 1
                state["pending_audit_rerun"] = None
            if outcome == "PASS":
                state["pending_correction"] = None
                state["blocked"] = None
            elif outcome == "PASS_WITH_REQUIRED_CORRECTIONS":
                corrections = pending.get("corrections", [])
                authorized = bool(corrections) and all(
                    item.get("authorized_handler") == "APPENDIX_A"
                    and item.get("blocking") is True
                    for item in corrections
                )
                if authorized:
                    state["pending_correction"] = {
                        "audit_stage_id": stage_id,
                        "audit_report_file": pending.get("audit_file"),
                        "audit_commit": pending["commit_hash"],
                        "corrections": corrections,
                    }
                    state["blocked"] = None
                else:
                    state["blocked"] = (
                        "Audit requires corrections but did not exclusively authorize Appendix A. "
                        "Human review is required."
                    )
            elif outcome == "BLOCKED":
                state["blocked"] = "Latest formal audit returned BLOCKED."
                state["pending_correction"] = None
        approval = pending.get("approval") or {}
        if approval.get("required") is True:
            state["approval_pending"] = approval
    elif action == "appendix_A":
        correction = state.get("pending_correction")
        if not correction:
            raise ControllerError("Appendix A merged but no pending correction is recorded.")
        state["appendix_history"].append(
            {
                "appendix": "A",
                "outcome": outcome,
                "commit_hash": pending["commit_hash"],
                "for_audit_stage": correction["audit_stage_id"],
                "reconciled_at": utc_now(),
            }
        )
        state["pending_audit_rerun"] = {
            "stage_id": correction["audit_stage_id"],
            "required_after_commit": pending["commit_hash"],
        }
        state["pending_correction"] = None
        state["blocked"] = None
    elif action in {"appendix_B", "appendix_C"}:
        state["appendix_history"].append(
            {
                "appendix": action[-1],
                "outcome": outcome,
                "commit_hash": pending["commit_hash"],
                "audit_file": pending.get("audit_file"),
                "reconciled_at": utc_now(),
            }
        )
        if action == "appendix_C" and outcome == "BLOCKED":
            state["blocked"] = "Appendix C SMS canary audit returned BLOCKED."

    branch = pending["branch"]
    state["pending_merge"] = None
    state["active_uncommitted"] = None
    state["last_stop"] = None
    save_state(root, state)

    if delete_branch and git(root, "branch", "--list", branch):
        git(root, "branch", "-d", branch)
        print(f"Deleted merged branch {branch}.")
    print("Merge reconciliation complete.")
    if state.get("pending_correction"):
        print("Next action is Appendix A through normal run command:")
        print("python3 automation/controller.py run")
    elif state.get("pending_audit_rerun"):
        print("Next action is the mandatory audit rerun:")
        print("python3 automation/controller.py run")
    elif state.get("blocked"):
        print(f"Progression remains blocked: {state['blocked']}")
    else:
        print("Next numbered stage may be started with:")
        print("python3 automation/controller.py run")


def numbered_roadmap_complete(roadmap: dict[str, Any], state: dict[str, Any]) -> bool:
    expected = {stage["id"] for stage in roadmap["stages"]}
    return expected.issubset(set(state.get("completed_numbered_stages", [])))


def appendix_completed(state: dict[str, Any], letter: str, outcomes: set[str] | None = None) -> bool:
    for item in state.get("appendix_history", []):
        if item.get("appendix") == letter and (outcomes is None or item.get("outcome") in outcomes):
            return True
    return False


def cmd_appendix(root: Path, letter: str, confirmation: str | None) -> None:
    roadmap = load_roadmap(root)
    config = load_config(root)
    state = load_state(root)
    letter = letter.upper()
    if letter not in {"A", "B", "C"}:
        raise ControllerError("Appendix must be A, B, or C.")

    if letter == "A":
        if not state.get("pending_correction"):
            raise ControllerError("Appendix A is available only for an authorized pending audit correction.")
        execute_action(root, action="appendix_A", stage=roadmap["appendices"]["A"], rerun=False)
        return

    lock = config.get("appendix_locks", {}).get(letter, {})
    if lock.get("enabled") is not True:
        raise ControllerError(
            f"Appendix {letter} is hard-locked in automation/controller.config.json. "
            "It cannot run until a human intentionally enables the lock after project review."
        )
    if not numbered_roadmap_complete(roadmap, state):
        raise ControllerError(f"Appendix {letter} cannot run before all numbered stages are complete.")
    latest = state.get("latest_formal_audit")
    final_id = roadmap["stages"][-1]["id"]
    if not latest or latest.get("stage_id") != final_id or latest.get("outcome") != "PASS":
        raise ControllerError(
            f"Appendix {letter} requires the final numbered audit ({final_id}) to be the latest PASS."
        )
    if state.get("pending_merge") or state.get("pending_correction") or state.get("pending_audit_rerun") or state.get("blocked"):
        raise ControllerError("Appendix execution is unavailable while another gate is pending or blocked.")

    required_confirmation = APPENDIX_B_CONFIRMATION if letter == "B" else APPENDIX_C_CONFIRMATION
    if confirmation != required_confirmation:
        raise ControllerError(f"Confirmation must exactly equal: {required_confirmation}")

    appendix = roadmap["appendices"][letter]
    approval_files = appendix.get("human_approval", {}).get("approval_files", [])
    ok, missing = approvals_satisfied(root, approval_files)
    if not ok:
        raise ControllerError(f"Appendix {letter} approval files are missing or unapproved: {missing}")

    if letter == "B":
        if appendix_completed(state, "B"):
            raise ControllerError("Appendix B has already completed; it will not be executed again automatically.")
    else:
        if not appendix_completed(state, "B", {"COMPLETED"}):
            raise ControllerError("Appendix C requires a reconciled COMPLETED Appendix B.")
        if appendix_completed(state, "C"):
            raise ControllerError("Appendix C has already been reconciled.")

    execute_action(root, action=f"appendix_{letter}", stage=appendix, rerun=False)


def cmd_abandon(root: Path, confirmation: str) -> None:
    if confirmation != ABANDON_CONFIRMATION:
        raise ControllerError(f"Confirmation must exactly equal: {ABANDON_CONFIRMATION}")
    config = load_config(root)
    roadmap = load_roadmap(root)
    state = load_state(root)
    active = state.get("active_uncommitted")
    if not active:
        raise ControllerError("No active uncommitted stage is recorded.")
    branch = active["branch"]
    if current_branch(root) != branch:
        raise ControllerError(f"Switch to recorded branch {branch!r} before abandoning it.")
    base = config.get("base_branch", roadmap.get("base_branch", "main"))
    git(root, "reset", "--hard", active["starting_commit"])
    git(root, "clean", "-fd")
    git(root, "switch", base)
    git(root, "branch", "-D", branch)
    state["active_uncommitted"] = None
    state["last_stop"] = {
        "outcome": "ABANDONED",
        "branch": branch,
        "created_at": utc_now(),
    }
    save_state(root, state)
    print(f"Abandoned and deleted uncommitted stage branch {branch}.")


def cmd_status(root: Path) -> None:
    state = load_state(root)
    output = {
        "repository": str(root),
        "branch": current_branch(root),
        "commit": current_commit(root),
        "working_tree_clean": not bool(clean_status(root)),
        "state": state,
    }
    roadmap_path = paths(root)["roadmap"]
    if roadmap_path.exists():
        roadmap = load_roadmap(root)
        output["roadmap"] = {
            "version": roadmap.get("roadmap_version"),
            "numbered_stage_count": len(roadmap.get("stages", [])),
            "numbered_complete": numbered_roadmap_complete(roadmap, state),
            "next_incomplete_stage": (
                next_incomplete_stage(roadmap, state) or {}
            ).get("id"),
            "appendix_b_normal_execution_eligible": roadmap.get("appendices", {}).get("B", {}).get("normal_execution_eligible"),
        }
    print(json.dumps(output, indent=2))


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Bounded autonomous Codex loop for AZ Permit Radar."
    )
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("setup", help="Create local runtime state and update .gitignore.")
    sub.add_parser("status", help="Show repository and controller state.")
    sub.add_parser("generate-roadmap", help="Generate roadmap.proposed.json with Codex in read-only mode.")

    validate = sub.add_parser("validate-roadmap", help="Validate a proposed or specified roadmap.")
    validate.add_argument("path", nargs="?", help="Defaults to automation/roadmap.proposed.json")

    promote = sub.add_parser("promote-roadmap", help="Promote the reviewed proposal to automation/roadmap.json.")
    promote.add_argument("--confirm", required=True)

    run = sub.add_parser("run", help="Run exactly one next eligible numbered/corrective action.")
    run.add_argument("--stage", help="Optional three-digit next stage id; cannot skip stages.")

    appendix = sub.add_parser("appendix", help="Explicitly invoke Appendix A, B, or C.")
    appendix.add_argument("letter", choices=["A", "B", "C", "a", "b", "c"])
    appendix.add_argument("--confirm")

    reconcile = sub.add_parser("reconcile", help="Record that the stage branch commit was merged.")
    reconcile.add_argument("--delete-branch", action="store_true")

    abandon = sub.add_parser("abandon", help="Destructively discard a recorded uncommitted stage branch.")
    abandon.add_argument("--confirm", required=True)

    return parser


def main() -> int:
    try:
        root = repo_root_from(Path.cwd())
        parser = build_parser()
        args = parser.parse_args()
        if args.command == "setup":
            cmd_setup(root)
        elif args.command == "status":
            cmd_status(root)
        elif args.command == "generate-roadmap":
            cmd_generate_roadmap(root)
        elif args.command == "validate-roadmap":
            cmd_validate_roadmap(root, args.path)
        elif args.command == "promote-roadmap":
            cmd_promote_roadmap(root, args.confirm)
        elif args.command == "run":
            cmd_run(root, args.stage)
        elif args.command == "appendix":
            cmd_appendix(root, args.letter, args.confirm)
        elif args.command == "reconcile":
            cmd_reconcile(root, args.delete_branch)
        elif args.command == "abandon":
            cmd_abandon(root, args.confirm)
        else:
            raise ControllerError(f"Unsupported command: {args.command}")
        return 0
    except (ControllerError, subprocess.SubprocessError, OSError) as exc:
        print(f"CONTROLLER STOPPED: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
