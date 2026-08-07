# AZPR v10.1 Release Verification Summary

## Developer-side disposition

**`READY_FOR_INDEPENDENT_V10_1_SOURCE_REASSESSMENT`**

This is not an independent promotion decision. It authorizes only reassessment of the exact frozen bytes. Pre-autonomous staging remains `FAIL`; final integration prompt authoring, Codex seating/application, trusted installation, Prompt 004, roadmap generation/promotion, numbered prompt execution, credentials, providers, customer data, and unattended execution remain unauthorized.

## Verified results

- Source-tree verifier: **PASS**, UID 1000, **120/120** isolated release tests.
- Fresh-extraction verifier: **PASS**, UID 1000, **120/120** isolated release tests.
- Source and extraction test IDs/nodes: byte-for-byte equivalent lists.
- Internal manifest: **312 authenticated entries** in each run.
- Python files compiled: **69**.
- Strict schemas verified: **73**.
- Current documents verified: **17**.
- Prompt identity: **38 numbered prompts + Appendices A–C**, unchanged SHA-256 `3b235cb7e33ca409241ff26523f60f8fee89cec524b3f09e91a69927a0aa4880`.
- Qualification artifact set: version **2.1**, exactly **57 artifacts**.
- No root state, credentials, network, cache creation, or source-tree mutation was required.

## Source-level correction status

Findings `AZPR-V10-IND-F01` through `AZPR-V10-IND-F06` are marked **closed at source level pending independent reassessment**. `AZPR-V10-IND-F07` remains open by design because organization, host, HSM/signer, remote anchor, supply-chain, key-custody, policy, roadmap, and application/provider evidence are not present.

## Major changes

1. Trust-root, signer, receipt-key, owner, and sequence selection were removed from caller-controlled qualification input.
2. The authority is resolved from a fixed signed host-root manifest and checked against a signed remote head.
3. Signed policy semantics are now consumed exactly rather than only hash-bound.
4. Probe-service attestation has an independently pinned signer/revocation path and is tied to actual executable, launcher, and runtime bytes.
5. The qualification set grew from 48 to 57 named artifacts.
6. All reported schema bounds were corrected, and every collected test is now isolated and release blocking.
7. Historical root-only fixtures were made reproducible for UID 1000 without skipping tests or weakening production ownership/identity requirements.

## Lingering concerns

The candidate remains unsigned and infrastructure-unqualified. A separate assessor must reproduce the complete caller-created authority attack, policy mutations, attestation/executable substitution, chronology/remote-head rollback, strict schema bounds, all 120 tests, and source/fresh verification before any later gate can change.
