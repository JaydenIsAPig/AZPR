# V10 Adversarial, Mutation, Substitution, and Test-Catalog Report

## Pre-patch reproductions

1. Caller-generated Ed25519 keyring + arbitrary policy + nine fabricated PASS envelopes: accepted by v9.
2. Mutated envelope signature: rejected by v9, isolating the defect to trust-root selection.
3. Symlinked bootstrap manifest and authority key: both accepted by v9.
4. Official verifier as unprivileged reviewer: failed at hardcoded `/root` temporary directory.

Raw reproduction evidence is preserved under `evidence/source-development/`.

## V10 release blockers

The 18-test catalog executes each node in a separate process. It covers independent probe authority, caller-created roots, field-by-field binding mutation, revoked/wrong-role keys, bootstrap symlink/hard-link/writable-ancestor/wrong-owner/stale-sequence cases, exact 48-artifact membership and alias substitution, independent signer validation, first-install phase separation, installer ordering, contradictory raw evidence, prompt identity, non-root verifier construction, 20-process serialization, rollback/recovery, and atomic key lifecycle.

## Pre-curation result

18/18 catalog nodes passed individually under the unprivileged `oai` account with bytecode disabled and pytest cache disabled. Final source-tree and fresh-extraction executions are recorded separately.

## Mutation expectation

Deleting or bypassing the trust-manifest hash, policy hash, keyring hash, service identity/attestation, revocation, host, candidate, challenge, key role, validity, exact artifact membership, or no-follow path checks causes a release-blocking test failure.
