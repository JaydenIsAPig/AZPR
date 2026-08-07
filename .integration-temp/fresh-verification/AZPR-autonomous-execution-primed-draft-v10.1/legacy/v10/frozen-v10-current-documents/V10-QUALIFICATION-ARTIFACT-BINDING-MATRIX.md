# V10 Qualification Artifact Binding Matrix

Artifact set: `AZPR_V10_QUALIFICATION_ARTIFACT_SET`  
Version: `2.0`  
Exact member count: **48**

Each member is named explicitly in the input manifest and receipt. Each path is opened without following symlinks, hashed, checked for a single inode identity, compared to the receipt, and included in the canonical aggregate. Aliased inodes, missing/extra names, substitutions, and changed files fail before authorization reservation.

| # | Artifact name | Security purpose | Enforcing consumers |
|---:|---|---|---|
| 1 | `agent_execution_profile` | Runtime/containment component identity | verifier + receipt + signer + installer |
| 2 | `anchor_helper` | Runtime/containment component identity | verifier + receipt + signer + installer |
| 3 | `approval_keyring` | Key identity/custody binding | verifier + receipt + signer + installer |
| 4 | `build_provenance` | Qualification/supply-chain evidence | verifier + receipt + signer + installer |
| 5 | `bundle_attestation` | Qualification/supply-chain evidence | verifier + receipt + signer + installer |
| 6 | `bundle_signing_public_key` | Key identity/custody binding | verifier + receipt + signer + installer |
| 7 | `bundle_zip` | Candidate/policy/dependency identity | verifier + receipt + signer + installer |
| 8 | `codex_binary` | Runtime/containment component identity | verifier + receipt + signer + installer |
| 9 | `codex_isolation_qualification_report` | Qualification/supply-chain evidence | verifier + receipt + signer + installer |
| 10 | `container_engine` | Runtime/containment component identity | verifier + receipt + signer + installer |
| 11 | `dedicated_host_policy` | Runtime/containment component identity | verifier + receipt + signer + installer |
| 12 | `dependency_lock` | Candidate/policy/dependency identity | verifier + receipt + signer + installer |
| 13 | `dependency_mirror_attestation` | Qualification/supply-chain evidence | verifier + receipt + signer + installer |
| 14 | `dependency_mirror_inventory` | Runtime/containment component identity | verifier + receipt + signer + installer |
| 15 | `dependency_mirror_public_key` | Key identity/custody binding | verifier + receipt + signer + installer |
| 16 | `evidence_keyring` | Key identity/custody binding | verifier + receipt + signer + installer |
| 17 | `evidence_private_key` | Key identity/custody binding | verifier + receipt + signer + installer |
| 18 | `evidence_public_key` | Key identity/custody binding | verifier + receipt + signer + installer |
| 19 | `git_binary` | Runtime/containment component identity | verifier + receipt + signer + installer |
| 20 | `governing_policy_source` | Candidate/policy/dependency identity | verifier + receipt + signer + installer |
| 21 | `handoff_quota_profile` | Runtime/containment component identity | verifier + receipt + signer + installer |
| 22 | `installation_signing_private_key` | Key identity/custody binding | verifier + receipt + signer + installer |
| 23 | `installation_signing_public_key` | Key identity/custody binding | verifier + receipt + signer + installer |
| 24 | `installer_fault_matrix_report` | Qualification/supply-chain evidence | verifier + receipt + signer + installer |
| 25 | `key_custody_qualification_report` | Key identity/custody binding | verifier + receipt + signer + installer |
| 26 | `key_lifecycle_state` | Key identity/custody binding | verifier + receipt + signer + installer |
| 27 | `phase_transition_keyring` | Key identity/custody binding | verifier + receipt + signer + installer |
| 28 | `probe_keyring` | Probe authority/policy binding | verifier + receipt + signer + installer |
| 29 | `probe_policy` | Probe authority/policy binding | verifier + receipt + signer + installer |
| 30 | `probe_revocation_state` | Probe authority/policy binding | verifier + receipt + signer + installer |
| 31 | `probe_service_attestation` | Probe authority/policy binding | verifier + receipt + signer + installer |
| 32 | `probe_service_identity` | Probe authority/policy binding | verifier + receipt + signer + installer |
| 33 | `python_binary` | Runtime/containment component identity | verifier + receipt + signer + installer |
| 34 | `qualification_authorization_keyring` | Key identity/custody binding | verifier + receipt + signer + installer |
| 35 | `qualification_probe_envelopes_manifest` | Runtime/containment component identity | verifier + receipt + signer + installer |
| 36 | `qualification_receipt_signing_public_key` | Key identity/custody binding | verifier + receipt + signer + installer |
| 37 | `qualification_revocation_list` | Runtime/containment component identity | verifier + receipt + signer + installer |
| 38 | `qualification_trust_authority_public_key` | Probe authority/policy binding | verifier + receipt + signer + installer |
| 39 | `qualification_trust_manifest` | Probe authority/policy binding | verifier + receipt + signer + installer |
| 40 | `remote_anchor_qualification_report` | Qualification/supply-chain evidence | verifier + receipt + signer + installer |
| 41 | `requirements_input` | Candidate/policy/dependency identity | verifier + receipt + signer + installer |
| 42 | `runtime_private_key` | Key identity/custody binding | verifier + receipt + signer + installer |
| 43 | `runtime_public_key` | Key identity/custody binding | verifier + receipt + signer + installer |
| 44 | `sbom` | Qualification/supply-chain evidence | verifier + receipt + signer + installer |
| 45 | `supply_chain_rebuild_report` | Qualification/supply-chain evidence | verifier + receipt + signer + installer |
| 46 | `validation_dockerfile` | Runtime/containment component identity | verifier + receipt + signer + installer |
| 47 | `validation_image_attestation` | Qualification/supply-chain evidence | verifier + receipt + signer + installer |
| 48 | `validation_registry_proof` | Qualification/supply-chain evidence | verifier + receipt + signer + installer |
