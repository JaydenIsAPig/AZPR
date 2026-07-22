---
prompt_id: "038"
sequence: 38
title: "Pilot Feedback and Business Validation Audit"
stage_group: "S10 - Pilot Learning"
effort_label: "Ultra"
prompt_type: "Read-only Audit"
normal_execution_eligible: true
---

BEGIN PROMPT

You are the read-only audit agent for AZ Permit Radar. Audit the repository at the current committed HEAD. Do not correct implementation defects during this prompt.

REQUIRED PREDECESSOR
- Prompt 37 validated pilot-feedback implementation commit and the approved pilot review-point data snapshot.
- Confirm the worktree is clean and record branch, full commit, short commit, repository status, and audit date.

READ-ONLY WRITE SCOPE
- Do not change product code, tests, schemas, migrations, configuration, source profiles, governed current documents, ADRs, runbooks, or runtime behavior.
- Create one new immutable report at docs/audits/pilot-feedback-business-validation-audit-<YYYY-MM-DD>-<shortsha>.md. Never overwrite a prior audit report.
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
Audit the pilot-feedback workflow, analysis definitions, and product-validation report so the project can draw a trustworthy Minimum Viable Product conclusion without automatically authorizing expansion.

MANDATORY EVIDENCE
- Feedback and customer notes are customer-owned, authorization-scoped, retention-governed, and never mutate shared Permit or Opportunity facts.
- Every response is bound to the exact Customer Match, Opportunity revision, score-policy version, customer-configuration version, parser/normalizer/classifier versions, source, and customer-visible timestamp.
- Confirmed quotes, bids, jobs, and contacts are separated from inferred views, opens, clicks, or model-generated assumptions.
- Negative feedback, dismissed records, and ignored records remain available; metrics do not improve by hiding or dropping unfavorable outcomes.
- Weekly reports preserve source/trade breakdowns, missing-information themes, false-positive causes, manually reported false-negative examples, alert delivery, and customer action funnel definitions.
- Privacy, free-text minimization, internal access, customer isolation, retention, deletion/anonymization, and analytics-event boundaries are implemented and tested.
- Sample size, observation window, selection bias, missing responses, and data-quality limitations are disclosed. Do not claim statistical significance, causation, profitability, or product-market fit without evidence.
- The product-validation report uses reproducible queries or calculations and recommends exactly one governed next action: continue the current pilot; improve data quality before expansion; narrow the target trade; change alert thresholds; evaluate the second Tucson/Pima source through a new source gate; or pause expansion because customer value is not demonstrated.
- No recommendation automatically changes production configuration, activates a second source, changes thresholds, enables billing/CRM, expands SMS, or authorizes a new roadmap.

RESULT
- PASS means the feedback system, evidence chain, and validation report are trustworthy enough for the human owner to make the next product decision. PASS does not mean economic value or product-market fit was proven.
- PASS WITH REQUIRED CORRECTIONS means the workflow is safe but named data-definition, reporting, traceability, or evidence-quality corrections must be completed and this audit rerun.
- BLOCKED applies to cross-customer exposure, altered/omitted negative outcomes, irreproducible metrics, broken version binding, unsafe free-text/retention handling, fabricated conclusions, or any automatic expansion outside the approved pilot.

ROADMAP COMPLETION
On PASS, state that this numbered roadmap is complete. Any second source, new jurisdiction, billing, CRM integration, broad SMS expansion, major threshold change, or service extraction requires an explicit human decision, a newly approved staged roadmap, and the formal audit gates required by the Master Operating Prompt.

VALIDATION
Run the complete non-mutating validation set applicable to the audited stage. Include exact commands and results. Do not edit files to force success. Confirm no product files changed during audit execution.

AUDIT COMMIT
After the report and index update are internally consistent, create one dedicated audit commit containing only the new immutable audit report and optional audit-index update. Do not push. Report the commit hash and message. If the worktree contains unrelated changes, stop without committing.

DOWNSTREAM INSTRUCTION
End the report with the exact next numbered prompt allowed on PASS, or explicitly state that no numbered prompt is authorized and name the required human decision or new roadmap. On PASS WITH REQUIRED CORRECTIONS or BLOCKED, name the exact correction scope, direct the user to Appendix A, and require this same audit to be rerun. No later numbered prompt may treat the result as approval.

END PROMPT
