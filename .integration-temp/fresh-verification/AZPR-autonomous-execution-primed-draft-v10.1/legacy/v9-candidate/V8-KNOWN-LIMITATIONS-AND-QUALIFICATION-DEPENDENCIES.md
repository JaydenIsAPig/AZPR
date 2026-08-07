# V8 Known Limitations and Qualification Dependencies

V8 may proceed only to independent source reassessment. A source PASS does not make these facts true:

1. The host actually provides and correctly delegates cgroup v2.
2. PID/mount/network namespace creation succeeds with the pinned kernel/LSM policy.
3. The exact Codex process cannot access host secrets.
4. The quota mount preserves controller/journal capacity under adversarial exhaustion.
5. The remote anchor is independently protected and rollback resistant.
6. Key custody is hardware-backed or narrowly brokered.
7. Supply-chain artifacts were independently reproduced.
8. Installer crash/reboot recovery works on the selected filesystem.
9. Provider adapters behave safely against isolated real targets.
10. The extracted canonical policy was visually reviewed and independently approved.
11. Prompt 004 and the exact roadmap were completed and independently promoted.
12. The application repository satisfies AZPR business/security invariants.

Each dependency must produce immutable, signed, fresh evidence that the v8 semantic verifier consumes and the one-use installation authorization binds.
