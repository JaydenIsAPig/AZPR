# AZPR v8 Confidence Assessment

| Area | Confidence | Basis |
|---|---:|---|
| Archive/prompt integrity | High | Exact manifests, sidecars, safe ZIP inspection, unchanged 41-file prompt archive. |
| Installer authorization ordering | High at source level | Read-only preflight and first-write reservation are explicit and regression-tested. |
| Semantic qualification rejection | High at source level | Positive strict fixture passes; empty, unsigned, stale, and substituted evidence paths fail. |
| Complete-tree containment | Medium-high at source level | Development black-box descendants are killed; production cgroup/namespace code is present and bound. Exact host execution remains untested. |
| Duplex I/O deadline | High at source level | Saturation, early exit, timeout, and overflow tests pass. |
| Handoff quota/cleanup | Medium | Source controls and mutation tests pass; real tmpfs/inode/full-disk behavior remains unexecuted. |
| Key lifecycle | Medium-low | Sequenced anchored state machine exists; end-to-end installed integration is incomplete. |
| Trusted pre-autonomous readiness | Not established | Independent reassessment and dedicated-host qualification have not occurred. |

No confidence score changes the required false readiness flags.
