# Source Parsing Runbook

## Scope

Use this runbook for processing an already archived immutable Source Artifact into Source Records. It does not authorize network access or live Tucson/Pima source use.

## Normal processing

1. Confirm the Import Batch is `acquired` and references the artifact.
2. Confirm the Source Profile parser identifier/version matches the selected parser.
3. Read the immutable artifact through the configured reader and verify SHA-256.
4. Run decoding, format validation, extraction, mapping, normalization, validation, stable-key comparison, and rejection reporting.
5. Review the Import Report counts: accepted, warned, rejected, duplicate, and unchanged.
6. Investigate any partially failed batch before downstream Permit projection.

## Outcome handling

- `accepted`: eligible for downstream processing.
- `warned`: eligible only according to the warning policy; review schema-drift warnings.
- `rejected`: inspect row issue codes in the quarantine/rejection reporter.
- `duplicate`: no action unless source ordering/duplicate policy is under review.
- `unchanged`: expected during same-version reprocessing; no duplicate downstream work.

## Artifact-level failure

For checksum, read, decoding, missing-header, ambiguous-header, or parser/profile mismatch:

1. Keep the artifact unchanged.
2. Confirm the parser version and Source Profile contract.
3. Compare the source header/encoding with approved fixtures.
4. Create a new parser version for a contract correction; never rewrite prior Source Records or raw artifacts.
5. Reprocess by creating a new acquired Import Batch referencing the archived artifact.

## Row-level failure

Invalid dates, currency, required values, unique identifiers, or row column counts quarantine only the affected row. If rejection volume changes materially, pause downstream use and escalate to the operational owner and parser owner.

## Privacy and safety

Do not place artifact bytes, permit numbers, addresses, or raw row values in logs or metric labels. Do not treat the synthetic Tucson fixtures as an approved production contract.

## Validation

```sh
PYTHONPATH=src python3 -m unittest tests.test_source_parsing -v
PYTHONPATH=src python3 -m unittest discover -s tests -v
python3 scripts/check_docs.py
```

