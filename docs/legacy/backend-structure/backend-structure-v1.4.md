---
document_id: backend-structure
version: 1.4
document_status: superseded
implementation_status: partially implemented
approved_on: 2026-07-17
---

# Backend Structure v1.4

## Status statement

**Implemented:** v1.3 acquisition plus deterministic file decoding, format validation, row extraction, alias mapping, normalization, validation, rejection reporting, stable external keys, Source Record persistence ports/adapters, import reports, checksum reads, and parser logs/metrics.

**Partially implemented:** parser persistence and batch mutation use local/in-memory adapters. A durable transactional parser unit of work, report repository, distributed processing claim, production archive reader, parser registry service, and Permit projection remain not selected.

## Parser stages

```text
immutable Source Artifact bytes
  -> file decoder
  -> format validator
  -> row/entry extractor
  -> source field mapper
  -> value normalizer
  -> record validator
  -> stable external-record key
  -> Source Record or quarantine result
  -> Import Report
```

Each stage is an application protocol. The CSV and fixture-specific implementations live in infrastructure. Connectors do not import or call parsing code.

## Parsed values and Source Records

Each `ParsedValue` retains canonical and source field names, raw value, normalized value, parser version, validation result, and warning/error issues. Supported normalized structured values are `CalendarDate` and `Money`; money accepts no float input and uses `Decimal` with USD currency.

Every created `SourceRecord` retains Source, Artifact, Import Batch, external key when available, normalized-payload digest, observed time, row number, parser version, values, and issues. Rejected rows are Source Records with rejection reasons; duplicate and unchanged rows are report results and do not create processing records.

## Stable identity and history comparison

The external-record key is SHA-256 over Source ID plus configured normalized unique-identifier fields. It is independent of row order, column order, aliases, artifact, batch, and parser version.

The payload digest is SHA-256 over canonical normalized field/value pairs. A row is `unchanged` only when external key, payload digest, and parser version match the latest parsed Source Record. A newer parser version therefore creates a new result from the same immutable artifact. Repeated keys inside one artifact are `duplicate` and are not processed again.

## Failure boundaries

Invalid encoding, checksum, missing/ambiguous required headers, or parser/profile mismatch makes the artifact unusable and fails the batch. A malformed row, invalid date, invalid currency, missing identifier, or source-specific validation error rejects only that row. Usable sibling rows continue.

The fixture CSV extractor intentionally supports quoted values within one physical line and quarantines malformed physical rows; multiline quoted fields are not part of the fixture contract.

## Processing transaction boundary

The pipeline verifies the archived checksum before parsing, transitions the batch to `processing`, saves accepted/warned/rejected Source Records, then completes the batch from registered record counts. Duplicate and unchanged report rows are excluded from batch processed/rejected counts.

The current in-memory repository is lock protected but the complete parsing operation is not a durable database transaction. A production adapter must atomically persist Source Records, Import Report, batch terminal state, and downstream outbox work. This is a known deferred boundary; raw artifacts remain immutable regardless of parser failure.

## Observability and privacy

Structured parser logs contain operational IDs, parser identity, safe failure category/message, and summary counts. Metrics count rows by controlled disposition and batches/failures by source/category. Raw values, artifact bytes, addresses, and permit numbers are excluded from logs and metric labels.

## Source-specific implementation status

`synthetic-tucson-permit-csv` supports representative local fixture aliases and explicit `%Y-%m-%d` / `%m/%d/%Y` dates. It is not approved for live Tucson or Pima data and must not be registered as a production source without onboarding/access/schema approval.

## Related current documents

- [Project structure v1.4](../project-structure/project-structure-v1.4.md)
- [Business logic v1.4](../business-logic/business-logic-v1.4.md)
- [Business data v1.0](../../current/business-data-v1.0.json)
- [Source parsing runbook](../../runbooks/source-parsing.md)
- [Backend structure log](../../logs/backend-structure-log-v1.4.md)
