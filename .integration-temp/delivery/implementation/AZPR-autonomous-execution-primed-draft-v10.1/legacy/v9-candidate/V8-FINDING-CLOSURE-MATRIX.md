# AZPR v8 Finding Closure Matrix for v9

```json
{
  "safe_for_unattended_execution_now": false,
  "trusted_pre_autonomous_installation_ready": false
}
```

## Assessment basis

The five independently reproducible v8 blockers were reproduced against the unchanged v8 archive before patching. The root-probe reproduction created a valid signed receipt after a malicious Codex probe ran as UID 0 and copied the receipt private key. A synchronized race accepted two sequence-1 reservations. Deleting the local ledger allowed exact authorization replay. Static/call-path analysis found only one of 39 receipt artifacts directly consumed and no prior qualification generation required for first-install activation.

| Finding | v9 status | Enforcing paths | Release-blocking evidence | Remaining limitation |
|---|---|---|---|---|
| AZPR-V8-F01 | `CLOSED_AND_TESTED` at source level | `operator-tools/verify_v9_cleanroom_prerequisites.py`; `v9_probe_boundary.py`; `v9_external_signer_client.py` | Nine malicious target roles are never executed; root/secret boundary claims reject; external signer protocol verifies returned signature and the verifier accepts no receipt private key | Real disposable VM/cgroup/namespace probe service and real external signer/HSM are not present |
| AZPR-V8-F02 | `CLOSED_AND_TESTED` at source level | `trusted-installation/install.py`; `v9_transaction.py` | Global kernel lock is acquired before preflight/recovery; 20 concurrent sequence-1 contenders produce exactly one advance; interrupted anchored transactions recover deterministically | Real power-loss, filesystem exhaustion, reboot, and qualified-host fault matrix remain required |
| AZPR-V8-F03 | `CLOSED_AND_TESTED` at source level | `v9_binding.py`; installer preflight; v9 receipt/input/authorization schemas | Exact 39-map substitution loop rejects every single replacement; aliases/symlinks/path substitutions reject; probe manifest separately binds mount/umount/adapter/verifier; pinned host bootstrap roots reject caller replacement | Independent mutation of the exact packaged installer call path remains required |
| AZPR-V8-F04 | `CLOSED_AND_TESTED` at source level | signed/hash-chained transaction records plus compare-and-publish anchor | stale restore after anchored completion rejects; pre-anchor pending rolls back; post-anchor pending completes; exact sequence/ID/nonce replays reject | File anchor is TEST ONLY; a qualified rollback-resistant remote service is absent |
| AZPR-V8-F05 | `CLOSED_AND_TESTED` at source level | `verify_phase_transition`; phase-transition schema and separate anchored phase journal | first install permits only `QUALIFICATION_ONLY`; wrong host, generation, receipt, launcher/fault evidence, policy record, or transition identity rejects | No real host has completed the two-stage exercise |
| AZPR-V8-F06 | `CLOSED_AND_TESTED` at source level | `v9_evidence_derivation.py`; verifier raw-evidence path | contradictory decisive raw evidence rejects even when the signed report says PASS | Real raw evidence/transcripts are absent |
| AZPR-V8-F07 | `PARTIALLY_CLOSED` | `apply_key_lifecycle_transition_v9.py`; trust epoch schema | ten-store immutable epoch staging, dual-role authorization, before/after-anchor recovery, rollback detection | Production consumers are not yet deployed against a real active-epoch resolver; independent host integration required |
| AZPR-V8-F08 | `NOT_CLOSED` as an infrastructure dependency | contracts and blocked status only | false readiness flags, no organization signature, no fabricated evidence | Dedicated host, supply-chain rebuild, release signature, hardware custody, remote anchor, provider and application qualification remain absent |

Every status remains subject to independent reassessment of the frozen v9 hashes.
