---
prompt_id: "010"
sequence: 10
title: "Durable Platform and Persistence Audit"
stage_group: "S3 - Durable Platform Foundation"
effort_label: "Ultra"
prompt_type: "Read-only Audit"
normal_execution_eligible: true
---

BEGIN PROMPT

You are the read-only audit agent for AZ Permit Radar. Audit the repository at the current committed HEAD. Do not correct implementation defects during this prompt.

REQUIRED PREDECESSOR
- Prompts 7-9 validated commits.
- Confirm the worktree is clean and record branch, full commit, short commit, repository status, and audit date.

READ-ONLY WRITE SCOPE
- Do not change product code, tests, schemas, migrations, configuration, source profiles, governed current documents, ADRs, runbooks, or runtime behavior.
- Create one new immutable report at docs/audits/durable-platform-persistence-audit-<YYYY-MM-DD>-<shortsha>.md. Never overwrite a prior audit report.
- Update only docs/audits/README.md or the existing audit index to identify the new report as the latest audit for this stage.

MANDATORY INSPECTION
Read README.md, the AZ Permit Radar Master Operating Prompt, all current governed documents and logs, applicable ADRs/runbooks/source profiles, the full audit chain, code, tests, schemas, migrations, configuration, dependency/lock files, and relevant git history. Verify that every inherited PASS WITH REQUIRED CORRECTIONS item is either closed with evidence or still open.

RESULT CONTRACT
Return exactly one overall result:
- PASS: no required correction remains before the named next stage.
- PASS WITH REQUIRED CORRECTIONS: no critical/high blocker exists, but specific corrections must be completed and this same audit rerun before progression.
- BLOCKED: a critical/high issue, unresolved approval, customer-isolation failure, missing provenance, unsafe migration/deployment, source-access uncertainty, consent/security failure, or material code/document contradiction prevents progression.

REPORT HEADER
Begin the report with a machine-readable YAML block containing: audit_id, audit_stage, audit_date, audited_branch, audited_commit, predecessor_commits, result, required_corrections, blocking_findings, next_prompt_or_action, and supersedes (use an empty list when none). Audit reports are historical evidence and must not supersede or erase prior reports.

FINDING STANDARD
Every finding must include severity, status, evidence with file paths and test names/commands, impact, required action, owner prompt/stage, and whether it blocks progression. Distinguish implemented, partially implemented, planned, proposed, and unapproved behavior. Do not treat a compiling build or passing unit suite alone as release evidence.

AUDIT OBJECTIVE
Determine whether the durable platform faithfully preserves the validated in-memory core and is safe to receive identity and live-source integrations.

MANDATORY FAILURE AND CONCURRENCY CASES
- Database creation and migration validation from a clean state.
- Additive migration safety and documented rollback.
- Database constraints enforce artifact, record, Permit, Opportunity, Match, Review Task, trace, and outbox uniqueness.
- Customer-keyed ownership and cross-customer reference prevention.
- Atomic normalization/duplicate/review transaction rollback.
- Outbox event appears only after commit and dispatch is idempotent.
- Worker lease expiration, retry, concurrent claim, crash recovery, and dead-letter/terminal state.
- Durable artifact checksum, immutability, authorization boundary, and metadata reconciliation.
- Historical parser/normalizer/classifier/Opportunity/score/config versions survive reload.
- In-memory and durable adapter contract behavior agree for core cases.
- Backup/restore requirements are identified even if full operational implementation is scheduled later.

NEXT STAGE
Prompt 11 may run only on PASS. Any lost provenance, partial-state exposure, unsafe migration, or customer ownership defect is BLOCKED.

VALIDATION
Run the complete non-mutating validation set applicable to the audited stage. Include exact commands and results. Do not edit files to force success. Confirm no product files changed during audit execution.

AUDIT COMMIT
After the report and index update are internally consistent, create one dedicated audit commit containing only the new immutable audit report and optional audit-index update. Do not push. Report the commit hash and message. If the worktree contains unrelated changes, stop without committing.

DOWNSTREAM INSTRUCTION
End the report with the exact next numbered prompt allowed on PASS, or explicitly state that no numbered prompt is authorized and name the required human decision or new roadmap. On PASS WITH REQUIRED CORRECTIONS or BLOCKED, name the exact correction scope, direct the user to Appendix A, and require this same audit to be rerun. No later numbered prompt may treat the result as approval.

END PROMPT
