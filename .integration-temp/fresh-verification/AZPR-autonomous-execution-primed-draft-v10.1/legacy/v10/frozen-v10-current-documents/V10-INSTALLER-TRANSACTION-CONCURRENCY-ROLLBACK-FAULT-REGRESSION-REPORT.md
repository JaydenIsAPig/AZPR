# V10 Installer Transaction, Concurrency, Rollback, and Fault Regression Report

## Preserved controls

V10 retains the v9 global installer lock, anchored authorization transaction store, pending-state recovery, one-use authorization ID and nonce enforcement, compare-and-publish anchor behavior, qualification-only first install, and separate policy phase transition.

The authorization ledger is versioned to `qualification-authorizations-v10`. New probe-trust and 48-artifact verification occurs while the global lock is held and before `_reserve_authorization`.

## Executed source regressions

- `test_f02_f04_twenty_process_same_sequence_exactly_one_advances`: PASS; 20 processes contend and exactly one advances.
- `test_f04_rollback_delete_restore_and_pending_recovery_fail_closed`: PASS.
- `test_f05_first_install_forced_qualification_only_and_exact_transition`: PASS.
- `test_v10_first_install_still_forced_qualification_only`: PASS.
- `test_v10_installer_enforces_trust_before_authorization_reservation`: PASS.

## Not claimed

No privileged real-host install, power cut, reboot, disk/inode exhaustion, read-only remount, anchor outage, or actual activation was performed. Those remain dedicated-host qualification gates.
