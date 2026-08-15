# ADR-0008: Customer-Scoped Access Context and Anti-Enumeration Boundary

- Status: Accepted
- Date: 2026-07-20

## Context

Customer Matches, explanations, lead state, and Customer Account configuration are customer-owned, while Permit and Opportunity are shared. Existing CQRS messages accepted caller-supplied customer IDs, repositories exposed broad `get/save` methods, and the only cross-customer check was a geography input invariant. No authentication system or framework has been selected, but object authorization must precede Prompt 11 onboarding.

## Decision

Require an explicit framework-neutral `AccessContext` on every customer-facing command and query. It carries a verified actor ID, customer-account relationships, role, and operation permissions. Customer handlers authorize before repository access, use customer-scoped ports, and re-check returned object ownership. Shared Opportunity and Permit facts are readable by a customer only through an authorized Match.

Use one anti-enumeration policy: to a customer, a cross-customer object and a nonexistent object both produce the same `ResourceNotFound` outcome. Missing authentication is distinct from an authenticated related actor lacking permission. Internal operations use a separate role, permission, service, and repository method rather than bypassing customer handlers.

Prompt 11 must construct the context only from verified authentication claims. This decision does not select identity provider, password/session/token design, web framework, middleware, database, or cryptography.

## Consequences

Normal application handlers cannot request every customer's records through their repository interfaces, and lead/configuration changes cannot cross customer ownership or mutate a shared Opportunity. Integration tests cover customer isolation and a deliberately leaky repository adapter.

In-memory locks are not durable authorization or database isolation. Production requires scoped queries/constraints, least-privilege roles, transactions, middleware, revocation/lifecycle behavior, audit events, and possibly database row policies after technology selection.

## Related documents

- [Project structure v1.17](../current/project-structure-v1.17.md)
- [Backend structure v1.12](../current/backend-structure-v1.12.md)
- [Business logic v1.12](../current/business-logic-v1.12.md)
- [Frontend design v1.1](../current/frontend-design-v1.1.md)
- [Business data v1.7](../current/business-data-v1.7.json)
