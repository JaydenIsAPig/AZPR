# AZPR Security Remediation Pack Reassessment

**Assessment date:** 2026-07-23  
**Overall verdict:** **NOT ACCEPTABLE FOR UNATTENDED AUTONOMOUS EXECUTION**

## Executive summary

The remediation pack materially improves the wording and stage design of the original system. It fixes the audit-agent write/commit contradiction, supplies all three appendices, makes Appendix A explicit, moves Stages 031/033/035 toward read-only or plan-only behavior, adds named audit-gate concepts, and introduces policy hashing, signed-approval concepts, network-denied capabilities, and prompt-injection language.

However, the pack remains unsafe to integrate as an autonomous controller. The most serious defects are now implementation-level: approval keys are inherited by the Codex child, authoritative state and nonce consumption live in an unsigned gitignored directory writable from the workspace, required approvals can be bypassed with an empty file list, and the validation sandbox can read the host and write the repository. These defects can defeat the protections the pack claims to add.

No numbered prompt reaches the 85/85 execution threshold because no regenerated narrow roadmap, complete active schemas, stage-specific validation profiles, actual repository tree, or external capability runner was supplied. This does **not** mean the prompts are poor; most have high prompt-security scores. It means the pack as delivered cannot safely execute them.

## Scoring model

- **Security score:** quality of the prompt/control design, least-privilege intent, data protections, stop conditions, and side-effect boundaries.
- **Confidence score:** confidence the prompt can be executed safely and correctly using the supplied remediation pack.
- **Acceptable:** both scores at least 85 and no systemic blocker.

Numbered prompts: **0 acceptable, 23 conditional, 15 unacceptable**. Appendices: **0 acceptable, 0 conditional, 3 unacceptable**.

## Verified positive changes

- All 58 entries in `SHA256SUMS.json` matched the extracted files.
- The hardened prompt ZIP contained 38 numbered prompts and 3 appendices; all matched the unpacked copies exactly.
- All Python files compiled. The two included controller security tests passed.
- The hardened ZIP had no path-traversal entries and removed the prior `__MACOSX` clutter.
- Formal audit prompts now return report Markdown instead of writing/committing product files.
- Stages 031, 033, and 035 were substantially redesigned to reduce blast radius.

## Release-blocking findings

### CR-01 — Approval signing secrets are inherited by the Codex child process (CRITICAL)

A controlled agent or repository command can read approval keys, forge signatures, satisfy multiple key IDs, and place secrets into allowed files or logs even with network disabled.

**Evidence**
- controller.hardened.py:413-425 loads all HMAC verifier/signing secrets from AZPR_APPROVAL_KEYS_JSON.
- controller.hardened.py:1031-1070 invokes Codex without a sanitized env, so the child inherits the operator environment.

**Required remediation**

Use asymmetric signatures (for example Ed25519) so the controller holds public keys only. Launch Codex with a minimal isolated environment/HOME that excludes approval and operator secrets; keep signing in a separate process or hardware-backed operator tool.

### CR-02 — The authoritative controller state is unsigned, gitignored, and workspace-writable (CRITICAL)

State can be changed or deleted to forge completed stages, latest audit PASS, pending corrections, consumed nonces, or active branch data. Crash/kill paths can preserve tampered state.

**Evidence**
- controller.hardened.py:647-703 stores state under .codex-loop/state.json with no signature or reconstruction.
- controller.hardened.py:1628 explicitly declares that local state authoritative.
- Git path enforcement cannot see ignored .codex-loop changes.

**Required remediation**

Move runtime state outside the agent/validator writable workspace. Reconstruct gates from committed, signed audit/run records or use an append-only signed journal with atomic locking and strict permissions. Never treat mutable cache state as the root of trust.

### CR-03 — required_before_run can be bypassed with an empty approval list or zero quorum (CRITICAL)

A roadmap can claim approval is required while the controller executes the stage without any approval.

