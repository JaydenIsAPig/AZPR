---
document_id: backend-structure
version: 1.12
document_status: current
implementation_status: partially implemented
approved_on: 2026-07-20
---
# Backend Structure v1.12

## Access context

`AccessContext` contains a verified actor identifier, either customer or internal role, explicit customer-account relationships, and permissions. An unauthenticated context carries none of those claims. Customer and internal permissions cannot be mixed. The type is a framework-neutral input contract, not proof that authentication has occurred; Prompt 11's adapter must construct it only from verified provider/middleware claims.

## Customer query boundary

Every customer query includes `AccessContext`, target Customer Account ID, and—where object data is requested—the Customer Match ID. `CustomerQueryService` authorizes before repository access and checks returned object ownership again. It supports scoped Match listing/filtering/sorting, one Match, linked shared Opportunity and Permit facts, customer-specific explanation, and customer configuration.

Cross-customer and nonexistent resources both raise the same `ResourceNotFound` message. This prevents authenticated customers from enumerating object existence. Missing authentication raises `AuthenticationRequired`; a related actor missing a permission raises `ForbiddenAccess`. A future transport may map these to 401, 404, and 403 respectively without exposing cross-customer existence.

## Customer command boundary

Save, dismiss, contacted, generic lead transition, configuration changes, and customer-only Match recalculation require explicit access context and permission. Lead/configuration updates use atomic customer-scoped in-memory update operations. Recalculation loads only the target customer's Matches and Customer Account, then reads shared Opportunities/Permits; it reports per-Match partial failure without broad customer enumeration.

Customer notes and relevance feedback are not modeled or approved, so no note/feedback command or query exists.

## Repository and internal paths

Normal Customer Account and Match ports expose only `get/list/update_for_customer` operations. The in-memory Match adapter retains internal generator methods, but normal handlers are typed against scoped ports and perform defense-in-depth owner checks. Operations/support listing uses `InternalCustomerQueryService`, `INTERNAL_CUSTOMER_READ`, and explicit `list_for_internal`; a customer context cannot invoke it.

## Persistence and middleware boundary

Current locks and deep copies provide only process-local isolation. A production adapter requires customer-keyed indexes and constraints, optimistic concurrency, transactions, least-privilege database roles, and possibly row-level security after database selection. Authentication verification, credential/session/token behavior, HTTP middleware, CSRF/CORS policy, rate limits, and security-event transport remain Prompt 11/framework work.

## Related current documents

- [Project structure v1.17](project-structure-v1.17.md)
- [Business logic v1.12](business-logic-v1.12.md)
- [Business data v1.7](business-data-v1.7.json)
- [Frontend design v1.1](frontend-design-v1.1.md)
- [ADR-0008](../adr/0008-customer-scoped-access-context.md)
- [Backend structure log](../logs/backend-structure-log-v1.12.md)
