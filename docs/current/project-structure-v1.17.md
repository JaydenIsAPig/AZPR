---
document_id: project-structure
version: 1.17
document_status: current
implementation_status: partially implemented
approved_on: pending
---
# Project Structure v1.17

## Status statement

**Implemented as inert source:** v1.16 behavior plus three operator-assistance
prompts and a fail-closed result schema around H0-ALV-00 preparation. The
guides automate repository checks, guest-local deterministic observation, safe
operator-input validation, and explicit handoff analysis. They remain
read-only source and cannot cross a human checkpoint or invoke an H0-ALV stage.

**Pending human action:** the exact fingerprint contract remains unchanged at
the separately reviewed bytes, while repository authority still records
ADR-0013 and the contract as proposed pending an attributable governed
approval reference. No human-created operator input exists. The assistance
guides cannot create or infer either record.

**Implemented as an inert approval channel:** ADR-0014 supplies a canonical
procedure-review request, deterministic immutable review, strict decision
schema, non-authoritative template, governed future-decision path, and
read-only validator. The decision path remains empty. A future valid record is
bound to exact procedure bytes and a separate human-authored Git commit, and
can approve only the procedure definition.

**Not active or installed:** no guide, live-validation stage, operator-approval
adapter, helper, trust record, replay ledger, controller, H0-T02 action, or
Ansible live run is activated by this source change. The existing
`AZPR-H0-TRANSPORT-20260807-001` ticket remains immutable and has no
authenticated decision or execution outcome.

**Partially implemented:** transport engineering evidence and repository-level
Ansible validation exist, but live H0-ALV preflight, check mode, human diff
review, two-apply idempotence, reconciliation, formal environment approval,
independent verifier runs, audit-owner identity, and final mapping approval
remain unresolved gates.

## Top-level responsibility boundaries

| Area | Responsibility | Authority boundary |
|---|---|---|
| `src/az_permit_radar/` | Domain-driven modular monolith and application/infrastructure adapters | Product behavior only; deterministic-first and customer-isolated |
| `automation/approval_manager.py` and `automation/approvals/` | Manifest validation, canonical tickets, immutable reviews, execution guards, record separation, and schemas/templates | No human identity proof, helper installation, action execution, or Git mutation |
| `automation/operator_approval.py` | Pinned helper verification, canonical assertion verification, host-state replay protection, and exact pre-action authorization boundary | Inert until host-owned paths, trust, key, subject, and enrollment receive separate authority |
| `automation/procedure_approval.py` and procedure request/review records | Exact-byte, repository-attributed approval channel for the H0 fingerprint procedure definition | No decision is present; cannot authorize targets/actions, authenticate execution, activate anything, or advance H0 |
| `native/operator-approval-helper/` | Noneditable native review UI and Secure Enclave signature source | Source only; no installed helper or key-enrollment entry point is active |
| `scripts/h0_target_fingerprint.py` and the H0 live pack | Read-only exact Linux identity observation, normalization, canonical serialization, digest comparison, operator-reference validation, and human-checkpoint guidance | Identifies and validates only; cannot approve, authorize, qualify, access a guest from the host, author operator input, or invoke a live stage |
| Other `automation/` content | Repository controller, prompts, schemas, and staged integration workflow | Controllers remain inert during H0/H1/H2; no Ansible host provisioning |
| `infrastructure/ansible/` | Requested Linux state for H0 qualification preparation | Qualification inventory only; Ansible never approves, qualifies, or runs the AZPR verifier |
| `docs/delivery-provenance/v10.1/validation/ansible/` | Non-authoritative provisioning evidence | Separate from formal Linux Run A/Run B and human approval |

## Operator-assistance boundary

The H0 live pack contains three assistance prompts that are not stages:

1. `H0-ALV-GUIDE-00` runs host-side repository, authority, mapping, runtime,
   documentation, protected-hash, and inactive-adapter checks. It stops for an
   attributable procedure-approval reference or deliberate human entry into
   an already-approved guest-local session.
2. `H0-ALV-GUIDE-01` can run only after a human invokes it inside that local
   disposable-guest session. It observes the governed target identity and H0
   runtime/input constraints, then stops for the human's exact-target decision
   and personal operator-input authorship.
3. `H0-ALV-GUIDE-02` returns to the repository host, validates the human file
   without displaying it, repeats drift and authority checks, and stops for a
   deliberate separate H0-ALV-00 invocation.

`operator-assistance-result.schema.json` disallows a `PASS` or other
unattended-success outcome. Every successful technical path still returns
`HUMAN_ACTION_REQUIRED` with one exact checkpoint. Dangerous actions, operator
input authorship, inferred authorization, adapter/controller activation,
automatic next-prompt execution, H0-T02, Ansible playbooks, transport/network
change, protected-artifact change, and Git writes are fixed false.

The guides store no resume state. Each invocation repeats current observations
and cannot rely on prior conversation as authentication or authority. A guide
result can name the next guide or H0-ALV-00, but only a human can deliberately
start the separate invocation.

`H0-ALV-GUIDE-00` accepts only the ADR-0014 validator result. Missing approval
remains `AWAITING_HUMAN_DECISION`; a future accepted reference has the fixed
`git:<commit>:<decision-path>` form. Chat text, the template, an uncommitted or
modified record, a mismatched author, or changed request/procedure bytes cannot
satisfy the checkpoint.

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
authentication state. This source change grants none of those Git authorities.

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

- [Backend structure v1.12](backend-structure-v1.12.md)
- [Business logic v1.12](business-logic-v1.12.md)
- [Business data v1.7](business-data-v1.7.json)
- [Frontend design v1.1](frontend-design-v1.1.md)
- [ADR-0008](../adr/0008-customer-scoped-access-context.md)
- [ADR-0010](../adr/0010-ansible-qualification-infrastructure.md)
- [ADR-0011](../adr/0011-digest-bound-approval-checkpoints.md)
- [ADR-0012](../adr/0012-macos-secure-enclave-operator-approval.md)
- [Proposed ADR-0013](../adr/0013-h0-live-target-fingerprint.md)
- [Operator-authentication runbook](../runbooks/operator-authentication.md)
- [H0 qualification runbook](../runbooks/ansible-qualification-environment.md)
- [Project structure log](../logs/project-structure-log-v1.17.md)
