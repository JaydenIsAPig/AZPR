# AZPR v10.1 Security Invariants and Architecture

## Readiness invariant
The highest permitted source disposition is `READY_FOR_INDEPENDENT_V10_1_SOURCE_REASSESSMENT`. Trusted installation, staging, policy activation, roadmap promotion, prompt execution, and external operations remain prohibited.

## Authority chain
1. A separately provisioned host authority signs the fixed host-root manifest.
2. A fixed anchor client, bound by a signed anchor identity, obtains a signed monotonic head for the exact host-root manifest hash and sequence.
3. The host-root manifest pins the qualification trust authority, probe policy, probe/attestor keyrings and revocations, service executable/identity/attestation, external signer client/identity, and receipt verification key.
4. The qualification trust authority signs the candidate/host/challenge-specific trust manifest.
5. The independent attestor signs the service/executable/launcher/runtime identity.
6. Probe envelopes are accepted only under approved probe keys and exact signed policy semantics.
7. The external signer independently reloads the same fixed roots and signs only an exactly matching receipt.
8. The installer repeats bootstrap, host-root, anchor, authority, envelope, receipt, and exact 57-artifact verification before authorization reservation.

## First state-changing boundary
No authorization reservation or installed state may be created until all trust, anchor, policy, attestation, envelope, receipt, artifact membership, alias, path, chronology, and freshness checks succeed.

## TOCTOU and path invariants
Security-critical local files use descriptor-based no-follow reads, trusted ancestors, owner/mode/link checks, bounded reads, and before/after inode metadata comparison. Unsupported semantics fail closed.

## Rollback and recovery
Signed sequence floors, revocation ordering, remote-head verification, installer serialization, authorization replay checks, transaction journals, and anchored generation state compose. Production durability and outage behavior require real-host qualification.
