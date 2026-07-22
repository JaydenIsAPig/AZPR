Effort Level: Extra High

BEGIN PROMPT

You are the implementation agent for AZ Permit Radar. Execute this task as one controlled, reviewable change within the existing domain-driven modular monolith.

REQUIRED PREDECESSOR
- Governing audit: Latest Post-Prompt-10 Corrective Audit and any newer audit affecting normalization, scoring, or processing traceability.
- Required predecessor evidence: The audited pre-Prompt-1 baseline commit identified by the governing audit. No Prompt 1 commit exists yet.
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
Implement the two required post-Prompt-10 traceability corrections and resolve the audit's unexplained missing-valuation score discrepancy without expanding product scope.

REQUIRED WORK
1. Add a governed normalizer identity and semantic version to the deterministic permit normalizer.
2. Retain normalizer identifier/version with every normalization result, Permit provenance record, correction snapshot, duplicate decision context, and any reprocessing result that depends on normalization.
3. Ensure a correction executed under a new normalizer version retains the prior normalized snapshot and all linked Source Record and raw-artifact evidence.
4. Implement a self-contained immutable processing trace query or projection. It must expose, without requiring callers to reconstruct the chain through arbitrary repository joins:
   - correlation/command identity and final status;
   - Source, Source Artifact hash, Import Batch, Source Record, external identifier when available, acquisition timestamp, and source publication/issue date when available;
   - parser identifier/version;
   - normalizer identifier/version;
   - Permit identity, canonical/superseded/voided state, duplicate and address-review state;
   - classifier identifier/version, origin, confidence, review state, and AI provider/model version when an AI proposal exists;
   - Opportunity identity and revision/currentness;
   - score-policy version, customer-configuration version, component values, exclusions, and final Match state.
5. Keep the trace customer-safe by design. Do not log or project raw addresses, descriptions, parties, parcel values, coordinates, or raw parsed values into routine log/metric labels.
6. Investigate the corrective audit discrepancy where one missing-valuation trace reports a score of 80 while the score-case matrix reports 85. Determine whether the cases use different customer configuration, notification readiness, fixture data, or whether code/documentation is wrong. Add regression evidence. Do not change score weights merely to make the numbers match.
7. Update the Permit Normalization runbook, source-integrity requirements, business logic, backend structure, business data/schema, glossary, definition of done, and tests as required.

ACCEPTANCE CRITERIA
- A trace can independently identify every processing and policy version required by the corrective audit.
- Replaying unchanged input under the same versions adds no duplicate trace/result.
- Reprocessing under a new normalizer version creates a distinguishable retained result without mutating the raw artifact.
- Corrected records preserve prior normalized snapshots and both old/new provenance.
- The missing-valuation 80-versus-85 difference is either reproducibly explained or corrected with tests and synchronized documentation.
- Existing unsafe publication gates and customer isolation remain unchanged.

BOUNDARY
Do not select a production framework, database, provider, or durable persistence mechanism in this prompt. Close the in-memory traceability release gate first.

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
