---
document_id: business-logic
version: 1.2
document_status: superseded
implementation_status: partially implemented
approved_on: 2026-07-17
---

# Business Logic v1.2

## Status statement

**Implemented:** all v1.1 domain rules plus source-profile validation, source-access preflight, raw acquisition limits/retries, checksum verification, immutable local artifact writes, acquisition health timestamps, structured failures/logging, and deterministic fake/manual acquisition tests.

**Partially implemented:** acquisition stops after raw artifact creation. Import Batch transaction handling, parsing, Source Record creation, permit normalization, scheduling, live municipal access, production persistence, and monitoring remain planned.

## Source registry rules

- Every configured source has an Arizona jurisdiction, stable source ID, source name, acquisition method, schedule/time zone, file contract, parser contract, historical/limitation notes, operational owner, and explicit access-review status.
- A network source cannot be enabled without an absolute endpoint; endpoint configuration cannot contain URL credentials or secret-bearing headers.
- Expected date fields and unique identifiers are part of the source contract and must be nonempty and unique. They inform the later parser but are not parsed by connectors.
- Disabled sources report disabled health. Acquisition success records both attempted and successful timestamps and healthy status; terminal acquisition failure records the attempt and failing status.
- Pending or restricted access review blocks acquisition before connector execution. No CAPTCHA bypass or access-control circumvention is allowed.

## Acquisition rules

- Callers provide an explicit user agent, timeout, response-byte ceiling, per-run request ceiling, and retry policy.
- Only failures categorized as retryable are retried. Attempts never exceed either configured ceiling.
- Connector output remains raw bytes. It cannot create permits, source records, classifications, or opportunities.
- Every nonempty payload receives a SHA-256 digest before storage. The immutable store verifies the digest before creation and after an existing content key is found.
- Identical bytes are idempotent at the artifact-storage level: the same content key is reused and bytes are not overwritten.
- Each preflight failure and connector attempt produces a structured log entry using safe messages and explicit failure categories.

## Implemented connector scope

`FakeConnector` is for deterministic tests. `ManualFixtureConnector` reads only a caller-selected file contained within a configured fixture directory and enforces the same byte limit. Neither parses content.

No live Tucson or Pima source is selected. A live connector may be implemented only after the [source onboarding checklist](../../governance/source-onboarding-checklist.md) records an approved access review, stable contract, limits, ownership, fixture, and parser handoff.

## Existing business rules

The domain distinctions, aggregate invariants, lifecycle rules, deterministic-first policy, explainability, consent, and provenance requirements documented in [business logic v1.1](business-logic-v1.1.md) remain in force.

## Remaining consistency boundary

The coordinator returns immutable `SourceArtifact` metadata but does not persist an Import Batch or artifact repository transaction. Production implementation must atomically associate the artifact with its batch and persist outbox events. Local filesystem permissions do not establish production retention, object lock, authorization, or disaster recovery.

## Related current documents

- [Project structure v1.2](../project-structure/project-structure-v1.2.md)
- [Backend structure v1.2](../backend-structure/backend-structure-v1.2.md)
- [Business data v1.0](../../current/business-data-v1.0.json)
- [Source acquisition runbook](../../runbooks/source-acquisition.md)
- [Business logic log](../../logs/business-logic-log-v1.2.md)
