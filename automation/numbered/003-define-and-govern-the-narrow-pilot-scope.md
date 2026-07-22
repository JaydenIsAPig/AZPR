---
prompt_id: "003"
sequence: 3
title: "Define and Govern the Narrow Pilot Scope"
stage_group: "S2 - MVP Scope and Architecture"
effort_label: "High"
prompt_type: "Decision and Conditional Implementation"
normal_execution_eligible: true
---

BEGIN PROMPT

You are the implementation agent for AZ Permit Radar. Execute this task as one controlled, reviewable change within the existing domain-driven modular monolith.

REQUIRED PREDECESSOR
- Governing audit: Prompt 2 Post-Core Traceability Corrective Audit with result PASS.
- Required predecessor evidence: Prompt 2 audit commit.
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
Define and govern the narrow Minimum Viable Product pilot scope without prematurely activating unapproved sources, trades, providers, or channels.

DECISION MODE
- If all required scope decisions already exist as approved, validate them and implement only the governed registry/configuration updates.
- If any required decision is missing, create a clearly labeled proposed decision package and stop for explicit human approval before activating runtime configuration.
- A proposal-only run may create a dedicated decision-proposal commit containing only proposed decision documents. After approval, rerun this prompt to create a separate decision-finalization/implementation commit. Never change proposed status to approved without explicit human instruction.

REQUIRED SCOPE PACKAGE
1. Define Tucson/Pima County as the pilot source family, but defer selection of the first enabled production endpoint to Prompt 14's source-access gate.
2. Define evidence-based criteria for choosing the first source: access legality/terms, publication frequency, stable identifiers, historical availability, field quality, operational owner, rate limits, expected maintenance, and replay/backfill value.
3. Compare pilot trade candidates using available fixture/source fields, deterministic classification precision, expected permit volume, geographic relevance, value-signal usefulness, review burden, and customer-action clarity.
4. Recommend a deliberately limited initial trade set only when evidence supports it. Otherwise record the missing evidence and keep the business-data trades registry empty/pending.
5. Define supported territory types for the pilot and the governed treatment of uncertain geography. Unverified geography remains excluded unless a customer explicitly opts in under approved rules.
6. Confirm email as the first fully enabled delivery channel.
7. Confirm controlled SMS capability is implemented only after email passes its dedicated audit; production SMS remains disabled behind feature/environment gates until separate approval and all consent, verification, suppression, webhook, quiet-hour, provider-failure, and rollback tests pass.
8. Confirm billing, CRM integration, marketplace behavior, permit application submission, national coverage, multiple active production jurisdictions, and microservice extraction are outside the current scope.
9. Define measurable acceptance journey, stage exit criteria, pilot-user boundaries, and what evidence is required to claim the Minimum Viable Product exists.

IMPLEMENTATION AFTER APPROVAL
- Add only approved sources/trades/geography/matching/notification policies to versioned governed business data.
- Preserve empty arrays or explicit pending registries for unapproved entries.
- Add validation preventing proposed/deferred entries from becoming active runtime configuration.
- Synchronize product, backend, business logic/data, frontend planning, roadmap/handoff, glossary, and source-onboarding documentation.

ACCEPTANCE CRITERIA
The repository clearly distinguishes source family from first enabled source, approved from proposed trades, supported from deferred territory behavior, enabled email from disabled SMS, and Minimum Viable Product scope from future expansion. No business scope is implied only by code comments or marketing language.

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
