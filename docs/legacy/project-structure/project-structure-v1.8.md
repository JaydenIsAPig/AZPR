---
document_id: project-structure
version: 1.8
document_status: superseded
implementation_status: partially implemented
approved_on: 2026-07-20
---
# Project Structure v1.8

## Status statement

**Implemented:** v1.7 behavior plus stable Opportunity projection generation, deterministic explainable Customer Match scoring, exclusion gates, idempotent replay, and score-history retention.

**Partially implemented:** persistence remains in-memory. No durable Opportunity projection/match tables, production matching worker, notification-intent trigger, or customer-facing API/UI is selected.

## Opportunity and matching ownership

| Path | Responsibility |
|---|---|
| `domain/opportunity.py` | Customer-independent, source-backed Opportunity projection and lifecycle |
| `domain/matching.py` | Customer-specific explanation, 100-point components, score history, lead/match lifecycle |
| `application/opportunity_matching.py` | Stable generation, eligibility gates, deterministic score/replay/recalculation |
| `infrastructure/opportunity_matching.py` | In-memory stores and governed score-policy loader |
| `tests/test_opportunity_generation_matching.py` | Positive, exclusion, boundary, configuration, history, isolation, replay tests |

## Related documents at supersession

- [Backend structure v1.8](../backend-structure/backend-structure-v1.8.md)
- [Business logic v1.8](../business-logic/business-logic-v1.8.md)
- [Business data v1.3](../business-data/business-data-v1.3.json)
- [Frontend design v1.0](../frontend-design/frontend-design-v1.0.md)
- [Project structure log](../../logs/project-structure-log-v1.8.md)
