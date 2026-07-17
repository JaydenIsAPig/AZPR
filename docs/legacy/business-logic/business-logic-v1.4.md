---
document_id: business-logic
version: 1.4
document_status: superseded
implementation_status: partially implemented
approved_on: 2026-07-17
---

# Business Logic v1.4

## Status statement

**Implemented:** v1.3 acquisition rules plus deterministic artifact-to-Source-Record parsing, explicit value provenance, row quarantine, stable keys, duplicate/unchanged suppression, version-aware reprocessing, import reports, and parser observability.

**Partially implemented:** behavior is proven with synthetic Tucson fixtures and local adapters. Live municipal mapping, durable processing transactions/outbox, Source Record-to-Permit projection, address normalization, classification, and external operations remain planned.

## Deterministic parser rules

- The primary parser uses no AI and performs no network acquisition.
- UTF-8 decoding is explicit; encoding guessing is prohibited.
- Accepted date formats are declared by parser version. Unsupported or invalid dates reject the row.
- Currency is parsed only from strings into `Decimal`/`Money`; float and boolean money input is rejected.
- Optional empty values produce an explicit `empty` validation result. Required empty values reject the row.
- Source aliases map into canonical fields. Column order does not affect identity. Ambiguous aliases or missing required columns make the artifact unusable.
- Unmapped columns are preserved as source-extra values with warnings so schema drift is visible.

## Provenance rules

- Every parsed value retains raw value, normalized value, source field, parser version, validation result, and issues.
- Every created Source Record retains Source, Artifact, Import Batch, row number, external key when available, normalized payload digest, parser version, values, and row issues.
- Rejected rows remain traceable Source Records; their errors are also sent to the rejection reporter.
- Parsing never mutates the Source Artifact.

## Row and batch outcome rules

The Import Report partitions every extracted entry into exactly one outcome:

- `accepted`: valid new or changed record with no warning;
- `warned`: valid new or changed record with at least one warning;
- `rejected`: row-level error; quarantined while sibling rows continue;
- `duplicate`: key already appeared in the current artifact; no Source Record is created;
- `unchanged`: latest parsed history has the same key, normalized digest, and parser version; no Source Record is created.

One malformed row does not fail a complete batch. The complete batch fails only when reliable row extraction is impossible, including checksum, decoding, header/format, or parser configuration failure.

## Stable key and reprocessing rules

- External keys hash Source ID plus the Source Profile's configured normalized unique-identifier fields.
- Keys do not depend on column order, aliases, artifact ID, batch ID, or parser version.
- Duplicate keys within an artifact use first-observed processing and suppress later rows.
- The normalized payload digest compares semantic field values, not raw byte formatting.
- Reprocessing with the same parser version produces `unchanged` outcomes where values have not changed.
- Reprocessing with a new parser version creates new Source Records even when values are equal, preserving correction history.

## Batch lifecycle and counts

- Parsing starts only from an acquired batch containing the referenced artifact.
- Accepted, warned, and rejected records register with the batch.
- Batch `processed_count` equals accepted plus warned; `rejected_count` equals rejected.
- Duplicate and unchanged outcomes appear in the Import Report but do not create processing records or inflate batch counts.
- Any rejected row completes the batch as partially failed; otherwise the batch completes.

## Observability and privacy

- Batch logs contain IDs, parser identity, safe error details, and aggregate counts only.
- Metrics count controlled row outcomes and failure categories.
- Raw values, permit numbers, addresses, artifact bytes, and sensitive configuration are excluded from logs and metric labels.

## Source-contract limitation

The current Tucson-named parser is fixture-only. It must not be treated as an approved description of Tucson or Pima production data. A live mapping requires the source onboarding checklist, access review, representative approved fixtures, and a versioned source contract.

## Related current documents

- [Project structure v1.4](../project-structure/project-structure-v1.4.md)
- [Backend structure v1.4](../backend-structure/backend-structure-v1.4.md)
- [Business data v1.0](../../current/business-data-v1.0.json)
- [Source parsing runbook](../../runbooks/source-parsing.md)
- [Business logic log](../../logs/business-logic-log-v1.4.md)
