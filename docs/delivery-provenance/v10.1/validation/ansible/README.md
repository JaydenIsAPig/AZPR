# H0 Ansible provisioning evidence

Everything in this directory is **non-authoritative provisioning evidence**.
It may show that a pinned Ansible runtime parsed the inventory, that playbooks
were syntactically valid, or that a disposable target converged idempotently.
It does not approve a Linux environment and is not a formal Linux verifier run.

Formal Run A and Run B must be recorded separately after the environment
definition is approved. Ansible output must never be copied into either run as
the adjudicating PASS.

- `environment-manifest.json` records observed host-laboratory facts and known
  limitations.
- `ansible-runtime-manifest.json` binds the project-local review runtime.
- `qualification-preflight.json` records the disposable-target preparation
  preflight.
- `idempotence-result.json` records the two-apply provisioning check.
- `h0-repository-validation.json` records repository-side checker results.
- `multipass-transport-repair.json` records hash-bound, non-authoritative
  engineering evidence that repeated fresh operator-terminal connections pass
  before and after a disposable-guest restart. It unblocks validation only and
  is not convergence, idempotence, qualification, approval, or H0 completion.
- `h0-t01-transport-authority.json` records the exact, human-supplied,
  time-bounded H0-T01 network-exception authority and its rollback boundary.
  It is preserved evidence for approval ID
  `AZPR-H0-TRANSPORT-20260807-001`; it is not by itself executable authority.
  H0-T02 now additionally requires the canonical ticket, immutable review, and
  a trusted-controller-authenticated decision bound to ticket SHA-256
  `f74a416c8770f7268e8fa2353c880ed46c65adf9ddad67f38db29859373aef67`.
  The checkpoint has no qualification, verifier, INT-00, materialization,
  controller, provider, or production effect.

Raw output is retained only when needed and must be checked for secrets before
commit. Hash-only summaries are preferred.
