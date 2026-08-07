# AZPR v10.1 Integration Conflict Report

Generated: `2026-08-06T23:11:48+00:00`

## Verdict

**BLOCKED BEFORE BRANCH/WORKTREE CREATION OR MATERIALIZATION.** The delivery identity is verified, but ten blocking conflicts and four non-blocking conflicts remain.

## Blocking conflicts

### B01 — PROMPT_COLLISION

- Stop condition(s): `integration_requires_prompt_changes`
- Paths: `automation/numbered/*.md; automation/appendices/*.md; automation/prompt-manifest.json`
- Finding: All 41 current canonical prompts conflict: 38 content collisions and three filename/semantic collisions at IDs 031, 033, and 035. Prompt modification is forbidden.
- Required human decision: Choose and explicitly approve one canonical prompt generation and all required reference/manifest retirements.

### B02 — OWNERSHIP_COLLISION

- Stop condition(s): `current_and_delivered_controller_conflict`
- Paths: `automation/controller.py; trusted-controller/controller.py; automation/controller.config.json`
- Finding: Repository-local controller v1.0.1 conflicts with an external trusted-controller v7 draft and a different host/runtime model.
- Required human decision: Approve controller ownership, install boundary, configuration model, and migration mapping.

### B03 — REFERENCE_COLLISION

- Stop condition(s): `unclear_file_destination`
- Paths: `automation/result.schema.json; automation/roadmap.schema.json; automation/schemas/result.schema.json; automation/schemas/roadmap.schema.json; automation/roadmap-generator-prompt.md; docs/audits/index.json`
- Finding: Schema locations/content and roadmap-generator instructions conflict; the delivered controller also requires a missing controller-owned audit index.
- Required human decision: Approve one controller/schema/reference contract; do not fabricate the audit index.

### B04 — ACTIVE_STATE_COLLISION

- Stop condition(s): `unexpected_active_roadmap`
- Paths: `automation/roadmap.json; automation/roadmap.proposed.json; .codex-loop/generated-roadmap.json; .codex-loop/state.json`
- Finding: Current controller treats the zero-byte roadmap and populated proposal as inactive; delivered verifier semantics reject path existence.
- Required human decision: Define active-roadmap semantics and an approved non-destructive disposition.

### B05 — ACTIVE_STATE_COLLISION

- Stop condition(s): `unexpected_active_policy`
- Paths: `docs/automation/autonomous-execution-policy.md; automation/policy/README.md; AGENTS.md`
- Finding: Current repository has an operative autonomous-execution policy document; delivery checks only a narrower absent canonical-policy authority.
- Required human decision: Define active-policy semantics and approve governance placement without activation.

### B06 — DOCUMENTATION_COLLISION

- Stop condition(s): `documentation_version_conflict`
- Paths: `docs/current/; CURRENT-DOCUMENT-INDEX.json; AUTONOMOUS_LOOP_INSTALL.md; docs/automation/`
- Finding: Delivery's 17 security current-documents are not the repository's five governed product-document families; old controller documentation has no delivered replacement.
- Required human decision: Approve a delivery-provenance location and a separate governed documentation migration; never copy reports into docs/current.

### B07 — OWNERSHIP_COLLISION

- Stop condition(s): `unclear_tool_ownership, unclear_file_destination`
- Paths: `operator-tools/; external-capability-runner/; trusted-installation/; trusted-validation-runner/; requirements-security.in`
- Finding: Operator, host installation, runtime, historical, and report content lacks an approved repository or host destination.
- Required human decision: Approve ownership and exact destinations separately; host installation remains outside this task.

### B08 — UNKNOWN_INTENT

- Stop condition(s): `mapping_not_approved`
- Paths: `.integration-reports/AZPR-v10.1-integration-path-mapping.csv`
- Finding: The exhaustive mapping exists but has not received the specification's required human approval.
- Required human decision: Review and approve the exact CSV hash or return corrections.
- Mapping SHA-256: `007786c1c1748f8264cee452df815b47e41e15deb8b532b31f426cd18b4f2525`

### B09 — UNKNOWN_INTENT

- Stop condition(s): `unapproved_base_commit`
- Paths: `dac0e0bf1695d44f4b6c0e0e7673559f5d87ec02`
- Finding: The clean current HEAD is recorded but was not explicitly approved as the integration base.
- Required human decision: Explicitly approve base commit dac0e0bf1695d44f4b6c0e0e7673559f5d87ec02 or identify another base.

### B10 — UNKNOWN_INTENT

- Stop condition(s): `test_count_mismatch`
- Paths: `VERIFY-V10-CANDIDATE.py; requirements-security.in`
- Finding: Both verifier attempts stopped at 'jsonschema unavailable'; pytest is also unavailable. Source tests 0/120 and fresh-extraction tests 0/120 executed.
- Required human decision: Provide an approved offline dependency set/runtime and rerun both complete 120-test verifier passes.

## Non-blocking conflicts

- **N01 — GENERATED_FILE_COLLISION:** Three prompt representations and duplicate report/verification copies are byte-identical and safely mapped to QUARANTINE.
- **N02 — DOCUMENTATION_COLLISION:** Current generated roadmap notes still say the Master Operating Prompt is absent although the repository now tracks it.
- **N03 — UNKNOWN_INTENT:** No formatter, linter, or static/type checker is configured; existing repository unittest/docs checks still pass.
- **N04 — GENERATED_FILE_COLLISION:** Pre-existing ignored caches and inactive local controller state remain local and were not copied into staging.

## Scope safeguards

No tracked file, branch, worktree, controller, prompt, policy, roadmap, provider, installer, runtime state, secret, or production capability was changed or activated. Delivery reports were not placed in `docs/current/`.
