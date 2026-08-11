# ADR-0011: Digest-Bound Approval Checkpoints

- **Status:** Accepted
- **Date:** 2026-08-07
- **Deciders:** Project owner
- **Supersedes:** None
- **Superseded by:** None

## Context

AZPR has human approval files and a preserved H0-T01 authority handoff, but the
repository controller historically treated file existence plus
`"approved": true` as sufficient. That convention does not prove what a human
reviewed, bind a decision to immutable bytes, revalidate execution targets, or
distinguish permission from a successful run. It also permits document
authoring to be mistaken for an authenticated decision.

The current H0 Multipass transport work needs a narrow checkpoint before
H0-T02. The repository has no approved authentication provider, so the
repository component must expose a fail-closed adapter boundary rather than
inventing identity proof.

## Decision

Use deterministic approval checkpoints for all new or revised controller
authority:

1. A version-controlled stage manifest is the sole source for ticket content.
2. Each action names its exact target, permission, expected effect, test, and
   stop condition. Evidence paths are repository-relative and SHA-256-bound.
3. The manager rejects missing, extra, malformed, absent, or drifted fields and
   evidence before generating a ticket.
4. Ticket JSON uses `AZPR_CANONICAL_JSON_V1`: UTF-8, lexicographically sorted
   object keys, compact separators, no trailing newline, integers but no
   floating-point values. SHA-256 is computed over those exact bytes.
5. The generated Markdown review is a deterministic projection of the ticket
   and digest. Regeneration or byte comparison detects review drift.
6. A trusted controller authentication adapter must challenge the reviewer
   with the ticket digest. The decision record binds the authenticated subject,
   role, authentication event, decision, decision time, expiry, approval ID,
   ticket ID, and ticket digest.
7. Execution fails closed when the manifest, evidence, ticket, review,
   authentication, digest, decision window, action list, or observed targets no
   longer match.
8. Approval, execution authorization, execution run, evidence bundle, and
   outcome are separate records. An approved decision never represents a
   successful action.
9. Simple non-authority revisions retain the base approval ID and add `-RNN`.
   A target, permission, validity grant, security boundary, or action-list
   change receives a new approval ID. Remediation receives a delta ticket only
   when it exceeds the original action authority.

The current Multipass approval ID is
`AZPR-H0-TRANSPORT-20260807-001`. Its preserved H0-T01 handoff is evidence for
the new ticket, not a substitute for the authenticated digest-bound decision.

## Consequences

### Positive

- Reviewers approve immutable, executable scope rather than authoring an
  ambiguous document.
- Ticket drift, expiry, evidence drift, and target substitution stop before
  execution.
- Run and outcome records can be audited without conflating permission and
  success.
- Revision and delta behavior is deterministic and fail-closed.

### Negative or trade-offs

- Existing `approved: true` gates remain legacy-only until separately migrated.
- H0-T02 cannot execute until an approved trusted controller authentication
  adapter returns a digest-challenge-bound verification result.
- Exact target bindings intentionally require a new review after benign target
  replacement or host-version drift.

## Rejected alternatives

### Continue using mutable approval JSON

Rejected because it does not establish immutable reviewed bytes or safe
execution-time target matching.

### Let the repository authenticate the operator itself

Rejected because no identity provider, signer trust store, credential policy,
or authentication lifecycle is approved. The manager therefore requires an
injected trusted-controller verifier and supplies no permissive default.

### Store success on the approval record

Rejected because approval and execution are different events with different
owners, timestamps, evidence, and failure modes.

## Validation and compliance

- Run `python3 automation/approval_manager.py check` for the applicable
  manifest/ticket/review before presenting or executing the stage.
- Run `python3 -m pytest -q tests/test_approval_manager.py`.
- Reject direct editing of generated tickets or review views.
- Preserve authenticated decisions and execution outcomes as separate
  canonical records with governed IDs.

## Related documents

- [Approval checkpoint guide](../../automation/approvals/README.md)
- [H0 qualification runbook](../runbooks/ansible-qualification-environment.md)
- [ADR-0009 staged controller transition](0009-staged-hybrid-controller-transition.md)
- [ADR-0010 Ansible qualification infrastructure](0010-ansible-qualification-infrastructure.md)
