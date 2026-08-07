# AZPR v8 Installer Recovery and Authorization Fault Matrix

## Non-negotiable ordering

`_qualification_preflight()` is read-only. It verifies the exact candidate, semantic qualification receipt, authorization keyring/revocation state, dual-role signatures, host/tool/profile/report bindings, policy status, expiry, sequence and nonce. No recovery, directory creation, private-key access, nonce ledger creation, or trusted state operation is permitted first.

The authorization reservation is the first allowed write. Once reserved, a valid authorization cannot be replayed even if a later installation step fails.

## Instrumented checkpoints

The installer exposes deterministic test-only checkpoints for:

1. authorization verified before first write;
2. authorization ledger creation;
3. before and after authorization record write/fsync;
4. authorization reservation complete;
5. every trusted file write and file fsync;
6. every directory fsync;
7. each atomic JSON replacement;
8. staged generation validation;
9. generation activation rename;
10. active-lock replacement;
11. pending and final receipt creation/recovery;
12. staged-generation cleanup and confined recovery.

Fault injection is accepted only with explicit test mode. Production input cannot enable it.

## Required dedicated-host matrix

For each checkpoint, execute exception and `SIGKILL` injection plus reboot, disk-full, inode-full, read-only filesystem, partial write, stale receipt, anchor outage, and restoration of an older local snapshot.

Expected outcomes:

- Before reservation: no state and authorization remains unused.
- After reservation: authorization is durably consumed/failed-consumed and never reusable.
- Before activation: prior complete generation remains authoritative.
- After activation switch: recovery finalizes the exact signed receipt or fails closed; it never silently rolls to an unrecorded generation.
- Every path read from recovery state is constrained beneath its exact AZPR-owned root before rename or deletion.

## Current result

Source ordering, path confinement, replay handling, and source-level fault tests pass. The root kill/reboot/filesystem matrix has not been executed and remains a mandatory signed qualification report.
