# Permit Normalization and Duplicate Review Runbook

## Atomic local persistence

Run normalization and duplicate decisions through `InMemoryNormalizationUnitOfWork`. Permit, duplicate candidate, and normalization Review Task stores share one lock and snapshot. Any exception before commit restores all three. Injected failure must leave no visible partial state.

This is process-local rollback, not database transactionality. A future adapter must use one database transaction and publish resulting events through a transactional outbox.

## Scope

Use this runbook after a Source Record has parsed successfully. It covers deterministic Permit normalization, address resolution review, probable duplicate review, correction handling, and manual merge/distinct decisions. It does not authorize live source access or select a production geocoder.

## Normal processing

1. Confirm the Source Record is `parsed`, retains parser version, and references its immutable Source Artifact and Import Batch.
2. Resolve the Source to its registered Arizona jurisdiction.
3. Normalize Permit identifiers, municipal status, type, description, dates, valuation, parties, address, parcel, and available coordinates.
4. If source coordinates are absent, invoke only the configured geocoder adapter.
5. Check Source + external identifier, then Source + fingerprint, before creating a Permit.
6. If no exact match exists, evaluate same-jurisdiction address/type/date similarity.
7. Review the workflow outcome and any Address or probable-duplicate tasks.

## Outcomes

- `created`: new Permit persisted with one Source Record evidence item.
- `exact_duplicate`: existing Permit retained; new Source Record evidence attached automatically.
- `corrected`: same Source/external identity with a changed fingerprint; prior normalized snapshot retained.
- `probable_duplicate`: separate Permit retained and a manual review candidate opened.

## Address review

For `review_required`:

1. Do not fabricate coordinates or silently accept a low-quality guess.
2. Compare raw address, normalized components, parcel, jurisdiction, and approved source detail.
3. Correct deterministic mapping in a new normalization version when appropriate.
4. Re-run from the unchanged Source Record/artifact and retain the previous result/history.

## Probable duplicate review

1. Compare both Permits and all linked Source Records/artifacts.
2. Confirm address, type, dates, permit identifiers, parcels, descriptions, and parties as available.
3. Choose `keep_distinct` when evidence does not prove one government record.
4. Choose `merge` only with an explicit actor and rationale. The earlier Permit remains canonical; the duplicate becomes superseded.
5. Never delete the duplicate Permit, Source Records, or raw artifacts.

## Corrections

A matching Source/external identifier with changed fingerprint is a correction, not a duplicate Permit. Verify that the previous normalized snapshot and both Source Record IDs remain present.

## Privacy and observability

Logs and metric labels may contain operational identifiers, outcomes, evidence layers, parser versions, and review counts. Do not log addresses, descriptions, contractor/applicant names, parcel values, coordinates, or raw parsed values.

## Validation

```sh
PYTHONPATH=src python3 -m unittest tests.test_permit_normalization -v
PYTHONPATH=src python3 -m unittest discover -s tests -v
python3 scripts/check_docs.py
```
