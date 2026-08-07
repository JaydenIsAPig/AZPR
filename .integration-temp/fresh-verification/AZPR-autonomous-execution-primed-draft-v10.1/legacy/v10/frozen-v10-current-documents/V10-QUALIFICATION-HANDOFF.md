# AZPR v10 Qualification Handoff

## Permissible next event

An independent security reviewer may verify the exact frozen v10 bytes and challenge every source-level closure. No other promotion event is authorized yet.

## Independent source reassessment checklist

1. Verify top-level delivery manifest, sidecars, archive safety, and internal manifests.
2. Run `VERIFY-V10-CANDIDATE.py --fresh-extraction` as a dedicated unprivileged reviewer from a read-only extraction.
3. Reproduce the original v9 attacks against v10 call paths.
4. Inspect signer and installer enforcement rather than accepting recorded hashes.
5. Mutate each trust-binding member and no-follow path check.
6. Review the exact 48-artifact membership for omitted consumed inputs.
7. Confirm prompts and Master Operating Prompt are unchanged and no active policy/roadmap exists.
8. Preserve all readiness flags as false.

## Order after an independent source PASS

1. Organization-sign exact frozen release bytes.
2. Provision and qualify dedicated host and bootstrap roots.
3. Deploy and qualify production external signer/HSM and remote anchor.
4. Execute real supply-chain rebuild and key ceremonies.
5. Execute full host fault matrix and recovery.
6. Approve exact canonical policy.
7. Execute Prompt 004 manually.
8. Generate and independently review/promote roadmap against all 41 prompt files.
9. Conduct isolated application/provider dry runs.
10. Request a separate promotion review before any semi-autonomous staging.
