# ADR-0009: Staged Hybrid Controller Transition

- **Status:** Accepted
- **Date:** 2026-08-06
- **Deciders:** Project owner
- **Supersedes:** None
- **Superseded by:** None

## Context

AZPR currently has a repository-local Python controller that owns development-stage Git, validation, run-record, and commit behavior. The v10.1 delivery also contains a materially different trusted controller intended to be installed outside the repository and backed by host-owned runtime, signing, qualification, and external-capability boundaries.

Replacing the repository controller in place would mix incompatible schemas, references, state models, and trust boundaries. Running both controllers as writers would risk duplicate stage advancement, divergent audit state, and ambiguous rollback. The project nevertheless needs a deliberate path from repository-based development to an independently trusted external control plane.

## Decision

Use a staged hybrid transition:

1. Keep `automation/controller.py` as the development-only repository controller while integration evidence and the selected v10.1 prompt generation are reviewed.
2. Keep the delivered trusted controller, installation tools, operator tools, and external-capability runner inert and outside the application repository.
3. Integrate only a human-approved repository mapping in an isolated branch. Do not activate a policy, roadmap, provider, installer, or production capability as part of prompt/schema integration.
4. Qualify the external controller later in a separate trust boundary, initially in read-only shadow mode against an immutable repository snapshot.
5. Permit cutover only after dual-run equivalence, independent audit, signed state snapshot, rollback rehearsal, exact artifact binding, and explicit human authorization.
6. Enforce one writer at every phase. The repository and external controllers must never concurrently write controller state or Git history.

The machine-readable gates and rollback rules are defined in `automation/integration/v10.1/controller-transition-contract.json`. Delivery evidence is retained under `docs/delivery-provenance/v10.1/` and is not a sixth governed product-document family.

## State-transfer boundary

Only committed, hash-bound, schema-validated evidence may cross the boundary. Live `.codex-loop` state, secrets, private keys, mutable ledgers, receipts, credentials, and provider authority must not be copied into the repository or inferred from delivery artifacts. Missing audit indexes, schemas, host ownership, or runtime decisions must be resolved explicitly rather than fabricated.

Before the first controller-managed formal audit, `docs/audits/README.md` is
the explicitly approved interim audit authority. It grants no prior audit
`PASS`. `INT-04` must return the first integration formal-audit result to the
invoking controller, which creates and commits the immutable report and
controller-owned `docs/audits/index.json` atomically. The delivered final-audit
JSON remains non-authoritative provenance.

## Consequences

### Positive

- Current repository development remains usable while external-control safeguards are built and tested.
- The external controller can be qualified without receiving write or provider authority.
- A single-writer fence and signed rollback point prevent ambiguous ownership during cutover.
- Prompt integration and controller activation remain separate human decisions.

### Negative or trade-offs

- Both controller models must be documented during the transition.
- Compatibility, state-export, and dual-run checks add work before external cutover.
- The delivered trusted controller cannot be treated as production-ready merely because its source passes repository-level tests.

## Rejected alternatives

### Immediate in-place replacement

Rejected because the delivered controller has a different host/runtime model and unresolved schema, reference, audit-index, and ownership requirements.

### Permanent repository-only controller

Rejected as the final production control plane because it would retain the code and privileged automation authority in one trust boundary.

### Concurrent dual-writer operation

Rejected because controller state, Git history, approvals, and rollback would no longer have one authoritative owner.

## Validation and compliance

- Run
  `.integration-temp/offline-validation/venv/bin/python scripts/check_v10_1_prompt_stage_pack.py`
  and require the exact ten-stage chain to pass before requesting mapping
  approval.
- Execute exactly one transition stage per invocation; never advance from one
  stage to the next automatically.
- Run `python3 scripts/check_v10_1_mapping_readiness.py` before requesting mapping approval.
- Bind any approval to the exact base commit, transition-contract hash, mapping
  hash, prompt archive hash, prompt-stage hash-manifest hash, and verifier
  evidence.
- Keep `active_policy` and `active_roadmap` null through preparation.
- Require both source-tree and fresh-extraction delivery verifier runs before materialization readiness.
- Require a separately approved, hash-locked Linux qualification runtime before external-controller activation.

## Related documents

- [Automation status](../automation/current-status.md)
- [Delivery provenance v10.1](../delivery-provenance/v10.1/README.md)
- [ADR-0001 modular monolith](0001-modular-monolith.md)
- [ADR-0003 documentation governance](0003-documentation-versioning.md)
