# AZPR v10.1 Corrective Security Development Candidate

This package is the source-level corrective successor to the frozen v10 candidate assessed on August 4, 2026.

## Status

`READY_FOR_INDEPENDENT_V10_1_SOURCE_REASSESSMENT`

This means only that the developer-side source correction and release checks completed. It does **not** mean staging or installation readiness.

```json
{
  "pre_autonomous_staging": "FAIL",
  "semi_autonomous_codex_staging_ready": false,
  "trusted_pre_autonomous_installation_ready": false,
  "safe_for_unattended_execution_now": false,
  "full_autonomous_pathway_viable": true
}
```

## Verification

Run the release verifier as a dedicated unprivileged reviewer from a read-only fresh extraction:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 VERIFY-V10-CANDIDATE.py --fresh-extraction
```

The verifier refuses root, verifies every source artifact and schema, preserves the canonical 41 prompt bytes, and executes all `120` collected tests in isolated process groups.

## Prohibited actions

Do not install the trusted control plane, activate policy, execute Prompt 004, generate/promote a roadmap, run numbered prompts, connect providers, or use credentials/customer data from this package.
