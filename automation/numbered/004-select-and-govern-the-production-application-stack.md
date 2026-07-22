---
prompt_id: "004"
sequence: 4
title: "Select and Govern the Production Application Stack"
stage_group: "S2 - MVP Scope and Architecture"
effort_label: "Ultra"
prompt_type: "Architecture Decision Gate"
normal_execution_eligible: true
---

BEGIN PROMPT

You are the implementation agent for AZ Permit Radar. Execute this task as one controlled, reviewable change within the existing domain-driven modular monolith.

REQUIRED PREDECESSOR
- Governing audit: Prompt 2 Post-Core Traceability Corrective Audit with result PASS.
- Required predecessor evidence: Prompt 3 decision/scope commit or approved decision proposal.
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
Select and govern the smallest cohesive production application stack that wraps the validated Python 3.12 domain kernel without rewriting it or introducing microservices.

SELECTION AUTHORITY CLASSIFICATION
For every proposed technology, classify the decision as one of:
- AUTO-SELECTABLE: one clearly compatible, common, secure, permissively licensed, low-cost option; no external trust boundary; no recurring provider commitment; no destructive data migration; limited lock-in; and a practical rollback/exit path.
- HUMAN APPROVAL REQUIRED: affects authentication, authorization, personal/customer data, durable database ownership, migration strategy, hosted infrastructure, secrets, external providers, legal/terms obligations, recurring cost, licensing risk, operational complexity, or expensive reversal.
- DEFERRED: not required for the next implementation stage and safer to decide near its integration prompt.

Codex may finalize and later implement an AUTO-SELECTABLE choice when repository evidence clearly satisfies every criterion. When reasonable options have material tradeoffs or any approval criterion applies, produce ADR recommendations and stop for explicit human approval. Do not infer approval from popularity.

REQUIRED CORE DECISIONS
- API/web framework and composition approach.
- Production database, data-mapper/ORM approach, and migration tool.
- Authentication integration approach and trust boundary.
- Worker/scheduler/outbox execution model.
- Durable raw-artifact storage abstraction and production target category.
- Frontend framework/rendering approach.
- Deployment topology, environment strategy, secrets-management category, and backup/restore ownership.

DEFERRED PROVIDER GATES
Document interfaces, security/data requirements, and decision criteria now, but provider-specific selection may remain deferred to the relevant prompt for email, SMS, and geocoding unless already approved. Do not bind the domain to any provider.

OPTION ANALYSIS
For each nontrivial category compare a small viable set against security model, customer isolation, transactional consistency, migration ergonomics, testability, local development, observability, deployment/rollback, maintenance burden, cost, licensing, portability, lock-in, and fit with a small Tucson/Pima pilot.

REQUIRED OUTPUTS
- Approved or proposed ADRs with status explicit.
- Text-based deployment/data-flow and dependency diagrams.
- A dependency map preserving domain -> application -> adapter direction.
- A staged implementation plan with migration/backfill and rollback points.
- A decision matrix identifying reversible and expensive-to-reverse choices.

TWO-RUN DECISION PROTOCOL
If any required core decision needs approval, create only proposed decision artifacts, validate them, optionally create a dedicated decision-proposal commit, and stop. After explicit approval, rerun this prompt to finalize ADR status, synchronize governed documents, and create the decision-finalization commit. Do not scaffold the material stack while required decisions remain pending.

ACCEPTANCE CRITERIA
Prompt 5 is unblocked only when every core decision needed for the application shell is approved or validly auto-selected, deferred provider gates are explicit, and no architecture document contradicts the selected modular-monolith path.

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
