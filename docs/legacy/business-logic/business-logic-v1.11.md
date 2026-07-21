---
document_id: business-logic
version: 1.11
document_status: superseded
implementation_status: partially implemented
approved_on: 2026-07-20
---
# Business Logic v1.11

## Processing rules

- One correlation identifier represents one replayable end-to-end command. Repeating it returns the retained result and cannot duplicate domain outcomes.
- Acquisition state is authoritative for Batch state and queue membership. Parsing cannot directly finalize a detached Batch.
- A Batch processing claim is exclusive. Terminal parser outcomes remove its queue entry. Retryable failure requires explicit reprocessing with a new Batch identity.
- Permit, duplicate candidate, and normalization Review Task writes commit or roll back together within the in-memory unit of work.
- A later-stage failure never changes an earlier successful stage into failure, but the overall run is `failed` or `partially_failed`, never falsely `completed`.
- Review and exclusion are valid explicit record outcomes, distinct from technical failure.

## Uniqueness expectations

The governed scopes are source+content hash for Artifacts; correlation and Batch claim for processing; external key plus parser version for Source Records; canonical Permit identity; per-Permit Classification revision; one current Opportunity projection; one active Customer/Opportunity Match; and Review Task subject+reason identity. Current enforcement is lock/deterministic-ID/index based and process-local. These scopes must become database unique or exclusion constraints before multi-process production use.

## Failure and observability rules

Stages distinguish acquisition, storage, parsing, normalization, geocoding, classification, review requirement, Opportunity projection, and matching. Failures carry a safe category and retry disposition; they are not swallowed. Every record can be traced from Artifact/hash and Batch through its final IDs/outcome without logging raw payloads, addresses, secrets, phone numbers, or email content.

## Existing projection/matching rules

The v1.10 Opportunity fingerprint/revision, source-freshness, single-count score, historical snapshot, exclusion, and stale-Match rules remain in force.

## Related current documents

- [Project structure v1.11](../project-structure/project-structure-v1.11.md)
- [Backend structure v1.11](../backend-structure/backend-structure-v1.11.md)
- [Business data v1.6](../business-data/business-data-v1.6.json)
- [ADR-0007](../../adr/0007-in-memory-processing-unit-of-work.md)
- [Business logic log](../../logs/business-logic-log-v1.11.md)
