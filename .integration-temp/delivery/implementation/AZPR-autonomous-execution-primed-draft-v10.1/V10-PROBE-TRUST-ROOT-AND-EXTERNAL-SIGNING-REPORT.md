# AZPR v10.1 Probe Trust Root and External Signing Report

The v10 caller-controlled higher-level authority was removed. Qualification input cannot select trust paths, owner IDs, sequence floors, signer clients, signer identities, receipt keys, or key IDs. The fixed host loader verifies a signed manifest and an independent signed anchor head before exposing any authority.

The authority binds probe and attestor keyrings, both revocation states, exact policy, service identity, independently signed attestation, actual executable bytes, launcher/runtime identities, external signer identity, and receipt key. The external signer reloads this same authority independently and rejects altered bindings.

Developer regressions reject complete caller-created authority chains, policy mismatch, stale policy evidence, forged attestation, wrong executable, wrong role, revoked key, binding mutations, signer substitution, future issuance, and rolled-back anchor sequence. Production signer, attestor, and anchor services remain unqualified.
