# AZPR Autonomous-Execution Primed Draft v9

```json
{
  "safe_for_unattended_execution_now": false,
  "trusted_pre_autonomous_installation_ready": false
}
```

V9 is an **unsigned corrective implementation candidate** derived from the authenticated v8 baseline. It is suitable only for isolated source review, adversarial reproduction, and a new independent security consultation. It is not approved for privileged installation, canonical-policy activation, Prompt 004, roadmap generation, autonomous stages, external operations, production credentials, or customer data.

## Baseline and disposition

The v8 implementation, reports, prompt archive, delivery manifest, and sidecars were verified against the handoff identities before any edit. The v8 implementation contained 196 safe ZIP members and 195 authenticated internal-manifest entries. The prompt set remains 38 numbered prompts plus Appendices A–C and the embedded prompt ZIP remains byte-identical to SHA-256 `3b235cb7e33ca409241ff26523f60f8fee89cec524b3f09e91a69927a0aa4880`.

V9 provides source-level enforcement for the v8 Critical/High defects, preserves the inherited v5–v8 controls, and adds release-blocking v9 regressions. Real dedicated-host, VM/kernel isolation, external signer, rollback-resistant anchor, hardware key custody, reproducible supply-chain, organization signing, provider, and application evidence remain qualification dependencies.

## Start here

1. `V8-FINDING-CLOSURE-MATRIX.md`
2. `V9-SECURITY-INVARIANTS-AND-ARCHITECTURE.md`
3. `V9-AFFECTED-FILES-FUNCTIONS-SCHEMAS-AND-MODIFICATION-BOUNDARIES.md`
4. `V9-ADVERSARIAL-AND-MUTATION-TEST-REPORT.md`
5. `V9-KNOWN-LIMITATIONS-AND-QUALIFICATION-DEPENDENCIES.md`

Run the verifier only against an immutable source tree or a fresh safe extraction:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 VERIFY-V9-CANDIDATE.py
```

A PASS establishes only internal source/package consistency. Independent reassessment remains mandatory.
