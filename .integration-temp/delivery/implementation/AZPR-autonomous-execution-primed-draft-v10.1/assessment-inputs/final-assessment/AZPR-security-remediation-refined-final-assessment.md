# AZPR Security Remediation Refined Pack — Final Security Assessment

**Assessment date:** 2026-07-24T21:43:04.281938+00:00  
**Refined pack SHA-256:** `e1ac23cdc71eca0cdacf04a0e8ade5bbb487ae822183570aef4ed96aed68a0b9`  
**Standalone refined prompts ZIP SHA-256:** `15695bdc0a511723075226e77869c946d73afb46fe03820e992fa3dfc8133476`

## Executive decision

**Promotion decision: BLOCK unattended autonomous execution.**

The refined remediation is a substantial improvement over the prior pack. The prompt language is disciplined, the audit prompts are read-only, deployment work is separated into planning and human-operated application, external capabilities are denied to the autonomous agent, and the pack correctly retains `safe_for_unattended_execution_now: false`.

The final pass nevertheless found **8 critical**, **11 high**, and **1 medium** findings. The most serious defects are implementation-level trust-boundary failures rather than weaknesses in the 41 prompt texts.

The current pack is appropriate for:

- continued security development;
- isolated controller testing with synthetic repositories and keys;
- manual review of regenerated roadmaps and validation profiles;
- non-production dry runs that cannot access credentials, providers, customer data, or deployment targets.

It is **not** appropriate for unattended use against a real AZPR repository or any staging/production environment.

## What was verified

- The refined pack verification script passed.
- **92** manifest entries were verified.
- **12** schemas and **7** validation profiles were present and verified.
- All **16** supplied tests passed.
- All **38 numbered prompts and 3 appendices** were present.
- The standalone `markdown-prompts-refined` archive matched the embedded prompt archive and repository-overlay copies byte-for-byte by SHA-256.
- No archive traversal or symlink entries were detected during controlled extraction.
- The Python sources compiled successfully.
- A direct concurrency test reproduced the nonce race: two simultaneous consumers both recorded the same nonce.

These results establish packaging consistency, but they do not prove safe execution.

## Strong controls that should be retained

1. Ed25519 public-key verification instead of shared approval HMAC secrets.
2. A minimal Codex child environment that removes approval, cloud, and operator secrets.
3. Trusted controller and validation-runner components intended to live outside the repository.
4. Signed hash-chain journals for runtime state and consumed nonces.
5. Digest-pinned, read-only, no-network validation containers.
6. Uniform instruction-integrity and prompt-injection warnings in all prompt files.
7. Read-only formal audits with controller-owned report materialization.
8. Stage 031 as an audit rather than a repository-wide hardening implementation.
9. Stages 033 and 035 as plan-only deployment stages.
10. Explicitly invoked, restricted appendices and a separate human-operated external capability runner.

## Findings overview

