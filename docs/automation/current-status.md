# AZ Permit Radar Autonomous Execution Status

State: staged-hybrid transition selected for integration review.

- The repository controller remains installed for development only.
- No roadmap or external-controller canonical policy is active; existing repository governance remains authoritative.
- The v10.1 prompt generation is selected but not integrated or active.
- A ten-stage transition prompt pack is prepared and hash-validated, but it is
  `DRAFT_NOT_ACTIVE`; it permits one stage per invocation and no automatic
  advancement.
- The external trusted-controller candidate is deferred, unqualified, and forbidden from writes or external capability.
- ADR-0012 authorizes a separately governed, inert source-only macOS
  operator-approval adapter. Swift source defines the immutable native review
  window and Touch-ID-protected Secure Enclave P-256 signing path; Python source
  defines exact helper identity checks, canonical assertion verification with
  `cryptography==46.0.4`, host-owned trust/replay contracts, and one-action
  nonce consumption. The accepted role is `Head of AZPR Operations`. No real
  operator subject, helper install path, owner/mode, signing identity, key,
  public trust record, replay ledger, or enrollment exists, and neither
  controller selects the adapter. Hardware Touch ID/Secure Enclave tests are
  not run by this source stage. Installation, activation, H0-T02, commit,
  merge, push, and stage progression remain unauthorized. The separate source
  extension leaves the SHA-bound v10.1 transition contract and current H0
  transport ticket unchanged.
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
  A separate four-stage H0 live-validation prompt pack now represents that
  remaining work as inert source: read-only exact-target preflight, check/diff
  plus hash-bound human review, one bounded `DISPOSABLE_TEST` two-apply
  attempt, and read-only evidence reconciliation. The pack is
  `DRAFT_NOT_ACTIVE`, permits one stage per invocation, does not advance
  automatically, and grants no execution authority. It does not activate the
  operator-approval adapter or alter the current H0 transport ticket.
  The pack now also contains a deterministic, executable
  `AZPR_H0_TARGET_FINGERPRINT_V1` contract with exact independently observed
  non-secret Linux fields, normalization, member order, canonical UTF-8 JSON,
  SHA-256 behavior, mismatch rules, and a golden vector. ADR-0013 is accepted
  for the exact procedure digest
  `d35da355850ee1440ea454c4e2663dae7fb15778bb2c935283ec16d7771f1d8a`.
  No operator input exists, and a matching fingerprint identifies but never
  authorizes a target. The operator-approval adapter remains inactive.
  Three additional source-only operator-assistance prompts now automate the
  repetitive host repository gates, guest-local deterministic observations,
  safe operator-input validation, and H0-ALV-00 handoff analysis. They are not
  stages, have no unattended-success result, store no resume state, and stop
  only for attributable procedure approval, deliberate guest-local entry,
  exact-target understanding/authorization, human operator-input authorship,
  protected-channel attribution confirmation, or deliberate H0-ALV-00
  invocation. They cannot enter the guest, create or infer approval, create or
  modify operator input, run Ansible, or start another prompt automatically.
  The ADR-0014 channel now contains the canonical human-authored decision. Its
  read-only validator reports `APPROVED` and derives
  `git:82ba27a1be4d1590e15f78a891568844639096dd:automation/approvals/procedure-decisions/AZPR_H0_TARGET_FINGERPRINT_V1.json`.
  The decision approves only the exact procedure definition. The protected
  live-pack contract retains its static `PROPOSED_PENDING_HUMAN_APPROVAL`
  marker because readiness derives from the decision channel, not a rewrite of
  protected procedure bytes. The approval has no target, execution,
  adapter/controller, H0, verifier, or Git authority.
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

Use `.codex-loop/state.json` for local machine state after setup. This committed file is a human-readable handoff only. The controlling transition gates are documented in [ADR-0009](../adr/0009-staged-hybrid-controller-transition.md); the narrow source-only exception is [ADR-0012](../adr/0012-macos-secure-enclave-operator-approval.md). The machine contract remains `automation/integration/v10.1/controller-transition-contract.json`, and review evidence is under [delivery provenance](../delivery-provenance/v10.1/README.md).
