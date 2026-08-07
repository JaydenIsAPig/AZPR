# V10 Finding Closure Matrix

All source closure labels remain subject to independent v10 reassessment. “Closed source level” never means operational qualification.

| Finding | V10 status | Source evidence | Remaining dependency |
|---|---|---|---|
| AZPR-V9-IND-F01 caller-selected probe root/policy | CLOSED_SOURCE_LEVEL | Signed pinned trust manifest; signer and installer independent verification; attacker-root and mutation tests pass | Production HSM/signer and anchor qualification |
| AZPR-V9-IND-F02 bootstrap symlink roots | CLOSED_SOURCE_LEVEL | Descriptor-relative no-follow reads; symlink/hard-link/writable-ancestor/owner/sequence tests pass | Dedicated-host filesystem/provisioning exercise |
| AZPR-V9-IND-F03 verifier requires `/root` | CLOSED_SOURCE_LEVEL | Reviewer-owned temp root; no `/root`; source/fresh unprivileged verification required | Independent reproduction on reviewer environment |
| AZPR-V9-IND-F04 real qualification absent | NOT_CLOSED | Schemas/contracts/tools only | Organization, host, signer, anchor, supply-chain, policy, roadmap, application evidence |
| AZPR-V9-IND-F05 filename mismatch/AppleDouble | CLOSED_AND_TESTED | Canonical delivered names, exact sidecars, safe archive audit | Independent delivery intake |
| AZPR-V9-IND-F06 stale current v8 documents | CLOSED_AND_TESTED | v10 current docs hash-indexed; superseded material under `legacy/v9-candidate/` | Independent documentation review |
| AZPR-V9-IND-F07 missing root-substitution tests | CLOSED_SOURCE_LEVEL | Every independent reproduction is in the 18-test release catalog | Independent mutation review |
| AZPR-V8-F01 no-secret qualification/external signing | PARTIALLY_CLOSED | Pinned probe authority and test-only external signing; no caller authority | Production signer/HSM and no-secret host qualification |
| AZPR-V8-F02 global serialization | CLOSED_SOURCE_LEVEL | 20-process test and recovery controls pass | Real fault/concurrency matrix |
| AZPR-V8-F03 complete qualification binding | CLOSED_SOURCE_LEVEL | Versioned exact 48-artifact set and trust binding | Independent completeness review as deployment inputs evolve |
| AZPR-V8-F04 rollback-resistant consumption | PARTIALLY_CLOSED | Signed journal/anchor semantics retained and rollback tests pass | Qualified rollback-resistant remote anchor |
| AZPR-V8-F05 first install qualification-only | CLOSED_SOURCE_LEVEL | Source and release blockers preserve phase separation | Real host exercise |
| AZPR-V8-F06 machine-derived evidence | CLOSED_SOURCE_LEVEL | Contradictory decisive raw evidence rejects signed PASS | Real machine evidence corpus |
| AZPR-V8-F07 atomic key lifecycle | PARTIALLY_CLOSED | Atomic epoch and interruption recovery test pass | Production key ceremonies and integration across all consumers |
| AZPR-V8-F08 real qualification evidence | NOT_CLOSED | No paper closure claimed | All real-world gates listed in known limitations |

## Evidence hashes

- v9 independent reproduction JSON: `792c98ca15d91c9b139acde40c1eb51b19836f979df65718aea2451089a240d8`
- v9 non-root failure stderr: `b5e1c5a9dde2b64a4fa0f4cefa467acd74e64fa9920f1ed8775115ed510b8403`
- 18-test pre-curation results: `eaad3a5f4c2be21e714f7e155d5bf712468c2b22d2f0da47e1bfe4e79e35649e`

## Independent reassessment

Required for every closure label. No status in this matrix authorizes installation or execution.
