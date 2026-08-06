# AZ Permit Radar Autonomous Roadmap Security Consultation

**Assessment basis:** `roadmap.proposed.json`, the 38 numbered prompts in `markdown-prompts.zip`, and the AZ Permit Radar Master Operating Prompt. The assessment evaluates control-plane safety and path sufficiency; it is not a source-code security audit of the repository itself.

## Executive verdict

**The roadmap is not safe enough for unattended autonomous execution in its current form.** The product-governance language is strong, but several controller-level controls are missing or contradictory. Only **3 of 38 numbered stages** meet the report threshold without changes; **22 are conditional** and **13 are unacceptable**. Appendix A is a critical blocker.

Scoring: **Security** measures least-privilege and blast-radius control. **Execution confidence** measures the likelihood that the prompt can complete correctly under the listed paths, approvals, sandbox, and validation. A stage is acceptable only when both scores are at least 85 and no critical control defect exists.

## Release-blocking findings

### Validation false assurance
Every numbered stage and appendix has only `python3 -m unittest discover -s tests -v` in the controller validation block. Frontend, package build, type/lint, migration, security, IaC, container, browser/E2E, accessibility, performance, restore, and rollback evidence can therefore be absent while the controller still marks validation complete.

### Audit sandbox contradiction
Audit prompts explicitly require creation of `docs/audits/...`, index updates, and a git commit, while the roadmap gives `read-only`, empty allowed paths. Notes say the controller materializes reports, but the prompt text tells the agent to write. This must be a single, unambiguous contract.

### Appendix A control bypass
Appendix A is included in normal execution, needs no explicit invocation or approval, has no hard lock, and allows nearly the entire repository. Its prompt is missing from the supplied pack. A PASS_WITH_REQUIRED_CORRECTIONS result could therefore open a broad correction channel that defeats stage isolation.

### External side effects are not capability-gated
Stages 14, 15, 17, 23, 25, 33, and 35 can access external sources/providers/cloud environments. Allowed paths constrain files, not HTTP destinations, cloud accounts, DNS, database targets, email/SMS recipients, or destructive API actions.

### Approvals are replayable and weakly bound
Approval files are named but no required schema, signature, expiration, nonce, approver quorum, target commit, roadmap hash, prompt hash, environment, cohort, or allowed-action list is specified.

### Prompt and policy integrity are not pinned
The roadmap references a controller-supplied Master Operating Prompt and prompt files without content hashes. A changed prompt, roadmap generator, or master prompt can alter behavior without changing the stage ID.

### High-risk broad write stages
Stages 005, 011, 023, 025, 026, 029, 030, 031, 033, 035, and 037 have either excessive repository reach or dangerous external authority. Stage 031 is especially incompatible with the one-coherent-change model.

### Required transport paths are missing
Stages 019, 023, 025, 026, and 037 require APIs or webhooks but do not include the actual transport/router path unless the approved architecture happens to place it under `infrastructure`. This can force wrong-layer implementation or incompleteness.

## Positive controls worth retaining

- Maximum one numbered stage per normal run.
- Consistent prohibition on `.git/**`, `.codex-loop/**`, `automation/**`, `.env`, `secrets/**`, and agent-written formal audit history.
- Explicit stage prerequisites, formal audit gates, immutable raw evidence, idempotency, provenance, customer isolation, deterministic-first logic, and stop conditions.
- Docs/ADR/runbook reconciliation and separate audit commits as a governance concept.
- Production SMS is intended to remain disabled until a later canary path.

## Numbered-stage scorecard

