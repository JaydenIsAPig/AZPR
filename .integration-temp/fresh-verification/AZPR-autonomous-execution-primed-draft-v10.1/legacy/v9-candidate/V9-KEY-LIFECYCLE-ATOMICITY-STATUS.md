# AZPR v9 Key-Lifecycle Atomicity Status

```json
{
  "safe_for_unattended_execution_now": false,
  "trusted_pre_autonomous_installation_ready": false
}
```

## Implemented source controls

A transition covers exactly ten trust stores: approval keyring, evidence keyring, runtime verification key, installation verification key, adapter authorization keyring, qualification authorization keyring, qualification receipt verification key, release verification key, phase-transition keyring, and bootstrap-root manifest.

The transition is independently signed by distinct `key-lifecycle-authorizer` and `security-approver` signers, has exact previous/new epoch IDs, monotonic sequence, one-use nonce/ID, and exact source path/hash for every store. All files are copied into one immutable staged epoch. A durable pending intent is written, the epoch head is compare-and-publish anchored, and one active pointer is atomically replaced. Recovery rolls back only an unanchored epoch or activates only the exact anchored epoch. Active-pointer deletion/rollback fails closed.

## Status

`PARTIALLY_CLOSED`: the source-level atomic epoch tool and regressions pass, but the real host’s controller, installer, external runner, signer, anchor, and lifecycle operating procedures have not all been deployed and independently exercised through the active-epoch resolver. V9 does not claim completed organization key rotation, revocation, emergency disablement, or hardware custody.
