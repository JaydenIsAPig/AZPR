---
document_id: frontend-design
version: 1.1
document_status: current
implementation_status: planned
approved_on: 2026-07-20
---
# Frontend Design v1.1

## Status statement

**Implemented:** No frontend application, design system, routes, screens, or browser tests exist. Customer-scoped backend query/command contracts and access outcomes are implemented in memory.

**Planned:** A narrow authenticated dashboard consuming those contracts after Prompt 11 selects authentication and a frontend/API framework.

## Query-model distinctions

Future presentation must render these as distinct concepts:

- shared source-observed Permit facts;
- shared customer-independent Opportunity interpretation;
- customer-specific Match explanation and score history;
- customer-specific lead state and configuration.

Permit and Opportunity detail is reached through an authorized Customer Match. The frontend must not request broad customer lists or infer ownership from an ID in route/payload state.

## Required states

- **Unauthenticated:** authentication-required; Prompt 11 defines the sign-in/reauth flow.
- **Forbidden:** the authenticated related actor lacks an operation permission.
- **Not found:** missing and cross-customer objects share one anti-enumeration response and presentation.
- **Stale:** Match status/reason indicates that the shared Opportunity changed and recalculation is required.
- **Partial failure:** list/recalculation result explicitly reports incomplete processing without presenting the whole operation as successful.
- **Success/empty/error:** remain distinct from the states above.

The UI must not reveal whether another customer's Match, explanation, configuration, notes, or lead state exists. Notes and relevance feedback are not currently modeled and must not be designed as implemented behavior.

## Existing design constraints

The frontend framework, rendering approach, personas/roles, route inventory, accessibility target, breakpoints, and browser support remain unselected. “MVP” means Minimum Viable Product. Model–View–Presenter and BLoC remain unapproved. The frontend consumes application/query contracts and never persistence adapters directly.

## Related current documents

- [Project structure v1.12](project-structure-v1.12.md)
- [Backend structure v1.12](backend-structure-v1.12.md)
- [Business logic v1.12](business-logic-v1.12.md)
- [Business data v1.7](business-data-v1.7.json)
- [ADR-0008](../adr/0008-customer-scoped-access-context.md)
- [Frontend design log](../logs/frontend-design-log-v1.1.md)
