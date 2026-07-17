---
document_id: frontend-design
version: 1.0
document_status: current
implementation_status: planned
approved_on: 2026-07-16
---

# Frontend Design v1.0

## Status statement

**Implemented:** No frontend application, design system, component library, routes, screens, or browser tests are implemented.
**Planned:** A narrow dashboard experience supporting the pilot workflow.
**Partially implemented:** None.

## Approved product outcomes

The planned frontend will allow an authenticated customer to view explainable Opportunity matches and manage customer-scoped lead state. Internal users are planned to review low-confidence classifications and monitor source health. Exact personas, roles, workflows, screen inventory, responsive breakpoints, accessibility target, and browser support remain **not selected**.

## Planned conceptual views

These are outcome-level plans, not approved wireframes or routes:

- Customer opportunity feed with source freshness and concise match reasons.
- Opportunity detail separating observed permit facts from derived classifications and match explanations.
- Customer configuration for trade/geography/filter preferences, subject to approved authorization rules.
- Customer lead-state controls that do not mutate shared Permit or Opportunity records.
- Notification preference and consent visibility before email/SMS behavior is enabled.
- Internal review/source-monitoring views appropriate to approved roles.

## Information rules

- Clearly distinguish source-observed facts, normalized values, deterministic derivations, and AI-derived values.
- Never display an unexplained match score.
- Show uncertainty and freshness without presenting inferred data as government fact.
- Do not expose provider errors, secrets, internal prompts, unnecessary personal data, or another customer's data.
- Destructive or high-impact actions require explicit confirmation and authorization.

## Architecture constraints

The frontend framework and rendering approach are **not selected**. “MVP” means Minimum Viable Product in this project. Model–View–Presenter is not approved by this document. BLoC is not approved and must not be introduced unless a selected framework and testing requirements justify it through a later decision.

The frontend must consume explicit application/query contracts and must not reach directly into persistence or source adapters. Read models may be optimized under lightweight CQRS without creating a separate service by default.

## Quality gates for future implementation

- Accessibility criteria and target conformance must be selected before delivery.
- Responsive behavior and supported browsers must be documented.
- Loading, empty, stale, partial-failure, unauthorized, and error states must be designed and tested.
- Critical authorization and customer-isolation behavior requires integration tests.
- Production screens must not rely on mock data or mocked delivery behavior.

## Related current documents

- [Project structure v1.5](project-structure-v1.5.md)
- [Backend structure v1.5](backend-structure-v1.5.md)
- [Business logic v1.5](business-logic-v1.5.md)
- [Business data v1.0](business-data-v1.0.json)
- [Frontend design log](../logs/frontend-design-log-v1.0.md)
