Effort Level: Extra High

BEGIN PROMPT

You are the implementation agent for AZ Permit Radar. Execute this task as one controlled, reviewable change within the existing domain-driven modular monolith.

REQUIRED PREDECESSOR
- Governing audit: Prompt 32 Formal Pilot Release Test Matrix and Release Gate Audit with result PASS.
- Required predecessor evidence: Prompt 32 audit commit and explicit authorization for staging deployment.
- Confirm the repository is at the intended committed HEAD and the worktree contains no unrelated changes before editing.

MANDATORY SOURCE AND STATE INSPECTION
Before editing, inspect the repository rather than assuming supplied filenames or version numbers remain current. Read:
- README.md.
- The AZ Permit Radar Master Operating Prompt available to the project.
- The current project-structure, backend-structure, business-logic, business-data, and frontend-design documents and their version logs.
- Applicable ADRs, runbooks, schemas, tests, migrations, configuration, source profiles, and implementation files.
- docs/audits/README.md or the repository audit index when present.
- The immediate governing audit named above and every later audit/checkpoint that contains unresolved required corrections relevant to this task.

AUDIT-CHAIN GATE
- Use audit content and audited commit metadata, not file modification time alone, to determine which report is current.
- If any applicable audit result is BLOCKED, stop without implementation and report the blocker.
- If any applicable audit result is PASS WITH REQUIRED CORRECTIONS, proceed only when this prompt explicitly covers every open correction. Otherwise stop and use the Audit Correction Prompt in Appendix A.
- If the required governing audit is missing, stale relative to the required predecessor commit, or does not audit the current implementation state, stop and request the proper audit.
- Do not infer approval from silence. Proposed, pending, deferred, or blocked decisions are not approved.

PRE-CHANGE REPORT
Before modifying files, report the branch, HEAD commit, worktree state, current behavior, governing documents, audit findings inherited, conflicts, proposed files, proposed tests, assumptions, risks, data/backfill effects, rollback approach, and any decision requiring human approval. Continue automatically only when no stop condition applies.

IMPLEMENTATION DISCIPLINE
- Preserve the distinctions among Source, Source Artifact, Import Batch, Source Record, Permit, Address, Parcel, Project, Party, Classification, Opportunity, Customer Account, Customer Match, Notification Attempt, and Customer Lead State.
- Use deterministic logic before AI. AI-derived values must retain provenance, model/classifier version, confidence, and review state.
- Preserve immutable raw evidence, complete processing provenance, idempotency, customer isolation, explainability, correction/merge history, and historical policy/configuration snapshots.
- Keep external systems behind adapters and framework code at transport/composition boundaries.
- Make the smallest coherent change. Do not add billing, CRM integration, a marketplace, national coverage, multiple active production jurisdictions, microservices, or unrelated refactors.
- Do not weaken tests or validation. Do not expose secrets or log unnecessary authentication, customer, address, party, parcel, coordinate, description, or raw parsed data.

TASK
Prepare and execute the approved pilot vertical slice deployment to staging only after the formal release gate audit returns PASS and the human invocation authorizes staging deployment.

REQUIRED WORK
- Provision the approved staging application, database, worker, artifact storage, secrets, networking, domain/email sandbox configuration, monitoring, and backups using reproducible infrastructure/configuration.
- Apply migrations through the approved gated process.
- Configure exactly the approved first source and bounded schedule/backfill.
- Keep production SMS disabled. Keep AI classification and any experimental scoring behind approved feature flags.
- Seed only safe staging test/customer data; do not copy production personal data.
- Execute smoke tests for authentication, onboarding, source acquisition, parse/normalize/review, Match creation, dashboard, lead transitions, email sandbox delivery, operations review, alerts, and audit traces.
- Execute a staging backup and isolated restore, reconciliation, application rollback, migration rollback where supported, and source/worker disable procedure.
- Verify deployment observability, health/readiness, alerts, log redaction, and provider webhook endpoints.
- Create deployment checklist, rollback procedure, support/escalation process, and staging evidence report.

BOUNDARIES
Do not deploy to production, enable production SMS, charge customers, broaden sources/trades, or bypass failed checks.

ACCEPTANCE CRITERIA
Staging reproduces the complete narrow acceptance journey with one approved source, limited trades, authenticated dashboard, email delivery, internal review, observability, and tested rollback/restore.

MANDATORY VALIDATION AND RECONCILIATION
Run every applicable formatter, linter, static/type check, unit test, integration test, contract test, end-to-end test, build/package check, migration check, documentation/link check, JSON/schema check, security scan, and git diff check. If a category is not configured or not applicable, state that explicitly and explain why; do not claim it passed.

LIGHTWEIGHT LOGIC AND STRUCTURE CHECK
Before committing, explicitly compare implementation, tests, migrations, configuration, current documents, ADRs, runbooks, source profiles, API/UI language, and operational behavior. Check:
- bounded-context ownership and dependency direction;
- state transitions, invariants, failure paths, and review gates;
- transaction boundaries, idempotency, concurrency, replay, and rollback;
- customer isolation, anti-enumeration, permissions, consent, and data minimization;
- provenance/version history and customer-visible explainability;
- implemented versus planned capability claims.
Correct in-scope inconsistencies before commit. If a material contradiction remains, stop without committing and identify the required corrective scope. Include the completed check in the final report; this is a lightweight implementation check, not a formal PASS/BLOCKED audit.

DOCUMENT GOVERNANCE
Update every affected governed current document and version log using the repository process. Validate the proposed replacement, move the prior current file to the correct legacy directory, update links, and confirm exactly one current version exists per governed family. Create or update ADRs and runbooks when behavior, boundaries, providers, persistence, security, deployment, or operations change.

COMMIT GATE
Only after required validation, documentation reconciliation, and the lightweight check succeed, create one dedicated commit for this prompt. Do not combine later work. Do not push or deploy unless this prompt and the human invocation explicitly authorize it. Report the commit hash and message. If validation fails or unrelated changes remain, do not commit.

COMPLETION REPORT
Return file changes; delivered behavior; migration/backfill impact; exact tests/results; lightweight-check result; documentation/ADR/runbook versions; incorporated audit findings; assumptions and remaining risks; deferred work; rollback notes; commit hash; and the exact next prompt or audit unblocked.

END PROMPT
