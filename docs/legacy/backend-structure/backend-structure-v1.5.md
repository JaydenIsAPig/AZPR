---
document_id: backend-structure
version: 1.5
document_status: superseded
implementation_status: partially implemented
approved_on: 2026-07-17
---

# Backend Structure v1.5

## Status statement

**Implemented:** v1.4 parser outputs plus deterministic Permit/Address/party/parcel normalization, registered-jurisdiction resolution, source/geocoder coordinates, geocoder metadata, reviewable address failures, layered duplicate detection, correction snapshots, manual merge/distinct decisions, and supersession history.

**Partially implemented:** persistence is in-memory and workflow commits are not a durable database transaction. No production geocoder, normalized Permit repository schema, duplicate-review UI/API, external queue, or Permit projection outbox is selected.

## Normalization flow

```text
parsed Source Record
  -> registered jurisdiction resolution
  -> deterministic Permit field normalization
  -> deterministic address/parcel/party normalization
  -> source coordinates or geocoder adapter
  -> Source + external-ID/fingerprint exact checks
  -> Permit create/correct/exact-evidence attach
  -> jurisdiction/address/type/date similarity check
  -> probable duplicate review candidate when warranted
```

Normalization reads parsed values and never mutates a Source Artifact or Source Record.

The synthetic Tucson fixture parser is version 1.1.0 for this contract and maps optional status, type, application date, contractor/applicant, parcel, jurisdiction, latitude, and longitude fields into canonical parser values.

## Permit and address model

`Permit` now retains municipal authority status separately from aggregate lifecycle, normalized type, description, application/issue dates, valuation, parties, address, parcel, parser version, source evidence, correction history, merged Permit IDs, and supersession target.

`Address` retains raw text, normalized components, resolution status, coordinate source, optional geocoder result, and review reason. A geocoder result stores provider, resolution timestamp, quality, confidence, and coordinates. Source-provided coordinates are marked separately and do not invoke the geocoder.

## Duplicate evidence and resolution

- Source + external identifier: exact identity layer. Same fingerprint attaches evidence; changed fingerprint applies a correction with a previous snapshot.
- Source + record fingerprint: exact identity fallback when an external identifier is absent.
- Jurisdiction + normalized address + normalized type + date: similarity score. Scores at least 75 create a probable candidate and review task; no automatic merge occurs.
- Manual decision: a retained actor/rationale/timestamp record resolves a candidate as merged or distinct.

Manual merge keeps the existing Permit canonical, absorbs the duplicate's Source Record evidence, and marks the duplicate Permit superseded. Both Permits and the decision remain queryable.

## Address behavior

The deterministic fixture normalizer standardizes case, whitespace, directionals, street suffixes, apartment/unit and suite formats, Arizona region codes, ZIP/ZIP+4, parcel punctuation, and coordinates represented as decimal strings. It is intentionally not an unrestricted postal parser.

If no source coordinates exist, geocoding occurs only through the application adapter. A null/failed result produces `review_required` and an Address review task; raw address values are excluded from structured logs and metric labels.

## Transaction boundary

The current workflow performs normalization, exact/probable lookup, Permit save, candidate save, and review save through separate in-memory ports. A production unit of work must atomically persist Permit/evidence/history, duplicate candidate/manual decision, review task, and downstream outbox work. Raw evidence remains unchanged if a normalization commit fails.

## Observability

Structured logs include Source/Source Record/Permit IDs, parser version, outcome, duplicate layer, and review count. Metrics count normalization outcomes and manual duplicate decisions using controlled labels. Contractor, applicant, address, parcel, and description values are excluded.

## Related current documents

- [Project structure v1.5](../project-structure/project-structure-v1.5.md)
- [Business logic v1.5](../business-logic/business-logic-v1.5.md)
- [Business data v1.0](../business-data/business-data-v1.0.json)
- [Permit normalization runbook](../../runbooks/permit-normalization.md)
- [Backend structure log](../../logs/backend-structure-log-v1.5.md)
