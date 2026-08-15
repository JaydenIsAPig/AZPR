---
document_id: business-logic
version: 1.12
document_status: current
implementation_status: partially implemented
approved_on: 2026-07-20
---
# Business Logic v1.12

## Authorization rules

- Customer-facing commands and queries require an explicit `AccessContext`; customer ID input alone never authorizes access.
- The context must be authenticated, related to the target Customer Account, and contain the permission required for the operation.
- Cross-customer and nonexistent objects are indistinguishable to a customer and return the same not-found outcome.
- A related authenticated actor without an operation permission receives forbidden. Missing authentication receives authentication-required.
- Normal customer handlers use only customer-scoped repository ports and verify ownership of returned objects.
- Internal visibility is a separate role, permission, service, and repository path; it is not an override flag in customer handlers.

## Shared and customer-owned state

Permit and Opportunity remain shared. Customer Match, Match explanation/history, lead state, and Customer Account configuration remain customer-owned. A customer can view shared facts only through an authorized Match. Lead-state or configuration changes cannot mutate another Match or the shared Opportunity.

## Customer operations

- List/filter/sort operates only on the authenticated customer's Match set.
- Read Match, explanation, Opportunity, or Permit requires an authorized linking Match.
- Save, dismiss, and contacted are forward-only `LeadState` transitions on the owned active Match.
- Configuration writes mutate only the related Customer Account.
- Recalculation loads only that customer's existing Matches and reports explicit partial failures; another customer's Match is neither read nor recalculated.
- Customer notes and relevance feedback are absent because they are not yet approved domain behavior.

## Prompt 11 requirements

Prompt 11 must select authentication and map verified subject, Customer Account relationships, role, and permissions into `AccessContext`. It must define unauthenticated and unauthorized transport behavior, middleware placement, lifecycle/revocation, and security audit events. This version does not implement authentication, passwords, tokens, sessions, or cryptography.

## Related current documents

- [Project structure v1.17](project-structure-v1.17.md)
- [Backend structure v1.12](backend-structure-v1.12.md)
- [Business data v1.7](business-data-v1.7.json)
- [Frontend design v1.1](frontend-design-v1.1.md)
- [ADR-0008](../adr/0008-customer-scoped-access-context.md)
- [Business logic log](../logs/business-logic-log-v1.12.md)
