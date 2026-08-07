# AZPR Security Remediation — Priority Fix Plan

## Gate 0: Keep execution disabled

- Preserve `safe_for_unattended_execution_now: false`.
- Do not copy the hardened controller into the active repository until the critical controls below have tests and independent review.

## Gate 1: Repair roots of trust

1. Replace HMAC approval verification with asymmetric signatures and public-key-only verification in the controller.
2. Launch Codex with a minimal sanitized environment and isolated HOME; never expose approval/signing secrets.
3. Move `.codex-loop` state outside the workspace and replace mutable authoritative state with signed, reconstructible run/audit records.
4. Persist consumed nonces in an append-only protected ledger independent of repository state.

## Gate 2: Repair validation isolation

1. Use a disposable clean worktree/container. Mount repository input read-only and expose a separate output/evidence directory.
2. Hide host HOME, `/proc`, cloud/SSH credentials, sockets, devices, and unrelated filesystem paths.
3. Add CPU, memory, process, file-size, disk, and timeout limits; kill the entire process group on timeout.
4. Hash the runner/toolchain and verify before every command. Fail on any repository mutation.

## Gate 3: Repair approvals and schemas

1. Reject `required_before_run: true` with empty approval files, zero quorum, empty actions, or missing required signer IDs.
2. Bind approvals to the exact plan/capability manifest, resources, account, cohort, window, limits, backup, and evidence outputs.
3. Require complete roadmap/result/approval/capability/evidence schemas and fail if schema validation is unavailable.
4. Add controller-native semantic checks for audit verdict/corrections/report consistency.

## Gate 4: Repair file and Git enforcement

1. Parse Git output with NUL delimiters and reject control-character filenames.
2. Use segment-aware path rules and resolve allowed scope against the actual repository tree.
3. Reject writable symlinks, hardlinks, submodules, nested repos, and symlinked controller-output paths.
4. Reconcile only an exact expected commit or approved merge with no unrelated commits.
5. Use unique run IDs and signed immutable manifests.

## Gate 5: Complete external capability separation

1. Implement the human-operated runner from a separate codebase/security boundary.
2. Add typed plan/apply/evidence manifests and signed target attestation.
3. Verify account identity and drift immediately before apply; consume nonce before side effects.
4. Keep staging, production, provider, source, DNS, database, and destructive recovery actions outside Codex.

## Gate 6: Regenerate and retest

1. Generate the roadmap from the real post-Stage-004 repository tree with exact stage paths.
2. Define complete backend, frontend, migration, security, infrastructure, recovery, and deployment-evidence validation profiles.
3. Add negative tests for every finding in the reassessment.
4. Rerun the security consultation before promotion.
