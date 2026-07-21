---
document_id: project-structure
version: 1.7
document_status: superseded
implementation_status: partially implemented
approved_on: 2026-07-17
---
# Project Structure v1.7

## Status statement

**Implemented:** v1.6 behavior plus customer-owned service territories, configurable limits, deterministic geography evaluation, explainable query results, and polygon containment behind a port.

**Partially implemented:** no production polygon provider, geospatial database/index, durable customer configuration repository, or customer-facing territory UI/API is selected.

## Geography ownership

| Path | Responsibility |
|---|---|
| `domain/customer.py` | Customer-owned radius/city/jurisdiction/ZIP/polygon-reference configuration and uncertain-location preference |
| `application/geography.py` | Policy validation, Haversine distance, isolation, cached evaluation, match/exclusion explanations |
| `infrastructure/geography.py` | Governed business-data policy loader |
| `tests/test_geography_service_territories.py` | Boundary, missing-data, limit, isolation, and adapter tests |

## Related current documents

- [Backend structure v1.7](../backend-structure/backend-structure-v1.7.md)
- [Business logic v1.7](../business-logic/business-logic-v1.7.md)
- [Business data v1.2](../business-data/business-data-v1.2.json)
- [Frontend design v1.0](../frontend-design/frontend-design-v1.0.md)
- [Project structure log](../../logs/project-structure-log-v1.7.md)
