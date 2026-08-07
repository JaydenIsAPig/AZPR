# V10 Probe Trust Root and External Signing Report

## Corrected v9 failure

V9 accepted nine fabricated PASS envelopes signed under a caller-created Ed25519 keyring and arbitrary policy. Signature corruption failed, proving the defect was authority selection rather than cryptographic verification.

## V10 trust chain

`bootstrap authority key -> signed host bootstrap roots -> qualification-trust authority key -> signed qualification-trust manifest -> exact keyring/policy/service identity/attestation/revocation artifacts -> envelope signatures and contextual bindings`.

The trust manifest binds host, candidate, challenge, validity interval, and sequence. Probe keys bind service ID, exact role, key ID, validity interval, and revocation state. Every envelope binds all trust-artifact hashes and contextual values.

## External signer

The signing request includes the complete canonical trust binding and its SHA-256. The signer independently loads and validates separately provisioned authority material and refuses omitted, substituted, stale, revoked, wrong-role, wrong-host, wrong-candidate, or wrong-challenge bindings. The client verifies that the returned signed receipt exactly matches the submitted receipt and trust binding.

## Installer

Before the first authorization reservation, the installer re-verifies bootstrap roots, the signed qualification-trust manifest, all pinned artifacts, every probe envelope, the receipt signature, the exact 48-artifact map, and freshness/context constraints.

## Test evidence

Release blockers cover approved authority success; attacker-generated keyring/policy rejection; mutation of every envelope binding field; revoked and wrong-role keys; signer rejection of a substituted policy; and installer ordering before state creation.

## Remaining dependency

The reference signer is test-only. Production HSM deployment, signer identity provisioning, key ceremony, availability, audit logging, and independent operational qualification remain open.
