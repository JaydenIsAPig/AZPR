# AZPR v10.1 Affected Files, Functions, Schemas, and Modification Boundaries

## Security-critical implementation changes

- `operator-tools/v10_1_host_trust.py`: fixed host roots, independent anchor verification, chronology and signer identity.
- `operator-tools/v10_probe_boundary.py`: exact policy semantics, attestor and executable verification, trust binding.
- `operator-tools/v10_external_signer_client.py`: fixed signer client/key and independent authority revalidation.
- `operator-tools/verify_v10_cleanroom_prerequisites.py`: caller trust removal and exact 57-artifact qualification.
- `trusted-installation/v10_binding.py`: exact set and higher bootstrap roots.
- `trusted-installation/install.py`: fixed root paths and enforcing order.
- `VERIFY-V10-CANDIDATE.py`: complete catalog, isolation, bounds, and non-root verification.
- `tests/test_v10_security_closures.py` and `tests/v10_1_test_support.py`: independent attack regressions.
- security schemas under `repository-overlay/automation/schemas/` for trust, policy, attestation, signer, receipt, host anchor, and artifact set.

No numbered prompt or appendix content was modified. No active policy or roadmap was created.
