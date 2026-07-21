---
document_id: backend-structure
version: 1.11
document_status: superseded
implementation_status: partially implemented
approved_on: 2026-07-20
---
# Backend Structure v1.11

## Authoritative Batch processing

`InMemoryAcquisitionState` is the sole Import Batch and processing-queue owner. Acquisition enqueues only acquired or explicit reprocessing Batches. `AuthoritativeBatchParser` obtains a correlation-scoped claim, parses a detached working copy, coordinates Source Record snapshot rollback, and commits the terminal Batch back through the owner. Completed, partially failed, and failed Batches are acknowledged and leave the queue. A second correlation cannot claim the same Batch. Parser failure stores category plus `retryable` or `terminal`; retries use an explicit new reprocessing Batch.

## Normalization atomicity

`InMemoryNormalizationUnitOfWork` supplies one shared re-entrant lock to Permit, duplicate-candidate, and normalization Review Task repositories. It snapshots all three before the operation and restores them if any write or injected commit check fails. Readers using these stores share the lock, so process-local code cannot observe an intermediate commit. This is not database atomicity.

## End-to-end orchestration and traces

`EndToEndPermitProcessingWorkflow` runs acquisition → parsing → normalization/geocoding → classification/review → Opportunity projection → customer matching. Each correlation command is serialized and its result replayed without rerunning side effects. `ProcessingTraceEntry` carries safe source, Artifact/hash, Batch, Source Record, Permit, Classification, Opportunity, Match, customer, Review Task, stage, category, and retry identifiers where applicable; it excludes payloads, addresses, contact values, and credentials.

Normal rows, missing valuation, malformed partial batches, address review, low-confidence classification, probable/superseded duplicate handling, exact-radius boundaries, correction replay, persistence rollback, and two-customer matching have continuous fixture-driven coverage.

## Events and production worker boundary

Acquisition Job events precede Batch events in the in-memory acquisition outbox. Cross-stage traces are ordered synchronously, but later-stage domain events are not yet dispatched through a durable transactional outbox. A production worker must use database-backed claims/leases, atomic commit/outbox publication, retry scheduling, poison-message handling, and terminal acknowledgement; none is claimed here.

## Related current documents

- [Project structure v1.11](../project-structure/project-structure-v1.11.md)
- [Business logic v1.11](../business-logic/business-logic-v1.11.md)
- [Business data v1.6](../business-data/business-data-v1.6.json)
- [ADR-0007](../../adr/0007-in-memory-processing-unit-of-work.md)
- [Backend structure log](../../logs/backend-structure-log-v1.11.md)