| ID | Severity | Finding | Component |
|---|---|---|---|
| F-01 | CRITICAL | Approval policy hash is self-referential | trusted-controller/controller.py |
| F-02 | CRITICAL | Nonce consumption is not atomic | trusted-controller/secure_runtime.py |
| F-03 | CRITICAL | Signed state is not bound to the current repository HEAD and exact roadmap | trusted-controller/controller.py |
| F-04 | CRITICAL | No trusted ingestion path for signed external evidence | trusted-controller |
| F-05 | CRITICAL | Controller-owned repository writes can follow symlinks | trusted-controller/controller.py |
| F-06 | CRITICAL | Repository Git configuration and hooks can execute host code | trusted-controller/controller.py |
| F-07 | CRITICAL | External runner trust roots are replaceable through command-line paths | external-capability-runner/capability_runner.py |
| F-08 | CRITICAL | Appendix A human authorization is not cryptographically enforced | trusted-controller/controller.py / Appendix A |
| F-09 | HIGH | Signed journals remain rollback/truncation vulnerable | trusted-controller/secure_runtime.py |
| F-10 | HIGH | Agent and controller output paths share the same change allowlist | trusted-controller/controller.py |
| F-11 | HIGH | Path budgets do not cap aggregate or untracked changes | trusted-controller/controller.py |
| F-12 | HIGH | Validation snapshot may include ignored secrets and local artifacts | trusted-validation-runner/trusted_validation_runner.py |
| F-13 | HIGH | Validation and adapter output capture is unbounded | trusted-validation-runner / external-capability-runner |
| F-14 | HIGH | External signer-role separation is weaker than stated | trusted-controller/secure_runtime.py / external runner |
| F-15 | HIGH | External adapter verification has path and TOCTOU weaknesses | external-capability-runner/capability_runner.py |
| F-16 | HIGH | ROLLED_BACK can still produce an APPLY_COMPLETE result | external-capability-runner/capability_runner.py |
| F-17 | HIGH | Signed evidence files are overwriteable | external-capability-runner / secure runtime |
| F-18 | HIGH | Generated reports and result payloads need stronger bounds and redaction | trusted-controller / result schemas |
| F-19 | HIGH | Security tests do not cover the highest-risk trust boundaries | tests |
| F-20 | MEDIUM | Operational hardening remains incomplete | operator tools / dependency and container configuration |

## Critical findings

### F-01 — Approval policy hash is self-referential

`policy_hashes()` includes every approval document in the hash map that the approval itself must embed. `verify_approval_file()` then demands exact equality with that map. This creates an impractical self-hash requirement.

**Consequence:** approval-required stages cannot be authorized without weakening the security design.

**Required correction:** exclude approval documents from the policy set they sign. Record their own hashes separately in the signed run record.

### F-02 — Nonce consumption is not atomic

`NonceLedger.consume()` checks prior use and appends in separate lock windows. The race was reproduced with the supplied implementation: both concurrent calls succeeded for the same nonce.

**Consequence:** one-use approvals and apply manifests can be replayed during concurrent execution.

**Required correction:** check and append under one exclusive transaction or uniqueness-enforced database operation.

### F-03 — Signed state is not bound to repository HEAD and the exact roadmap

The controller trusts signed completed-stage and audit state without requiring current HEAD to include the last reconciled commit. The state also relies on a roadmap version string rather than the exact file hash.

**Consequence:** branch rollback or policy mutation can silently separate the signed execution history from the code being executed.

**Required correction:** bind every state transition to the exact commit/tree, roadmap hash, prompt catalog, controller, schemas, and master prompt; verify ancestry before every run.

### F-04 — Trusted external evidence cannot be ingested

The release and canary audit prompts require verified signed evidence, but the controller does not provide a trusted evidence-ingestion and verification command.

**Consequence:** final readiness audits cannot securely PASS.

**Required correction:** build an immutable evidence registry and controller command that verifies signatures, schemas, target attestations, plan hashes, nonces, and operation outcomes before evidence is exposed to an audit.

### F-05 — Controller-owned writes can follow repository symlinks

Controller reports are written using ordinary pathname operations.

**Consequence:** a stage can prepare a symlink and make the trusted controller write outside the repository.

**Required correction:** descriptor-relative, no-follow secure writes and strict separation of agent-writable and controller-owned paths.

### F-06 — Git can execute repository-controlled host code

Normal Git operations can invoke hooks, filters, signing tools, fsmonitor, and configured helpers.

**Consequence:** untrusted repository configuration can escape the validation container and execute with host/controller privileges.

**Required correction:** pin and sanitize Git, disable hooks and helpers, and reject unsafe repository/global configuration.

### F-07 — External-runner trust roots are caller-selectable

The runner accepts arbitrary config and schema paths that define trusted keys and adapters.

**Consequence:** a caller can substitute an entirely different trust domain.

**Required correction:** use a root-owned installed launcher with pinned signed configuration and schema hashes.

### F-08 — Appendix A does not cryptographically prove human authorization

A non-empty authorization ID is not the same as a verified authorization document.

**Consequence:** the model can invent an identifier and make sensitive corrections appear approved.

