---
document_id: business-logic
version: 1.6
document_status: superseded
implementation_status: partially implemented
approved_on: 2026-07-17
---

# Business Logic v1.6

## Permit classification rules

- Tags cover market segment, new construction, remodel, addition, demolition, tenant improvement, mechanical, electrical, plumbing, roofing, solar, fire suppression, low voltage, concrete/structural, landscaping/equipment indicators, value band, owner-builder, and data completeness.
- Normalized phrase boundaries prevent substring-only matches. Source categories may use explicit jurisdiction mappings.
- Valuation bands are `under_25k`, `25k_to_100k`, `100k_to_500k`, `500k_plus`, and `unknown`.
- Data completeness is based on normalized type, description, valuation, and address and yields `complete`, `partial`, or `sparse`.
- Every assertion records `source`, `deterministic_rule`, `ai`, or `human` origin. Deterministic assertions include rule ID/version; AI assertions include provider/model/classifier versions.
- AI proposals never replace deterministic tags. Invalid output and provider failure fail closed without suppressing deterministic results.
- AI acceptance and review thresholds come from governed business-data JSON. Accepted results below the review threshold create deterministic, idempotent review-task IDs.
- Human decisions can produce labeled evaluation records. Retraining is never automatic.
- The fixed fixture set reports precision per predicted tag.

## Related current documents

- [Project structure v1.6](../project-structure/project-structure-v1.6.md)
- [Backend structure v1.6](../backend-structure/backend-structure-v1.6.md)
- [Business data v1.1](../business-data/business-data-v1.1.json)
- [Business logic log](../../logs/business-logic-log-v1.6.md)
