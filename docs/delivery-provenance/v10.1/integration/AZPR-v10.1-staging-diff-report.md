# AZPR v10.1 Staging Diff Report

Generated: `2026-08-06T23:11:48+00:00`

## Result

No isolated staging worktree or integration branch was created, and no integration overlay was materialized. This is the required stopped state after `mapping_not_approved`, `unapproved_base_commit`, prompt/controller conflicts, and `test_count_mismatch` were found.

## Tracked diff

- Base: `dac0e0bf1695d44f4b6c0e0e7673559f5d87ec02` on `main`, synchronized with `origin/main` at phase-1 freeze.
- Tracked working-tree diff: none.
- Cached/staged diff: none.
- Application, prompt, policy, roadmap, controller, documentation, configuration, and test files changed: 0.

## Task-created untracked paths

- `.integration-temp/`: safe extractions and validation evidence only.
- `.integration-reports/`: the nine required handoff reports only.

## Expected approved candidate additions (not applied)

- 73 files under `automation/schemas/`.
- Seven files under `automation/validation-profiles/`.
- `automation/policy/README.md` as a fail-closed notice only.

Every other delivered component is `DEFER`, `QUARANTINE`, or `KEEP_CURRENT` pending explicit human resolution.
