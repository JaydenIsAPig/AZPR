---
document_id: business-logic
version: 1.0
document_status: superseded
implementation_status: planned
approved_on: 2026-07-16
---

# Business Logic v1.0

## Status statement

**Implemented:** No product business logic is implemented.
**Planned:** The product definition, domain distinctions, deterministic-first policy, provenance, idempotency, explainability, and safety constraints below are approved.
**Partially implemented:** None.

## Product scope

AZ Permit Radar is planned as an Arizona-specific permit intelligence and opportunity-alert platform. It will acquire newly published municipal permit records, archive original source material, normalize and classify records, derive opportunities, match them to construction businesses using trade and geographic preferences, and present explainable results through a dashboard and controlled notifications.

It is not currently approved as a permit-application platform, full CRM, bidding marketplace, national permit database, or microservice ecosystem.

## Pilot priority

The planned first vertical slice is limited to one approved Arizona jurisdiction or source family, a limited approved trade set, reliable ingestion, explainable classification, trade/geographic matching, a dashboard feed, email alerts, controlled SMS, and internal review/source monitoring. The jurisdiction, source, trades, timing, thresholds, and provider choices are **not selected** and remain empty in [business data v1.0](../../current/business-data-v1.0.json).

## Domain invariants

- A Permit is an observed government record.
- An Opportunity is a product interpretation derived from one or more records.
- A Customer Match relates an Opportunity to one customer and retains its explanation.
- A Notification is a delivery attempt concerning a Customer Match.
- Customer Lead State is customer-scoped and cannot mutate shared Permit or Opportunity state.
- Source, Source Artifact, Import Batch, Source Record, Permit, Address, Parcel, Project, Party, Classification, Opportunity, Customer Match, Notification, and Customer Lead State must remain distinct.

The [domain glossary](../../governance/domain-glossary.md) is authoritative for terminology.

## Deterministic-first policy

Under [ADR-0002](../../adr/0002-deterministic-first-ai.md), deterministic code is required before AI for structured parsing, dates, currency, deduplication, address normalization, geographic inclusion, permissions, authentication, billing, notification consent, calculations, database constraints, workflow transitions, and destructive operations.

AI is planned only where language ambiguity makes deterministic extraction insufficient. Any AI-derived value must retain provenance, provider/model identifier and version, prompt/classifier version, confidence where meaningful, review status, and timestamps. No AI provider or model is selected.

## Explainable matching

Every planned Customer Match must persist or reproducibly calculate:

- matching trade tags;
- applied geographic rule;
- relevant customer filters;
- score components;
- exclusions considered;
- source freshness; and
- confidence values.

A single unexplained score is not acceptable.

## Source integrity and retry safety

- Raw artifacts are immutable.
- Parser corrections create new processing results.
- All acquisition and processing operations are retry-safe.
- Repeated imports must not create duplicate Permits, Opportunities, Customer Matches, or notification intents.
- Notification delivery must distinguish intent, attempt, provider acceptance, delivery, failure, and suppression.

## Configurable versus invariant

Planned configurable values include approved sources, source mappings, trade taxonomy, geographic rule definitions, thresholds, exclusions, freshness windows, review thresholds, and notification policies. None are approved in v1.0.

Invariants remain enforced in code and persistence: authorization, customer isolation, consent enforcement, provenance, immutability, idempotency, legal state transitions, and database constraints.

## Safety gates

Implementation must not guess about authentication, authorization, billing, personal data, notification consent, source-access compliance, destructive migrations, deletion, security controls, or customer-visible factual claims. Missing information produces an issue, TODO, decision record, or blocked result rather than silent behavior.

## Related current documents

- [Project structure v1.0](../project-structure/project-structure-v1.0.md)
- [Backend structure v1.0](../backend-structure/backend-structure-v1.0.md)
- [Business data v1.0](../../current/business-data-v1.0.json)
- [Frontend design v1.0](../../current/frontend-design-v1.0.md)
- [Business logic log](../../logs/business-logic-log-v1.0.md)
