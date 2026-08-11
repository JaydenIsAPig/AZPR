---
document_id: project-structure
version: 1.13
document_status: superseded
implementation_status: partially implemented
approved_on: 2026-08-07
---
# Project Structure v1.13

## Status statement

**Implemented:** v1.12 behavior plus a strictly infrastructure-bound H0 Ansible
qualification-preparation layer under `infrastructure/ansible/`. The layer has
one qualification inventory, pinned local runtime metadata, four bounded roles,
preflight/prepare/seal/reset playbooks, failure-path contracts, and
non-authoritative provisioning evidence. It does not deploy the AZPR product or
receive approval, qualification, controller, prompt, policy, roadmap, provider,
materialization, or production authority.

**Partially implemented:** the prior Multipass guest-control transport blocker
has been repaired and repeated fresh connections pass before and after a
disposable-guest restart. Live check-mode and two-apply idempotence validation
remain pending and are not inferred from transport evidence.
Formal Linux environment approval, two independent verifier runs, audit-owner
identity, and final mapping approval remain unimplemented human/evidence gates.
Authorization remains enforced only in the in-process application boundary and
in-memory adapters. No authentication provider, web/API framework, middleware,
session/token handling, database, row-level policy, audit sink, or frontend is
implemented.

## Top-level responsibility boundaries

| Area | Responsibility | Authority boundary |
|---|---|---|
| `src/az_permit_radar/` | Domain-driven modular monolith and application/infrastructure adapters | Product behavior only; deterministic-first and customer-isolated |
| `automation/` | Repository controller, prompts, schemas, and staged integration workflow | Controllers remain inert during H0/H1/H2; no Ansible host provisioning |
| `infrastructure/ansible/` | Requested Linux state for H0 qualification preparation | Qualification inventory only; Ansible never approves, qualifies, or runs the AZPR verifier |
| `docs/delivery-provenance/v10.1/validation/ansible/` | Non-authoritative provisioning evidence | Separate from formal Linux Run A/Run B and human approval |

The Ansible inventory uses an operator-mediated local connection inside the
guest. This prevents ad-hoc SSH credential creation and keeps Multipass limited
to VM laboratory lifecycle. Privilege escalation is disabled by default and
allowlisted only for approved validation packages plus creation/reset of the
exact `/srv/azpr-validator` root.

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
evidence of ownership.

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
- [H0 qualification runbook](../../runbooks/ansible-qualification-environment.md)
- [Project structure log](../../logs/project-structure-log-v1.13.md)
