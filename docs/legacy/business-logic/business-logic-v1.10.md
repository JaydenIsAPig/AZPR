---
document_id: business-logic
version: 1.10
document_status: superseded
implementation_status: partially implemented
approved_on: 2026-07-20
---
# Business Logic v1.10

## Opportunity identity and revision rules

- One logical Opportunity identity represents one canonical Permit across projection changes.
- The projection fingerprint covers every material normalized fact, lifecycle/provenance/version input, current authoritative Classification Result, and governed projection policy.
- An identical fingerprint is an idempotent replay. A different fingerprint creates the next revision, preserves the old projection as immutable `superseded` history, and makes only the replacement current.
- Active Matches for the Opportunity become `stale`; a customer-specific evaluation either recalculates them against the current revision or excludes them under stable reason codes. Superseded projections are never actively matched.

## Freshness and completeness rules

- Source freshness date precedence is `issued_on`, then `applied_on`.
- Missing source dates remain unknown and earn zero freshness points. Acquisition and processing timestamps remain distinct historical context and cannot make a record appear fresh.
- Valuation is scored once, only in the value component.
- Completeness uses permit type, description, address, and source permit date; valuation is prohibited from completeness.

## Historical explainability

Every governed Match explanation stores the policy identity/version and exact weights/boundaries, customer trade/territory/filter/notification configuration, geography result including distance/unit when applicable, source/acquisition/processing/evaluation/calculation times, publication threshold, Opportunity revision, components, machine rules, and human rationale. A material change appends the complete prior explanation; unchanged replay does not create history.

Customer Match identity and snapshots remain scoped to one customer. Configuration changes affect only that customer’s evaluation.

## Reprocessing requirement

There is no durable database migration. Existing in-memory Opportunity and Match state must be discarded and rebuilt under v1.10/business-data v1.5.

## Related current documents

- [Project structure v1.10](../project-structure/project-structure-v1.10.md)
- [Backend structure v1.10](../backend-structure/backend-structure-v1.10.md)
- [Business data v1.5](../business-data/business-data-v1.5.json)
- [ADR-0006](../../adr/0006-versioned-opportunity-projections.md)
- [Business logic log](../../logs/business-logic-log-v1.10.md)
