# ADR-0006: Version Opportunity Projections and Match Evaluation Snapshots

- Status: Accepted
- Date: 2026-07-20

## Context

A stable Opportunity identifier previously returned an existing published object even when normalized Permit facts, parser output, Classification Results, or rules changed. Match score history retained the old explanation but not every policy, configuration, territory, freshness, and revision input needed to reproduce it. Acquisition or processing time could also obscure an unknown source event date, and valuation contributed to both value and completeness.

## Decision

Keep a stable logical Opportunity ID per canonical Permit and add a deterministic material-input fingerprint plus monotonically increasing projection revision. An unchanged fingerprint is a no-op. A changed fingerprint stores the prior projection as immutable superseded history, installs the replacement as current, and marks active customer Matches stale for reevaluation.

Govern source freshness as issue date, then application date, else unknown with zero credit. Preserve acquisition and processing timestamps separately. Score valuation only in the value component and prohibit it from completeness.

Store a complete immutable evaluation snapshot with every current and historical governed Match explanation: policy identity/version/weights/boundaries, customer configuration, territory result/distance/unit, source/acquisition/processing/evaluation/calculation times, publication threshold, Opportunity revision, components, rules, and rationale.

## Consequences

Projection and score changes are auditable and replayable. Superseded content cannot remain actively matched, unchanged replay creates no false history, and customer-specific configuration cannot change another customer’s Match. In-memory deployments must rebuild Opportunity and Match state; durable persistence and migration remain future work.

## Related documents

- [Project structure v1.13](../current/project-structure-v1.13.md)
- [Backend structure v1.12](../current/backend-structure-v1.12.md)
- [Business logic v1.12](../current/business-logic-v1.12.md)
- [Business data v1.7](../current/business-data-v1.7.json)