**Evidence**
- controller.hardened.py:867-872 checks only that approval keys exist, not that approval_files is non-empty or min_approvals is positive.
- controller.hardened.py:1677-1683 treats an empty approval_files list as automatically satisfied.

**Required remediation**

Fail when required_before_run=true unless approval_files is non-empty, min_approvals>=1, required_actions is non-empty, environment is valid, and required_key_ids/quorum are coherent. Enforce this in mandatory JSON Schema and duplicate it in controller code.

### CR-04 — Validation sandbox can read host secrets and mutate the repository (CRITICAL)

Repository-controlled tests/scripts can read SSH/cloud/browser credentials or process environments, alter code/tests, and have those changes committed as stage output.

**Evidence**
- run_sandboxed.py:14 preserves HOME.
- run_sandboxed.py:17 allows file-read* across macOS and file writes across the repository.
- run_sandboxed.py:20 read-binds the entire Linux host, exposes /proc and /dev, and makes the repository writable.

**Required remediation**

Run validation in a disposable clean worktree/container with the repository mounted read-only, an empty HOME, minimal system mounts, isolated PID/user/IPC/UTS namespaces, no host /proc, limited devices, CPU/memory/disk limits, and a separate artifact output directory. Fail on any repository mutation.

### CR-05 — Sandbox wrapper integrity has a time-of-check/time-of-use gap (CRITICAL)

An early validator can modify the wrapper or related scripts so later validation commands escape restrictions before the final diff check notices the change.

**Evidence**
- controller.hardened.py:390-411 policy_hashes does not include automation/security/run_sandboxed.py.
- Validation writes are permitted in the repository and path enforcement occurs only after all commands.

**Required remediation**

Place the runner outside the mutable repository or hash/verify it before every command. Execute validators from an immutable image/toolchain and compare the repository tree before and after every validation command.

### HI-01 — HMAC approvals do not enforce independent human signers or durable single use (HIGH)

One operator/process can impersonate every signer, and deleting/resetting state can replay an approval.

**Evidence**
- approval.schema.json supports HMAC signatures only.
- All verifier secrets are supplied together in AZPR_APPROVAL_KEYS_JSON.
- Consumed nonces exist only in mutable .codex-loop state.

**Required remediation**

Use asymmetric per-approver keys, external identity/attestation, an append-only consumed-nonce ledger, key revocation/rotation metadata, and policy requiring distinct signer identities for production.

### HI-02 — Approval schema does not bind the full consequential decision (HIGH)

An approval can be valid while the actual deployment plan, resources, recipients, or capability manifest differ.

**Evidence**
- approval.schema.json binds stage, commit, roadmap/prompt/master hashes, controller version, environment, and action strings only.
- It lacks plan hash, capability-manifest hash, AGENTS/config/schema/runner hashes, account/resource/cohort/window/cost/backup fields claimed in the remediation report.

**Required remediation**

Add typed, required bindings for plan/capability hashes, account/project/region, exact resources, database, hosts/methods, recipients/cohort, limits, window, backup/rollback point, evidence outputs, and all policy-root hashes.

### HI-03 — Path enforcement is bypass-prone and glob semantics are broader than they appear (HIGH)

Crafted filenames, rename syntax, or alternative globs can cause incorrect allowed/forbidden decisions and overbroad writes.

