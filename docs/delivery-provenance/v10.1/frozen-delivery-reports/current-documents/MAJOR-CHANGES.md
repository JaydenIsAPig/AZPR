# AZPR v10.1 Major Changes

## Basis and disposition

This corrective candidate starts from the frozen v10 implementation archive with SHA-256 `3e748b2e8e61033c741f138dae4357d60f020c7db15489333be73bed329741af`. It addresses `AZPR-V10-IND-F01` through `AZPR-V10-IND-F06` identified by the August 4, 2026 internal independent assessment. The assessment itself remains authoritative for the observed v10 failures; this document reports developer-side correction evidence only.

The candidate remains an unsigned development artifact. It is not authorized for installation, policy activation, Prompt 004, roadmap generation or promotion, numbered prompt execution, provider access, or unattended operation.

## Major source changes

1. **Eliminated caller-selected higher-level qualification authority.** Qualification input no longer accepts trust-root paths, trust owner IDs, sequence floors, signer clients, signer identities, receipt keys, or signing-key IDs. The production loader resolves these only from fixed host-owned paths.
2. **Added independently anchored host-root verification.** A fixed anchor client and signed anchor identity verify the exact host-root manifest hash and sequence before the authority is consumed. Stale or forked sequences fail closed. A real remote anchor service remains an operational dependency.
3. **Enforced signed probe-policy semantics.** Target membership, all boundary fields, network mode, UID/GID, required observations, and maximum envelope age are enforced exactly from the signed policy.
4. **Added independent probe-service attestation.** A separately pinned attestor keyring, attestor revocation state, signed attestation, actual descriptor-opened executable digest, launcher digest, and runtime-configuration digest are verified and transitively bound.
5. **Removed the configurable reference signer from the release path.** The old environment-selected signer was quarantined under `legacy/v10/unsafe-reference-signer/`. The current signer client and verification key are fixed host-root artifacts.
6. **Expanded the qualification set from 48 to 57 artifacts.** The versioned `2.1` set includes the higher host roots, anchor client and identity, attestor roots, service executable, signer identity, and all prior consumed inputs.
7. **Validated chronology and monotonic state.** Host roots, trust manifests, signer identity, attestation, keyrings, revocation states, envelopes, and remote-anchor responses enforce validity windows, maximum skew, sequence floors, ordering, and rollback/fork rejection.
8. **Strictly bounded critical schemas.** The ten independently identified unbounded locations were corrected. New host-anchor and attestor schemas are strict and bounded.
9. **Made the complete test suite release blocking.** The release catalog contains every collected test node, runs each in a separate process group, compares the catalog to fresh collection, applies time/output limits, rejects leaked descendants, and fails if any collected test is absent.
10. **Preserved prompt identity and readiness gates.** The 41 prompt files and canonical prompt archive bytes remain unchanged; no canonical policy or roadmap was activated.

## Least-privilege inherited anchor regression

The complete read-only UID 1000 verifier exposed that the bundled non-production file-anchor regression lost its explicitly test-owned anchor root and fell back to a shared `/tmp` default. The controller now forwards that root only to the named bundled reference helper and only outside production mode. Production anchor helpers remain pinned and receive the sanitized fixed environment.

The least-privilege run also exposed umask-dependent permissions in an inherited external-runner fixture. Security-critical fixture documents now receive explicit non-group/non-world-writable modes, so the test exercises rollback evidence semantics rather than failing before the intended trust boundary.

The inherited installer bundle-authentication test no longer creates its fixture under `/root`. It consumes an immutable root-owned fixture shipped in the read-only source tree and uses a narrowly scoped metadata mutation to prove writable bundle content is rejected. This preserves the root-ownership invariant and makes the oracle executable by the non-root reviewer.

Remaining inherited root-only unit fixtures were split into honest source-level non-root oracles and retained root branches for later host qualification. No test is skipped: the non-root catalog verifies exact mode logic, identity-transition code, result symlink/hard-link rejection, qualification signature rejection, and key-lifecycle behavior. Actual UID transition and root-owned secret access proofs remain explicit dedicated-host gates.

The activation-recovery unit test now observes the required `chown(..., 0, 0)` call instead of attempting it under the non-root reviewer. Receipt movement, final mode, fsync, state removal, and recovery result remain exercised; actual privileged ownership application remains part of the host installer qualification matrix.

The inherited v7 clean-room completeness test now executes its full manifest-shape and alias logic in-process under the non-root reviewer using mocked root metadata only at the obsolete v7 file-ownership boundary. The production verifier still requires root, and the actual v10.1 authority path is covered separately by the new fixed-root tests.

The v8 black-box execution-unit exerciser now uses the reviewer's own UID/GID only when the verifier is non-production explicit-test mode. The bounded runner preserves its execution-unit, process-tree, duplex, timeout, and output-overflow behavior but avoids an impossible `setgroups`/identity transition by an unprivileged reviewer. Production and privileged host execution paths are unchanged.

The inherited v9 signer-client test now selects a reviewer-owned trusted directory with non-writable ancestors when executed as UID 1000, while retaining `/root` for privileged runs. The external signer path checks, executable identity, protocol, and no-private-key assertions remain unchanged.
