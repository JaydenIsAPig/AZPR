# Domain Language Audit

**Audit date:** 2026-07-16
**Baseline:** Supplied AZ Permit Radar master operating prompt
**Actual code/model state:** No domain source, schemas, migrations, APIs, DTOs, events, fixtures, or tests exist.

## Conclusion

There is no existing domain model to inspect, so `Permit`, `Opportunity`, `Customer Match`, and `Notification` are **not currently combined in code**. They are also not yet protected as separate concepts. The present risk is prospective: without explicit models and lifecycle boundaries, the first implementation could combine them incorrectly.

The supplied charter is internally clear on the central distinctions:

- A **Permit** is an observed government record.
- An **Opportunity** is a product interpretation derived from one or more records.
- A **Customer Match** relates an opportunity to a customer.
- A **Notification** is a delivery attempt concerning a match.

These definitions should become executable invariants, not merely naming guidance.

## Required ubiquitous-language map

| Term | Required meaning and ownership | Must not be treated as |
|---|---|---|
| Source | Registered external publisher/feed and its access configuration | A downloaded file, an import execution, or a permit |
| Source Artifact | Immutable acquired file or raw payload with hash and acquisition metadata | A mutable parsed permit |
| Import Batch | One retry-safe acquisition/processing execution and its outcome | The source itself or an individual permit |
| Source Record | A record as represented by a source/artifact, before canonical interpretation | The canonical permit or opportunity |
| Permit | Canonical observed government record traceable to source evidence | An inferred sales lead, customer match, or alert |
| Address | Normalized location value with provenance/quality | A parcel or project identity |
| Parcel | Jurisdictional land identifier | An address string |
| Project | Optional grouping of related records/permits | A permit by default |
| Party | Person/organization named in source data, subject to privacy rules | A platform customer unless explicitly linked |
| Classification | Versioned interpretation with provenance, confidence, and review state | The opportunity itself or an unexplained label |
| Opportunity | Product interpretation derived from one or more source-backed records | A permit, customer-specific match, or lead workflow state |
| Customer Match | Explainable relation between one opportunity and one customer/configuration | A global opportunity or notification |
| Notification | A channel-specific delivery attempt concerning a match | The match itself or proof that delivery succeeded |
| Customer Lead State | Customer-owned workflow state for a match/opportunity | A mutation of the shared permit/opportunity |

## Recommended aggregate and reference boundaries

This is a modeling recommendation for the implementation stage, not an implementation change:

```text
Source -> Source Artifact -> Import Batch / Source Record -> Permit
                                                        \-> Classification
Permit(s) + Classification(s) -> Opportunity
Opportunity + Customer Configuration -> Customer Match
Customer Match -> Notification Attempt(s)
Customer Match -> Customer Lead State
```

- Raw evidence remains immutable and independently addressable.
- A permit references source provenance without owning acquisition behavior.
- An opportunity may reference one or more permits and is not customer-specific.
- A match records the customer-specific explanation and relevant configuration/version.
- A notification attempt records channel, consent basis, idempotency key, provider reference, status, timestamps, and sanitized failure detail.
- Customer lead state is customer-scoped and must not alter the shared opportunity or permit.

## Lifecycle separation checks to encode

| Concept | Example independent lifecycle |
|---|---|
| Source Artifact | acquired -> integrity verified -> archived; never overwritten |
| Import Batch | started -> acquired -> processed/partially failed/failed -> completed |
| Permit | observed -> superseded/corrected/void as supported by source evidence |
| Classification | pending -> produced -> reviewed/accepted/rejected; versioned replacement rather than provenance loss |
| Opportunity | candidate -> reviewable -> published/suppressed/expired |
| Customer Match | eligible -> matched/excluded -> active/expired; explanation retained |
| Notification Attempt | queued -> submitted -> delivered/failed/suppressed; retries remain distinct attempts under one idempotent intent |
| Customer Lead State | new -> saved/contacted/dismissed/etc., scoped to one customer |

The exact state names require product decisions, but state transitions must not be shared across these concepts merely for convenience.

## Issues

### DL-01 — Domain language exists only in an external charter

- **Severity:** High
- **Evidence:** No repository domain glossary, source code, schema, ADR, or tests exist; the only definitions are in the supplied DOCX outside the repository.
- **Likely effect:** Contributors and automation can use inconsistent terms or lose the charter when working from a fresh clone.
- **Recommended action:** Add an authoritative, versioned repository glossary and link it from architecture/business-logic documents and the README. Preserve the four core definitions verbatim in meaning.
- **Milestone:** M0

