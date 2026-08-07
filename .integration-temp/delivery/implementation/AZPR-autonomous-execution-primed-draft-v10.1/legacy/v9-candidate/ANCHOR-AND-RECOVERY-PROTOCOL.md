# AZPR v8 Anchor and Recovery Protocol

Exact-sequence anchor acknowledgement, transactional operation/evidence handling, and versioned installation recovery are retained. V8 additionally requires qualification evidence for the remote anchor and binds that evidence into the semantic receipt and one-use installation authorization.

Key lifecycle transitions require a remote-anchor acceptance receipt over the new transition-chain hash before local state advances. Installation authorization reservations and final receipts are create-once and cannot be inferred from unsigned local state.

A file-backed reference anchor remains test-only. A production remote anchor must be independently protected, authenticated, idempotent, rollback resistant, challenge-tested, and qualified under partition, stale-receipt and restored-local-snapshot scenarios.
