# AZ Permit Radar Autonomous Execution Status

State: staged-hybrid transition selected for integration review.

- The repository controller remains installed for development only.
- No roadmap or external-controller canonical policy is active; existing repository governance remains authoritative.
- The v10.1 prompt generation is selected but not integrated or active.
- A ten-stage transition prompt pack is prepared and hash-validated, but it is
  `DRAFT_NOT_ACTIVE`; it permits one stage per invocation and no automatic
  advancement.
- The external trusted-controller candidate is deferred, unqualified, and forbidden from writes or external capability.
- Commit `ce80d335aef52c8900bd363bbcfacc1e497c0404` is the human-approved
  pre-Ansible H0 transition base. Its direct parent
  `d60e5d9b5fe3b39fa07a1b2e6bfa2719425eb6e5` remains recorded as source-tree
  lineage; neither commit is final mapping approval.
- The current mapping is a regenerable H0 review artifact. Final
  mapping approval is deferred until the Ansible work and the remaining H0
  human/evidence gates are complete.
- A local Ubuntu 24.04 ARM64 Multipass pre-qualification reproduced both exact
  delivery verifier modes at 120/120 offline with no source mutation. The
  result is preparation evidence only, not a formal `INT-01` result or external
  controller qualification.
- The bounded H0 Ansible qualification-infrastructure layer now exists under
  `infrastructure/ansible/`. Its qualification-only inventory, machine
  contract, pinned `ansible-core 2.21.2` runtime, four roles, four playbooks,
  focused failure-path tests, inventory validation, and syntax checks pass.
  The idempotence evidence boolean and reviewer-HOME safeguards are corrected
  and regression-tested. The Multipass host-transport blocker was repaired
  without guest deletion, guest reconfiguration, credential regeneration, or
  a firewall, VPN, kill-switch, route, or network-extension change. Three fresh
  operator-terminal connections passed before and after a disposable-guest
  restart; packet and kernel diagnostics distinguish successful guest SSH from
  a Codex-process-context NECP rejection. The retained `azpr-validator` identity
  and configuration remained unchanged and that guest is stopped. This
  non-authoritative engineering evidence only unblocks live check/diff and
  two-apply idempotence work; neither has been run or inferred from the repair.
  Before H0-T02, approval ID `AZPR-H0-TRANSPORT-20260807-001` is now represented
  by a version-controlled stage manifest, canonical ticket, and immutable
  review view. The ticket SHA-256 is
  `f74a416c8770f7268e8fa2353c880ed46c65adf9ddad67f38db29859373aef67`.
  The prior H0-T01 authority handoff is preserved as evidence but is not alone
  executable authority. No authenticated digest-bound decision or execution
  outcome exists, so H0-T02 remains stopped at the approval checkpoint.
  Ansible may establish requested machine state but may not approve or qualify
  it. Formal Linux-environment approval,
  two independently evidenced 120/120 verifier runs, proof of run
  independence, the actual audit-governance owner name/role, regeneration and
  human approval of the final exact mapping, and the `INT-00` preflight all
  remain unresolved. `INT-00` is blocked until those preconditions are
  satisfied in the order recorded by the transition contract.
- `docs/audits/README.md` remains the approved interim audit authority until
  `INT-04`, when the invoking controller must create the first immutable report
  and index atomically. No unresolved human identity or approval may be
  invented or silently bypassed.

Use `.codex-loop/state.json` for local machine state after setup. This committed file is a human-readable handoff only. The controlling transition gates are documented in [ADR-0009](../adr/0009-staged-hybrid-controller-transition.md), the machine contract is `automation/integration/v10.1/controller-transition-contract.json`, and review evidence is under [delivery provenance](../delivery-provenance/v10.1/README.md).
