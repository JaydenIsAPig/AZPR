# AZPR v9 Security Decisions

```json
{
  "safe_for_unattended_execution_now": false,
  "trusted_pre_autonomous_installation_ready": false
}
```

1. **Qualification targets are data to the verifier, never child processes.** Only immutable signed probe envelopes cross the boundary.
2. **Receipt signing is external.** The semantic verifier holds no receipt private key and verifies the signer response with a pinned public key.
3. **The global lock begins before any state read.** Recovery, reservation, activation, receipt, anchor completion, and failure completion are one serialized transaction.
4. **The remote head is authoritative with exact reconciliation.** No local-only repair or sequence reset is permitted.
5. **The anchored object is the immutable signed record.** Transport receipts are retained separately and cannot change the committed hash.
6. **Complete equality is required, not documentary inclusion.** Every qualified map member and separately bound executable/bootstrap identity is consumed by enforcing code before reservation.
7. **Bootstrap trust cannot be supplied by the installer caller.** Fixed host authority paths authenticate qualification, receipt, phase, and anchor roots.
8. **First installation is qualification only.** Policy status cannot derive installation phase.
9. **A phase transition is a separate one-use authorization.** It binds prior generation, host, receipt, launcher/fault evidence, and canonical-policy record.
10. **Signatures prove provenance, not PASS.** Decisive measurements are recomputed from raw evidence.
11. **Trust stores move as one epoch.** Partial store rotation is not an accepted active state.
12. **Reference signer and anchor implementations are test oracles only.** They are never represented as production infrastructure.
13. **Independent reassessment is the promotion authority.** Self-authored test success cannot set readiness true.
