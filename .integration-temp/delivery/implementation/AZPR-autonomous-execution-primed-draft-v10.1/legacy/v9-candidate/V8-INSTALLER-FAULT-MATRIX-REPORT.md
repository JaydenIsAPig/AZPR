# AZPR v8 Installer Fault-Matrix Report

## Source-instrumented boundaries

The installer exposes deterministic failpoints around:

- authorization verified before first write;
- authorization ledger creation/reservation;
- file writes and file fsync;
- directory fsync;
- atomic JSON replacement;
- generation activation rename;
- active-lock replacement;
- pending/final receipt recovery.

## Source-level expectations

- Fault before authorization reservation: no installer state and no consumed nonce.
- Fault after reservation: authorization remains consumed or failed-consumed; it is never reusable.
- Fault before active-lock replacement: previous active generation remains authoritative and staged artifacts are recoverable/removable.
- Fault after active-lock replacement: recovery must finalize the exact pending receipt or fail closed.
- Persisted recovery paths are confined to AZPR-owned roots.

## Status

Static ordering and source recovery tests pass. The complete root kill/reboot/disk/full-filesystem matrix is **not executed** in this environment and remains a dedicated-host qualification requirement.
