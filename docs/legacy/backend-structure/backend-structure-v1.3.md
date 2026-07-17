---
document_id: backend-structure
version: 1.3
document_status: superseded
implementation_status: partially implemented
approved_on: 2026-07-17
---

# Backend Structure v1.3

## Status statement

**Implemented:** v1.2 source-profile/connectors plus scheduled/manual Acquisition Jobs, per-attempt Import Batches, safe response metadata, SHA-256 identity, source+digest uniqueness, duplicate batches, retryable failures, manual reprocessing, atomic metadata finalization, artifact-acquired outbox events, processing suppression/enqueue decisions, metrics, and structured workflow logs.

**Partially implemented:** transaction semantics are exercised by a lock-serialized in-memory adapter and atomic local filesystem store. A durable database, transactional outbox publisher, distributed job claim/lease, production object lock, external scheduler, and live municipal connector remain not selected.

## Acquisition model

`AcquisitionJob` has a stable ID/idempotency key, source, trigger (`scheduled`, `manual`, or `manual_reprocess`), source schedule expression, scheduled occurrence, attempt count, timestamps, safe failure details, and lifecycle:

```text
pending -> running -> archived | duplicate | reprocessed | disabled
                   -> failed -> running (explicit retry)
```

Completed job replays return the existing result without fetching, storing, emitting another artifact event, or enqueueing processing. A failed job can be claimed again; each job attempt receives a deterministic, distinct Import Batch.

`AcquisitionRecord` stores job/source/batch identity, outcome, attempt, artifact/digest where available, safe failure details, and allowlisted response metadata. Result history is retained across retries.

## Import Batch and artifact behavior

Every claimed job creates a started Import Batch. Outcomes are:

- new valid content: artifact metadata is registered and the batch becomes `acquired`;
- exact duplicate: the batch becomes terminal `duplicate` and references the archived artifact;
- failure: the batch becomes `failed` with a safe category/message;
- disabled source: the batch becomes terminal `skipped` without connector execution;
- manual reprocessing: the batch becomes `acquired`, references the existing immutable artifact, and emits no new acquisition event.

`SourceArtifact` remains frozen and includes safe response metadata. Authorization, cookie, proxy authorization, Set-Cookie, and API-key attributes are rejected.

## Transaction boundaries

```text
create/recover job -> claim attempt/batch -> fetch/hash/store -> atomic metadata finalization
```

Blob storage is content addressed and create-once; metadata finalization rechecks Source+digest uniqueness while holding the state lock. Concurrent identical responses produce one archived artifact/processing batch and duplicate batches for the others.

## Events and downstream processing

New artifacts emit `ArtifactAcquired` and enter processing. Deliberate manual reprocessing also enters processing without a new acquisition event. Duplicate, failed, and skipped batches do not enter processing.

## Validation boundary

Acquisition validates safe transport/content facts only. Permit fields, dates, identifiers, and records remain parser responsibilities.

## Related documents

- [Project structure v1.3](../project-structure/project-structure-v1.3.md)
- [Business logic v1.3](../business-logic/business-logic-v1.3.md)
- [Backend structure log](../../logs/backend-structure-log-v1.3.md)