**Required correction:** require a signed, expiring, one-use authorization bound to exact correction IDs, file paths, commit, and policy hashes.

## High and medium findings

### State and scope controls

- Signed journals need external rollback resistance.
- Controller-owned status and run-history files must not be agent-writable.
- Change budgets must be enforced over the aggregate actual diff, including untracked files.
- A stage result must be bound to an exact, strict external-plan schema rather than generic JSON.

### Validation isolation

- Build snapshots from tracked files plus explicitly authorized additions, not the full worktree.
- Bound stdout, stderr, evidence bytes, file count, directory depth, and inode use.
- Pin the container engine and validation runner binaries.
- Hold a repository/worktree lock or use a dedicated immutable checkout while snapshotting.
- Test every validation profile against the real selected stack because some read-only builds require controlled writable caches/output directories.

### External capability execution

- Enforce one distinct signer identity per required privileged role.
- Remove adapter hash/execute TOCTOU and require root-owned immutable adapter installation.
- Treat `ROLLED_BACK` as a non-success terminal result.
- Create evidence once with unique, content-addressed paths and immutable indexing.
- Bind the exact target-attestation hash to the manifest.
- Schema-validate and size-cap every adapter request and response.

### Output and operational safety

- Redact and size-limit generated histories, audit findings, correction descriptions, and external plans.
- Upgrade the operator signing tool to validate schemas, show canonical hashes, require explicit confirmation, and use secure writes.
- Hash-pin Python dependencies and trusted executable artifacts.
- Use domain-separated signing keys for state, nonces, run manifests, and external evidence.

## Prompt security and confidence scores

**Interpretation**

- **Security score:** quality of the prompt's own scope, stop conditions, trust boundaries, and safety language.
- **Confidence score:** confidence that the prompt can be executed safely through the supplied refined controller and runners.
- **Acceptable threshold:** both scores at least 85.

