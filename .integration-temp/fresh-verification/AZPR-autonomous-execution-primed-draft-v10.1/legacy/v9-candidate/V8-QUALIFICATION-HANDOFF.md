# AZPR v8 Dedicated-Host Qualification Handoff

## Entry condition

Use only an exact v8 artifact that has passed independent source reassessment with no open Critical/High implementation finding. Verify its organization release signature when an authority exists; otherwise do not install it as trusted.

## Required order

1. Build real offline mirror/wheelhouse, SBOM, provenance, image, and registry proof.
2. Prepare a disposable dedicated host and immutable host identity.
3. Qualify cgroup v2, PID/mount/network namespaces, mounts, quotas, capabilities, groups, ACLs, LSM, and controller storage reservation.
4. Qualify exact Codex, Git, Python, container engine, anchor helper, and adapters.
5. Exercise key custody, rotation, revocation, compromise recovery, and remote anchor.
6. Execute every installer fault point and recovery state.
7. Produce six independently signed qualification reports with immutable raw evidence.
8. Run `verify_v8_cleanroom_prerequisites.py`; preserve its still-blocked receipt.
9. Obtain a separate dual-signed one-use installation authorization.
10. Install a `QUALIFICATION_ONLY` generation. Confirm controller/external launchers fail closed.
11. Independently review and approve the exact canonical policy.
12. Obtain a new authorization that activates the exact policy record.
13. Execute Prompt 004 manually, then generate and independently review the roadmap once.

No step authorizes production/customer data or external side effects.
