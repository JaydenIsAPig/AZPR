# AZPR v9 Adversarial and Mutation Test Report

```json
{
  "safe_for_unattended_execution_now": false,
  "trusted_pre_autonomous_installation_ready": false
}
```

## Catalog

The frozen candidate contains 96 exact pytest test IDs across ten modules, plus the inherited six-case v8 black-box harness. The v9 module contributes 12 release-blocking tests and internal loops covering nine malicious probe roles, 39 one-at-a-time artifact substitutions, 20 concurrent authorization contenders, seven exact phase-binding mutations, rollback/recovery states, and ten trust stores.

## V9 adversarial cases

- Malicious scripts for all nine probe roles would create a marker if executed; signed-envelope verification completed with no marker.
- A signed envelope claiming UID 0 is rejected.
- Source inspection and protocol execution prove the receipt verifier has no receipt private-key argument or symbol; the external signer response is independently signature-verified.
- A signed PASS report paired with raw evidence changing a decisive check to false is rejected.
- Every member of the exact 39-artifact map is modified independently and rejected before state.
- Hard-link alias, symlink, and alternate-path substitutions reject.
- Caller replacement of a pinned bootstrap root rejects.
- First-install policy activation rejects; every prior-generation/host/receipt/evidence/policy binding mutation rejects.
- Twenty synchronized sequence-1 processes yield exactly one success and anchored sequence 1.
- Stale ledger restore, pre-anchor interruption, post-anchor interruption, epoch pointer rollback, and lifecycle transition interruption fail closed or recover to the only anchored result.

## Inherited controls

The v5–v8 modules retain Git topology rejection, exact policy extraction, process-tree containment, bounded I/O and cleanup, quota/special-file rejection, immutable evidence, signature-role separation, authorization semantics, and production-loader phase blocking. Tests are executed one exact node per isolated process with hard timeouts by `VERIFY-V9-CANDIDATE.py`.

## Interpretation

These are source/package regressions, not dedicated-host qualification. No result is treated as evidence of real kernel, VM, HSM, remote-anchor, provider, or application behavior.