| ID | Prompt | Security | Confidence | Status |
|---|---|---:|---:|---|
| 001 | 001-close-the-post-core-traceability-release-gate | 93 | 61 | CONDITIONAL |
| 002 | 002-post-core-traceability-corrective-audit | 94 | 58 | UNACCEPTABLE_FOR_UNATTENDED_EXECUTION |
| 003 | 003-define-and-govern-the-narrow-pilot-scope | 94 | 63 | CONDITIONAL |
| 004 | 004-select-and-govern-the-production-application-stack | 95 | 60 | CONDITIONAL |
| 005 | 005-bootstrap-the-production-application-shell-and-engineering-baseline | 92 | 59 | UNACCEPTABLE_FOR_UNATTENDED_EXECUTION |
| 006 | 006-mvp-scope-and-architecture-decision-audit | 94 | 58 | UNACCEPTABLE_FOR_UNATTENDED_EXECUTION |
| 007 | 007-design-and-implement-the-durable-database-schema-and-migrations | 93 | 55 | UNACCEPTABLE_FOR_UNATTENDED_EXECUTION |
| 008 | 008-implement-durable-repositories-and-transaction-boundaries | 93 | 55 | UNACCEPTABLE_FOR_UNATTENDED_EXECUTION |
| 009 | 009-implement-immutable-artifact-storage-outbox-workers-and-crash-recovery | 94 | 53 | UNACCEPTABLE_FOR_UNATTENDED_EXECUTION |
| 010 | 010-durable-platform-and-persistence-audit | 95 | 54 | UNACCEPTABLE_FOR_UNATTENDED_EXECUTION |
| 011 | 011-implement-authentication-session-security-and-accesscontext-construction | 94 | 50 | UNACCEPTABLE_FOR_UNATTENDED_EXECUTION |
| 012 | 012-implement-customer-account-lifecycle-versioned-configuration-and-onboarding-api | 93 | 52 | UNACCEPTABLE_FOR_UNATTENDED_EXECUTION |
| 013 | 013-identity-authorization-and-customer-isolation-audit | 96 | 50 | UNACCEPTABLE_FOR_UNATTENDED_EXECUTION |
| 014 | 014-select-and-approve-the-first-tucson-or-pima-county-production-source | 95 | 48 | UNACCEPTABLE_FOR_UNATTENDED_EXECUTION |
| 015 | 015-implement-durable-scheduled-acquisition-and-the-approved-live-connector | 94 | 47 | UNACCEPTABLE_FOR_UNATTENDED_EXECUTION |
| 016 | 016-implement-the-production-source-parser-replay-and-backfill-contract | 94 | 58 | UNACCEPTABLE_FOR_UNATTENDED_EXECUTION |
| 017 | 017-implement-required-production-geography-and-address-resolution | 93 | 52 | UNACCEPTABLE_FOR_UNATTENDED_EXECUTION |
| 018 | 018-pilot-source-ingestion-normalization-and-geography-audit | 96 | 48 | UNACCEPTABLE_FOR_UNATTENDED_EXECUTION |
| 019 | 019-implement-the-authorized-customer-api-and-query-projections | 94 | 54 | UNACCEPTABLE_FOR_UNATTENDED_EXECUTION |
| 020 | 020-build-the-authenticated-frontend-foundation-and-onboarding-experience | 93 | 55 | UNACCEPTABLE_FOR_UNATTENDED_EXECUTION |
| 021 | 021-build-the-explainable-opportunity-dashboard-and-lead-workflow | 93 | 56 | UNACCEPTABLE_FOR_UNATTENDED_EXECUTION |
| 022 | 022-customer-api-frontend-and-data-exposure-audit | 96 | 50 | UNACCEPTABLE_FOR_UNATTENDED_EXECUTION |
| 023 | 023-implement-email-notification-orchestration-and-delivery | 94 | 47 | UNACCEPTABLE_FOR_UNATTENDED_EXECUTION |
| 024 | 024-email-delivery-audit | 96 | 46 | UNACCEPTABLE_FOR_UNATTENDED_EXECUTION |
| 025 | 025-implement-controlled-sms-infrastructure-behind-a-disabled-feature-flag | 96 | 44 | UNACCEPTABLE_FOR_UNATTENDED_EXECUTION |
| 026 | 026-build-internal-review-and-source-operations-tooling | 93 | 45 | UNACCEPTABLE_FOR_UNATTENDED_EXECUTION |
| 027 | 027-notification-sms-and-operations-audit | 96 | 44 | UNACCEPTABLE_FOR_UNATTENDED_EXECUTION |
| 028 | 028-implement-the-privacy-conscious-analytics-event-model | 94 | 56 | UNACCEPTABLE_FOR_UNATTENDED_EXECUTION |
| 029 | 029-implement-observability-health-alerting-and-operational-runbooks | 94 | 49 | UNACCEPTABLE_FOR_UNATTENDED_EXECUTION |
| 030 | 030-implement-backup-restore-reconciliation-and-rollback-procedures | 95 | 43 | UNACCEPTABLE_FOR_UNATTENDED_EXECUTION |
| 031 | 031-security-privacy-performance-and-recovery-hardening-audit | 96 | 48 | UNACCEPTABLE_FOR_UNATTENDED_EXECUTION |
| 032 | 032-formal-pilot-release-test-matrix-and-release-gate-audit | 96 | 46 | UNACCEPTABLE_FOR_UNATTENDED_EXECUTION |
| 033 | 033-prepare-controlled-staging-deployment-plan | 97 | 44 | UNACCEPTABLE_FOR_UNATTENDED_EXECUTION |
| 034 | 034-final-staging-and-pilot-readiness-audit | 97 | 38 | UNACCEPTABLE_FOR_UNATTENDED_EXECUTION |
| 035 | 035-prepare-controlled-production-pilot-release-plan | 98 | 42 | UNACCEPTABLE_FOR_UNATTENDED_EXECUTION |
| 036 | 036-production-pilot-launch-verification-audit | 98 | 35 | UNACCEPTABLE_FOR_UNATTENDED_EXECUTION |
| 037 | 037-implement-pilot-feedback-and-business-validation-workflow | 93 | 50 | UNACCEPTABLE_FOR_UNATTENDED_EXECUTION |
| 038 | 038-pilot-feedback-and-business-validation-audit | 96 | 46 | UNACCEPTABLE_FOR_UNATTENDED_EXECUTION |
| A | appendix-a-audit-correction-prompt | 96 | 38 | UNACCEPTABLE_FOR_UNATTENDED_EXECUTION |
| B | appendix-b-optional-controlled-sms-canary-enablement-prompt | 98 | 40 | UNACCEPTABLE_FOR_UNATTENDED_EXECUTION |
| C | appendix-c-optional-controlled-sms-canary-activation-audit | 98 | 34 | UNACCEPTABLE_FOR_UNATTENDED_EXECUTION |

