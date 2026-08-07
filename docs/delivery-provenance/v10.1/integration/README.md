# AZPR v10.1 integration evidence

The inventory, conflict, plan, rollback, and staging-diff reports in this
directory are preserved snapshots from the original stopped staging attempt.
They describe the earlier 467-row unresolved mapping, SHA-256 `007786c1...`,
missing validation dependencies, zero executed delivery tests, and a worktree
before the current preparation changes. Their approval and next-action text is
historical and must not be followed as current instruction.

The original mapping bytes are retained as
`AZPR-v10.1-integration-path-mapping.staging-original.csv`. The current
project-owner decisions are expressed only by the regenerated
`AZPR-v10.1-integration-path-mapping.csv`, the transition contract, ADR-0009,
and `../validation/mapping-readiness-assessment.json`.

The exact 527-row, `c84d45f...` approval-candidate bytes that preceded the H0
Ansible workstream are preserved under `historical-prequalification/` and are
explicitly non-current. Commit
`ce80d335aef52c8900bd363bbcfacc1e497c0404` is the human-approved pre-Ansible
transition base; `d60e5d9...` is its recorded source-tree parent. This base
approval is not final mapping approval.

Do not edit the historical reports to make their old conclusions look current.
Regenerate the executable assessment after any current mapping or safeguard
change.

The current transition prompt pack is under
`automation/integration/v10.1/prompt-stages/`. Its manifest and SHA-256 file are
part of the deterministic mapping, and
`scripts/check_v10_1_prompt_stage_pack.py` must pass before the mapping is
structurally ready for review. The pack remains draft and grants no runtime or
materialization authority. Final mapping approval is deferred until the H0
Ansible, Linux environment, two-run independence, and governance-owner gates
are complete and the current mapping has been regenerated again.