### DL-02 — Core distinctions are not enforced by types or persistence

- **Severity:** Critical
- **Evidence:** No models or database schema exist for permit, opportunity, customer match, notification, or lead state.
- **Likely effect:** A single “lead/permit” row may accumulate customer, score, notification, and workflow fields, producing duplication, ambiguous ownership, privacy leakage, and difficult reprocessing.
- **Recommended action:** Define separate identities, tables/types, ownership, references, invariants, and lifecycle tests before implementing ingestion or the dashboard.
- **Milestone:** M1

### DL-03 — Acquisition provenance concepts are not modeled

- **Severity:** Critical
- **Evidence:** No Source, Source Artifact, Import Batch, Source Record, raw payload, hash, acquisition timestamp, external ID, or parser version model exists.
- **Likely effect:** Normalized permits could become untraceable, raw evidence could be overwritten, and parser corrections could destroy reproducibility.
- **Recommended action:** Model and test the full provenance chain with immutable artifacts and versioned processing results before creating normalized permits.
- **Milestone:** M2

### DL-04 — Classification provenance and AI boundaries are undefined

- **Severity:** High
- **Evidence:** No classification model, deterministic rule version, AI adapter, prompt/model version, confidence, provenance, or review status exists.
- **Likely effect:** Inferred values may be indistinguishable from source facts and impossible to review or reproduce.
- **Recommended action:** Separate observed, normalized, deterministic-derived, and AI-derived values. Require derivation method, version, confidence where meaningful, evidence/provenance, timestamps, and review status.
- **Milestone:** M3

### DL-05 — Match explainability has no contract

- **Severity:** High
- **Evidence:** No match type or schema exists for trade tags, geographic rule, customer filters, score components, exclusions, source freshness, or confidence.
- **Likely effect:** The product may expose an unexplained score, weakening trust and making disputes/debugging difficult.
- **Recommended action:** Define a versioned match explanation contract and tests that reconstruct every inclusion, exclusion, and score component from recorded inputs.
- **Milestone:** M3

### DL-06 — Notification intent, attempt, consent, and delivery are not distinguished

- **Severity:** Critical
- **Evidence:** No notification or consent models exist, and no provider/outbox boundary exists.
- **Likely effect:** Retries could duplicate alerts; “sent” may be confused with “delivered”; SMS/email may be attempted without a durable consent basis.
- **Recommended action:** Distinguish notification intent from each delivery attempt and provider event. Snapshot consent/channel eligibility, use idempotency keys and an outbox, and retain auditable suppression/failure reasons without sensitive logging.
- **Milestone:** M4

### DL-07 — Geography and trade vocabularies are unspecified

- **Severity:** High
- **Evidence:** No canonical trade taxonomy, jurisdiction registry, geographic rule types, aliases, effective dates, or versioned business-data files exist.
- **Likely effect:** Source labels and customer preferences may be compared as ad hoc strings, creating silent false positives/negatives.
- **Recommended action:** Define versioned, configurable trade and geography vocabularies with stable identifiers, source mappings, validation, and effective/version metadata.
- **Milestone:** M0 definition; M3 implementation

### DL-08 — Project, parcel, address, and party identity rules are undecided

- **Severity:** Medium
- **Evidence:** The charter names these as distinct concepts, but no identity, merge, deduplication, or privacy rules exist in the repository.
- **Likely effect:** Records may be over-merged, parties may be mistaken for customers, or address strings may become unstable entity identifiers.
- **Recommended action:** Document identity and confidence rules before automatic linking. Begin conservatively: preserve source assertions and make inferred links reviewable/versioned.
- **Milestone:** M2-M3

## Acceptance checks for the first model

- Reimporting the same artifact creates no duplicate permit, opportunity, match, or notification intent.
- Reprocessing with a new parser/classifier version preserves the original artifact and prior processing result.
- A permit can exist without an opportunity; an opportunity can be suppressed without altering its permits.
- One opportunity can yield different explainable matches for different customers without duplicating the opportunity.
- Customer lead-state changes do not mutate another customer's state or the shared opportunity.
- Notification retries do not create duplicate customer-visible messages and do create auditable attempt history.
- Source-observed and AI-derived fields are distinguishable in storage and responses.
