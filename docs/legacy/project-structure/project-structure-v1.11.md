---
document_id: project-structure
version: 1.11
document_status: superseded
implementation_status: partially implemented
approved_on: 2026-07-20
---
# Project Structure v1.11

## Status statement

**Implemented:** v1.10 behavior plus one synchronous modular-monolith workflow from acquisition through Customer Match, authoritative Import Batch/queue ownership, process-local normalization rollback, correlated stage traces, explicit outcomes, and serialized replay/concurrency boundaries.

**Partially implemented:** all repositories, processing leases, the trace ledger, rollback snapshots, and the outbox remain in-memory. No production database, worker, API/UI, durable lease, transactional outbox dispatcher, or migration is implemented.

## Repository and transaction ownership

| Owner | Aggregates/data | Implemented boundary |
|---|---|---|
| `InMemoryAcquisitionState` | Acquisition Job, Artifact metadata, Import Batch, acquisition result, processing queue/claim, acquisition outbox | Lock-serialized job claim/finalization and parser claim/terminal acknowledgement |
| Immutable artifact store | Raw Artifact bytes by source + SHA-256 | Create-once content-addressed file write; metadata finalization is a separate boundary |
| `InMemorySourceRecordRepository` | Source Records and latest external-key index | Snapshot/restore coordinated with authoritative Batch parsing |
| `InMemoryNormalizationUnitOfWork` | Permits, duplicate candidates, normalization Review Tasks | Shared lock, snapshot rollback, no partial visible state inside this process |
| `InMemoryClassificationState` | Classification Results and classification Review Tasks | One lock-serialized Result/review commit and current-revision constraint |
| Opportunity/Match stores | Current Opportunity projections and customer Matches | Repository-exclusive generation/replay; stable active identities |
| Processing run/trace stores | Correlation command result and privacy-safe stage entries | One result per correlation ID and ordered in-process trace entries |

## Vertical workflow

`application/processing.py` coordinates acquisition, authoritative parsing, normalization, classification, publication, and customer matching. Individual stages remain independently invokable. A final record outcome is Match created, explicitly excluded, Review Task required, or failed with stage/category/retry disposition.

## Future production constraints

A later approved database must enforce unique source+digest Artifact metadata, processing command/Batch claims, Source Record external identity by parser version, canonical Permit identity, Classification revision/currentness, one active Opportunity projection, one active Customer/Opportunity Match, and Review Task idempotency. Batch/record commits, normalization writes, projection/stale-Match changes, and published events require database transactions plus a transactional outbox. This version does not select a database.

## Related current documents

- [Backend structure v1.11](../backend-structure/backend-structure-v1.11.md)
- [Business logic v1.11](../business-logic/business-logic-v1.11.md)
- [Business data v1.6](../business-data/business-data-v1.6.json)
- [Frontend design v1.0](../frontend-design/frontend-design-v1.0.md)
- [ADR-0007](../../adr/0007-in-memory-processing-unit-of-work.md)
- [Project structure log](../../logs/project-structure-log-v1.11.md)
