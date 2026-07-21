---
document_id: backend-structure
version: 1.10
document_status: superseded
implementation_status: partially implemented
approved_on: 2026-07-20
---
# Backend Structure v1.10

## Projection flow

`OpportunityGenerator` resolves the authoritative current `ClassificationResult`, applies central publication eligibility, projects only customer-independent source-backed fields, and hashes every material projection input. The stable logical Opportunity ID remains the SHA-256-derived Permit identity. An unchanged fingerprint is a no-op; a changed fingerprint advances exactly one revision, stores the prior projection as `superseded`, publishes the replacement, and marks active Matches stale.

Material inputs include normalized Permit facts and lifecycle/version state, parser version, current Result identity/revision/confidence, classifier and rule-set versions, source evidence and acquisition provenance, processing timestamp, safe output fields, and the projection-policy version.

## Time and score semantics

Source freshness uses `issued_on`, then `applied_on`, and otherwise remains unknown with zero freshness credit. Artifact acquisition is context only; processing time is provenance only. Neither substitutes for a source event date.

`ExplainableMatchGenerator` snapshots score policy identity/version/weights/boundaries, customer configuration, territory rule and distance/unit, source/acquisition/processing time evaluation, calculation time, publication threshold, and Opportunity revision. Recalculation appends the complete old explanation. A replay with the same effective inputs does not append score history even when attempted later.

Valuation contributes only to the value component. Completeness uses permit type, description, address, and source permit date. Deterministic machine exclusion codes are paired with customer-readable explanations.

## Persistence

All repositories remain in-memory. Deployments must reprocess existing Permit/Classification state into v1.10 Opportunities and Matches.

## Related current documents

- [Project structure v1.10](../project-structure/project-structure-v1.10.md)
- [Business logic v1.10](../business-logic/business-logic-v1.10.md)
- [Business data v1.5](../business-data/business-data-v1.5.json)
- [ADR-0006](../../adr/0006-versioned-opportunity-projections.md)
- [Backend structure log](../../logs/backend-structure-log-v1.10.md)
