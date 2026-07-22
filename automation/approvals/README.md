# Human Approval Files

Approval files are deliberate human gates. The controller accepts an approval only when the file exists, is valid JSON, and contains `"approved": true`.

Never let Codex create its own approval. Copy a template, review the relevant ADR/audit/evidence, complete the fields, and commit the approval manually.

Typical files:

- `post-mvp-project-review-approved.json`
- `sms-canary-approved.json`
- `sms-canary-audit-approved.json`
- technology/provider approvals named by `automation/roadmap.json`

Approval files should identify the decision, reviewer, date, selected option, constraints, evidence, and expiration or review trigger when appropriate.
