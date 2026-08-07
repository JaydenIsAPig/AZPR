# AZPR v10.1 Security Decisions

## SD-10.1-01 — Trust roots are host-owned, not qualification-input-owned
The qualification caller may supply evidence and non-trust artifacts only. All authority roots, signer identities, attestor identities, service executable identity, and receipt verification keys are resolved from fixed host paths and are excluded from the caller schema.

## SD-10.1-02 — Local signatures require an independent monotonic head
A locally valid host-root manifest is insufficient. The loader must receive an independently signed anchor response for the exact manifest hash and sequence. Rollback, fork, wrong candidate, wrong host, wrong challenge, stale time, bad signature, or client substitution fails before authority construction.

## SD-10.1-03 — Signed policy fields are executable requirements
Signed policy data is not informational metadata. The verifier compares every policy-controlled boundary and observation field exactly and applies the signed maximum age.

## SD-10.1-04 — Service identity requires independent attestation and actual bytes
The service identity must match the actual no-follow descriptor-read executable. An independently pinned attestor signs the service, executable, launcher, runtime configuration, host, candidate, challenge, and validity interval.

## SD-10.1-05 — Complete tests are the release subset
No hidden smaller release oracle is permitted. Every collected test is included, process isolated, timeout bounded, output bounded, and release blocking. A catalog/collection mismatch is a release failure.

## SD-10.1-06 — Source closure is not operational qualification
Passing developer tests can support only `READY_FOR_INDEPENDENT_V10_1_SOURCE_REASSESSMENT`. It cannot establish organization signing, real host containment, production HSM custody, remote-anchor durability, supply-chain provenance, policy approval, roadmap approval, or application/provider safety.
