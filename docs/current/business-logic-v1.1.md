---
document_id: business-logic
version: 1.1
document_status: current
implementation_status: partially implemented
approved_on: 2026-07-17
---

# Business Logic v1.1

## Status statement

**Implemented:** Minimum domain vocabulary, validated value objects, entity/aggregate invariants, lifecycle transitions, explainability structure, deterministic/AI provenance constraints, consent-bearing notification preferences/attempts, domain errors/events, and tests.
**Partially implemented:** Business behavior exists only as an in-memory domain kernel; no use-case handler, persistence constraint, matching execution, notification delivery, source parsing, or customer authorization is implemented.
**Planned:** The complete acquisition-to-delivery vertical slice and business configuration populated after source/trade decisions.

## Product scope

AZ Permit Radar remains an Arizona-specific permit intelligence and opportunity-alert platform. It is not approved as a permit-application platform, full CRM, bidding marketplace, national permit database, or microservice ecosystem.

No pilot jurisdiction, source, trade, threshold, provider, or notification policy is selected in [business data v1.0](business-data-v1.0.json). Domain examples in tests are fixtures, not approved business data or production behavior.

## Implemented domain distinctions

- `SourceArtifact` is immutable acquisition evidence; `SourceRecord` is a source-level assertion; `Permit` is the observed canonical government record.
- `ProjectClassification` is a classification value and `ClassificationResult` records a versioned interpretation with method, evidence, confidence, and review state.
- `Opportunity` is customer-independent and derives from Permit and Classification Result IDs.
- `OpportunityMatch` relates one Opportunity to one Customer Account and owns an explicit `MatchExplanation` plus customer-scoped `LeadState`.
- `NotificationPreference` records channel eligibility/consent; `NotificationAttempt` represents one delivery attempt. Submission is not delivery.
- `ReviewTask` points to a precise subject type without becoming or mutating that subject.

No generic domain entity named `Data`, `Record`, `Item`, or `Lead` exists. `SourceRecord` and `LeadState` are retained because they are precise approved terms.

## Implemented value-object invariants

- Typed identifiers reject blanks and unsafe characters.
- Money is finite, non-negative, currency-qualified, and quantized to two decimal places.
- Confidence is finite and bounded from 0 through 1.
- Coordinates enforce latitude/longitude bounds.
- Calendar dates, date ranges, and UTC timestamps reject invalid/reversed/naive values.
- Phone numbers require E.164 form; email addresses normalize to lowercase.
- Normalized addresses require line, city, two-letter region, and ZIP/ZIP+4.
- Content digests support SHA-256 only; idempotency keys require safe nontrivial values.

These validate shape, not whether a source assertion is factually correct.

## Implemented aggregate invariants

- Pilot Jurisdictions are Arizona (`AZ`) only.
- Artifacts are frozen and must match their Source and Import Batch when registered.
- Import completion counts must equal registered Source Records.
- Permits require source provenance and parser version; corrections append a new Source Record instead of replacing evidence.
- AI-assisted Classification Results require provider/model/prompt versions; deterministic results reject AI provenance; all classifications require evidence and trade tags.
- Opportunities require Permit, Classification Result, and Trade Tag references and cannot contain customer configuration.
- Service Territories require at least one valid geographic scope; Customer Filters enforce compatible valuation bounds.
- Enabled Notification Preferences require a channel-appropriate destination, consent time, and consent reference.
- Match explanations require matching trades, geographic reasoning, unique score components, freshness, exclusions considered, and confidence.
- Notification Attempts require consent reference and idempotency key; terminal attempts cannot retry in place.
- Review Tasks require a precise subject and reason; terminal reviews cannot reopen.

## State transitions

The state-transition sets documented in [backend structure v1.1](backend-structure-v1.1.md) are implemented and tested. Invalid transitions raise `InvalidStateTransition`; invalid construction or operations raise `InvalidValue`, `InvariantViolation`, or `ConsentRequired`. `ConcurrencyConflict` is defined for future repository adapters.

## Domain events

Aggregates record immutable `StateChanged`, `ArtifactRegistered`, `ClassificationReviewed`, `OpportunityMatchCreated`, and `ConfigurationChanged` events for important changes. Application code must pull and persist/publish them transactionally in future infrastructure. Event recording is implemented; an outbox and event handlers are not.

## Deterministic-first and explainability

[ADR-0002](../adr/0002-deterministic-first-ai.md) remains controlling. The model enforces derivation provenance but implements no classifier or AI call. `MatchExplanation` provides the required shape; no actual matching/scoring algorithm or threshold is implemented. Numeric score component values are explanatory inputs, not an approved universal scoring formula.

## Consistency and idempotency

In-aggregate consistency is implemented synchronously. Typed IDs, content digests, and idempotency keys are implemented as values. Cross-aggregate uniqueness—external source IDs, source/permit identity, Opportunity/Customer pair, notification intent/attempt keys—and transactional outbox guarantees remain planned for persistence.

## Safety limits

No authentication, authorization, billing, source access, personal-data retention, deletion, notification provider, or customer-visible factual response is implemented. Consent values in the domain model do not by themselves authorize delivery; future application handlers must verify current policy and customer authorization.

## Related current documents

- [Project structure v1.1](project-structure-v1.1.md)
- [Backend structure v1.1](backend-structure-v1.1.md)
- [Business data v1.0](business-data-v1.0.json)
- [Frontend design v1.0](frontend-design-v1.0.md)
- [Business logic log](../logs/business-logic-log-v1.1.md)
- [Domain glossary](../governance/domain-glossary.md)
