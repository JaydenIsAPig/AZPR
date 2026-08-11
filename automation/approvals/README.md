# Approval checkpoints

Legacy roadmap gates still name historical `approved: true` files, but that
single boolean is not an execution-safe approval. New or revised controller
work must use `automation/approval_manager.py` and the contract below.

1. Define the exact authority in a version-controlled file under
   `stage-manifests/`. Every action requires a target, permission, expected
   effect, test, and stop condition; every evidence file is SHA-256-bound.
2. Generate the canonical ticket and immutable review view. Ticket bytes use
   `AZPR_CANONICAL_JSON_V1` (UTF-8, sorted keys, compact separators, no trailing
   newline, no floating-point values).
3. Present the review view to an authenticated human. The trusted controller
   authentication adapter must challenge the reviewer with the current ticket
   digest and create a separate canonical decision. Editing a template or
   setting `approved: true` never grants authority.
4. Immediately before execution, regenerate and compare the ticket and review,
   reverify authentication, check decision expiry, and compare all observed
   targets exactly. Any mismatch stops execution.
5. Record the execution run, evidence bundle, and outcome separately. Approval
   is permission to attempt the listed actions, not proof that they succeeded.

Generate or verify a ticket from the repository root:

```sh
python3 automation/approval_manager.py generate \
  --manifest automation/approvals/stage-manifests/AZPR-H0-TRANSPORT-20260807-001.json \
  --ticket automation/approvals/tickets/AZPR-H0-TRANSPORT-20260807-001.json \
  --review automation/approvals/reviews/AZPR-H0-TRANSPORT-20260807-001.md

python3 automation/approval_manager.py check \
  --manifest automation/approvals/stage-manifests/AZPR-H0-TRANSPORT-20260807-001.json \
  --ticket automation/approvals/tickets/AZPR-H0-TRANSPORT-20260807-001.json \
  --review automation/approvals/reviews/AZPR-H0-TRANSPORT-20260807-001.md
```

## IDs, revisions, and deltas

- Approval: `AZPR-<LIFECYCLE>-<SCOPE>-<YYYYMMDD>-<NNN>`
- Simple revision: append `-RNN` while preserving the base approval ID.
- Execution run: `AZPR-RUN-<LIFECYCLE>-<YYYYMMDD>-<NNNN>`
- Outcome: `AZPR-OUT-<LIFECYCLE>-<YYYYMMDD>-<NNNN>`
- Evidence bundle: `AZPR-EVD-<LIFECYCLE>-<YYYYMMDD>-<NNNN>`

The run, outcome, and evidence records share lifecycle, date, and sequence and
refer to the immutable approval ID. A changed target, permission, validity
grant, security boundary, or action list requires a new approval ID. A delta
ticket is created only when remediation includes an action outside the
original authority; in-scope retries retain the original authority and receive
new run/outcome/evidence IDs.

The current Multipass checkpoint is
`AZPR-H0-TRANSPORT-20260807-001`. Its checked-in ticket is intentionally still
missing an authenticated decision, so it grants no H0-T02 execution authority.
