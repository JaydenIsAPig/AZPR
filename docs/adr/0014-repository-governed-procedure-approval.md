# ADR-0014: Repository-Governed Procedure-Approval Channel

- **Status:** Accepted
- **Date:** 2026-08-14
- **Deciders:** Project owner
- **Supersedes:** None
- **Superseded by:** None

## Context

ADR-0013 requires attributable human approval of the exact H0 target-
fingerprint procedure before guest-local target authorization can be prepared.
The execution-grade operator-approval adapter in ADR-0012 is intentionally
uninstalled and inactive. Requiring that adapter to approve a non-executing
procedure definition creates a deadlock, while accepting chat text or a loose
`approved: true` file would lose exact-byte binding and durable attribution.

The procedure decision must remain distinct from target authorization. It must
not install or activate the operator adapter, authorize an action, select a
guest, invoke an H0 stage, or advance H0.

## Decision

Adopt a repository-governed channel only for approval or rejection of the exact
`AZPR_H0_TARGET_FINGERPRINT_V1` procedure definition:

1. The canonical request
   `AZPR-H0-FINGERPRINT-PROCEDURE-20260814-001.json` binds the exact procedure
   path and SHA-256, allowed deciding role, required acknowledgements, and a
   fixed non-execution authority boundary.
2. A deterministic immutable review view binds the canonical request digest
   and displays the exact procedure digest and boundary.
3. The checked-in template is explicitly non-authoritative. Only the project
   owner may create the real canonical decision at
   `automation/approvals/procedure-decisions/AZPR_H0_TARGET_FINGERPRINT_V1.json`
   in a separate human-authored Git commit.
4. `automation/procedure_approval.py` validates strict fields, canonical bytes,
   request and procedure digests, decision identity and time, deciding role,
   all boundary acknowledgements, an unmodified committed record, commit
   ancestry, exact committed bytes, and agreement between the named decider and
   Git author attribution.
5. The stable reference is derived as `git:<commit>:<decision-path>`. Contract,
   request, review, record, worktree, ancestry, author, or time drift blocks.
6. Missing decision state is `AWAITING_HUMAN_DECISION`; it is not an error and
   is never inferred as approval. A valid `REJECTED` record is attributable but
   never approval.

This channel records repository attribution, not cryptographic identity
authentication. That limited assurance is accepted only for this inert
procedure-definition decision. ADR-0011 and ADR-0012 continue to govern any
execution authority. The channel cannot be generalized to target approval,
environment approval, controller actions, provider changes, secrets, or Git
authority without a new ADR.

## Authority boundary

An `APPROVED` procedure record establishes only that the exact procedure bytes
may be treated as human-approved. It does not:

- contain, select, identify, or authorize a target;
- approve or qualify an environment;
- authorize Ansible, H0-T02, H0-ALV, the AZPR verifier, or Git;
- activate or install the operator-approval adapter or either controller;
- create operator input, an execution authorization, a run, evidence, or an
  outcome; or
- advance H0 or the numbered roadmap.

The fingerprint contract itself remains `PROPOSED_PENDING_HUMAN_APPROVAL` and
unchanged until a valid separate decision exists. Readiness derives approval
from the decision channel rather than mutating the protected procedure bytes.

## Consequences

### Positive

- A human has one exact, durable review and decision path with no dependency on
  the inactive execution adapter.
- Procedure-byte drift and post-commit record edits fail closed.
- The approval reference is stable and independently reproducible from Git.
- Target authorization and execution-grade authentication remain separate.

### Negative or trade-offs

- Git author attribution is not cryptographic authentication and is unsuitable
  for execution authority.
- A procedure change requires a new request and human decision; the old record
  cannot be reused.
- The project owner must create and commit the decision manually; agents may
  only validate it.

## Validation and compliance

- Run `python3 scripts/check_h0_fingerprint_procedure_approval.py check`.
- Run `python3 -m pytest -q tests/test_procedure_approval.py`.
- Keep the checked-in decision template non-authoritative and keep the governed
  decision path absent until the project owner acts.
- Never use this channel to create an approval, target authorization, adapter
  activation, controller action, H0 stage result, or stage progression.

## Related documents

- [ADR-0011 digest-bound approvals](0011-digest-bound-approval-checkpoints.md)
- [ADR-0012 operator-approval boundary](0012-macos-secure-enclave-operator-approval.md)
- [ADR-0013 H0 target fingerprint](0013-h0-live-target-fingerprint.md)
- [Approval checkpoint guide](../../automation/approvals/README.md)
- [H0 Ansible runbook](../runbooks/ansible-qualification-environment.md)
