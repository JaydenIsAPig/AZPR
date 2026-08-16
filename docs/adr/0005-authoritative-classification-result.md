# ADR-0005: Authoritative Classification Result and Central Publication Eligibility

- **Status:** Accepted
- **Date:** 2026-07-20
- **Deciders:** Project owner
- **Supersedes:** None
- **Superseded by:** None

## Context

Classification assertions, aggregate Results, Review Tasks, Opportunity generation, and Customer matching previously had partially independent control paths. That allowed ambiguity about which object authorized publication and made duplicate, Permit-lifecycle, review-status, and confidence changes difficult to enforce consistently.

## Decision

`ClassificationResult` is the sole downstream classification authority. It owns assertion evidence, effective project/trade output, confidence, provenance/version identity, review status, revision, supersession, and human decisions. Assertions may explain a Result but cannot independently authorize an Opportunity or Match.

Classification writes persist the Result and any exact Result-linked Review Task atomically. Stable content/version identity makes classification replay idempotent. Human review records actor, rationale, timestamp, prior/new value, source assertion origin, and classification version; identical decisions replay without duplicated state changes.

One `PublicationEligibilityPolicy` governs both Opportunity generation and Customer matching. It fails closed unless referenced Permits are canonical and active, duplicate uncertainty is resolved, authoritative Results are accepted and meet the governed publication confidence, Opportunities are published, and matching geography is verified. It returns explicit machine-readable reasons and reevaluates existing active outputs when inputs or thresholds change.

## Consequences

- Opportunity and Match callers must supply authoritative Results rather than assertion tuples.
- Low-confidence, pending, rejected, missing, voided, superseded, noncanonical, probable-duplicate, unpublished, and geographically unverified states cannot publish or match.
- The compatibility assertion projection is read-only and temporary.
- Current in-memory state must be reprocessed; no database migration exists yet.
- Durable transactional repositories must preserve the same Result/Review atomicity and revision checks.

## Alternatives considered

Keeping assertions and Results as peer authorities was rejected because it permits bypass and inconsistent lifecycle checks. Duplicating eligibility rules in generation and matching was rejected because policy changes could drift.

## Related documents

- [Project structure v1.18](../current/project-structure-v1.18.md)
- [Backend structure v1.12](../current/backend-structure-v1.12.md)
- [Business logic v1.12](../current/business-logic-v1.12.md)
- [Business data v1.7](../current/business-data-v1.7.json)
