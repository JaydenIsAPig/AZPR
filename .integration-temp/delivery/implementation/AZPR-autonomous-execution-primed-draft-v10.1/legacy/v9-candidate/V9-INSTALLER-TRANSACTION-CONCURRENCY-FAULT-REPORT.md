# AZPR v9 Installer Transaction, Concurrency, and Fault Report

```json
{
  "safe_for_unattended_execution_now": false,
  "trusted_pre_autonomous_installation_ready": false
}
```

## Global transaction

`InstallerGlobalLock` uses an exclusive kernel `flock` on the fixed installer lock. The installer acquires it before preflight and holds it until anchored completion or a persisted recoverable failure path. Kernel lock ownership disappears on process death; the stable inode is not itself authorization state.

## Concurrency observation

Command: `pytest -q tests/test_v9_security_closures.py::test_f02_f04_twenty_process_same_sequence_exactly_one_advances`

Observed: 20 independent processes requested authorization sequence 1 with distinct IDs/nonces under the global lock. Exactly one printed `SUCCESS`; the signed/anchored head reported authorization sequence 1; journal recovery returned without ambiguity.

## Recovery observations

- Stale local restore after reservation completion: rejected as local/remote rollback mismatch.
- Failure before anchor publication with durable pending intent: recovery removed the unanchored pending transaction.
- Failure after anchor publication but before local record: recovery materialized the exact signed record and head.
- Existing signed record and anchored head with stale pending marker: recovery removes only the marker.
- Missing/truncated/forked records or any non-enumerated local/remote pair: fail closed.

## Fault qualification not claimed

The source tests exercise transaction-level interruption boundaries and exact recovery states. They do not constitute a real SIGKILL-at-every-syscall, disk-full, inode-full, read-only remount, power-loss, reboot, NFS, or filesystem-specific atomicity qualification. Those scenarios remain mandatory on the selected dedicated host and qualified anchor before installation eligibility.
