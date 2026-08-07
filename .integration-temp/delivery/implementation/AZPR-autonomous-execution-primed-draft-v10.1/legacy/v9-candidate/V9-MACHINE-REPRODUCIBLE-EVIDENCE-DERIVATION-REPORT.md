# AZPR v9 Machine-Reproducible Evidence Derivation Report

```json
{
  "safe_for_unattended_execution_now": false,
  "trusted_pre_autonomous_installation_ready": false
}
```

Six qualification report classes are mapped to explicit raw-evidence checks and output fields: Codex isolation, remote anchor, key custody, installer fault matrix, supply-chain rebuild, and dedicated-host policy.

For each report, the verifier validates the raw-evidence schema, host/archive binding, command identity hashes, nonzero/zero exit semantics as required, transcript hash, required decisive boolean checks, and deterministic measurement output. It then requires the signed report status and measurements to equal the recomputed result exactly.

Regression `test_f06_contradictory_machine_evidence_fails` first validates a correct remote-anchor report, then changes `rollback_test_passed` to false while preserving the report’s signed PASS claim. Verification rejects at the decisive raw check. This prevents a signature from substituting for evidence correctness.

The delivery contains contracts and derivation code, not genuine host transcripts. Real evidence must be generated immutably by independent roles and reassessed.
