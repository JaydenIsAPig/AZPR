# V10 Evidence Derivation and Key Lifecycle Integration Report

## Evidence derivation

The carried machine-derived evidence verifier recomputes decisive measurements from raw evidence rather than trusting a signed PASS label. The v10 release blocker first verifies a consistent report, then changes a decisive rollback check to false and confirms the unchanged PASS report is rejected.

The legacy v9 test helper attempted to overwrite a read-only fixture and failed before reaching its oracle. V10 did not weaken the oracle; it added a corrected release-blocking test with safe fixture mutation and the same contradiction requirement.

## Key lifecycle

V10 preserves the atomic multi-store trust epoch, active epoch pointer rollback detection, interrupted transition recovery, stale-key rejection, and `ROLLED_BACK_UNANCHORED_EPOCH` handling. The inherited atomic key-lifecycle interruption/recovery test passes.

## New integration

Probe key role, validity, revocation, service identity, and trust-manifest sequence are now bound into qualification evidence. Full rollback resistance for these values still depends on the production remote anchor and real consumer integration.