### Score summary

- Acceptable: **0**
- Conditional: **3**
- Unacceptable for unattended execution: **38**

The low confidence scores do **not** mean the prompt wording is poor. They reflect shared controller and runner defects that affect every stage. Prompts 034, 036, and Appendix C score especially low because their required trusted external evidence path does not yet exist. Appendix A also remains unsafe because its human authorization is not cryptographically enforced.

## Required promotion sequence

### P0 — Correct before any autonomous repository run

1. Remove the approval self-hash cycle and add an end-to-end approval test.
2. Make nonce consumption atomic across threads and processes.
3. Bind signed state to exact HEAD/tree, roadmap hash, prompt catalog, controller, schemas, and master prompt.
4. Enforce secure no-follow controller writes and reserve controller-owned paths.
5. Harden all Git operations against hooks, filters, helpers, signing, and hostile configuration.
6. Implement signed external-evidence ingestion and immutable registration.
7. Pin external-runner config/schema/keyring/adapter trust roots.
8. Require a real signed human authorization for Appendix A security-sensitive corrections.

### P1 — Correct before staging dry runs

1. Add anti-rollback anchoring for state and nonce journals.
2. Make path budgets aggregate and diff-based.
3. Snapshot only tracked and explicitly approved files.
4. Bound child output and evidence inode/file use.
5. Enforce signer-role separation and immutable adapter execution.
6. Correct rollback result semantics and create-once evidence.
7. Add strict deployment-plan, adapter-output, and result schemas.
8. Redact and cap all generated repository artifacts.

### P2 — Correct before production promotion

1. Hash-pin dependencies and trusted binaries.
2. Run adversarial security tests on a dedicated host and disposable repository.
3. Test all validation profiles using the actual Stage 004 stack.
4. Exercise staged recovery, provider failure, evidence ingestion, journal rollback, key rotation, and emergency stop procedures.
5. Perform an independent human review of the regenerated roadmap and every approval/capability/evidence binding.
6. Keep the external capability runner isolated from the autonomous controller and require human operation.

## Minimum promotion test matrix

Promotion should require passing tests for:

- approval creation, signing, verification, expiry, wrong commit, wrong environment, wrong policy hash, and replay;
- simultaneous nonce use from threads and independent processes;
- branch reset, force-push, roadmap mutation, prompt mutation, and stale audit state;
- symlinks at every controller-owned output ancestor and leaf;
- malicious Git hooks, filters, signing programs, fsmonitor, pagers, and config includes;
- ignored `.env`, credential, cache, and socket files in the worktree;
- infinite stdout/stderr, zero-byte file floods, deep paths, and oversized JSON;
- substituted external config/schema/keyring/adapter files;
- dual-role signer edge cases;
- adapter replacement between hash and execution;
- `FAILED`, `ROLLED_BACK`, partial apply, and evidence-write collision behavior;
- invalid, stale, mismatched, and replayed external evidence;
- Appendix A with absent, invented, expired, mismatched, or reused human authorization.

## Final recommendation

Keep the refined prompts. They are a strong basis for the project and should not be broadened.

Do **not** promote the supplied controller or external capability runner yet. Repair the P0 issues, regenerate the roadmap against the real repository, run the expanded adversarial test matrix, and repeat a focused promotion audit. Until then, preserve:

```json
{"safe_for_unattended_execution_now": false}
```
