# AZPR v8 External Capability Runner Operations

External capabilities remain disabled. Production configuration may select only components recorded in the signed installation manifest; arbitrary keyring, adapter, schema or runtime paths are forbidden.

Each future adapter requires a signed adapter installation manifest, exact hash/version, allowed operation set, target attestation, bounded request/response schemas, idempotency key, dry-run/live separation, explicit rollback status and isolated target qualification. The complete process tree and writable surface are subject to the same cgroup, namespace, I/O deadline and quota controls as Codex.

No adapter apply operation is authorized by this bundle.
