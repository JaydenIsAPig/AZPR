---
document_id: project-structure
version: 1.12
document_status: current
implementation_status: partially implemented
approved_on: 2026-07-20
---
# Project Structure v1.12

## Status statement

**Implemented:** v1.11 behavior plus a framework-neutral Identity and Access contract, customer-scoped query and command services, scoped repository ports/adapters, an explicit internal query path, anti-enumeration errors, and integration-level customer-isolation coverage.

**Partially implemented:** authorization is enforced only in the in-process application boundary and in-memory adapters. No authentication provider, web/API framework, middleware, session/token handling, database, row-level policy, audit sink, or frontend is implemented.

## Ownership and access structure

| Area | Ownership | Implemented access boundary |
|---|---|---|
| Permit | Shared source-backed state | Read for a customer only through an authorized Match and linked Opportunity |
| Opportunity | Shared customer-independent projection | Read for a customer only through an authorized Match |
| Customer Account/configuration | Customer-owned | Customer relationship plus configuration read/write permission |
| Customer Match/explanation/lead state | Customer-owned | Customer relationship plus operation-specific permission and scoped repository method |
| Internal customer operations | Operations-owned access path | Separate internal role/permission and internal repository methods |

`domain/access.py` defines verified actor, relationship, role, permission, and deterministic access outcomes. `application/queries.py` and `application/commands.py` own normal customer use cases. `infrastructure/customer_access.py` and the scoped Match-store methods implement the current in-memory ports. Notes and relevance feedback remain unmodeled and are not exposed.

## Prompt 11 integration seam

Prompt 11 must select authentication and supply a verified external subject as `AccessActorId`, customer-account relationships, role, and permissions. Framework middleware must create `AccessContext`, reject missing/invalid authentication before handlers, and map authentication-required, forbidden, and anti-enumeration not-found outcomes. Request payload customer IDs are never evidence of ownership.

## Future production constraints

A selected database must enforce customer foreign keys and scoped uniqueness, optimistic concurrency, and transactional writes. Normal application queries must include customer predicates; internal operations must use separate credentials/roles. Framework middleware, database authorization/row policies, immutable security audit events, and abuse monitoring remain future decisions.

## Related current documents

- [Backend structure v1.12](backend-structure-v1.12.md)
- [Business logic v1.12](business-logic-v1.12.md)
- [Business data v1.7](business-data-v1.7.json)
- [Frontend design v1.1](frontend-design-v1.1.md)
- [ADR-0008](../adr/0008-customer-scoped-access-context.md)
- [Project structure log](../logs/project-structure-log-v1.12.md)
