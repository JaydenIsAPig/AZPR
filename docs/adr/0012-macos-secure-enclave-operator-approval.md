# ADR-0012: macOS Secure Enclave Operator-Approval Boundary

- **Status:** Accepted
- **Date:** 2026-08-11
- **Deciders:** Project owner
- **Supersedes:** ADR-0009 only for the inert source-placement restriction described here
- **Superseded by:** None

## Context

ADR-0011 requires a trusted authentication adapter before a digest-bound
approval can authorize execution. ADR-0009 kept delivered trusted-controller,
installation, and operator tooling outside the repository while their trust
boundary remained unresolved. The project owner has separately authorized an
inert, source-only implementation in an explicit repository allowlist. The
existing H0 transport ticket SHA-256-binds the original transition contract,
so changing that contract would invalidate an immutable checkpoint.

## Decision

Permit the source-only implementation described by
`automation/integration/v10.1/operator-approval-source-contract.json` without
modifying the bound v10.1 transition-contract bytes. This decision supersedes
ADR-0009 only to allow those inert repository paths. It does not supersede its
single-writer, activation, installation, qualification, or cutover controls.

The adapter uses a native Swift helper and the macOS Security,
LocalAuthentication, AppKit, and CryptoKit frameworks. An approved enrollment
ceremony may create one permanent P-256 Secure Enclave key with
`kSecAttrTokenIDSecureEnclave`,
`kSecAttrAccessibleWhenUnlockedThisDeviceOnly`, `privateKeyUsage`, and
`biometryCurrentSet`. The helper never creates or replaces a key during a
decision. Each Approve or Deny action creates a fresh `LAContext`, sets
authentication reuse to zero, and must complete
`SecKeyCreateSignature` with
`ecdsaSignatureMessageX962SHA256`; policy evaluation alone is not proof.

The controller verifies the canonical assertion using
`cryptography==46.0.4`, the exact ANSI X9.63 uncompressed P-256 public-key
encoding, a host-owned trust record, and an atomic host-owned replay ledger.
Subject and role come only from that trust record. The only currently allowed
role is `Head of AZPR Operations`. Repository content contains no authoritative
subject, helper path, ownership, public key, signer identity, trust state, or
enrollment record.

Approval, authorization, run, evidence, outcome, and commit eligibility remain
separate. The adapter can return an authorization object after complete
reverification and one-time nonce consumption, but this source-only stage does
not activate a controller or authorize an action or Git operation.

## Trust boundaries

- The repository owns inert source, schemas, tests, fixtures, documentation,
  and a null-valued trust template only.
- A later host administrator owns the installed helper, file ownership and
  permissions, code-signing or H0 hash pin, Secure Enclave key, trust record,
  replay ledger, authenticated subject, and revocation lifecycle.
- The helper recomputes the ticket digest from exact canonical ticket bytes;
  the controller independently verifies helper identity, assertion fields,
  public key, ECDSA signature, freshness, ticket/review bytes, target
  observations, and replay state.
- Model output is not authentication evidence and cannot select a helper,
  software signer, subject, role, key, trust record, or ledger.
- A software P-256 signer exists only as compiled test code and has no
  environment-variable, command-line, configuration, or production entry
  point.

## Consequences

### Positive

- Approve and Deny can be bound to exact ticket bytes and a biometric-protected
  nonexportable key after a separately approved installation.
- Cancel, expiry, drift, helper substitution, revoked trust, invalid signature,
  and replay fail without executable authority.
- The current H0 transport ticket and transition-contract digest remain
  unchanged.

### Negative or trade-offs

- macOS hardware qualification cannot be inferred from software fixtures or a
  successful build.
- `cryptography==46.0.4` becomes a pinned dependency of the later controller
  runtime and must be installed and verified during that separate ceremony.
- A hash-pinned unsigned helper is, at most, an H0 qualification limitation;
  production readiness requires an approved signing and deployment boundary.

## Deferred activation inputs

The operator subject, helper installation path, owner/group/mode, host trust
and replay-state paths, signing identity, key creation, enrollment, helper
artifact digest, and installation approval are deliberately unset. Their
selection changes the security boundary and requires a new immutable approval
identity, proposed as `AZPR-H0-OPERATORAUTH-20260811-001`. The adapter cannot
bootstrap that authority.

## Validation and compliance

- Build and test the Swift package on compatible macOS tooling; mark Secure
  Enclave and Touch ID hardware tests separately.
- Run the focused and complete Python suites with exactly
  `cryptography==46.0.4`.
- Validate schemas, canonical Swift/Python golden vectors, documentation,
  prompt pack, mapping readiness, approval ticket, and Git whitespace.
- Never install, enroll, activate, execute H0-T02, commit, merge, or push under
  this decision.

## Related documents

- [ADR-0009 staged controller transition](0009-staged-hybrid-controller-transition.md)
- [ADR-0011 digest-bound approval checkpoints](0011-digest-bound-approval-checkpoints.md)
- [Operator-authentication runbook](../runbooks/operator-authentication.md)
- [Approval checkpoint guide](../../automation/approvals/README.md)
- [Automation status](../automation/current-status.md)
