# AZPR v9 Qualification-Only Phase Transition Report

```json
{
  "safe_for_unattended_execution_now": false,
  "trusted_pre_autonomous_installation_ready": false
}
```

## First installation

When no active lock exists, only `installation_phase=QUALIFICATION_ONLY`, `canonical_policy_status=NOT_YET_APPROVED`, no phase authorization, and no canonical-policy derivative are accepted. Production controller, external runner, and validation loaders reject qualification-only manifests.

## Later policy activation

`POLICY_ACTIVATED` requires all of the following before reservation:

- immutable prior manifest whose phase is `QUALIFICATION_ONLY`;
- exact prior installation ID, manifest hash, active-lock hash, and installation-receipt hash;
- same host ID;
- exact launcher evidence and installer fault-matrix evidence, both PASS;
- exact independently approved canonical-policy record;
- separate fresh dual-role phase-transition authorization;
- separate anchored phase journal with one-use sequence, nonce, and transition ID.

The mutation test changes each prior-generation/host/receipt/evidence/policy field independently and requires rejection. No real host phase transition was performed.
