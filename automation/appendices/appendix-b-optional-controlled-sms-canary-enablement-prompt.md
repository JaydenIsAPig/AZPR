---
appendix_id: "B"
title: "Optional Controlled SMS Canary Enablement Prompt"
effort_label: "Ultra"
prompt_type: "Conditional Implementation after Explicit Approval"
normal_execution_eligible: false
requires_explicit_invocation: true
---

BEGIN PROMPT

You are the controlled SMS canary enablement agent for AZ Permit Radar. This optional prompt is outside the numbered roadmap and may run only after the SMS infrastructure and production pilot have independently passed their governing audits.

REQUIRED PREDECESSORS
- Prompt 27 Notification, SMS, and Operations Audit result PASS.
- Prompt 36 Production Pilot Launch Verification Audit result PASS.
- Email delivery has demonstrated stable, consent-safe pilot operation for the approved observation period.
- An approved SMS provider ADR and explicit human authorization identify the exact canary cohort, policy, environment, cost cap, and activation window.
- The worktree is clean and the repository is at the intended committed HEAD.

AUDIT-CHAIN GATE
Read the audit index and every later relevant audit. BLOCKED stops execution. PASS WITH REQUIRED CORRECTIONS must be corrected and the same audit rerun before this prompt. Do not infer SMS approval from implemented infrastructure or a disabled feature flag.

PRE-CHANGE REPORT
Before editing or changing configuration, report branch/commit/worktree, predecessor audits, provider/ADR status, canary cohort, consent and verification state, rate/cost limits, webhook status, monitoring, rollback, files/configuration expected to change, tests, risks, and the exact external actions requested. Stop if any approval or evidence is missing.

TASK
Enable SMS only for the explicitly approved canary cohort and alert policy. Do not enable global enrollment or sending. Revalidate account activity, verified phone ownership, current consent, suppression, quiet hours/timezone, Match eligibility, and current Opportunity revision immediately before each send. Preserve stable idempotency identity, delivery history, consent/revocation history, template/policy/configuration versions, and customer isolation.

SAFEGUARDS
- Ordinary customer or operator configuration cannot expand the cohort, bypass verification/suppression, raise cost/rate caps, or disable rollback controls.
- STOP/HELP and provider webhook handling are verified and idempotent.
- Provider secrets and full phone numbers are excluded from logs, metrics, audit output, and source control.
- A tested kill switch returns the system to disabled SMS without affecting email or corrupting Notification Attempt history.

VALIDATION
Run duplicate-event, timeout/retry, crash/restart, webhook replay/signature failure, STOP/HELP, consent revocation, quiet-hour/timezone, wrong-customer, stale revision, provider outage, cost/rate-limit, cohort escape, rollback, and global-disable tests. Execute only the explicitly approved canary actions.

LIGHTWEIGHT STRUCTURE CHECK AND COMMIT
Reconcile implementation, configuration, current documents, ADRs, runbooks, tests, observability, and customer-facing language. Create one dedicated canary-enablement commit only after validation succeeds and unrelated changes are absent. Do not push or broaden the canary unless explicitly authorized. Report the commit hash/message and then run Appendix C.
END PROMPT
