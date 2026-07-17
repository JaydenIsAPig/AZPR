---
document_id: business-logic
version: 1.3
document_status: superseded
implementation_status: partially implemented
approved_on: 2026-07-17
---

# Business Logic v1.3

## Status statement

**Implemented:** v1.2 registry/access rules plus idempotent scheduled/manual job creation, retryable attempts, per-attempt Import Batches, response metadata/hash capture, exact-duplicate suppression, changed-content archival, artifact-acquired events, source health/results, manual reprocessing, concurrency control, logs, and metrics.

**Partially implemented:** raw acquisition and archival are implemented against deterministic/local adapters. External scheduling, live source access, durable persistence/outbox publication, parsing, Source Record creation, and permit normalization remain planned.

## Scheduled acquisition rules

- Scheduler timestamp and Source ID derive a stable job identity.
- Recreating the same occurrence returns the same job.
- Each attempt creates a distinct Import Batch.
- Completed jobs replay without connector or storage calls.
- Disabled sources are skipped without fetch.

## Raw fetch and validation rules

- Access review and connector method must permit the fetch.
- Connector attempts obey explicit request policies.
- SHA-256 and safe response metadata are retained.
- Record parsing never occurs in the connector or acquisition workflow.

## Archival and duplicate rules

- Artifact identity is unique by Source plus SHA-256.
- Exact duplicates create duplicate batches and no processing work.
- New bytes use immutable content-addressed storage.
- Manual reprocessing references the archived artifact without mutation or another acquisition event.

## Failure and observability rules

- Failures are categorized, logged, metered, and recorded on job/batch/result.
- Failed jobs may retry under the same job identity with a new batch.
- Logs and metrics exclude payload bytes and request authentication/configuration.

## Related documents

- [Project structure v1.3](../project-structure/project-structure-v1.3.md)
- [Backend structure v1.3](../backend-structure/backend-structure-v1.3.md)
- [Business logic log](../../logs/business-logic-log-v1.3.md)

