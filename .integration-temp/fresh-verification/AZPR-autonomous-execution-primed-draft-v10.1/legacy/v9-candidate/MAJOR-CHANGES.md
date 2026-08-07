# AZPR v9 Major Changes

```json
{
  "safe_for_unattended_execution_now": false,
  "trusted_pre_autonomous_installation_ready": false
}
```

- Removed execution of qualification targets from the receipt verifier and made the verifier refuse root.
- Removed receipt private-key handling from qualification; added an authenticated external signer client and TEST ONLY reference signer.
- Added signed no-secret probe envelopes for nine executable roles.
- Added one global installer lock and signed, hash-chained, compare-and-publish authorization/phase journals with deterministic pending recovery.
- Enforced one canonical 39-artifact map before reservation, plus exact probe-target, installer, schema, mount/unmount, verifier, adapter-set, lifecycle, and pinned-bootstrap identities.
- Forced first installation to `QUALIFICATION_ONLY`; policy activation is a separate transition from an exact prior generation.
- Added deterministic raw-evidence derivation for all six qualification report classes.
- Added atomic ten-store trust epochs and interruption recovery.
- Added twelve v9 release-blocking tests while retaining all inherited tests and the six-case black-box harness.
- Preserved the 41 prompt bytes, no-active-policy/no-roadmap state, and false readiness flags.
