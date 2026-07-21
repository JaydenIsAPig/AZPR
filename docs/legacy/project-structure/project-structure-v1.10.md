---
document_id: project-structure
version: 1.10
document_status: superseded
implementation_status: partially implemented
approved_on: 2026-07-20
---
# Project Structure v1.10

## Status statement

**Implemented:** v1.9 behavior plus deterministic Opportunity projection fingerprints and revisions, immutable superseded projection snapshots, acquisition provenance, governed source-date precedence, stale Match reevaluation, and complete score/configuration/territory/freshness snapshots.

**Partially implemented:** repositories remain in-memory. No durable tables, production worker, API/UI, notification-intent trigger, or database migration is implemented.

## Ownership

| Path | Responsibility |
|---|---|
| `domain/opportunity.py` | Stable logical Opportunity identity, current projection revision, and immutable superseded projections |
| `domain/matching.py` | Match lifecycle plus immutable score, customer configuration, territory, freshness, threshold, and Opportunity-revision history |
| `application/opportunity_matching.py` | Material-input fingerprinting, regeneration, explicit exclusions, source freshness, and deterministic scoring |
| `domain/ingestion.py`, `application/parsing.py` | Artifact acquisition timestamp propagation into source records |
| `application/normalization.py`, `domain/permit.py` | Acquisition provenance propagation into Permit source evidence |
| `infrastructure/opportunity_matching.py` | Governed projection/score policy loading and in-memory stale-Match marking |
| `tests/test_opportunity_generation_matching.py` | Projection, replay, freshness, single-count scoring, and historical snapshot regressions |

## Reprocessing

No database migration is required because persistence is in-memory. Discard and rebuild runtime Opportunity and Match state under v1.10. A material Permit, parser, Classification Result, classifier/rule version, source evidence, or projection-policy change advances the same logical Opportunity to its next projection revision and marks active customer Matches stale. Unchanged fingerprints replay without new history.

## Related current documents

- [Backend structure v1.10](../backend-structure/backend-structure-v1.10.md)
- [Business logic v1.10](../business-logic/business-logic-v1.10.md)
- [Business data v1.5](../business-data/business-data-v1.5.json)
- [Frontend design v1.0](../frontend-design/frontend-design-v1.0.md)
- [ADR-0006](../../adr/0006-versioned-opportunity-projections.md)
- [Project structure log](../../logs/project-structure-log-v1.10.md)
