# AZPR v10.1 Known Limitations and Qualification Dependencies

## Open operational gates

The following are not supplied or proven by this source correction and remain mandatory:

- organization signature over the exact frozen v10.1 bytes;
- a dedicated hardened host with qualified kernel, filesystem, namespaces, cgroups, mounts, UID/GID, LSM, quotas, and exact Codex/toolchain versions;
- production external signer/HSM and independently protected remote anchor;
- real key-generation, custody, rotation, revocation, emergency-disablement, recovery, and separation-of-duty ceremonies;
- reproducible dependency mirror, lock, SBOM, provenance, image, registry, and rebuild evidence;
- power-loss, kill-9, reboot, disk-full, inode-full, read-only-remount, concurrent recovery, and anchor-outage testing on the target host;
- approved canonical policy derived from the Master Operating Prompt;
- manual Prompt 004 result and independently reviewed/promoted roadmap;
- actual AZPR repository integration and tests for authorization, customer isolation, source provenance, source-access terms, idempotency, migrations, backup/restore, notifications, consent/suppression, PII, provider behavior, and rollback.

## Source-evidence limitation

All v10.1 closure labels are developer-side source findings. The exact frozen candidate must receive a new independent assessment that reproduces the previous attacks and verifies the corrected call paths. No source claim in this package overrides that review.

## Readiness limitation

`pre_autonomous_staging=FAIL`, `semi_autonomous_codex_staging_ready=false`, `trusted_pre_autonomous_installation_ready=false`, and `safe_for_unattended_execution_now=false` remain mandatory.
