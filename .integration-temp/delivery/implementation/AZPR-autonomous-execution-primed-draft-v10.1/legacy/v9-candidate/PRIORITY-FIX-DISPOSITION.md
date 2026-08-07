# AZPR v8 Priority-Fix Disposition

## Governing disposition

- `safe_for_unattended_execution_now`: **false**
- `trusted_pre_autonomous_installation_ready`: **false**
- Root installation in this development environment: **not performed**
- Canonical-policy approval, Prompt 004, roadmap generation, autonomous stages, and external operations: **blocked**

## P0/P1 disposition

| Priority | Finding | Source-candidate disposition | Remaining qualification dependency |
|---|---|---|---|
| P0.1 | AZPR-V7-F01 installer bypassed qualification | `CLOSED_AND_TESTED` | Independent authorization signers and real host-bound evidence must be produced. |
| P0.2 | AZPR-V7-F02 fabricated evidence could receive a signed receipt | `CLOSED_AND_TESTED` | Real immutable evidence and independent signers remain unavailable here. |
| P0.3 | AZPR-V7-F03 descendants survived controller completion | `CLOSED_AND_TESTED` | Exact cgroup v2, namespaces, LSM, mounts, and Codex binary require dedicated-host qualification. |
| P1.1 | AZPR-V7-F04 bidirectional pipe deadlock | `CLOSED_AND_TESTED` | Exact installed Codex/adapter workloads require host testing. |
| P1.2 | AZPR-V7-F05 handoff lacked quotas | `CLOSED_AND_TESTED` | Actual tmpfs quota enforcement, disk/inode exhaustion, and cleanup interruption require root host tests. |
| P1.3 | Required black-box/mutation coverage | `CLOSED_AND_TESTED` | A genuinely independent reviewer must rerun and extend it. |

## P2 disposition

- `AZPR-V7-F06`: `PARTIALLY_CLOSED`. V8 adds an anchored, sequenced, dual-authorized, one-use transition state machine with replay/epoch checks and historical-key retention. It is not yet atomically integrated with real installed key stores or a real remote anchor.
- `AZPR-V7-F07`: `CLOSED_AND_TESTED` for the development delivery envelope. All referenced verification artifacts are included and the governing DOCX results are no longer described as unavailable. Organization release signing remains intentionally absent and is explicitly marked.

## Additional v8 corrections

- `AZPR-V8-D01`: `CLOSED_AND_TESTED`. Qualification-only installation and later policy activation are separate states; production loaders reject the former.
- `AZPR-V8-D02`: `CLOSED_AND_TESTED` at source level. The trusted gate now creates PID, mount, and network namespaces instead of merely recording a profile claim.
