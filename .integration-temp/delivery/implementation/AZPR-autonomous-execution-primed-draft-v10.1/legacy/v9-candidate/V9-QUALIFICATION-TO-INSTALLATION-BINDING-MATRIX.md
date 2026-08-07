# AZPR v9 Qualification-to-Installation Binding Matrix

```json
{
  "safe_for_unattended_execution_now": false,
  "trusted_pre_autonomous_installation_ready": false
}
```

## Canonical 39-artifact map

| # | Artifact role | Enforcement | Mutation oracle |
|---:|---|---|---|
| 1 | `agent_execution_profile` | receipt map + qualified-input exact path/hash + authorization aggregate | one-at-a-time substitution rejects |
| 2 | `anchor_helper` | receipt map + qualified-input exact path/hash + authorization aggregate | one-at-a-time substitution rejects |
| 3 | `approval_keyring` | receipt map + qualified-input exact path/hash + authorization aggregate | one-at-a-time substitution rejects |
| 4 | `build_provenance` | receipt map + qualified-input exact path/hash + authorization aggregate | one-at-a-time substitution rejects |
| 5 | `bundle_attestation` | receipt map + qualified-input exact path/hash + authorization aggregate | one-at-a-time substitution rejects |
| 6 | `bundle_signing_public_key` | receipt map + qualified-input exact path/hash + authorization aggregate | one-at-a-time substitution rejects |
| 7 | `bundle_zip` | receipt map + qualified-input exact path/hash + authorization aggregate | one-at-a-time substitution rejects |
| 8 | `codex_binary` | receipt map + qualified-input exact path/hash + authorization aggregate | one-at-a-time substitution rejects |
| 9 | `codex_isolation_qualification_report` | receipt map + qualified-input exact path/hash + authorization aggregate | one-at-a-time substitution rejects |
| 10 | `container_engine` | receipt map + qualified-input exact path/hash + authorization aggregate | one-at-a-time substitution rejects |
| 11 | `dedicated_host_policy` | receipt map + qualified-input exact path/hash + authorization aggregate | one-at-a-time substitution rejects |
| 12 | `dependency_lock` | receipt map + qualified-input exact path/hash + authorization aggregate | one-at-a-time substitution rejects |
| 13 | `dependency_mirror_attestation` | receipt map + qualified-input exact path/hash + authorization aggregate | one-at-a-time substitution rejects |
| 14 | `dependency_mirror_inventory` | receipt map + qualified-input exact path/hash + authorization aggregate | one-at-a-time substitution rejects |
| 15 | `dependency_mirror_public_key` | receipt map + qualified-input exact path/hash + authorization aggregate | one-at-a-time substitution rejects |
| 16 | `evidence_keyring` | receipt map + qualified-input exact path/hash + authorization aggregate | one-at-a-time substitution rejects |
| 17 | `evidence_private_key` | receipt map + qualified-input exact path/hash + authorization aggregate | one-at-a-time substitution rejects |
| 18 | `evidence_public_key` | receipt map + qualified-input exact path/hash + authorization aggregate | one-at-a-time substitution rejects |
| 19 | `git_binary` | receipt map + qualified-input exact path/hash + authorization aggregate | one-at-a-time substitution rejects |
| 20 | `governing_policy_source` | receipt map + qualified-input exact path/hash + authorization aggregate | one-at-a-time substitution rejects |
| 21 | `handoff_quota_profile` | receipt map + qualified-input exact path/hash + authorization aggregate | one-at-a-time substitution rejects |
| 22 | `installation_signing_private_key` | receipt map + qualified-input exact path/hash + authorization aggregate | one-at-a-time substitution rejects |
| 23 | `installation_signing_public_key` | receipt map + qualified-input exact path/hash + authorization aggregate | one-at-a-time substitution rejects |
| 24 | `installer_fault_matrix_report` | receipt map + qualified-input exact path/hash + authorization aggregate | one-at-a-time substitution rejects |
| 25 | `key_custody_qualification_report` | receipt map + qualified-input exact path/hash + authorization aggregate | one-at-a-time substitution rejects |
| 26 | `python_binary` | receipt map + qualified-input exact path/hash + authorization aggregate | one-at-a-time substitution rejects |
| 27 | `qualification_authorization_keyring` | receipt map + qualified-input exact path/hash + authorization aggregate | one-at-a-time substitution rejects |
| 28 | `key_lifecycle_state` | receipt map + qualified-input exact path/hash + authorization aggregate | one-at-a-time substitution rejects |
| 29 | `qualification_receipt_signing_public_key` | receipt map + qualified-input exact path/hash + authorization aggregate | one-at-a-time substitution rejects |
| 30 | `qualification_revocation_list` | receipt map + qualified-input exact path/hash + authorization aggregate | one-at-a-time substitution rejects |
| 31 | `remote_anchor_qualification_report` | receipt map + qualified-input exact path/hash + authorization aggregate | one-at-a-time substitution rejects |
| 32 | `requirements_input` | receipt map + qualified-input exact path/hash + authorization aggregate | one-at-a-time substitution rejects |
| 33 | `runtime_private_key` | receipt map + qualified-input exact path/hash + authorization aggregate | one-at-a-time substitution rejects |
| 34 | `runtime_public_key` | receipt map + qualified-input exact path/hash + authorization aggregate | one-at-a-time substitution rejects |
| 35 | `sbom` | receipt map + qualified-input exact path/hash + authorization aggregate | one-at-a-time substitution rejects |
| 36 | `supply_chain_rebuild_report` | receipt map + qualified-input exact path/hash + authorization aggregate | one-at-a-time substitution rejects |
| 37 | `validation_dockerfile` | receipt map + qualified-input exact path/hash + authorization aggregate | one-at-a-time substitution rejects |
| 38 | `validation_image_attestation` | receipt map + qualified-input exact path/hash + authorization aggregate | one-at-a-time substitution rejects |
| 39 | `validation_registry_proof` | receipt map + qualified-input exact path/hash + authorization aggregate | one-at-a-time substitution rejects |

## Separately consumed identities

The signed receipt separately binds `qualification_probe_envelopes_manifest`. The installer verifies every envelope file hash and exact target identity for Git, Python, Codex, container engine, anchor helper, mount, unmount, clean-room adapter, and qualification verifier. The installation authorization consumes mount/unmount hashes, verifier hash, adapter-set aggregate, probe-manifest hash, installer hash, installation-manifest schema hash, and key-lifecycle-state hash.

## Bootstrap roots

Fixed host paths `/etc/azpr/bootstrap/host-bootstrap-roots-v9.json` and `/etc/azpr/bootstrap/host-bootstrap-authority.pem` authenticate the qualification authorization keyring, receipt verification key, phase-transition keyring, and anchor-helper identity. Caller-selected replacements fail before reservation.

Paths must be regular, single-link, non-writable, non-symlinked through every ancestor, stable across the read, and root-owned when the installer runs as root. Aliased inodes are forbidden.