| ID | Stage | Security | Confidence | Verdict | Access decision | Main issue |
|---:|---|---:|---:|---|---|---|
| 001 | Close the Post-Core Traceability Release Gate | 76 | 82 | CONDITIONAL | Narrow after preflight; no broader generic access | Cross-layer traceability work can justify several modules, but three whole source layers plus all tests permit unrelated changes. Add docs/adr/** only when the pre-change report proves an ADR is required. |
| 002 | Post-Core Traceability Corrective Audit | 93 | 72 | CONDITIONAL | Fix audit materialization contract | Product read-only is strong, but the prompt orders the agent to create docs/audits files and commit while the roadmap grants no write paths and a read-only sandbox. Make the agent return a report payload and let the controller write/commit, or grant only the exact report and index paths. |
| 003 | Define and Govern the Narrow Pilot Scope | 88 | 88 | ACCEPTABLE | Keep; narrow tests where practical | The named domain files and governed documentation fit pilot-scope decisions. Runtime activation remains approval-sensitive. No broader write access is justified. |
| 004 | Select and Govern the Production Application Stack | 95 | 93 | ACCEPTABLE | Keep docs-only | This is a decision gate and correctly excludes implementation code. ADR/current/log/runbook access is appropriate. |
| 005 | Bootstrap the Production Application Shell and Engineering Baseline | 62 | 86 | UNACCEPTABLE | Narrow CI, scripts, config, and source paths | src/**, scripts/**, config/**, and .github/** allow broad code, workflow, and supply-chain changes. Restrict to the approved composition root, health/config modules, validation scripts, and exact CI workflow files. |
| 006 | MVP Scope and Architecture Decision Audit | 93 | 72 | CONDITIONAL | Fix audit materialization contract | Same read-only-versus-report-write/commit contradiction as Stage 002. |
| 007 | Design and Implement the Durable Database Schema and Migrations | 76 | 78 | CONDITIONAL | Narrow persistence modules; allow exact migration config if needed | The stage may need a selected migration-tool config file not listed. Whole domain and infrastructure globs are broader than schema/mapping work requires. Bind paths to the approved Stage 004 stack. |
| 008 | Implement Durable Repositories and Transaction Boundaries | 74 | 84 | CONDITIONAL | Narrow to repositories, UoW, transaction adapters, and exact migrations | Whole application/domain/infrastructure trees exceed the repository/transaction scope. Add docs/schema/** only if this stage legitimately changes the approved schema. |
| 009 | Implement Immutable Artifact Storage, Outbox, Workers, and Crash Recovery | 70 | 82 | CONDITIONAL | Narrow to artifact, outbox, worker, and reconciliation modules | config/** and whole application/domain/infrastructure trees are too broad. Permit one exact reconciliation command location if the repository convention requires it. |
| 010 | Durable Platform and Persistence Audit | 93 | 72 | CONDITIONAL | Fix audit materialization contract | Same audit-control contradiction; validation also needs persistence, migration, and concurrency profiles beyond the single unit command. |
| 011 | Implement Authentication, Session Security, and AccessContext Construction | 58 | 88 | UNACCEPTABLE | Strongly narrow auth/session/middleware paths | An authentication stage with src/** and config/** can alter unrelated authorization, domain, notification, or deployment behavior. Limit it to verified-claim middleware, AccessContext, session/auth adapters, config/auth/**, exact migrations, and security tests. |
| 012 | Implement Customer Account Lifecycle, Versioned Configuration, and Onboarding API | 76 | 78 | CONDITIONAL | Narrow customer modules; add exact API-contract and ADR paths | Versioned request/response contracts are required, but openapi/** or the approved transport-contract path is absent. docs/adr/** may be needed for retention/anonymization decisions. |
| 013 | Identity, Authorization, and Customer-Isolation Audit | 93 | 72 | CONDITIONAL | Fix audit materialization contract | Read-only is appropriate, but report creation and commit ownership must be made controller-only and machine-verifiable. |
| 014 | Select and Approve the First Tucson or Pima County Production Source | 80 | 84 | CONDITIONAL | Keep write scope; add network read policy and exact registry tests | Write access is narrow, but source comparison can involve live external access. Enforce destination allowlists, read-only HTTP methods, response-size limits, and no credentials. The single named test file may be under-inclusive. |
| 015 | Implement Durable Scheduled Acquisition and the Approved Live Connector | 78 | 76 | CONDITIONAL | Add exact scheduler/worker and manual-replay paths; narrow everything else | The task includes scheduling, leases, and manual reprocessing, but only acquisition-specific files are allowed. This may force code into the wrong layer unless exact existing worker/command modules are added. |
| 016 | Implement the Production Source Parser, Replay, and Backfill Contract | 87 | 88 | ACCEPTABLE | Keep; add schema docs only if contract changes | The source-specific parser paths are focused and replay/backfill remains bounded. New dependencies should require a separate approved path change. |
| 017 | Implement Required Production Geography and Address Resolution | 82 | 78 | CONDITIONAL | Add docs/schema/** and only an approved provider-adapter path | Geography provenance can change schema documentation. If an external geocoder is approved, the exact adapter/transport path should be added rather than widening infrastructure generally. |
| 018 | Pilot Source, Ingestion, Normalization, and Geography Audit | 93 | 72 | CONDITIONAL | Fix audit materialization contract | Read-only safety is good; report write/commit and complete source/geography validation remain unresolved. |
| 019 | Implement the Authorized Customer API and Query Projections | 68 | 66 | UNACCEPTABLE | Add the exact API transport/router path; narrow application/infrastructure | The prompt must expose endpoints, but the roadmap omits the transport layer created by Stage 005 unless it happens to live under infrastructure. This can force architecture leakage or make completion impossible. |
| 020 | Build the Authenticated Frontend Foundation and Onboarding Experience | 69 | 72 | UNACCEPTABLE | Keep frontend subtree, permit only the selected package manager and exact config files | All major lockfiles are writable and validation contains no frontend lint/type/build/test command. Dependency and package-script execution need supply-chain controls. |
| 021 | Build the Explainable Opportunity Dashboard and Lead Workflow | 78 | 76 | CONDITIONAL | Keep frontend scope; make dependency files read-only unless explicitly needed | Dashboard work is focused, but broad tests and writable package/lock files allow unrelated dependency changes. The roadmap lacks browser, accessibility, build, and end-to-end validation. |
| 022 | Customer API, Frontend, and Data-Exposure Audit | 93 | 72 | CONDITIONAL | Fix audit materialization contract | Data-exposure auditing is correctly read-only, but the controller/report contract and full API/UI security test profile must be explicit. |
| 023 | Implement Email Notification Orchestration and Delivery | 54 | 74 | UNACCEPTABLE | Require provider approval file; add exact webhook route; narrow notification modules | Email introduces customer data, external delivery, reputation, webhooks, and cost, yet no machine-enforced provider approval exists. The transport path for verified webhooks is also absent. |
| 024 | Email Delivery Audit | 93 | 72 | CONDITIONAL | Fix audit materialization contract | The dedicated audit is valuable, but its immutable report and commit must be controller-owned and provider evidence must be authenticated. |
| 025 | Implement Controlled SMS Infrastructure Behind a Disabled Feature Flag | 48 | 72 | UNACCEPTABLE | Require provider approval and immutable disabled-by-default enforcement | SMS has legal/consent/cost exposure. The prompt says approval is required, but the roadmap has no approval file. Add an exact webhook route and CI policy proving production enrollment/sending cannot be enabled in this stage. |
| 026 | Build Internal Review and Source Operations Tooling | 58 | 72 | UNACCEPTABLE | Narrow privileged operations and add exact internal transport/domain paths | This stage creates highly privileged review, reprocessing, merge, source-disable, and retry capabilities. Broad app/infra access plus no explicit internal API route and domain paths creates cross-tenant and evidence-destruction risk. |
| 027 | Notification, SMS, and Operations Audit | 93 | 72 | CONDITIONAL | Fix audit materialization contract | Audit separation is good; controller-only report materialization and complete notification/operations validation are required. |
| 028 | Implement the Privacy-Conscious Analytics Event Model | 74 | 82 | CONDITIONAL | Narrow to analytics-event modules and registry | Whole domain/application/infrastructure access is unnecessary for server-side event emission and increases privacy risk. External analytics integration should require its own approval artifact. |
| 029 | Implement Observability, Health, Alerting, and Operational Runbooks | 58 | 78 | UNACCEPTABLE | Narrow to instrumentation middleware, health, alert rules, and runbooks | src/** and ops/** are excessively broad for observability. A mistake can leak PII/secrets into logs, expose health internals, or create unbounded metric cardinality and cost. |
| 030 | Implement Backup, Restore, Reconciliation, and Rollback Procedures | 52 | 75 | UNACCEPTABLE | Remove migration write access by default; separate authoring from destructive recovery execution | Backup/restore code is inherently dangerous. src/**, ops/**, and migrations/** permit unrelated or destructive changes. Recovery execution needs a separate approval and environment capability gate. |
| 031 | Perform Security, Privacy, Performance, and Recovery Hardening | 35 | 80 | UNACCEPTABLE | Redesign as read-only audit plus per-finding correction stages | This mega-stage can modify almost the whole repository, dependencies, deployment, configuration, migrations, tests, and workflows. It defeats narrow-stage governance and can hide control weakening inside a hardening commit. |
| 032 | Formal Pilot Release Test Matrix and Release Gate Audit | 93 | 68 | CONDITIONAL | Fix audit contract and encode the full release matrix | The read-only gate is conceptually strong, but the roadmap runs only Python unittest despite requiring frontend, E2E, migration, security, performance, restore, and rollback evidence. |
| 033 | Prepare and Execute the Controlled Staging Deployment | 62 | 74 | UNACCEPTABLE | Add staging account/environment capability manifest and plan/apply split | Filesystem paths are focused, but they do not constrain cloud, DNS, email sandbox, database, or secret side effects. Pin the staging account, region, resource set, commit, and approved actions. |
| 034 | Final Staging and Pilot Readiness Audit | 93 | 68 | CONDITIONAL | Fix audit contract and verify immutable staging evidence | The readiness audit is safe only if staging evidence is signed, environment-bound, and controller materialization is explicit. |
| 035 | Deploy the Controlled Production Pilot | 42 | 70 | UNACCEPTABLE | Require two-person production approval, target pinning, plan/apply split, and canary | Production deployment can migrate data, change providers, enable schedules, and enroll users. Path controls cannot prevent wrong-account deployment, duplicate alerts, or destructive changes. |
| 036 | Production Pilot Launch Verification Audit | 93 | 68 | CONDITIONAL | Fix audit contract and authenticate production evidence | Read-only verification is appropriate, but production facts must come from trusted, signed deployment/monitoring evidence rather than self-reported agent output. |
| 037 | Implement Pilot Feedback and Business Validation Workflow | 65 | 70 | UNACCEPTABLE | Narrow feedback modules; add exact API/OpenAPI path and retention approval | The stage spans all backend layers, frontend, migrations, and analytics. The transport path is missing, and optional free text/customer outcomes create privacy and cross-customer risks. |
| 038 | Pilot Feedback and Business Validation Audit | 93 | 68 | CONDITIONAL | Fix audit contract and bind the approved review snapshot | The final audit is read-only, but the approval snapshot, evidence, report, and audited commit need cryptographic binding and controller-only materialization. |

## Appendix scorecard

| Appendix | Security | Confidence | Verdict | Required action | Main issue |
|---|---:|---:|---|---|---|
| A — Audit Correction Prompt | 20 | 45 | CRITICAL | Disable until prompt exists and derive a per-finding allowlist | Appendix A is included in normal execution, requires no explicit invocation or approval, has no hard lock, and can change nearly the entire repository including deploy and CI. Its prompt file is absent from the supplied prompt pack, so its behavior cannot be cross-checked. |
| B — Optional Controlled SMS Canary Enablement Prompt | 52 | 55 | UNACCEPTABLE | Keep disabled; enable hard lock and exact canary capability scope | Approvals and explicit invocation are present, but the hard lock is disabled by default, the prompt is absent from the pack, and write access is broad across backend/frontend/migrations/dependencies. Activation must be cohort/window/provider/account bound. |
| C — Optional Controlled SMS Canary Activation Audit | 90 | 55 | CONDITIONAL | Keep read-only; supply and verify the missing prompt | Read-only scope is appropriate, but the referenced prompt is absent and the same report-write/commit ambiguity applies. |

## Required controller redesign before autonomous execution

### Cryptographically bind every run
Create a run manifest containing the SHA-256 of the roadmap, exact numbered prompt, Master Operating Prompt, repository HEAD, prior audit, approval files, selected validation profile, and controller version. Refuse execution on any mismatch.

### Use signed, scoped approvals
Approval JSON should include stage ID, target commit, environment/account, approved external actions, providers/hosts, feature flags, cohort/recipients, issued/expiry times, nonce, approver identities, quorum, and signatures. Mark approvals consumed after use.

### Separate file permissions from external capabilities
For each stage, define network egress hosts and methods, cloud account/project, database target, provider mode, recipient restrictions, secret names, and destructive-action permissions. Default deny.

### Generate path allowlists after inspection
The agent should first return a machine-readable pre-change plan. A policy engine or human should approve exact files/directories derived from the current repository and prior ADR, then restart the write phase with that narrower allowlist. Never let the agent self-expand access.

### Encode stage-specific validation profiles
Backend, frontend, migration, security, infrastructure, deployment, and audit stages need different mandatory commands. Results should be captured as immutable artifacts with exit codes and hashes. Missing categories must cause BLOCKED unless explicitly approved as not applicable.

### Make audits truly independent
Run audits with a separate identity/context, no product write capability, and no deployment credentials. The auditor returns a structured report; the controller writes the immutable report and signed index entry. Gate on the audited commit and audit type, not merely “latest formal”.

### Split dangerous stages
Replace Stage 031 with a read-only security/privacy/performance/recovery audit, then create one correction stage per approved finding with exact paths. Split Stages 033 and 035 into plan, approval, apply, and verification phases.

### Protect tests and dependencies
Reject increased skips, deleted assertions, reduced coverage, or changed test discovery without approval. New dependencies require registry allowlisting, lockfile consistency, license review, SBOM update, vulnerability scan, and no unreviewed install scripts.

### Harden path enforcement
Resolve real paths, reject symlinks/hardlinks/submodule escapes, normalize case, reject archive traversal, and compare the final git diff against the approved allowlist. Ignore `__MACOSX` metadata in prompt archives.

### Defend against prompt injection
Treat repository documents, municipal records, raw artifacts, HTML, PDFs, CSV cells, logs, and provider responses as untrusted data, never as instructions. Run parsers and package scripts in an ephemeral no-secret sandbox with resource and network limits.

## Catastrophe scenarios if unchanged

- Stage 031 modifies authentication, deployment, dependencies, migrations, and tests in one commit; a weakened test suite still passes the sole controller command.
- Stage 035 targets the wrong cloud account or database, applies a destructive migration, enables schedules, and sends duplicate emails to real users because external actions are not environment-bound.
- Stage 025 integrates or accidentally activates an SMS provider without a machine-enforced provider approval, causing consent violations, opt-out failures, cost, and reputational/legal exposure.
- Stage 026 exposes raw source artifacts or cross-customer records through an internal tool, or performs an irreversible merge/retry action without independent authorization.
- Stage 030 runs a restore or rollback command against production rather than an isolated target, overwriting current state or breaking provenance links.
- A malicious municipal record, README, issue text, fixture, or provider response contains prompt-injection instructions that the autonomous agent follows while it has write or deployment credentials.
- A stale approval file is replayed against a newer commit, prompt, provider, cohort, or environment because approvals are not signed and content-bound.
- A symlink inside an allowed directory points to `automation/`, `.git/`, secrets, or another protected location and bypasses string-based glob checks.

## Implementation nuances

- Overly narrow paths can be as dangerous as broad paths: they may force code into the wrong architectural layer. The correct answer is a two-phase dynamic allowlist tied to the actual repository, not permanently broad globs.
- Document governance legitimately touches current, legacy, and log directories, but a structural checker should enforce exactly one current version, valid links, and synchronized versions.
- A read-only audit can execute tests that write caches, coverage files, temporary databases, or generated artifacts. Run audits in an ephemeral copy and verify the repository diff remains limited to controller-created audit files.
- “Latest formal PASS” is insufficient when several audit types exist. Each stage should require a named audit slug, audited commit, and predecessor chain.
- The Master Operating Prompt is a valuable policy layer, but because it is controller-supplied and not repository-pinned, it currently represents a mutable root of trust.
- Confidence scores are lower where the approved Stage 004 architecture and actual repository tree determine the correct transport, migration, worker, and frontend paths.

## File-integrity observations

- Numbered prompt files missing from the supplied pack: `[]`.
- Appendix prompt files referenced by the roadmap but missing from the supplied pack: `['appendix-a-audit-correction-prompt.md', 'appendix-b-optional-controlled-sms-canary-enablement-prompt.md', 'appendix-c-optional-controlled-sms-canary-activation-audit.md']`.
- The ZIP contains `__MACOSX/` metadata entries; extraction logic should ignore them and reject path traversal.
- Supplied-file SHA-256 values:
  - `roadmap.proposed.json`: `30c858b8ec02a2e6dae94a991395e1c0baabbf4b65bcf07e25d8dc30334f18c7`
  - `markdown-prompts.zip`: `67fe18e625209d860eedcfdde40f0161b1a57efa1f060381105a30e4edb0cb15`
  - `AZ Permit Radar Master Operating Prompt(2).docx`: `37800ebde204070d1ac20c2cfff5c809ee4f318cfcc44312514c393077334ae6`

## Final decision

**Do not promote this roadmap to unattended autonomous execution yet.** First fix the controller validation model, audit write contract, Appendix A, approval integrity, prompt hashing, external capability policies, and the unacceptable stages listed above. After those changes, regenerate the roadmap and rerun this consultation against the actual repository tree and selected architecture.