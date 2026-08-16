# ADR-0013: Deterministic H0 Live-Target Fingerprint

- **Status:** Accepted
- **Date:** 2026-08-15
- **Deciders:** Project owner
- **Supersedes:** None
- **Superseded by:** None

## Context

The inert H0 Ansible live-validation pack requires exact target binding, but it
previously named only a SHA-256 value without defining the approved identity
fields or canonical bytes. Earlier Multipass transport evidence calculated a
non-authoritative configuration fingerprint for a different host-side scope.
That evidence does not govern H0-ALV target identity and cannot be promoted to
an authorization procedure.

The target fingerprint is security-relevant because an ambiguous or unstable
procedure could let an authorization for one disposable guest be replayed
against another. The procedure must still avoid turning machine identity into
permission: a matching fingerprint can identify a target but cannot establish
that a human authorized it.

## Decision

Adopt `AZPR_H0_TARGET_FINGERPRINT_V1` as defined byte-for-byte by
`automation/integration/v10.1/h0-ansible-live-stages/target-fingerprint-contract.json`.
The implementation observes nine non-secret fields inside the already-open
local guest session, independently of operator input:

1. kernel hostname as `target_id` from `/proc/sys/kernel/hostname`;
2. `/etc/machine-id`;
3. `ID` and `VERSION_ID` from `/etc/os-release`, parsed without execution;
4. architecture from `uname(2).machine`; and
5. name, UID, GID, and home from `getpwnam(3)` for `ubuntu`.

The contract fixes field-specific normalization and the H0-required Ubuntu
24.04/AArch64/reviewer values. Canonical bytes are a compact JSON object whose
first member is the contract discriminator and whose remaining members follow
the exact identity-field order. The encoding is UTF-8 with RFC 8259 escaping,
no byte-order mark, spaces, or trailing newline. SHA-256 produces 64 lowercase
hexadecimal characters. The golden vector fixes normalization, JSON text,
bytes, and digest.

Any missing, unreadable, duplicate, invalid, unsupported, or mismatched field
blocks without a usable digest. The complete procedure is re-run before each
live stage. No field may be substituted, omitted, or recovered from operator
text. A changed fingerprint requires new, separately governed authorization.

The project owner approved the exact contract SHA-256
`d35da355850ee1440ea454c4e2663dae7fb15778bb2c935283ec16d7771f1d8a`
through the narrow repository-governed ADR-0014 channel. The canonical checker
derives the attributable reference
`git:82ba27a1be4d1590e15f78a891568844639096dd:automation/approvals/procedure-decisions/AZPR_H0_TARGET_FINGERPRINT_V1.json`.
The protected contract, canonical request, and immutable review remain
unchanged; the contract's static `PROPOSED_PENDING_HUMAN_APPROVAL` marker is
not the readiness authority.

A supplied operator-input reference must bind that contract digest, affirm
procedure approval, bind the independently observed target digest, name the
allowed stage, and remain attributable and unexpired. Neither this ADR, the
procedure approval, the contract, a digest match, nor model output authorizes
a target, approves or qualifies an environment, activates the operator adapter
or a controller, or authorizes Ansible, H0-T02, the AZPR verifier, or Git.

## Consequences

### Positive

- Exact target identity is reproducible without a shell, network access,
  credentials, or host-side Multipass state.
- Canonical bytes and test vectors make independent implementations auditable.
- Machine identity, procedure approval, target authorization, and execution
  outcome remain separate.

### Negative or trade-offs

- A legitimate hostname, machine-ID, OS, architecture, or reviewer change
  invalidates the binding and requires a fresh human authorization.
- Cloned guests must have distinct machine IDs; the procedure intentionally
  blocks if that premise cannot be established.
- The decision adds another exact hash that must be reconciled in the H0 pack,
  contract, mapping, and operator reference.

### Risks and mitigations

- **Risk:** permissive normalization hides meaningful drift. **Mitigation:**
  normalize only ASCII whitespace/case where specified and enforce exact H0
  values without aliases.
- **Risk:** machine ID alone is copied with a clone. **Mitigation:** bind it
  together with hostname, OS, architecture, and complete reviewer identity,
  and require disposable-target confirmation through separate authority.
- **Risk:** a digest is mistaken for approval. **Mitigation:** schemas,
  implementation output, prompts, and documentation state
  `authority_effect=false` and require a separate human-owned reference.

## Alternatives considered

### Reuse the Multipass configuration fingerprint

Rejected because it is host-laboratory evidence, depends on Multipass-specific
configuration, covers a different scope, and lacks canonical governed bytes.

### Hash only hostname or machine ID

Rejected because either value alone is too easy to reuse, clone, or change
without exposing a complete H0 reviewer/platform mismatch.

### Include IP address, power state, boot ID, or runtime counters

Rejected because those fields are mutable session state and would make a
stable authorization binding dependent on ordinary reboot or DHCP changes.

## Validation and compliance

- Run `python3 -m pytest -q tests/test_h0_target_fingerprint.py`.
- Run `python3 scripts/check_h0_ansible_live_prompt_pack.py`.
- Run `python3 scripts/check_h0_ansible.py --ansible-bin-dir <pinned-bin>`.
- Validate any later human-supplied operator input with Draft 2020-12 JSON
  Schema and an enabled `date-time` `FormatChecker` through
  `scripts/h0_target_fingerprint.py validate-operator-input`.
- Never create the human operator input, access a guest, or run Ansible while
  validating this decision.

## Related documents

- [ADR-0010 Ansible qualification infrastructure](0010-ansible-qualification-infrastructure.md)
- [ADR-0011 digest-bound approvals](0011-digest-bound-approval-checkpoints.md)
- [ADR-0012 operator-approval boundary](0012-macos-secure-enclave-operator-approval.md)
- [ADR-0014 procedure-approval channel](0014-repository-governed-procedure-approval.md)
- [H0 Ansible runbook](../runbooks/ansible-qualification-environment.md)
- [H0 live-validation prompt pack](../../automation/integration/v10.1/h0-ansible-live-stages/README.md)
