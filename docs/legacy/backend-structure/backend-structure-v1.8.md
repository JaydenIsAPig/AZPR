---
document_id: backend-structure
version: 1.8
document_status: superseded
implementation_status: partially implemented
approved_on: 2026-07-20
---
# Backend Structure v1.8

## Opportunity projection

A stable Permit-derived identifier makes replay idempotent. The projection stores source Permit and Classification references, source-attributed headline/description, normalized locality, jurisdiction/date, categories/trades, value/band, completeness, confidence, and freshness. Contact-like text is removed from the concise customer-safe description.

## Match flow

```text
Opportunity + referenced Permits + Customer Account
  -> suppressed/expired and active-account gates
  -> enabled trade overlap
  -> customer-isolated service territory
  -> valuation/value-band, permit, project, confidence, date exclusions
  -> deterministic versioned 100-point components
  -> stable Opportunity+Customer Match ID
  -> replay or history-retaining recalculation
```

The score is the exact sum of governed trade, geography, value, completeness, freshness, and notification-readiness components. No AI call or model output produces the total. Each explanation stores version, component values, matched rules, exclusion rules considered, configuration version, confidence, freshness, and readable rationale.

Weight or customer-configuration changes recalculate the same Match and append the prior explanation to history. Dismissed/ended matches do not reactivate. Suppression or a newly triggered exclusion terminally excludes an existing active Match.

## Related documents at supersession

- [Project structure v1.8](../project-structure/project-structure-v1.8.md)
- [Business logic v1.8](../business-logic/business-logic-v1.8.md)
- [Business data v1.3](../business-data/business-data-v1.3.json)
- [Backend structure log](../../logs/backend-structure-log-v1.8.md)
