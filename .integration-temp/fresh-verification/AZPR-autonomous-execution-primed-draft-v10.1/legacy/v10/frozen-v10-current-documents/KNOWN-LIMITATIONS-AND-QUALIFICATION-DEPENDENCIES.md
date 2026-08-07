# AZPR v10 Known Limitations and Qualification Dependencies

## Open real-world gates

The following are **not closed** by this source candidate:

1. Organization release signing against a separately provisioned release root.
2. Dedicated hardened-host qualification of the exact kernel, filesystem, container engine, Codex/toolchain, cgroups, namespaces, mounts, LSM, UID/GID, quotas, cleanup, and output controls.
3. Production external signer/HSM deployment, key custody, rotation, revocation, and ceremony evidence.
4. Rollback-resistant remote anchor deployment and outage/recovery qualification.
5. Real power-loss, kill-9, reboot, disk-full, inode-full, read-only-remount, concurrent-recovery, and anchor-outage fault matrix.
6. Reproducible supply-chain mirror, lock, SBOM, provenance, image attestation, registry proof, and independent rebuild.
7. Approved canonical policy derived from the Master Operating Prompt.
8. Manual Prompt 004 result and independent roadmap generation/review/promotion.
9. Real AZPR application, provider, credentials, customer isolation, source terms, consent/suppression, PII, migrations, backup/restore, idempotency, and rollback qualification.

## Source-level limitations

- The bundled external signer is a reference test implementation, not a production HSM service.
- Production bootstrap ownership assumes UID 0 and trusted `/etc` ancestry; tests use an explicit single-owner test trust root.
- Monotonic trust-manifest and revocation-state sequence checks require integration with a qualified remote anchor to become rollback-resistant across host compromise.
- Carried v9 transaction, evidence-derivation, and key-lifecycle modules remain version-labeled v9 where their source was preserved; v10 re-tests their invariants rather than falsely renaming unchanged code.

## Mandatory disposition

The candidate remains unsigned and is not authorized for pre-autonomous staging, semi-autonomous Codex staging, trusted installation, or unattended execution.
