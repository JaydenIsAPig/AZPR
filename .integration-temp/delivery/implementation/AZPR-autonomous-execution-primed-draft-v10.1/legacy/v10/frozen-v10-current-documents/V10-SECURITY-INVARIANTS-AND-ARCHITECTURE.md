# AZPR v10 Security Invariants and Architecture

## Status boundary

This source candidate remains a development artifact. `pre_autonomous_staging=FAIL`, `semi_autonomous_codex_staging_ready=false`, `trusted_pre_autonomous_installation_ready=false`, and `safe_for_unattended_execution_now=false`. The highest possible source-development disposition is `READY_FOR_INDEPENDENT_V10_SOURCE_REASSESSMENT`.

## Threat model

Protected assets are qualification evidence, probe authority and policy, receipt and authorization integrity, bootstrap roots, installer state, anchored journals, key lifecycle state, prompt identity, and release bytes. Threat actors include a qualification submitter controlling input paths and JSON, a malicious local user able to replace writable files or ancestors, a compromised probe client, a replaying caller, a compromised signing client, and accidental packaging or documentation drift.

## Trust roots

1. The organization release authority is external and not supplied by this unsigned candidate.
2. The bootstrap authority public key and signed bootstrap-root manifest are independently provisioned under a trusted owner and filesystem path.
3. The bootstrap manifest pins the qualification receipt key, authorization and phase-transition keyrings, authorization anchor, qualification-trust authority key, and exact signed qualification-trust manifest.
4. The qualification-trust manifest pins the approved probe keyring, probe policy, probe-service identity, independent service attestation, revocation state, host, candidate, challenge, validity window, and sequence.
5. The external receipt signer and installer independently reconstruct and verify the same trust binding.

## First state-changing boundary

All bootstrap, qualification-trust, probe-envelope, receipt, artifact-set, authorization, freshness, host/candidate/challenge, revocation, and signature checks must complete before authorization reservation or installer state creation. The verifier writes only a final receipt with create-exclusive semantics after external signature verification.

## Versioned qualification artifact set

The v9 fixed-count assumption is replaced by `AZPR_V10_QUALIFICATION_ARTIFACT_SET` version `2.0`. Membership is explicit and collision-safe. Every receipt and installation authorization binds both the complete map and its canonical aggregate. The installer independently re-hashes every member and rejects missing, extra, aliased, symlinked, writable, or changed files.

## Probe authority invariant

A caller-provided keyring, policy, identity, attestation, or revocation list has no authority by itself. Each must match the hash in the independently signed qualification-trust manifest, and every enforcing consumer verifies the signed manifest through the bootstrap-pinned qualification-trust authority key. Probe keys require the exact service ID and role, a valid interval, and non-revoked state. Envelopes bind host, candidate, challenge, policy, service identity, attestation, keyring, revocation state, and trust-manifest hash.

## Bootstrap path invariant

Security-critical roots are opened using descriptor-relative component walks with `O_NOFOLLOW`, single-link regular-file checks, owner and mode checks, trusted-directory checks, and before/after inode metadata comparison. Unsupported primitives fail closed. Production bootstrap verification requires UID 0 ownership and trusted `/etc` ancestry. Tests may use an explicitly designated, single-owner test trust root without changing production defaults.

## External signer contract

The signing request includes the complete qualification trust binding and its canonical hash. The signer must independently validate it against separately provisioned trust roots before signing. The client verifies that the signer did not alter the receipt or binding. The bundled reference signer is test-only and refuses operation without explicit test configuration.

## Installer re-verification contract

The installer re-verifies bootstrap roots, qualification trust, probe envelopes, versioned artifact bindings, receipt signature, authorization binding, and freshness before reservation. The installed-generation manifest and installation receipt carry the trust-binding hash and artifact-set version. First install remains `QUALIFICATION_ONLY`.

## Replay, rollback, and recovery

Existing authorization journals, global serialization, anchored heads, one-use authorization, phase separation, and key-epoch mechanisms remain in force. Trust manifests and revocation state carry monotonic sequence values; downgrade to an older sequence is rejected by the caller-provided minimum sequence and must later be backed by the qualified remote anchor.

## Unsupported or unproven areas

This candidate does not prove organization signing, dedicated-host filesystem and kernel behavior, production HSM signer behavior, remote rollback-resistant anchoring, real key ceremonies, supply-chain reproduction, fault-matrix execution, canonical-policy approval, Prompt 004, roadmap promotion, or application/provider qualification.

## Acceptance evidence

The source implementation is accepted for independent reassessment only when all 18 release tests pass both in the source tree and a fresh read-only extraction, all strict schemas validate, prompt bytes match SHA-256 `3b235cb7e33ca409241ff26523f60f8fee89cec524b3f09e91a69927a0aa4880`, current documents match their index, and the authenticated internal manifest is exact.
