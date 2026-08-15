---
document_id: project-structure
version: 1.16
document_status: superseded
implementation_status: partially implemented
approved_on: pending
---
# Project Structure v1.16

## Status statement

**Implemented as inert source:** v1.15 behavior plus a deterministic H0
live-target fingerprint implementation, exact proposed contract, golden
vector, Draft 2020-12 operator-input validation with enabled date-time format
checking, and focused failure-path tests. The procedure reads only fixed
non-secret Linux identity surfaces and has no execution or authorization
effect.

**Pending human approval:** ADR-0013 and the exact
`AZPR_H0_TARGET_FINGERPRINT_V1` contract remain proposed. A matching digest
identifies a target but does not authorize it. No human-created operator input
exists, and H0-ALV-00 cannot pass until a separately governed reference binds
both the approved procedure contract hash and the independently observed exact
target hash.

**Not active or installed:** no real helper path, owner, permission mode,
signing identity, key, public trust record, replay ledger, operator subject, or
enrollment exists. No controller uses the adapter. Secure Enclave and Touch ID
behavior is not hardware-qualified. The existing
`AZPR-H0-TRANSPORT-20260807-001` ticket remains immutable and has no
authenticated decision or execution outcome; H0-T02 remains stopped.

**Partially implemented:** the prior Multipass guest-control transport blocker
has been repaired and repeated fresh connections pass before and after a
disposable-guest restart. Live check-mode and two-apply idempotence validation
remain pending and are not inferred from transport evidence. Formal Linux
environment approval, independent verifier runs, audit-owner identity, final
mapping approval, fingerprint-procedure approval, exact live-target
authorization, and the separately governed operator-authentication
installation and enrollment ceremony remain unimplemented gates.

## Top-level responsibility boundaries

| Area | Responsibility | Authority boundary |
|---|---|---|
| `src/az_permit_radar/` | Domain-driven modular monolith and application/infrastructure adapters | Product behavior only; deterministic-first and customer-isolated |
| `automation/approval_manager.py` and `automation/approvals/` | Manifest validation, canonical tickets, immutable reviews, execution guards, record separation, and schemas/templates | No human identity proof, helper installation, action execution, or Git mutation |
| `automation/operator_approval.py` | Pinned helper verification, canonical assertion verification, host-state replay protection, and exact pre-action authorization boundary | Inert until host-owned paths, trust, key, subject, and enrollment receive separate authority |
| `native/operator-approval-helper/` | Noneditable native review UI and Secure Enclave signature source | Source only; no installed helper or key-enrollment entry point is active |
| `scripts/h0_target_fingerprint.py` and the H0 live pack | Read-only exact Linux identity observation, normalization, canonical serialization, digest comparison, and operator-reference validation | Proposed procedure only; identifies a target but cannot approve, authorize, qualify, access, or mutate it |
| Other `automation/` content | Repository controller, prompts, schemas, and staged integration workflow | Controllers remain inert during H0/H1/H2; no Ansible host provisioning |
| `infrastructure/ansible/` | Requested Linux state for H0 qualification preparation | Qualification inventory only; Ansible never approves, qualifies, or runs the AZPR verifier |
| `docs/delivery-provenance/v10.1/validation/ansible/` | Non-authoritative provisioning evidence | Separate from formal Linux Run A/Run B and human approval |

The accepted operator-approval source extension is
`automation/integration/v10.1/operator-approval-source-contract.json`. It does
not modify the transition-contract bytes bound by the current H0 ticket and
grants no install, enrollment, activation, execution, commit, merge, or push
authority. The later fingerprint proposal is separately governed by ADR-0013
and does not enlarge that accepted source extension.

## H0 target-fingerprint boundary

`AZPR_H0_TARGET_FINGERPRINT_V1` orders `target_id`, `machine_id`,
`operating_system_id`, `operating_system_version_id`, `architecture`,
`reviewer_name`, `reviewer_uid`, `reviewer_gid`, and `reviewer_home`. The
implementation observes each field inside the local guest session from
`/proc/sys/kernel/hostname`, `/etc/machine-id`, `/etc/os-release`, `uname(2)`,
and `getpwnam(3)` rather than trusting operator-input values.

Normalization is deliberately narrow and the H0 platform/reviewer values are
exact. Canonical compact JSON uses a fixed member order and UTF-8 bytes with no
BOM or trailing newline; SHA-256 returns lowercase hexadecimal. Missing,
invalid, unsupported, or mismatched fields block without a digest fallback.
The complete observation repeats before each stage.

