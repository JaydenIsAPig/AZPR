---
document_id: backend-structure
version: 1.0
document_status: superseded
implementation_status: planned
approved_on: 2026-07-16
---

# Backend Structure v1.0

## Status statement

**Implemented:** No backend application behavior is implemented. Documentation governance is implemented outside the backend.
**Planned:** The boundaries and constraints in this document are approved architecture direction.
**Partially implemented:** None.

## Architecture

The backend is planned as a domain-driven modular monolith under [ADR-0001](../../adr/0001-modular-monolith.md). It will be one deployable application unless an accepted later ADR authorizes a different topology. Language, framework, package manager, database product, job runner, artifact store, and hosting target remain **not selected**.

## Planned bounded contexts

| Context | Planned responsibility | Explicit exclusions |
|---|---|---|
| Identity and Access | Authentication, authorization, customer isolation, roles/policies | Permit interpretation and billing rules |
| Customer Configuration | Customer trades, geography, filters, channels, consent-linked preferences | Global opportunity state |
| Source Registry | Source identity, access metadata, schedules, policy constraints | Parsing source records into permits |
| Permit Ingestion | Acquisition adapters, immutable artifacts, batches, source records, parsing | Opportunity scoring and customer delivery |
| Permit Intelligence | Normalization and versioned deterministic/AI-assisted classification | Customer-specific matching |
| Geography | Address normalization and geographic rule evaluation | Customer lead workflow |
| Opportunity Matching | Opportunity derivation and explainable customer matches | Notification provider details |
| Lead Workflow | Customer-scoped lead state | Shared permit/opportunity mutation |
| Notification | Consent-aware intents, outbox, attempts, provider adapters | Match eligibility decisions |
| Analytics and Operations | Source health, review queues, operational telemetry | Source-of-truth business entities |
| Billing placeholder | Reserved boundary only | Billing behavior before requirements are approved |

## Planned dependency rules

- Domain code must not depend on web frameworks, databases, AI SDKs, notification providers, or source-specific clients.
- Application use cases coordinate domain behavior and depend on interfaces.
- Infrastructure adapters implement interfaces for persistence, source acquisition, AI, email, SMS, and other external systems.
- Source-specific fields, statuses, endpoints, and parsing remain within ingestion adapters and source mappings.
- Cross-context work uses explicit application interfaces and domain/integration events rather than direct table mutation.
- Asynchronous side effects that must follow committed state use a transactional outbox.
- Lightweight CQRS may separate write use cases from read projections; it does not require separate services or databases.

## Planned data integrity constraints

- Source artifacts are immutable and content-addressed or hash-verified.
- Every normalized Permit traces to Source, Import Batch, raw artifact/payload, external identifier when available, acquisition time, publication/issue date when available, and parser version.
- Reprocessing creates a new processing result rather than overwriting raw evidence.
- Stable keys, hashes, uniqueness constraints, and idempotency keys prevent duplicate permits, opportunities, matches, and notification intents.
- Permit, Opportunity, Customer Match, Notification, and Customer Lead State have separate identities and lifecycles.

## Planned interfaces

The exact signatures remain unapproved. The architecture requires adapter boundaries for source acquisition, artifact storage, persistence, time/identity generation, AI inference, email, SMS, and operational telemetry. Authentication and billing require separate approved requirements before provider selection.

## Validation expectations for future backend work

- Formatting, linting, static/type checks, unit tests, integration tests, build, and migration validation.
- Architecture tests for module dependency rules.
- Replay/idempotency tests for acquisition and delivery.
- Authorization and customer-isolation tests.
- Provenance, immutable-artifact, outbox, and failure-path tests.

## Related current documents

- [Project structure v1.0](../project-structure/project-structure-v1.0.md)
- [Business logic v1.0](../business-logic/business-logic-v1.0.md)
- [Business data v1.0](../../current/business-data-v1.0.json)
- [Frontend design v1.0](../../current/frontend-design-v1.0.md)
- [Backend structure log](../../logs/backend-structure-log-v1.0.md)
