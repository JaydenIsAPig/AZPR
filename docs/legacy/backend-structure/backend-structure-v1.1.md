---
document_id: backend-structure
version: 1.1
document_status: superseded
implementation_status: partially implemented
approved_on: 2026-07-17
---

# Backend Structure v1.1

## Status statement

**Implemented:** Python 3.12 domain entities/value objects, lifecycle rules, domain errors/events, repository protocols, CQRS messages/handler protocols, and unit tests.
**Partially implemented:** The modular monolith has a tested domain/application-contract kernel but no use-case handlers or adapters.
**Planned:** Persistence, outbox, source acquisition, AI, notification, authentication, API, jobs, monitoring, and deployment.

## Technology decision

[ADR-0004](../../adr/0004-python-domain-kernel.md) selects Python 3.12 and standard-library-only domain/application contracts. No web framework, database/ORM, migration tool, job runner, package-manager workflow, artifact store, provider, or hosting target is selected.

## Aggregate boundaries and consistency rules

| Aggregate or owned concept | Owns / enforces | Cross-boundary references and consistency |
|---|---|---|
| `Jurisdiction` | Arizona pilot region identity and active state | Referenced by ID; Source/Permit cannot mutate it |
| `Source` | Source identity, jurisdiction association, source-family name, lifecycle | Does not own downloaded artifacts or import execution |
| `ImportBatch` | Batch lifecycle; membership of artifacts/source records; completion counts | Checks Source/Batch/Artifact IDs; persistence must atomically save state and events |
| `SourceArtifact` | Immutable acquisition metadata and SHA-256 digest | Append-only repository; bytes/storage are infrastructure concerns |
| `SourceRecord` | Source-level record provenance and parsed/rejected lifecycle | Independent of external response classes; links Source, Artifact, Batch by typed IDs |
| `Permit` | Observed permit identity, source-record provenance, address/parcel components, corrections/voiding | Owns `Address` and `ParcelReference` values; never owns Opportunity/Match state |
| `ClassificationResult` | Versioned method/provenance, classification, trade tags, confidence, evidence, one-time review | References Permit by ID; prior results are preserved by repository policy |
| `Opportunity` | Customer-independent interpretation and candidate/published/suppressed/expired lifecycle | References one or more Permits and Classification Results; no customer fields |
| `CustomerAccount` | Account lifecycle and trade, territory, filter, notification preference configuration | Owns configuration values; does not mutate shared Opportunities |
| `OpportunityMatch` | One Opportunity-to-Customer relation, explanation, match status, customer-scoped `LeadState` | Unique Opportunity/Customer pair is a repository/database constraint |
| `NotificationAttempt` | One consent-linked channel attempt and delivery lifecycle | References Match and idempotency key; retries require a new attempt, not state rewind |
| `ReviewTask` | Review subject, reason, assignee, resolution/cancellation lifecycle | References a typed subject category plus subject ID; does not mutate subject directly |

Within an aggregate, invariant checks and event recording occur synchronously. Cross-aggregate uniqueness, durable idempotency, and event publication require future persistence transactions and constraints; they are not claimed as implemented.

## Implemented dependency rules

- Domain modules import no application, transport, persistence, AI, notification-provider, or source-client code.
- External API response models cannot enter entities; adapters must translate them into command/domain values.
- Application repository protocols expose domain-specific operations and no provider payloads.
- Commands represent write intent; queries represent read intent; handler protocols do not require separate services or databases.
- Domain events are recorded by aggregates and pulled by application code. Transactional outbox persistence/publication remains planned.
- Source-specific endpoints, fields, pagination, and parsing remain outside the domain kernel.

## Implemented lifecycle groups

- Source: draft -> active/retired; active <-> paused; active/paused -> retired.
- Import Batch: started -> acquired -> processing -> completed/partially failed; nonterminal -> failed.
- Source Record: received -> parsed/rejected.
- Permit: active -> corrected/voided; corrected -> corrected with new provenance or voided.
- Classification Result: pending -> accepted/rejected.
- Opportunity: candidate -> published/suppressed; published -> suppressed/expired.
- Customer Account: active <-> suspended; active/suspended -> closed.
- Lead State: new -> saved/contacted/dismissed; saved -> contacted/dismissed; contacted -> dismissed.
- Opportunity Match: active -> excluded/expired.
- Notification Attempt: queued -> submitted/failed/suppressed; submitted -> delivered/failed.
- Review Task: open -> in progress/resolved/cancelled; in progress -> resolved/cancelled.

Terminal states do not reopen in the current model. A changed business requirement requires tests and current-document reconciliation.

## Repository ports

Protocols exist for Jurisdiction, Source, Source Artifact, Import Batch, Source Record, Permit, Classification Result, Trade Tag, Opportunity, Customer Account, Opportunity Match, Notification Attempt, and Review Task. They define no database, serialization, session, or network behavior. Optimistic version fields are present on aggregate roots; actual concurrency enforcement remains planned.

## CQRS contracts

Write messages cover registration/acquisition, permit creation, classification, opportunity/customer/match creation, configuration, lead-state changes, notification queuing, and review opening. Read messages cover permit/opportunity retrieval, customer matches, open reviews, and source import health. Only messages and handler protocols are implemented; use-case handlers and projections are planned.

## Planned bounded contexts and infrastructure

The bounded contexts in [ADR-0001](../../adr/0001-modular-monolith.md) remain approved. Current modules are a minimum kernel, not complete contexts. Persistence must eventually add stable keys, uniqueness constraints, append-only artifacts/results, optimistic concurrency, and an outbox. Authentication/authorization, consent enforcement at use-case boundaries, source-access compliance, encryption/secrets, and customer isolation require separate approved implementation work.

## Validation

- Standard-library unit tests cover value objects, invariants, state transitions, event creation, concept presence, forbidden generic names, and infrastructure-free contract imports.
- No database, integration, contract-provider, or end-to-end tests exist because those systems are not implemented.

## Related current documents

- [Project structure v1.1](../project-structure/project-structure-v1.1.md)
- [Business logic v1.1](../business-logic/business-logic-v1.1.md)
- [Business data v1.0](../../current/business-data-v1.0.json)
- [Frontend design v1.0](../../current/frontend-design-v1.0.md)
- [Backend structure log](../../logs/backend-structure-log-v1.1.md)
