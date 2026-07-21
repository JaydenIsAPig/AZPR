---
document_id: backend-structure
version: 1.7
document_status: superseded
implementation_status: partially implemented
approved_on: 2026-07-17
---
# Backend Structure v1.7

## Geography query flow

```text
requesting Customer ID + Customer Account + Permit
  -> customer-isolation check
  -> jurisdiction / normalized city / ZIP5 rules
  -> cached Haversine radius calculation when coordinates exist
  -> optional polygon adapter
  -> uncertain-geography opt-in only when verification is impossible
  -> inside, distance + unit, matched rule, exclusion reason, verification status
```

Customer radius origins are stored as validated normalized coordinates. Distance is Haversine great-circle distance using a spherical Earth mean radius of 6,371.0088 km and is rounded to 0.001 km. This is deterministic and suitable for service-area screening, but does not model road distance, elevation, ellipsoidal geodesics, parcels, municipal boundaries, or legal boundary precision.

The pure calculation cache is bounded to 4,096 coordinate pairs and contains no customer data. Polygon containment is reserved behind `PolygonContainment`; absence of an adapter does not guess containment.

## Related current documents

- [Project structure v1.7](../project-structure/project-structure-v1.7.md)
- [Business logic v1.7](../business-logic/business-logic-v1.7.md)
- [Business data v1.2](../business-data/business-data-v1.2.json)
- [Backend structure log](../../logs/backend-structure-log-v1.7.md)
