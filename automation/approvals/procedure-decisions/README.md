# Procedure decision records

This directory is the governed destination for human-authored procedure-only
decisions. It contains the canonical project-owner decision for
`AZPR_H0_TARGET_FINGERPRINT_V1` at
`AZPR_H0_TARGET_FINGERPRINT_V1.json`.

For the H0 target-fingerprint procedure, only the project owner may author the
record, and only after reviewing the canonical request and immutable review
view. The present record conforms to
`../schemas/procedure-approval-decision-v1.schema.json`, uses canonical
`AZPR_CANONICAL_JSON_V1` bytes, and was added in separate human-authored commit
`82ba27a1be4d1590e15f78a891568844639096dd`, whose author name matches
`decided_by.name`. The validator derives the stable reference
`git:82ba27a1be4d1590e15f78a891568844639096dd:automation/approvals/procedure-decisions/AZPR_H0_TARGET_FINGERPRINT_V1.json`
for exact procedure digest
`d35da355850ee1440ea454c4e2663dae7fb15778bb2c935283ec16d7771f1d8a`.

An agent may validate the committed record but must never repair, rewrite,
replace, stage, recommit, or infer it. The record approves only the exact
procedure bytes. It cannot authorize a target or execution, approve or qualify
an environment, activate an adapter/controller, invoke H0-T02 or an H0-ALV
stage, run the AZPR verifier, or authorize Git activity.
