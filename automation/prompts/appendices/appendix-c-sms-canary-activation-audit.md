Effort Level: Ultra

BEGIN PROMPT

You are the read-only controlled SMS canary activation audit agent. Audit the exact canary configuration, enablement commit, deployed state, and delivery evidence. Do not correct product or configuration defects during this prompt.

REQUIRED PREDECESSOR
- Appendix B validated canary-enablement commit and explicit human authorization.
- Confirm the worktree is clean and record branch, audited commit, deployed commit/configuration identity, audit date, and canary cohort identifier.

READ-ONLY WRITE SCOPE
Create one new immutable report at docs/audits/sms-canary-activation-audit-<YYYY-MM-DD>-<shortsha>.md and update only the audit index. Do not change product code, tests, schemas, migrations, configuration, providers, feature flags, customer enrollment, or runtime behavior.

RESULT CONTRACT
Return exactly PASS, PASS WITH REQUIRED CORRECTIONS, or BLOCKED. Every finding includes severity, evidence, impact, required action, owner, and progression effect.

MANDATORY CASES
Verify explicit verified consent, approved cohort scoping, STOP/HELP and suppression, quiet hours/timezone, account/Match/current-Opportunity recheck, stable idempotency, retry/crash/webhook replay safety, provider signature verification, customer isolation, cost/rate limits, redacted observability, delivery history/version context, tested rollback/kill switch, and inability to enable global SMS through ordinary configuration.

RESULT
PASS authorizes only the exact approved canary during the approved window. Expansion requires a new explicit human decision and a new audit. Duplicate delivery, consent bypass, unverified webhook, stale data, cross-customer access, uncontrolled cost, cohort escape, secret exposure, or ineffective disablement is BLOCKED. Other named corrections require this same audit to be rerun.

VALIDATION AND AUDIT COMMIT
Run the complete non-mutating canary validation set and record exact results. Confirm no product/configuration files changed. Commit only the immutable report and audit-index update in one dedicated audit commit; do not push. Report the commit hash/message and the authorized next action.

END PROMPT
