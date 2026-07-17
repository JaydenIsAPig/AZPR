---
document_id: business-logic
version: 1.5
document_status: current
implementation_status: partially implemented
approved_on: 2026-07-17
---

# Business Logic v1.5

## Status statement

**Implemented:** v1.4 deterministic parsing plus Permit, Address, party, parcel, jurisdiction, coordinate, correction, duplicate, merge, and supersession rules.

**Partially implemented:** behavior is local/fixture-backed. Live source mappings, production geocoding, durable transactions, customer-visible Permit delivery, classification execution, and duplicate-review interfaces remain planned.

## Normalized Permit rules

- Permit identifiers are uppercased and punctuation/whitespace is converted to stable hyphen separators.
- Missing permit identifiers use a stable Source Record fingerprint fallback and generate a warning; they are not guessed.
- Municipal status is normalized separately from the Permit aggregate's active/corrected/voided/superseded lifecycle.
- Known permit types map to stable codes; unknown nonempty types become deterministic slugs rather than inferred classifications.
- Descriptions collapse whitespace without semantic rewriting.
- Application and issue dates use parsed `CalendarDate` values. An application date after issue date is omitted with a warning.
- Valuation remains `Money`/`Decimal`; no floating-point conversion is introduced.
- Contractor/applicant names and contractor license numbers remain normalized source assertions, not verified identities.
- Parcel identifiers remove formatting punctuation, remain jurisdiction-qualified, and retain their raw source value.
- Jurisdiction resolves through the registered Source-to-Jurisdiction adapter; an unresolvable jurisdiction blocks Permit normalization.

## Address and coordinates

- Common Arizona directionals, suffixes, casing, ZIP formats, and apartment/suite variants normalize deterministically.
- Valid source latitude/longitude strings take precedence and are marked `source` coordinates.
- Otherwise the workflow may call only a configured geocoder adapter.
- Geocoder results store provider, timestamp, quality, confidence, and coordinates.
- Failed/unresolved geocoding marks the Address `review_required` and opens an Address review task.
- Missing addresses produce no fabricated Address and no geocoder request.

## Exact duplicate and correction rules

- Source + external identifier is checked first.
- Source + record fingerprint is the exact fallback, including records without external identifiers.
- Matching exact fingerprint evidence attaches the new Source Record to the existing Permit without creating another Permit or changing normalized facts.
- A matching Source/external identifier with a changed fingerprint is a correction: normalized values update, the previous snapshot is retained, and both Source Records remain linked.
- No duplicate or correction path mutates archived artifacts or Source Records.

## Probable duplicate rules

Probable comparison is limited to the same registered jurisdiction. Evidence weights are:

- normalized address exact match: 45;
- normalized permit type exact match: 25;
- same permit date: 30;
- permit dates within seven days: 20.

A score of at least 75 creates a probable duplicate candidate and review task. Both Permits remain separate and active pending a manual decision.

## Manual decisions, merge, and supersession

- Every manual decision stores merge/distinct result, actor, rationale, timestamp, and candidate history.
- `keep_distinct` closes the candidate without altering either Permit.
- `merge` keeps the prior Permit canonical, absorbs all Source Record evidence, records the merged Permit ID, and marks the duplicate superseded.
- Canonical and superseded Permit histories retain the decision relationship and previous normalized snapshots.
- Superseded Permits are excluded from future exact-index ownership and probable comparisons.

## Observability and privacy

- Outcomes and evidence layers are logged/metered with controlled identifiers and labels.
- Address, description, contractor, applicant, parcel, and raw Source Record values are not logged.
- Probable matches are never silently converted into exact matches.

## Related current documents

- [Project structure v1.5](project-structure-v1.5.md)
- [Backend structure v1.5](backend-structure-v1.5.md)
- [Business data v1.0](business-data-v1.0.json)
- [Permit normalization runbook](../runbooks/permit-normalization.md)
- [Business logic log](../logs/business-logic-log-v1.5.md)

