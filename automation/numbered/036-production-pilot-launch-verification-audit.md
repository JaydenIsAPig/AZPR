---
prompt_id: "036"
sequence: 36
title: "Production Pilot Launch Verification Audit"
stage_group: "S9 - Staging and Production Pilot"
effort_label: "Ultra"
prompt_type: "Read-only Audit"
normal_execution_eligible: true
---

BEGIN PROMPT

You are the read-only audit agent for AZ Permit Radar. Audit the repository at the current committed HEAD. Do not correct implementation defects during this prompt.

REQUIRED PREDECESSOR
- Prompt 35 controlled production pilot deployment evidence and commit.
- Confirm the worktree is clean and record branch, full commit, short commit, repository status, and audit date.

READ-ONLY WRITE SCOPE
- Do not change product code, tests, schemas, migrations, configuration, source profiles, governed current documents, ADRs, runbooks, or runtime behavior.
- Create one new immutable report at docs/audits/production-pilot-launch-audit-<YYYY-MM-DD>-<shortsha>.md. Never overwrite a prior audit report.
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
Audit the actual controlled production deployment before it is treated as a stable pilot baseline or used for business-validation conclusions.

MANDATORY EVIDENCE
- Deployed commit, migrations, current documents, source profile, feature flags, and provider modes match the approved staging/release evidence.
- Only the approved source, trades, territories, accounts, and channels are enabled.
- Customer isolation, anti-enumeration, consent, publication/review gates, current Opportunity revision, and Match explainability hold in production smoke tests.
- Scheduled acquisition archives immutable evidence and can be disabled safely.
- Email delivery is idempotent, consent-safe, revision-aware, observable, and limited to the pilot cohort.
- SMS is disabled unless the optional SMS enablement audit is PASS and explicit activation approval is recorded.
- Health/readiness, alerts, logs/metrics redaction, backups, restore evidence, reconciliation, rollback, incident response, and support escalation are operational.
- No unsupported billing, CRM, extra source, marketplace, national, or microservice scope is active.
- Production configuration and secrets are not present in repository history or audit output.

RESULT
Prompt 37 may run only on PASS. PASS confirms the production pilot baseline is suitable for controlled learning; it does not authorize expansion, billing, additional sources, or SMS activation. Any deployment/configuration mismatch, isolation failure, duplicate delivery, missing backup/rollback, or unsafe source access is BLOCKED.

VALIDATION
Run the complete non-mutating validation set applicable to the audited stage. Include exact commands and results. Do not edit files to force success. Confirm no product files changed during audit execution.

AUDIT COMMIT
After the report and index update are internally consistent, create one dedicated audit commit containing only the new immutable audit report and optional audit-index update. Do not push. Report the commit hash and message. If the worktree contains unrelated changes, stop without committing.

DOWNSTREAM INSTRUCTION
End the report with the exact next numbered prompt allowed on PASS, or explicitly state that no numbered prompt is authorized and name the required human decision or new roadmap. On PASS WITH REQUIRED CORRECTIONS or BLOCKED, name the exact correction scope, direct the user to Appendix A, and require this same audit to be rerun. No later numbered prompt may treat the result as approval.

END PROMPT
