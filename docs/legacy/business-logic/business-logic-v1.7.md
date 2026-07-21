---
document_id: business-logic
version: 1.7
document_status: superseded
implementation_status: partially implemented
approved_on: 2026-07-17
---
# Business Logic v1.7

## Service territory rules

- Territory scopes may combine a validated-coordinate radius, normalized city names, jurisdiction IDs, ZIP-code sets, and a reserved polygon reference.
- Radius distance uses Haversine kilometers and includes records exactly on the rounded boundary.
- ZIP and ZIP+4 values compare by their five-digit base. Cities normalize whitespace and case.
- Any verified configured rule match includes the record and identifies the matching rule.
- Missing coordinates do not block city, jurisdiction, or ZIP verification.
- If none of the configured rules can be verified, the record is excluded unless that customer explicitly enables uncertain geography. A verified outside location is never rescued by that preference.
- Every result exposes inclusion, optional distance and unit, matched rule, exclusion reason, and verification status.
- The requesting Customer ID must match the territory-owning Customer Account.
- Governed business-data limits radius size and the number of ZIP, jurisdiction, and city entries.
- Polygon evaluation requires an injected adapter and otherwise fails as unverifiable.

## Related current documents

- [Project structure v1.7](../project-structure/project-structure-v1.7.md)
- [Backend structure v1.7](../backend-structure/backend-structure-v1.7.md)
- [Business data v1.2](../business-data/business-data-v1.2.json)
- [Business logic log](../../logs/business-logic-log-v1.7.md)
