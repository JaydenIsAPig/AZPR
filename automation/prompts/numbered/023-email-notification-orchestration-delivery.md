Effort Level: Extra High

BEGIN PROMPT

You are the implementation agent for AZ Permit Radar. Execute this task as one controlled, reviewable change within the existing domain-driven modular monolith.

REQUIRED PREDECESSOR
- Governing audit: Prompt 22 Customer API, Frontend, and Data-Exposure Audit with result PASS.
- Required predecessor evidence: Prompt 22 audit commit.
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
Implement email as the first fully enabled pilot notification channel using provider-neutral orchestration, the durable transactional outbox, and an approved provider adapter.

EMAIL PROVIDER DECISION GATE
If no email provider is approved, compare a small viable set for security, domain authentication, webhook verification, bounce/complaint handling, suppression, data retention, cost, testing/sandbox support, portability, and exit path. Because customer email and delivery reputation create an external trust boundary, stop for explicit human approval unless an approved ADR already exists. Provider-neutral orchestration and deterministic fake tests may be prepared, but do not claim pilot email is complete until the approved adapter is integrated and validated.

REQUIRED WORK
- Generate notification intent only from an eligible active Customer Match and approved preference.
- Recheck current Opportunity revision, Match eligibility/state, account activity, consent, suppression, and customer configuration immediately before send.
- Define stable idempotency identity using Customer Account, Match, Opportunity revision, channel, template version, and intended delivery window/event.
- Implement daily digest first. Add immediate email only when explicitly approved and feature-gated.
- Implement customer timezone, quiet-hour policy where applicable, rate limits, retries, terminal/dead-letter state, duplicate suppression, unsubscribe, bounce, complaint, provider-failure, and verified webhook handling.
- Version templates separately from delivery code.
- Include why the Match exists, safe location, permit/project type, value signal when available, source freshness/unknown state, uncertainty, and authenticated detail link.
- Never send pending/rejected classification, unresolved duplicate, superseded/voided/noncanonical Permit, stale Opportunity projection, disallowed uncertain geography, or inactive-account data.
- Expose delivery state to authorized customers and internal operations without exposing provider secrets.

ACCEPTANCE CRITERIA
A consented eligible Match produces exactly one intended email per policy; stale or ineligible queued data is suppressed at send time; historical attempts and template/policy/revision context remain traceable; and provider failures are retryable/observable without duplicate customer delivery.

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
