# AZPR v10.1 Integration Rollback Plan

Generated: `2026-08-06T23:11:48+00:00`

## Current rollback state

No integration branch, worktree, commit, tracked edit, prompt replacement, controller copy, policy/roadmap activation, runtime-state copy, or installation occurred. Rollback is therefore limited to task-created untracked evidence.

## Reproducible rollback procedure

1. Preserve `.integration-reports/` externally if the handoff must be retained.
2. Confirm `git diff --exit-code` and `git diff --cached --exit-code` both succeed.
3. Confirm the only task-created untracked roots are exactly `.integration-temp/` and `.integration-reports/`.
4. Remove only those two exact directories; do not use a repository-wide clean, reset, checkout, or history rewrite.
5. Verify `git status --short --branch` returns `## main...origin/main` and HEAD remains `dac0e0bf1695d44f4b6c0e0e7673559f5d87ec02`.
6. Verify `git worktree list --porcelain` still contains only the main worktree.

## Rehearsal result

Non-destructive rehearsal passed: there is no tracked/cached diff and no integration branch/worktree exists. The exact generated roots are inside the allowed boundary. The required reports intentionally remain present, so cleanup was not executed.

## Future materialized rollback boundary

If a later approved integration creates `integration/v10.1-staging`, record the approved base and mapping hash first. Rollback must remove only files added by approved mapping rows or abandon the isolated worktree/branch; never rewrite `main`, delete source evidence, or modify canonical prompt bytes without a separately approved migration.
