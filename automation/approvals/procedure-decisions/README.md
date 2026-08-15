# Procedure decision records

This directory is the governed destination for human-authored procedure-only
decisions. It intentionally contains no decision record.

For the H0 target-fingerprint procedure, only the project owner may create
`AZPR_H0_TARGET_FINGERPRINT_V1.json`, and only after reviewing the canonical
request and immutable review view. The record must conform to
`../schemas/procedure-approval-decision-v1.schema.json`, use canonical
`AZPR_CANONICAL_JSON_V1` bytes, and be added in a separate human-authored Git
commit whose author name matches `decided_by.name`.

An agent may validate a committed record but must never populate, repair,
rewrite, stage, commit, or infer it. The record can approve only the exact
procedure bytes. It cannot authorize a target or execution, approve or qualify
an environment, activate an adapter/controller, invoke H0-T02 or an H0-ALV
stage, run the AZPR verifier, or authorize Git activity.