**Evidence**
- controller.hardened.py:211-223 parses newline-delimited porcelain output manually.
- A proof test parsed "allowed -> controller.py" as controller.py and escaped quoted/newline filenames.
- controller.hardened.py:226-228 uses fnmatch, where src/* matches nested paths.
- controller.hardened.py:957-966 rejects only a small exact denylist of broad patterns.

**Required remediation**

Use NUL-delimited git status/diff output, reject control characters and ambiguous names, define segment-aware glob semantics, expand patterns against the actual tree, reject excessive scope quantitatively, and inspect staged diff objects directly.

### HI-04 — Filesystem escape handling is incomplete (HIGH)

Writes can escape the intended repository or affect external files without appearing as changed product paths.

**Evidence**
- changed_symlinks checks changed paths only.
- Controller output directories and runtime paths are not checked for symlink ancestry.
- No hardlink, submodule, nested repository, or pre-existing symlink policy is enforced.

**Required remediation**

Preflight every writable path and ancestor with lstat/openat O_NOFOLLOW, reject writable symlinks/hardlinks/submodules/nested repos, and use a disposable copy or mount namespace rather than trusting repository topology.

### HI-05 — Audit correction semantics are not enforced by controller code (HIGH)

A compromised or mistaken audit can authorize arbitrary exact files for Appendix A, issue contradictory verdicts, or advance with malformed evidence.

**Evidence**
- controller.hardened.py:1456-1478 verifies only audit outcome/report presence.
- The result-schema security extension is an example that must be merged manually.
- PASS/PASS_WITH_REQUIRED_CORRECTIONS/BLOCKED consistency, report YAML, correction path scope, and handler eligibility are not cross-validated.

**Required remediation**

Make schema support mandatory and add controller-native semantic checks. Bind each correction to the audited commit, finding evidence, allowed path budget, severity, owner, acceptance criteria, and a signed human authorization when touching security-sensitive files.

### HI-06 — Merge reconciliation accepts unrelated commits (HIGH)

Additional unreviewed or malicious commits can be merged at the same time and the controller will still mark the stage complete and update audit gates.

**Evidence**
- controller.hardened.py:1869 only checks that the stage commit is an ancestor of HEAD.

**Required remediation**

Require a fast-forward to exactly the expected commit or verify an approved merge commit whose complete delta contains only the pending stage commit and explicitly reviewed merge metadata.

### HI-07 — Run manifests and SHA manifests provide no durable authenticity (HIGH)

After-the-fact evidence cannot prove which policies or artifacts actually governed a run.

**Evidence**
- Run manifests are written under mutable .codex-loop and are not signed or verified at completion.
- SHA256SUMS.json matches all 58 listed files but is itself unsigned and can be replaced with altered files.

**Required remediation**

Commit or externally attest signed run manifests, hash the validation toolchain and evidence, use unique run nonces, and publish the pack checksum/signature through a trusted channel.

### HI-08 — External capability and deployment evidence implementation is missing (HIGH)

Stages 033-036 and Appendices B/C cannot form a trustworthy plan-approve-apply-attest-audit chain.

**Evidence**
- EXTERNAL-CAPABILITY-RUNNER-SPEC.md explicitly says no runner implementation is provided.
- No typed deployment-plan/evidence schema is included; result-schema extension covers corrections only.

**Required remediation**

Implement and separately review the runner, typed manifests, evidence signatures, account/drift preflight, nonce consumption, target allowlists, rollback proof, and secure evidence ingestion before staging, production, email/SMS, geocoder, or recovery actions.

### HI-09 — Validation and audit evidence can be incomplete while schemas are optional (HIGH)

Malformed roadmaps/results/approvals or missing validation profiles can pass local checks, producing false assurance.

**Evidence**
- controller.hardened.py:720-727 silently skips JSON Schema validation when jsonschema is absent.
- The pack supplies only examples/fragments, not integrated active schemas.
- Only two controller security unit tests are included.

**Required remediation**

Vendor or require the schema validator, fail closed when unavailable, ship complete schemas, add extensive negative tests, and require non-empty stage-specific validation profiles for every risk category.

### HI-10 — Logs and controller-created records can retain sensitive or injected content (HIGH)

Secrets/PII may persist locally or in commits, and generated text can become a later prompt-injection source.

**Evidence**
- Codex stdout/stderr and full validator output are written without redaction.
- Runtime directory permissions are not hardened.
- Agent summary/remaining_risks and audit Markdown are committed without structural sanitization.

**Required remediation**

Use 0700/0600 permissions, redaction and size limits, structured fields, fenced/untrusted rendering, retention policies, and never pass raw generated prose back as authority.

### ME-01 — Prompt and policy naming still create operator ambiguity (MEDIUM)

Humans and automation may misunderstand whether a stage applies changes, and agents receive mixed terminology.

**Evidence**
- Files 031, 033, and 035 retain implementation/deploy-oriented filenames while their titles are now read-only audit or plan-only stages.
- Implementation prompts still say “Before committing” despite controller-owned commits.
- AGENTS allows external actions when a capability manifest authorizes them, while the autonomous capability schema always denies them.

**Required remediation**

Rename or clearly alias the files, use “before controller handoff,” and explicitly state that capability manifests are consumed only by the separate human-operated runner.

## Component scorecard

| Component | Security | Confidence | Verdict | Summary |
|---|---:|---:|---|---|
| Hardened numbered prompt pack | 91 | 65 | CONDITIONAL | Strong instruction-integrity, no-commit, read-only-audit, and plan-only rewrites; exact paths and controller enforcement are not integrated. |
| AGENTS.hardened.md | 90 | 70 | CONDITIONAL | Strong authority and untrusted-data policy; external capability wording and generated-authority ordering should be tightened. |
| controller.hardened.py | 48 | 42 | CRITICAL | Contains direct approval bypass, secret inheritance, mutable authoritative state, weak reconciliation, and incomplete audit/path enforcement. |
| run_sandboxed.py | 28 | 30 | CRITICAL | Network denial is useful, but host-wide reads, writable repository, HOME/proc/dev exposure, and mutable runner make it unsafe for hostile repository code. |
| Approval schema and signing tools | 42 | 36 | CRITICAL | HMAC/shared-secret design, incomplete decision binding, mutable nonce ledger, and child secret exposure defeat claimed two-person/single-use guarantees. |
| Capability policy schema | 90 | 58 | UNACCEPTABLE | Autonomous default deny is correct, but only local/test is modeled and no external apply manifest/evidence schema or runner is implemented. |
| Audit/result schema extension | 68 | 42 | UNACCEPTABLE | Useful correction fields, but only a fragment/example and no controller semantic cross-check. |
| External capability runner specification | 92 | 25 | UNACCEPTABLE | The specification is directionally strong; there is intentionally no implementation to review or use. |
| Pack integrity manifest | 94 | 75 | CONDITIONAL | All 58 listed hashes verified and prompt ZIP matched local files, but the manifest has no trusted signature/authenticity. |
| Controller security tests | 35 | 25 | CRITICAL | Only two tests exist; they do not cover the identified approval, environment, state, path parsing, merge, sandbox, evidence, or schema failures. |

## Numbered prompt scorecard

| ID | Prompt | Security | Confidence | Verdict | Main remaining concern |
|---:|---|---:|---:|---|---|
| 001 | Close the Post-Core Traceability Release Gate | 90 | 72 | CONDITIONAL | Traceability, provenance, privacy, and no-commit controls are strong. Safe execution still depends on a regenerated exact cross-layer path set and on fixing controller state, validation, and approval boundaries. |
| 002 | Post-Core Traceability Corrective Audit | 96 | 74 | CONDITIONAL | The read-only audit/report handoff contradiction is fixed. The controller still does not semantically validate correction payloads, report YAML, or audit-index integrity, and audit state is mutable. |
| 003 | Define and Govern the Narrow Pilot Scope | 92 | 77 | CONDITIONAL | The scope gate is well constrained and avoids silent activation. Exact files, approval values, and runtime activation controls are absent because no remediated roadmap was supplied. |
| 004 | Select and Govern the Production Application Stack | 94 | 75 | CONDITIONAL | The architecture decision prompt is appropriately decision-first and implementation-light. Confidence is limited by weak approval enforcement and lack of an authenticated research/dependency evidence channel. |
| 005 | Bootstrap the Production Application Shell and Engineering Baseline | 84 | 61 | CONDITIONAL | The prompt correctly limits product behavior, but bootstrapping can alter dependencies, CI, scanners, scripts, and configuration. No exact remediated path list, SBOM/signature policy, or safe validator boundary is supplied. |
| 006 | MVP Scope and Architecture Decision Audit | 96 | 74 | CONDITIONAL | Read-only audit ownership is corrected. The remaining audit-result, correction, state-integrity, and validation-sandbox defects prevent reliable gating. |
| 007 | Design and Implement the Durable Database Schema and Migrations | 87 | 64 | CONDITIONAL | Migration safeguards and customer-keyed constraints are strong. Exact database/migration-tool paths, isolated immutable migration validation, and protection from destructive validator code remain unresolved. |
| 008 | Implement Durable Repositories and Transaction Boundaries | 87 | 66 | CONDITIONAL | Repository/UoW and concurrency requirements are good. The pack lacks architecture-specific paths and a safe database/concurrency validation profile. |
| 009 | Implement Immutable Artifact Storage, Outbox, Workers, and Crash Recovery | 86 | 63 | CONDITIONAL | Artifact, outbox, lease, retry, and reconciliation requirements are strong. Storage-provider decisions, exact worker/reconciliation paths, resource limits, and safe execution evidence remain unresolved. |
| 010 | Durable Platform and Persistence Audit | 96 | 72 | CONDITIONAL | The audit contract is fixed and the evidence list is strong. Audit semantics and persistence validation are not reliably enforced by the supplied controller/schema set. |
| 011 | Implement Authentication, Session Security, and AccessContext Construction | 89 | 55 | UNACCEPTABLE | The prompt has strong authentication and anti-enumeration requirements. It remains unsafe under a controller that exposes inherited environment secrets, uses mutable local state, and lacks exact auth-only paths. |
| 012 | Implement Customer Account Lifecycle, Versioned Configuration, and Onboarding API | 89 | 64 | CONDITIONAL | PII minimization, versioned configuration, consent, and retention stops are good. The transport/schema paths and approved deletion/anonymization policy are not concretely bound. |
| 013 | Identity, Authorization, and Customer-Isolation Audit | 97 | 71 | CONDITIONAL | The audit prompt is strong and read-only. Trust still depends on mutable controller state, unvalidated corrections, and unsafe validator isolation. |
| 014 | Select and Approve the First Tucson or Pima County Production Source | 90 | 61 | CONDITIONAL | The legal/source-access decision gate is careful. Autonomous networking is denied, so current source evidence must be supplied through a trusted, hashed channel that the pack does not define. |
| 015 | Implement Durable Scheduled Acquisition and the Approved Live Connector | 86 | 58 | UNACCEPTABLE | The connector prompt is disciplined and can use offline fixtures, but exact source profile, scheduler/worker paths, host/method/response limits, and approved-source evidence are not integrated. |
| 016 | Implement the Production Source Parser, Replay, and Backfill Contract | 91 | 68 | CONDITIONAL | The parser/replay prompt is comparatively narrow and provenance-aware. Backfill resource ceilings, exact schema paths, and stage-specific validation are still missing. |
| 017 | Implement Required Production Geography and Address Resolution | 89 | 61 | CONDITIONAL | Conditional geocoder/provider handling and provenance are strong. Exact adapter paths, provider licensing/retention approvals, and authenticated external evidence are not supplied. |
| 018 | Pilot Source, Ingestion, Normalization, and Geography Audit | 96 | 70 | CONDITIONAL | Read-only source/geography audit design is strong. Controller audit-state, evidence, correction, and validator defects remain gating risks. |
| 019 | Implement the Authorized Customer API and Query Projections | 91 | 63 | CONDITIONAL | Authorization-from-Customer-Match and anti-enumeration intent are strong. The selected transport/OpenAPI paths and stack-specific security tests are unresolved. |
| 020 | Build the Authenticated Frontend Foundation and Onboarding Experience | 88 | 59 | UNACCEPTABLE | The frontend prompt is safety-conscious, but the pack provides no mandatory frontend type/lint/build/browser/accessibility profile or exact dependency/lockfile paths. |
| 021 | Build the Explainable Opportunity Dashboard and Lead Workflow | 90 | 61 | CONDITIONAL | The UI is correctly treated as non-authoritative and customer-scoped. Browser/E2E/accessibility validation and exact frontend/API contract paths remain absent. |
| 022 | Customer API, Frontend, and Data-Exposure Audit | 97 | 70 | CONDITIONAL | The data-exposure audit is strong and read-only. Its PASS cannot be trusted until audit evidence, state, corrections, and validation are hardened. |
| 023 | Implement Email Notification Orchestration and Delivery | 88 | 54 | UNACCEPTABLE | Consent, outbox idempotency, and provider-neutral design are good. The external runner is absent, provider/webhook evidence is not schema-bound, and exact transport paths are unresolved. |
| 024 | Email Delivery Audit | 96 | 67 | CONDITIONAL | The email audit prompt is strong. Provider delivery facts and webhook evidence lack an authenticated, hashed ingestion and attestation path. |
| 025 | Implement Controlled SMS Infrastructure Behind a Disabled Feature Flag | 90 | 49 | UNACCEPTABLE | Disabled-by-default SMS, consent, STOP/HELP, quiet-hours, and idempotency controls are strong. Approval quorum is not independently enforced, the runner is absent, and the legal/cost blast radius remains high. |
| 026 | Build Internal Review and Source Operations Tooling | 88 | 55 | UNACCEPTABLE | The internal-operations prompt contains strong privilege and audit expectations. Exact RBAC/transport paths, dual control for destructive operations, and raw-evidence access enforcement are not bound. |
| 027 | Notification, SMS, and Operations Audit | 97 | 67 | CONDITIONAL | The notification/SMS/operations audit is strong. The same mutable state, evidence, corrections, and validator issues prevent reliable PASS gating. |
| 028 | Implement the Privacy-Conscious Analytics Event Model | 91 | 63 | CONDITIONAL | Privacy-conscious event design is strong. Exact taxonomy/retention paths and any analytics-vendor approval/evidence boundary are unresolved. |
| 029 | Implement Observability, Health, Alerting, and Operational Runbooks | 88 | 53 | UNACCEPTABLE | Redaction, bounded cardinality, and truthful readiness are explicit. Observability can touch most of the system and leak data; exact paths and a secret-safe validator are absent. |
| 030 | Implement Backup, Restore, Reconciliation, and Rollback Procedures | 89 | 45 | UNACCEPTABLE | The prompt requires isolated restore and provenance-preserving reconciliation. The supplied validator can read the host and write the repository, and no recovery capability runner or signed restore-evidence schema exists. |
| 031 | Security, Privacy, Performance, and Recovery Hardening Audit | 97 | 68 | CONDITIONAL | The dangerous mega-hardening stage was correctly replaced by a read-only audit. Correction authorization, mutable runtime state, and unsafe validation remain; the legacy filename still implies implementation. |
| 032 | Formal Pilot Release Test Matrix and Release Gate Audit | 97 | 58 | UNACCEPTABLE | The release matrix is comprehensive. The pack does not supply the mandatory stage-specific validation commands, so the controller can still lack the evidence needed for a trustworthy PASS. |
| 033 | Prepare the Controlled Staging Deployment Plan | 93 | 55 | UNACCEPTABLE | Plan-only staging is a major improvement. No machine-validated deployment-plan schema, implemented capability runner, signed evidence chain, or safe approval enforcement is supplied; the filename still says execute. |
| 034 | Final Staging and Pilot Readiness Audit | 97 | 52 | UNACCEPTABLE | The staging audit is strong and correctly limits its authority. There is no authenticated staging-evidence ingestion or plan/apply attestation mechanism. |
| 035 | Prepare the Controlled Production Pilot Release Plan | 94 | 45 | UNACCEPTABLE | Plan-only production and two-person intent are major improvements. HMAC key handling does not enforce independent humans, approval fields do not bind the full plan/account/resources, and the runner is absent; the filename still says deploy. |
| 036 | Production Pilot Launch Verification Audit | 97 | 48 | UNACCEPTABLE | The production verification audit is strong in content. Production facts have no implemented trusted evidence channel or signed attestation chain. |
| 037 | Implement Pilot Feedback and Business Validation Workflow | 89 | 52 | UNACCEPTABLE | Customer-owned feedback, version binding, and negative-outcome retention are strong. Exact privacy/retention/transport paths and a human-approved pilot snapshot are not bound. |
| 038 | Pilot Feedback and Business Validation Audit | 97 | 54 | UNACCEPTABLE | The final audit is rigorous. Snapshot authenticity, reproducible evidence, correction semantics, and controller state/index integrity are unresolved. |

## Appendix scorecard

| Appendix | Security | Confidence | Verdict | Main remaining concern |
|---|---:|---:|---|---|
| A | 89 | 35 | UNACCEPTABLE | The prompt is now narrow and explicit, but correction paths are taken from agent output stored in unsigned, writable local state. A typed confirmation is not a cryptographic authorization. |
| B | 92 | 40 | UNACCEPTABLE | The prompt correctly denies provider calls and sending. Safe activation still depends on a missing external runner and an approval model whose HMAC keys/quorum can be compromised or replayed through mutable state. |
| C | 96 | 43 | UNACCEPTABLE | The audit is read-only and thorough, but the provider/deployment evidence channel, activation attestation, and controller audit-state integrity are not implemented. |

## Highest-priority correction order

1. Replace HMAC/shared-secret approval verification with asymmetric public-key verification and isolate all child environments.
2. Move controller state and nonce consumption outside the agent/validator workspace and make gating reconstructible from signed committed evidence.
3. Fix required-approval empty-list/zero-quorum bypasses and enforce complete mandatory schemas.
4. Replace the validation wrapper with a disposable read-only repository sandbox that cannot read host secrets.
5. Implement NUL-safe diff/path parsing, segment-aware glob rules, and full symlink/hardlink/submodule protection.
6. Add controller-native semantic validation for audit verdicts, corrections, report headers, and Appendix A scope.
7. Require exact-commit/approved-merge reconciliation with no unrelated commits.
8. Implement and separately audit the external capability runner plus typed plan/evidence manifests.
9. Regenerate the roadmap against the actual repository with exact paths and complete stage-specific validation profiles.
10. Expand security tests to cover every fail-closed control and identified bypass.

## Important implementation nuances

- **The pack correctly labels itself not integrated.** Preserve that fail-closed status; do not reinterpret the presence of hardened files as authorization to copy them directly into production.
- **Prompt design and controller safety are different layers.** The prompts are generally much better, while the controller and sandbox still contain exploitable trust-boundary errors.
- **A confirmation phrase is not approval.** Appendix A, roadmap promotion, abandonment, and appendix locks need stronger operator identity and signed intent for consequential actions.
- **Read-only audits still execute code.** Tests, package scripts, parsers, and build tools must run in a hostile-code sandbox with a read-only repository and no host secrets.
- **Exact paths must be generated from the real post-Stage-004 tree.** Permanently broad globs are unsafe, but permanently guessed narrow paths can force wrong-layer implementation.
- **Deployment audits require authenticated evidence.** Screenshots, logs, provider responses, and generated reports must be hashed, signed, target-bound, and treated as evidence—not instructions.
- **The filenames for 031/033/035 should be renamed or explicitly aliased.** Their current names still suggest hardening implementation or deployment execution even though their content is audit/plan-only.

## Final decision

**Do not promote or run the remediation pack unattended.** First correct the controller, approval, state, sandbox, path, audit-result, and merge-integrity defects; implement the external capability runner and evidence schemas; then regenerate the roadmap and repeat this reassessment against the actual repository and active configuration.
