Effort Level: Ultra

BEGIN PROMPT

You are the implementation agent for AZ Permit Radar. Execute this task as one controlled, reviewable change within the existing domain-driven modular monolith.

REQUIRED PREDECESSOR
- Governing audit: Prompt 6 MVP Scope and Architecture Decision Audit with result PASS.
- Required predecessor evidence: Prompt 8 validated durable repository/transaction commit.
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
Implement durable immutable artifact storage, transactional outbox dispatch, scheduled workers, leases, retries, and crash recovery behind approved adapters.

REQUIRED WORK
- Implement content-addressed raw-artifact storage with immutable writes, checksum verification, retention metadata, safe access controls, and a deterministic fake/local adapter.
- Keep artifact metadata and domain references in the approved database while preserving the raw payload in the approved storage boundary.
- Implement transactional outbox dispatch with stable event identity, claim/lease semantics, retry schedule, dead-letter/terminal state, metrics, and duplicate suppression.
- Implement durable worker/scheduler coordination for acquisition and processing, including lease expiry, crash recovery, explicit failed attempts, safe retry, and concurrency limits.
- Preserve exactly-once domain effects through idempotent consumers and database constraints rather than claiming exactly-once transport delivery.
- Add reconciliation commands/queries for orphan metadata, missing blobs, stuck outbox entries, expired leases, and incomplete batches without silently rewriting history.
- Document local development, staging, and production behavior separately.

FAILURE TESTS
Cover artifact write failure, checksum mismatch, database commit failure, dispatcher crash before/after provider handoff boundary, duplicate event delivery, expired worker lease, concurrent acquisition/processing, retry after failure, dead-letter handling, and reconciliation dry run.

ACCEPTANCE CRITERIA
The durable platform can archive evidence, commit domain state and integration intent atomically, recover workers after crashes, and replay safely without duplicate Permits, Opportunities, Matches, Review Tasks, traces, or notifications.

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
