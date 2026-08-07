# AZPR v10.1 Finding Closure Matrix

| Finding | Developer-side status | Correction | Release-blocking evidence | Remaining limitation |
|---|---|---|---|---|
| AZPR-V10-IND-F01 | CLOSED_SOURCE_LEVEL_PENDING_INDEPENDENT_REASSESSMENT | Caller trust fields removed; fixed host-root loader; fixed signer/receipt roots; anchor-verified higher authority | complete caller-created authority input rejected; public loader has no root parameter; signer independently reloads roots | host provisioning and remote service must be independently qualified |
| AZPR-V10-IND-F02 | CLOSED_SOURCE_LEVEL_PENDING_INDEPENDENT_REASSESSMENT | Exact signed policy boundary, observations, target set, and maximum age enforced | network-mode mismatch and one-second-age policy attacks rejected | real probe boundary execution remains host qualification |
| AZPR-V10-IND-F03 | CLOSED_SOURCE_LEVEL_PENDING_INDEPENDENT_REASSESSMENT | independent attestor keyring/revocation; signed attestation; actual executable, launcher, and runtime hashes | forged attestation and executable substitution rejected | actual production attestor and immutable launch path remain operational gates |
| AZPR-V10-IND-F04 | CLOSED_SOURCE_LEVEL_PENDING_INDEPENDENT_REASSESSMENT | all collected tests cataloged and isolated; catalog/collection equality enforced | `120/120` isolated tests pass in source and must repeat after fresh extraction | independent assessment must judge catalog adequacy and exact results |
| AZPR-V10-IND-F05 | CLOSED_SOURCE_LEVEL_PENDING_INDEPENDENT_REASSESSMENT | all ten reported schema locations bounded; signer/policy nested objects strict | inherited global strict-bounds oracle passes | parser/resource behavior must still be qualified on target host |
| AZPR-V10-IND-F06 | CLOSED_SOURCE_LEVEL_PENDING_INDEPENDENT_REASSESSMENT | issuance chronology, skew, sequence floors, ordering, and signed remote head enforcement | future trust/revocation and rolled-back host-head attacks rejected | production rollback-resistant anchor availability/durability unproven |
| AZPR-V10-IND-F07 | OPEN_BY_DESIGN | no paper closure attempted | readiness metadata and forbidden policy/roadmap checks | all real qualification and integration gates remain open |

No finding is labeled independently closed by this development team.
