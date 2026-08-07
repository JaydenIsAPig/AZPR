# AZPR v8 Trust Boundary

## Trusted only after independent qualification

- frozen organization-authenticated v8 release;
- privileged installer and signed installation manifest;
- independent qualification and installation-authorization signers;
- root/controller state, keys, journals, approvals and evidence;
- pinned Git, Python, Codex, container, mount helpers and adapters;
- remote rollback-resistant anchor;
- validation image and supply-chain identity.

## Untrusted by default

- Codex and every descendant;
- repository content and Git metadata until topology checks pass;
- prompt/tool output;
- provider/source payloads;
- all qualification files until schema, signature, provenance, freshness, revocation and cross-binding verification succeeds.

## Execution invariant

The target cannot execute before cgroup attachment and namespace setup. On every completion path the full execution unit is terminated and proven empty, the writable mount is revoked/sealed, and only then may results or repository state be inspected. Agent-owned data never becomes trusted merely because the main PID exits successfully.
