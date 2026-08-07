# AZPR v9 Security Invariants and Architecture

```json
{
  "safe_for_unattended_execution_now": false,
  "trusted_pre_autonomous_installation_ready": false
}
```

## Trust boundaries

1. **Untrusted qualification targets.** Git, Python, Codex, container engine, anchor helper, mount, unmount, adapter, and verifier bytes are never executed by the receipt verifier. Behavior is imported only through signed, bounded no-secret probe envelopes.
2. **No-secret probe service.** The envelope contract requires a non-root UID/GID, disposable boundary, PID/mount isolation, cgroup v2, no host mounts or daemon sockets, denied or controlled network, and affirmative denial observations. The source package does not claim a real service exists.
3. **External receipt signer.** Receipt signing is a separate authenticated client operation. The verifier holds only the receipt public key and verifies the returned signature. The test signer is explicitly TEST ONLY.
4. **Root installer transaction.** One fixed root-owned kernel lock covers preflight, activation recovery, anchored authorization recovery/reservation, staging, activation, receipt generation, anchored completion, and terminal cleanup.
5. **Rollback-resistant state.** Authorization and phase journals use signed hash-chained records, exact monotonic sequence, unique ID/nonce checks, compare-and-publish remote heads, pending intents, fsync/rename writes, and deterministic reconciliation.
6. **Complete binding.** The signed qualification receipt and installation authorization bind one canonical 39-artifact aggregate. The probe envelope manifest separately binds the nine executable target identities. The authorization additionally consumes exact mount, unmount, verifier, adapter-set, lifecycle-state, installer, schema, and bootstrap-root identities before reservation.
7. **Two-stage installation.** Absence of a prior active generation constrains installation to `QUALIFICATION_ONLY`. `POLICY_ACTIVATED` requires a separate dual-role one-use phase transition bound to a prior immutable qualification-only generation/receipt, same host, successful launcher/fault evidence, and independently approved canonical-policy record.
8. **Machine-derived reports.** Signatures authorize provenance, not correctness. Six report classes are recomputed from strict raw evidence and decisive false checks fail closed.
9. **Atomic trust epoch.** Ten trust stores are staged into one immutable epoch and activated by one anchored pointer after a dual-role transition. Recovery either rolls back an unanchored epoch or activates an anchored epoch; pointer rollback fails closed.
10. **No readiness promotion.** No code path in this development delivery changes either readiness flag to true, activates a policy, creates a roadmap, or authorizes autonomous/external execution.

## Transaction ordering

The actual installer order is: acquire global lock → complete read-only v9 preflight → recover activation and anchored journals → reserve main and optional phase authorization → prepare immutable generation → activate → create installation receipt bound to reservation/anchor heads → complete anchored journals → release lock. A legacy v8 static-audit comment is retained solely so the inherited string-scanning black-box case remains observable; the v9 test locates the real executable call after recovery.

## Persistence semantics

`atomic_write` creates a same-directory temporary file, sets mode, writes, fsyncs the file, renames atomically, and fsyncs the parent directory. A pending transaction is durable before anchor publication. The signed record hash—not the transport receipt—is the anchored head. Anchor receipts are stored separately. Recovery recognizes only three unambiguous states: previous/previous (rollback pending), previous/new (materialize anchored record/head), and new/new (remove stale pending marker). Every other combination fails closed.