The repository template remains null-valued and non-authorizing. A human must
separately approve the exact procedure contract hash, observe and authorize
the exact disposable target, and create the operator input. The validator
checks the supplied reference with Draft 2020-12 and an active `date-time`
format checker, recomputes both bindings, and retains no credential values. It
does not authenticate the authorizer or activate the operator-approval adapter.

## Operator-approval trust boundary

`AZPR_OPERATOR_DECISION_ASSERTION_V1` signs exactly the decision, ticket and
approval identity, canonical ticket SHA-256, nonce, request/decision/expiry
timestamps, authenticator event, authenticator ID, and key ID. The envelope
retains the DER ECDSA signature, exact public-key digest, algorithm, and helper
build identity. Python derives the authenticated subject and allowed role only
from the host trust record and independently verifies the signature with
`cryptography==46.0.4`.

Before invocation, the adapter requires an absolute regular non-symlink Mach-O
helper outside the repository, exact ownership/mode/hash, optional designated
code-signing requirement, expected build identity, active key, and strict
X9.63 public key. It invokes one argv element with no shell, a sanitized
environment, timeout, and bounded protocol output. Pending and consumed nonces
are locked and atomically replaced in host-owned state outside the repository.

Approve and Deny both sign through a fresh zero-reuse `LAContext` and the
`biometryCurrentSet`-protected key. Cancel, close, timeout, unavailable or
failed biometrics, missing/invalidated key, and signing failure return only a
non-authorizing terminal response. The helper never regenerates a missing key.

## Approval, execution, and commit separation

An Approval Ticket, signed assertion, Approval Decision, Execution
Authorization, Execution Run, Evidence Bundle, and Outcome Record are distinct
records. Immediately before each material action the adapter regenerates the
ticket/review, reverifies signature/trust/freshness/replay state, reobserves all
targets, and atomically claims the action for one run. Approval permits an
attempt; it never establishes a successful outcome.

Commit eligibility is only a pure guard. It requires an active contract and
stage that independently permit commit, the recorded base commit, an isolated
branch, exact changed-path allowlisting, passed action and independent tests,
separate evidence/outcome records, `git diff --check`, and no trust, key, or
authentication state. This source stage grants none of those Git authorities.

## Ownership and access structure

| Area | Ownership | Implemented access boundary |
|---|---|---|
| Permit | Shared source-backed state | Read for a customer only through an authorized Match and linked Opportunity |
| Opportunity | Shared customer-independent projection | Read for a customer only through an authorized Match |
| Customer Account/configuration | Customer-owned | Customer relationship plus configuration read/write permission |
| Customer Match/explanation/lead state | Customer-owned | Customer relationship plus operation-specific permission and scoped repository method |
| Internal customer operations | Operations-owned access path | Separate internal role/permission and internal repository methods |

`domain/access.py` defines verified actor, relationship, role, permission, and
deterministic access outcomes. Product authentication is separate from the
controller operator-authentication adapter. Prompt 11 must still select its
own product identity provider and middleware; request payload customer IDs are
never evidence of ownership.

## Deferred installation and production limits

The proposed installation identity is
`AZPR-H0-OPERATORAUTH-20260811-001`. A human must approve its exact host, OS,
architecture, built helper digest, signing identity or explicit H0 hash-pin
limitation, install path, owner/mode, application tag, key access-control
flags, trust and replay paths, subject, role, test, revocation, recovery,
rollback, and prohibited fallback methods through the independently verified
project-owner channel. The adapter cannot approve its own installation.

An unsigned hash-pinned local helper cannot be called production-ready.
Software signing fixtures cannot qualify Secure Enclave, Touch ID,
`biometryCurrentSet`, password/Watch fallback exclusion, or code-signature
enforcement. A database, framework middleware, audit sink, production host,
and external controller cutover remain future governed decisions.

## Related current documents

- [Backend structure v1.12](../../current/backend-structure-v1.12.md)
- [Business logic v1.12](../../current/business-logic-v1.12.md)
- [Business data v1.7](../../current/business-data-v1.7.json)
- [Frontend design v1.1](../../current/frontend-design-v1.1.md)
- [ADR-0008](../../adr/0008-customer-scoped-access-context.md)
- [ADR-0010](../../adr/0010-ansible-qualification-infrastructure.md)
- [ADR-0011](../../adr/0011-digest-bound-approval-checkpoints.md)
- [ADR-0012](../../adr/0012-macos-secure-enclave-operator-approval.md)
- [Proposed ADR-0013](../../adr/0013-h0-live-target-fingerprint.md)
- [Operator-authentication runbook](../../runbooks/operator-authentication.md)
- [H0 qualification runbook](../../runbooks/ansible-qualification-environment.md)
- [Project structure log](../../logs/project-structure-log-v1.16.md)
