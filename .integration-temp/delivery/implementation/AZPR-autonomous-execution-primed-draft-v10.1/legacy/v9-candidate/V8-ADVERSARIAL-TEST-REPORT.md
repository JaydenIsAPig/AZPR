# AZPR v8 Adversarial Test Report

## Mandatory v7 reproductions

| Case | Expected v8 behavior | Result |
|---|---|---|
| Installer invoked without valid qualification authorization | Reject before recovery or any installation write | PASS |
| Empty/fabricated qualification artifact set | Reject; no receipt created | PASS |
| Detached/background Codex descendant | Complete execution unit killed and proven empty before return | PASS |
| Bidirectional stdin/stdout saturation | No deadlock; one deadline remains active | PASS |
| Output overflow | Full execution unit terminated; no success result | PASS |
| Missing quota controls | Release verifier requires tmpfs/inode/entry/cleanup enforcement markers and schemas | PASS |

## Mutation and substitution coverage

- Unsigned qualification report with updated artifact hash: rejected.
- Wrong artifact hash/path alias/unknown/missing artifact: rejected.
- Stale report/revocation/profile: rejected by freshness checks.
- Wrong bundle, process gate, quota profile, image, SBOM, provenance, mirror, or registry binding: rejected.
- Duplicate signer identity or duplicate Ed25519 material: rejected.
- Key transition replay/current-epoch mismatch: rejected.
- Qualification-only installation carrying canonical derivatives: rejected.
- Production loader presented a qualification-only manifest: rejected.

The black-box harness uses separate processes and does not import its pass/fail result from the unit-test oracle.
