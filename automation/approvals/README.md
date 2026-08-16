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

## H0 fingerprint procedure-only channel

ADR-0014 defines a narrower channel for the exact non-executing
`AZPR_H0_TARGET_FINGERPRINT_V1` procedure. It does not replace the authenticated
checkpoint above and cannot authorize a target or action.

The canonical request is under `procedure-requests/`, with its deterministic
immutable review under `procedure-reviews/`. The decision schema and
non-authoritative template are under `schemas/` and `templates/`. The governed
decision is
`procedure-decisions/AZPR_H0_TARGET_FINGERPRINT_V1.json`.

Only the project owner may author the decision in a separate human-authored
commit. Agents must not populate, repair, rewrite, replace, stage, recommit, or
infer it. The read-only check is:

```sh
python3 scripts/check_h0_fingerprint_procedure_approval.py check
```

The current decision returns `APPROVED`, procedure digest
`d35da355850ee1440ea454c4e2663dae7fb15778bb2c935283ec16d7771f1d8a`, and
stable reference
`git:82ba27a1be4d1590e15f78a891568844639096dd:automation/approvals/procedure-decisions/AZPR_H0_TARGET_FINGERPRINT_V1.json`.
The validator checks canonical bytes, exact request and procedure digests, role
and acknowledgements, commit ancestry, unchanged committed bytes, and Git-author
attribution. This is repository attribution, not execution-grade
authentication; it is accepted only for the procedure definition. It never
activates the adapter/controller or authorizes a target, environment, H0
action, verifier, stage progression, or Git write. If the record were absent,
the channel would return `AWAITING_HUMAN_DECISION` and a nonzero exit code.

## Inert macOS operator adapter

ADR-0012 permits source-only implementation under
`native/operator-approval-helper/` and `automation/operator_approval.py`. It is
not installed, enrolled, activated, or selected by either controller. The
existing transport ticket and its bound transition-contract bytes are
unchanged.

The controller request is canonical JSON with exactly the request format and
record kind, canonical ticket bytes encoded as strict base64, a controller-
generated 256-bit nonce, request and expiry timestamps, authenticator/key IDs,
and preflight result. No digest is sent separately: the helper parses the
canonical ticket and recomputes its SHA-256.

`AZPR_OPERATOR_DECISION_ASSERTION_V1` contains an exact signed payload:

- format version `1.0`, record kind
  `AZPR_OPERATOR_DECISION_ASSERTION`, and purpose
  `AZPR_OPERATOR_APPROVAL_DECISION_V1`;
- approval ID, ticket ID, ticket SHA-256, and exactly `APPROVED` or `REJECTED`;
- nonce, requested/decided/expiry timestamps, authenticator ID,
  authentication-event ID, and key ID.

Its envelope contains only the signed payload, algorithm
`ECDSA_MESSAGE_X962_SHA256`, DER ECDSA signature as base64, SHA-256 of the exact
65-byte `ANSI_X9_63_UNCOMPRESSED_P256` public key, and
`AZPR_OPERATOR_APPROVAL_HELPER_V1` build identity. Unknown, duplicate,
floating-point, oversized, malformed, invalid-UTF-8, and noncanonical values
fail closed. Python verifies with exactly `cryptography==46.0.4`; that pinned
package is already present in the qualification test runtime but installation
into an active controller runtime is deferred.

The host trust schema is
`schemas/operator-trust-record-v1.schema.json`. The checked-in
`templates/operator-trust-record.template.json` is deliberately
non-authoritative and null-valued. A real record must be absolute and outside
the repository and AI-writable directories. It binds helper path/hash/build/
owner/mode and optional designated requirement, exact public key/key ID,
authenticator, subject, roles, state, and enrollment/revocation times. Runtime
subject and role are derived only from that record.

The replay ledger is also host-owned. It uses an exclusive file lock, 0600
files, fsync, and atomic replacement. A challenge progresses from PENDING to
VERIFIED or TERMINAL and then to CONSUMED for one run; each material action may
be claimed at most once. Restart, concurrency, partial writes, and mismatched
bindings fail closed.

Cancel, close, timeout, biometric failure/lockout/unavailability, missing or
invalidated key, signing failure, process failure, or excessive output creates
no approved decision. A signed REJECTED assertion may create an audit record
but never an execution authorization. The software P-256 signer is compiled
only into unit tests and cannot be selected with an environment variable,
command-line argument, or live configuration.

See the
[operator-authentication runbook](../../docs/runbooks/operator-authentication.md)
for the separately governed installation/enrollment inputs, revocation and
recovery behavior, hardware qualification, and H0-versus-production limits.
