# AZPR v10.1 Qualification Artifact Binding Matrix

The canonical qualification artifact set is version `2.1` and contains exactly 57 named artifacts. It extends v10 with:

- `host_root_anchor_client`;
- `host_root_anchor_identity`;
- `host_qualification_roots_manifest` and authority key;
- probe attestor keyring and revocation state;
- actual probe-service executable;
- external signer client and identity;
- all previously qualified product, supply-chain, runtime, evidence, authorization, and recovery inputs.

Every member is explicit in code and schema. Qualification input, receipt, installation authorization, installer expected paths, installed-generation records, and test fixtures use the same version. Missing, extra, hash-substituted, aliased, symlinked, writable, oversized, or changed-during-read members fail closed.
