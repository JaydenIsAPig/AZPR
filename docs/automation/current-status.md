# AZ Permit Radar Autonomous Execution Status

State: staged-hybrid transition selected for integration review.

- The repository controller remains installed for development only.
- No roadmap or external-controller canonical policy is active; existing repository governance remains authoritative.
- The v10.1 prompt generation is selected but not integrated or active.
- A ten-stage transition prompt pack is prepared and hash-validated, but it is
  `DRAFT_NOT_ACTIVE`; it permits one stage per invocation and no automatic
  advancement.
- The external trusted-controller candidate is deferred, unqualified, and forbidden from writes or external capability.
- The integration mapping and transition contract are awaiting the governed
  preflight and later human approval.
- A local Ubuntu 24.04 ARM64 Multipass pre-qualification reproduced both exact
  delivery verifier modes at 120/120 offline with no source mutation. The
  result is preparation evidence only, not a formal `INT-01` result or external
  controller qualification.
- `INT-00` is the next review stage. `docs/audits/README.md` is the approved
  interim audit authority until `INT-04`, when the invoking controller must
  create the first immutable report and index atomically. The governance
  owner's actual name/role, exact host/image approval, and an independently
  bounded reviewer identity remain required; none may be invented or silently
  bypassed. After the pre-qualification patch is committed cleanly, execute
  `INT-00`, then rerun `INT-01` formally against that approved boundary.

Use `.codex-loop/state.json` for local machine state after setup. This committed file is a human-readable handoff only. The controlling transition gates are documented in [ADR-0009](../adr/0009-staged-hybrid-controller-transition.md), the machine contract is `automation/integration/v10.1/controller-transition-contract.json`, and review evidence is under [delivery provenance](../delivery-provenance/v10.1/README.md).
