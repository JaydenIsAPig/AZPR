# Source Onboarding Checklist

Use this checklist before enabling any Arizona municipal permit source. A profile may remain drafted while evidence is incomplete; remote acquisition must not run until access review permits it.

## 1. Identity, scope, and ownership

- [ ] Assign stable source and Arizona jurisdiction identifiers.
- [ ] Record the official source name, source family, operational owner, backup owner, and escalation route.
- [ ] Confirm the source is within the currently approved pilot scope.
- [ ] Check governed business data for approval; do not treat a test fixture as an approved production source.

## 2. Access and terms review

- [ ] Record the official landing page and exact download/API/page endpoint separately.
- [ ] Review published terms, robots guidance where relevant, open-data license, rate guidance, and redistribution/storage restrictions.
- [ ] Record `approved`, `not_required`, `pending`, or `restricted`, the reviewer, evidence links, decision date, and review-expiry/change trigger.
- [ ] Confirm the proposed method does not require CAPTCHA bypass, access-control circumvention, credential sharing, or misleading identity.
- [ ] If authentication is required, identify the approved secret reference and rotation owner without placing the secret in source configuration or logs.
- [ ] Stop onboarding when terms or authorization are ambiguous; keep the source disabled and escalate to the owner.

## 3. Source contract

- [ ] Select exactly one acquisition method: file download, HTTP API, HTML page, or manual upload.
- [ ] Record URL/endpoint structure, HTTP method, non-secret query/header fields, content negotiation, redirects, and expected status codes.
- [ ] Record media type, extension, compression, encoding, delimiter/sheet name where applicable, and maximum expected size.
- [ ] Document pagination, cursors, date windows, ordering guarantees, late corrections, deletions, and historical availability.
- [ ] List expected date fields with formats/time semantics and expected unique identifiers with stability/collision notes.
- [ ] Record known limitations, missing periods, schema variability, and source-publication latency.
- [ ] Save a legally obtained, non-sensitive raw fixture and its SHA-256 checksum for deterministic contract tests.

## 4. Safe request policy

- [ ] Define an explicit truthful user agent with an operational contact.
- [ ] Set connection/read timeout behavior in the future network adapter's approved HTTP contract.
- [ ] Set per-run request and response-byte limits below source guidance.
- [ ] Set retry attempts, retryable categories/statuses, exponential backoff, jitter policy, and `Retry-After` handling.
- [ ] Define schedule and IANA time zone; avoid unnecessary polling and overlapping runs.
- [ ] Confirm credentials, cookies, query secrets, and full provider responses will not be logged.

## 5. Parser handoff and provenance

- [ ] Assign a parser identifier/version independently of the connector.
- [ ] Demonstrate that the connector returns raw bytes and transport metadata only.
- [ ] Map expected fields in parser tests, including invalid dates, missing IDs, duplicate rows, corrections, and encoding edge cases.
- [ ] Document Permit/address/parcel normalization mappings and representative unit/address variants.
- [ ] Define exact and probable duplicate evidence, thresholds, and the manual merge owner.
- [ ] Approve geocoding access, provider attribution, quality/confidence handling, and failure review behavior if geocoding is used.
- [ ] Preserve Source -> Import Batch -> Source Artifact -> Source Record -> Permit traceability.
- [ ] Confirm reprocessing creates a new result/version and never changes the archived raw artifact.

## 6. Artifact storage and idempotency

- [ ] Verify SHA-256 before storage and after retrieval.
- [ ] Configure immutable/object-lock retention, encryption, access control, backup, and lifecycle policy for the deployment target.
- [ ] Verify identical content reuses its digest key without overwriting bytes.
- [ ] Define uniqueness/idempotency keys for batches, external records, and normalized permits.

## 7. Observability and operations

- [ ] Configure structured acquisition logs and alerts for failure, staleness, repeated identical artifacts, schema drift, and unexpected volume.
- [ ] Define healthy/degraded/failing thresholds and expected freshness.
- [ ] Exercise the [source acquisition runbook](../runbooks/source-acquisition.md) with the assigned owner.
- [ ] Record last-tested date and evidence for success, retry, limit, terms-block, oversized response, checksum mismatch, and storage failure.

## 8. Approval gate

- [ ] Product/source owner approves scope and source identity.
- [ ] Access reviewer approves terms/access status.
- [ ] Engineering owner approves contract tests, limits, parser boundary, and rollback.
- [ ] Operations owner approves schedule, monitoring, storage controls, and runbook.
- [ ] Add the approved source to governed business data and update its schema/document version if required.
- [ ] Enable only after all blocking items are complete; otherwise record the exact blocker and keep `enabled = false`.

## Initial Tucson/Pima decision

As of 2026-07-17, no Tucson or Pima source appears in governed business data and no source contract/access review is approved. Therefore no live Tucson/Pima connector is implemented. The repository's Tucson-named CSV is synthetic test data only.
