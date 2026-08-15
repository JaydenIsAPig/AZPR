---
document_id: project-structure
version: 1.14
document_status: superseded
implementation_status: partially implemented
approved_on: 2026-08-07
---
# Project Structure v1.14

## Status statement

**Implemented:** v1.13 behavior plus the deterministic approval-checkpoint
component under `automation/approval_manager.py` and `automation/approvals/`.
New controller authority can be populated only from a version-controlled stage
manifest whose actions and evidence are validated before a canonical ticket
and digest-bound review view are generated. The current Multipass checkpoint is
`AZPR-H0-TRANSPORT-20260807-001`.

**Partially implemented:** the prior Multipass guest-control transport blocker
has been repaired and repeated fresh connections pass before and after a
disposable-guest restart. Live check-mode and two-apply idempotence validation
remain pending and are not inferred from transport evidence. The ticket has no
authenticated decision or execution outcome. The repository supplies a
fail-closed trusted-controller authentication adapter boundary but does not
implement or select an identity provider, signer trust store, or credential
lifecycle. Formal Linux environment approval, two independent verifier runs,
audit-owner identity, and final mapping approval remain unimplemented gates.

## Top-level responsibility boundaries

| Area | Responsibility | Authority boundary |
|---|---|---|
| `src/az_permit_radar/` | Domain-driven modular monolith and application/infrastructure adapters | Product behavior only; deterministic-first and customer-isolated |
| `automation/approval_manager.py` and `automation/approvals/` | Manifest validation, canonical approval tickets, immutable review views, execution guards, revision/delta classification, and separate outcome records | No human authentication or action execution; a trusted adapter and exact target observation are mandatory |
| Other `automation/` content | Repository controller, prompts, schemas, and staged integration workflow | Controllers remain inert during H0/H1/H2; no Ansible host provisioning |
| `infrastructure/ansible/` | Requested Linux state for H0 qualification preparation | Qualification inventory only; Ansible never approves, qualifies, or runs the AZPR verifier |
| `docs/delivery-provenance/v10.1/validation/ansible/` | Non-authoritative provisioning evidence | Separate from formal Linux Run A/Run B and human approval |

The Ansible inventory uses an operator-mediated local connection inside the
guest. This prevents ad-hoc SSH credential creation and keeps Multipass limited
to VM laboratory lifecycle. Privilege escalation is disabled by default and
allowlisted only for approved validation packages plus creation/reset of the
exact `/srv/azpr-validator` root.

## Approval record boundary

An Approval Ticket, authenticated Approval Decision, Execution Authorization,
Execution Run, Evidence Bundle, and Outcome Record are distinct controller
records. Ticket JSON uses `AZPR_CANONICAL_JSON_V1`; SHA-256 binds the human
decision to the exact ticket. A pre-execution guard regenerates the ticket from
its manifest, checks the immutable review bytes, reverifies authentication and
expiry, and requires exact target equality.

Simple non-authority revisions preserve the base approval ID and append
`-RNN`. Changes to targets, permissions, validity, security boundaries, or the
action list receive a new approval ID. Remediation uses a delta ticket only
when it introduces an action outside the original authority. Successful
execution is recorded only in a separate outcome linked to the approval ID.

## Ownership and access structure

| Area | Ownership | Implemented access boundary |
|---|---|---|
| Permit | Shared source-backed state | Read for a customer only through an authorized Match and linked Opportunity |
| Opportunity | Shared customer-independent projection | Read for a customer only through an authorized Match |
| Customer Account/configuration | Customer-owned | Customer relationship plus configuration read/write permission |
| Customer Match/explanation/lead state | Customer-owned | Customer relationship plus operation-specific permission and scoped repository method |
| Internal customer operations | Operations-owned access path | Separate internal role/permission and internal repository methods |

`domain/access.py` defines verified actor, relationship, role, permission, and
deterministic access outcomes. `application/queries.py` and
`application/commands.py` own normal customer use cases.
`infrastructure/customer_access.py` and the scoped Match-store methods implement
the current in-memory ports. Notes and relevance feedback remain unmodeled and
are not exposed. The top-level `infrastructure/ansible/` directory is host
qualification infrastructure and is not part of the Python application's
infrastructure adapter package.

## Prompt 11 integration seam

Prompt 11 must select authentication and supply a verified external subject as
`AccessActorId`, customer-account relationships, role, and permissions.
Framework middleware must create `AccessContext`, reject missing/invalid
authentication before handlers, and map authentication-required, forbidden,
and anti-enumeration not-found outcomes. Request payload customer IDs are never
evidence of ownership. This product authentication seam is separate from the
trusted-controller operator authentication adapter required by approval
checkpoints.

## Future production constraints

A selected database must enforce customer foreign keys and scoped uniqueness,
optimistic concurrency, and transactional writes. Normal application queries
must include customer predicates; internal operations must use separate
credentials/roles. Framework middleware, database authorization/row policies,
immutable security audit events, and abuse monitoring remain future decisions.

No staging or production Ansible inventory may be created by changing a
qualification variable. Either environment requires separate authorization,
physical inventory separation, security review, and a new/updated ADR.

## Related current documents

- [Backend structure v1.12](../../current/backend-structure-v1.12.md)
- [Business logic v1.12](../../current/business-logic-v1.12.md)
- [Business data v1.7](../../current/business-data-v1.7.json)
- [Frontend design v1.1](../../current/frontend-design-v1.1.md)
- [ADR-0008](../../adr/0008-customer-scoped-access-context.md)
- [ADR-0010](../../adr/0010-ansible-qualification-infrastructure.md)
- [ADR-0011](../../adr/0011-digest-bound-approval-checkpoints.md)
- [H0 qualification runbook](../../runbooks/ansible-qualification-environment.md)
- [Project structure log](../../logs/project-structure-log-v1.14.md)
