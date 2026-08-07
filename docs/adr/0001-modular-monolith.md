# ADR-0001: Domain-Driven Modular Monolith

- **Status:** Accepted
- **Date:** 2026-07-16
- **Deciders:** Project owner
- **Supersedes:** None
- **Superseded by:** None

## Context

The repository is pre-implementation. The product charter calls for a narrow Arizona pilot and distinguishes multiple business capabilities with strong provenance, idempotency, consent, and explainability requirements. A distributed system would add deployment and consistency overhead before the product has validated one vertical slice. An unstructured monolith would risk collapsing core concepts and embedding external-source behavior into shared logic.

## Decision

AZ Permit Radar will be designed as a domain-driven modular monolith: one deployable application by default, with explicit bounded-context modules, dependency direction, application interfaces, and separately modeled domain concepts.

The planned bounded contexts are Identity and Access, Customer Configuration, Source Registry, Permit Ingestion, Permit Intelligence, Geography, Opportunity Matching, Lead Workflow, Notification, Analytics and Operations, and a Billing placeholder.

Modules may use lightweight CQRS, domain events, and integration events. Reliable asynchronous side effects use a transactional outbox. External sources, storage, AI, notification providers, and other external systems are isolated behind adapter interfaces. This decision does not select a language, framework, database product, job runner, or hosting target.

Microservices require a later accepted ADR supported by operational or scaling evidence. A module is not a service merely because it has a bounded context.

## Consequences

### Positive

- One deployment keeps the pilot operationally small.
- Explicit boundaries protect domain language and make future extraction possible if evidence justifies it.
- Local transactions simplify provenance, idempotency, matching, and outbox consistency.

### Negative or trade-offs

- Boundary discipline must be enforced within one codebase.
- Shared database access can tempt cross-module coupling.
- Scaling and deployment remain application-wide until a later decision.

### Risks and mitigations

- **Risk:** A “shared” module becomes a dumping ground. **Mitigation:** Keep shared primitives minimal and use module-owned interfaces.
- **Risk:** Direct cross-module table access bypasses invariants. **Mitigation:** Use application interfaces/events and architecture tests.
- **Risk:** Placeholder modules imply behavior. **Mitigation:** Label unimplemented modules as planned and avoid speculative code.

## Alternatives considered

### Microservices

Rejected for the pilot because independent deployments, distributed consistency, observability, and operational overhead are not justified.

### Unstructured layered monolith

Rejected because technical layers alone do not protect the domain distinctions required by the charter.

## Validation and compliance

Future implementation must include module-boundary tests, no direct domain dependency on infrastructure SDKs, and documented exceptions through ADRs.

## Related documents

- [Backend structure](../current/backend-structure-v1.12.md)
- [Project structure](../current/project-structure-v1.13.md)
- [Domain glossary](../governance/domain-glossary.md)
