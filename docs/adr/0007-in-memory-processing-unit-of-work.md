# ADR-0007: Authoritative Batch Ownership and In-Memory Processing Unit of Work

- Status: Accepted
- Date: 2026-07-20

## Context

Acquisition owned an `ImportBatch` and queue entry, but parsing mutated a deep copy. The authoritative Batch remained `acquired` after a local parser copy became completed or failed. Normalization persisted Permit, duplicate candidate, and Review Task changes through separate stores, allowing injected failure to expose partial state. No command correlated all stages through a final Customer Match, exclusion, review, or failure.

## Decision

Keep the domain-driven modular monolith and current in-memory adapters. Acquisition state is the sole Batch and queue owner. Parsing uses an exclusive correlation-scoped claim and commits a terminal working copy back through that owner; Source Record state is snapshot-restored if parsing or commit fails.

Coordinate Permit, duplicate-candidate, and normalization Review Task stores with a shared process-local lock and snapshot rollback. Serialize end-to-end correlation commands and Opportunity/Match generation at their repository boundaries. Add one synchronous application workflow and privacy-safe stage trace ledger.

Retryable parsing failures are explicit but terminal for that Batch; retry creates a new reprocessing Batch. Do not introduce a database or claim process-local behavior is durable transactionality.

## Consequences

Batch state and queue membership cannot diverge inside the current process. Injected normalization failure exposes no partial normalized state. Repeated/concurrent correlation commands, projections, and Matches do not duplicate active outcomes. This design does not protect across processes or crashes.

A production persistence ADR must select technology later. It must translate the documented uniqueness scopes into database constraints and replace snapshot rollback/locks with transactions, leases, and a transactional outbox.

## Related documents

- [Project structure v1.17](../current/project-structure-v1.17.md)
- [Backend structure v1.12](../current/backend-structure-v1.12.md)
- [Business logic v1.12](../current/business-logic-v1.12.md)
- [Business data v1.7](../current/business-data-v1.7.json)
