Effort Level: Ultra

BEGIN PROMPT

You are the read-only audit agent for AZ Permit Radar. Audit the repository at the current committed HEAD. Do not correct implementation defects during this prompt.

REQUIRED PREDECESSOR
- Prompt 33 controlled staging deployment evidence and commit.
- Confirm the worktree is clean and record branch, full commit, short commit, repository status, and audit date.

READ-ONLY WRITE SCOPE
- Do not change product code, tests, schemas, migrations, configuration, source profiles, governed current documents, ADRs, runbooks, or runtime behavior.
- Create one new immutable report at docs/audits/staging-pilot-readiness-audit-<YYYY-MM-DD>-<shortsha>.md. Never overwrite a prior audit report.
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
Audit the actual staging deployment and decide whether a controlled production pilot may be proposed to the human owner.

MANDATORY EVIDENCE
- Deployed commit and configuration match the release-gated artifacts.
- Database migrations, source profile, feature flags, secrets, network boundaries, workers, storage, monitoring, and backups are correct.
- End-to-end acceptance journey succeeds in staging.
- Source acquisition is lawful/approved, bounded, observable, and safely disableable.
- Customer isolation, authorization, stale/review publication gates, explainability, and provenance hold in the deployed environment.
- Email sandbox/provider path is idempotent and consent-safe.
- SMS is disabled and cannot be enabled accidentally through ordinary configuration.
- Backup restore, reconciliation, rollback, alerting, incident runbooks, and support escalation are demonstrated.
- No unsupported claims, billing, CRM, extra source, or microservice scope appears.

RESULT
A PASS authorizes only preparation for an explicitly approved controlled production pilot; it does not itself authorize production deployment, customer charging, or SMS enablement. Any material staging/configuration mismatch is BLOCKED.

NEXT STAGE
Prompt 35 may run only on PASS and only after explicit human authorization for controlled production deployment.

VALIDATION
Run the complete non-mutating validation set applicable to the audited stage. Include exact commands and results. Do not edit files to force success. Confirm no product files changed during audit execution.

AUDIT COMMIT
After the report and index update are internally consistent, create one dedicated audit commit containing only the new immutable audit report and optional audit-index update. Do not push. Report the commit hash and message. If the worktree contains unrelated changes, stop without committing.

DOWNSTREAM INSTRUCTION
End the report with the exact next numbered prompt allowed on PASS, or explicitly state that no numbered prompt is authorized and name the required human decision or new roadmap. On PASS WITH REQUIRED CORRECTIONS or BLOCKED, name the exact correction scope, direct the user to Appendix A, and require this same audit to be rerun. No later numbered prompt may treat the result as approval.

END PROMPT
