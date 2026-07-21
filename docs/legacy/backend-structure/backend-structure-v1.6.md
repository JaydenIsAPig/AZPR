---
document_id: backend-structure
version: 1.6
document_status: superseded
implementation_status: partially implemented
approved_on: 2026-07-17
---

# Backend Structure v1.6

## Classification flow

```text
Permit + optional occupancy/project/source categories
  -> versioned deterministic rules
  -> immutable per-tag assertions and provenance
  -> sanitized description-only AI request when configured
  -> strict response validation; invalid/provider failure yields no AI assertions
  -> deterministic tag precedence
  -> governed confidence thresholds
  -> low-confidence review tasks
```

Rules consume normalized permit type, bounded description phrases, Decimal valuation, occupancy/project signals, existing source categories, contractor fields, and jurisdiction mappings. Rule IDs and semantic versions are stored on each assertion. Observed source, deterministic, AI, and human origins are separate.

The AI port receives only a sanitized, capped description and a response schema. AI cannot overwrite an existing deterministic tag. No exception from the provider path blocks deterministic output. Human decisions can be exported as labeled examples; no training operation exists.

The fixed evaluation fixture reports precision independently for every predicted tag. The current adapter is provider-neutral and no production provider/model has been approved.

## Related current documents

- [Project structure v1.6](../project-structure/project-structure-v1.6.md)
- [Business logic v1.6](../business-logic/business-logic-v1.6.md)
- [Business data v1.1](../business-data/business-data-v1.1.json)
- [Backend structure log](../../logs/backend-structure-log-v1.6.md)
