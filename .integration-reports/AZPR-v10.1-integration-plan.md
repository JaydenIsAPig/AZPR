# AZPR v10.1 Integration Plan

Generated: `2026-08-06T23:11:48+00:00`

## Outcome

The integration plan stops after mapping and validation evidence. Phase 6 onward is not authorized because the base commit and path mapping are not human-approved and declared stop conditions are present.

## Completed phases

1. Discovered and froze clean `main` at `dac0e0bf1695d44f4b6c0e0e7673559f5d87ec02`; confirmed one worktree and the AZPR boundary.
2. Verified outer/nested hashes, sidecars, archive safety, internal manifests, prompt copies, and frozen readiness flags.
3. Inventoried 261 tracked repository files and 407 delivered file instances across all archive representations.
4. Assigned exactly one allowed classification to every delivered file.
5. Created a 467-row mapping: 407 delivered dispositions plus 60 explicit affected-current dispositions.

## Proposed integration order after approval

1. Resolve controller ownership, schema locations, `docs/audits/index.json`, policy/roadmap semantics, and documentation migration.
2. Resolve the canonical 41-prompt generation and all renamed prompt/manifest/roadmap references without modifying bytes casually.
3. Approve base `dac0e0bf1695d44f4b6c0e0e7673559f5d87ec02` and mapping CSV SHA-256 `007786c1c1748f8264cee452df815b47e41e15deb8b532b31f426cd18b4f2525`.
4. Create only `integration/v10.1-staging` and `/Users/jayden/Desktop/Business/AZ-Permit-Radar/AZPR-v10.1-integration-staging`.
5. Apply approved `ADD` rows in order: 73 schemas, seven validation profiles, policy-directory notice; then only explicitly approved prompt/controller/document changes.
6. Never copy host installation tools, live runtime state, secrets, private keys, receipts, or ledgers into the repository.
7. Run both complete 120-test verifier passes from an approved offline dependency runtime, plus repository tests/docs/reference checks.

## Approval boundary

This plan is a handoff, not approval. Do not create a branch/worktree, copy mapped files, commit, install, or activate anything until every blocking conflict is resolved and the exact mapping/base are approved.
