# AZPR v9 Known Limitations and Qualification Dependencies

```json
{
  "safe_for_unattended_execution_now": false,
  "trusted_pre_autonomous_installation_ready": false
}
```

## Blocking limitations

- No organization release signature or organization-held release key is provided.
- No dedicated host has been installed, measured, hardened, or independently attested.
- No disposable VM/rootless probe service has executed the malicious target matrix on the selected kernel/container stack.
- No production external receipt signer/HSM or independent signing policy exists in this delivery.
- No qualified rollback-resistant remote anchor exists; the file anchor is TEST ONLY.
- No real power-loss, disk-full, inode-full, read-only-remount, reboot, filesystem, or concurrent recovery matrix has been completed.
- No real supply-chain mirror/rebuild, registry, SBOM/provenance, or image attestation is supplied for v9.
- No real runtime/evidence/installation/qualification key custody or rotation ceremony has occurred.
- Atomic trust epochs are not yet integrated and exercised across all production consumers on a real host.
- No canonical policy is approved or active; Prompt 004 has not executed; no roadmap is generated or promoted.
- No trusted controller stage, autonomous stage, provider operation, production credential, customer data, or application qualification was used.

## Required next event

Freeze the exact v9 ZIPs and sidecars, then conduct an independent source-level consultation. It must reproduce every v8 blocker, inspect the complete installer call path, mutate every binding, interrupt each transaction phase, test anchor rollback/fork behavior, assess test-oracle independence, and decide whether the candidate may proceed to dedicated-host qualification or requires v10.
