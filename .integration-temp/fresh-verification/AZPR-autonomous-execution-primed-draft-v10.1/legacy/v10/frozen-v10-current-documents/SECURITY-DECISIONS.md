# AZPR v10 Security Decisions

## SD-10-01 — Authority must be independently provisioned
A caller-supplied probe keyring, policy, service identity, attestation, or revocation list is data, not authority. Authority derives only from the bootstrap-pinned qualification-trust authority and its signed manifest.

## SD-10-02 — Every enforcing consumer verifies the binding
Recording a hash is insufficient. The cleanroom verifier, external signer, installer, phase transition, and installed state must consume and verify the same canonical trust binding.

## SD-10-03 — Artifact membership is versioned, explicit, and exact
The set identifier is `2.0`; membership is 48 exact names. Runtime aggregation is supplemental and cannot replace exact member verification.

## SD-10-04 — Trust-root filesystem uncertainty fails closed
No ordinary `Path.read_bytes()` fallback is permitted for bootstrap roots. Unsupported no-follow or filesystem semantics stop the operation.

## SD-10-05 — First installation remains qualification-only
V10 does not activate canonical policy during first installation. Policy activation remains a separately authorized phase transition after real qualification.

## SD-10-06 — Source closure is not operational qualification
Passing source tests can support only `READY_FOR_INDEPENDENT_V10_SOURCE_REASSESSMENT`. It does not prove organization signing, hardened-host behavior, HSM custody, remote anchoring, supply-chain reproduction, or application/provider safety.

## SD-10-07 — Prompt and governing-policy bytes are immutable in this iteration
The 38 numbered prompts, Appendices A–C, prompt archive, and supplied Master Operating Prompt are unchanged. No active canonical policy or promoted roadmap is included.
