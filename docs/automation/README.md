# AZ Permit Radar Autonomous Agent Loop

## Controller boundary

This guide covers the repository controller only. Under [ADR-0009](../adr/0009-staged-hybrid-controller-transition.md), it is development-only; H0, H1, and H2 permit no controller writer, and a separately approved H3 cutover may make the external controller the sole writer. The delivered external-controller candidate must stay inert and outside the repository; prompt integration does not authorize external installation, state transfer, provider access, or production apply.

Before treating the v10.1 mapping as structurally ready for review, run:

```bash
.integration-temp/offline-validation/venv/bin/python \
  scripts/check_v10_1_prompt_stage_pack.py
.integration-temp/offline-validation/venv/bin/python \
  scripts/check_v10_1_mapping_readiness.py
```

The checkers are read-only and never create an approval. Structural readiness
does not make the mapping eligible for final human approval. That approval is
deferred until the pre-`INT-00` Ansible, Linux-environment, two-run
independence, and governance-owner gates recorded by the transition contract
are complete. The prompt pack is a routing and transition-preparation layer
only: its presence does not execute a stage, activate the selected
implementation prompts, or authorize either controller. The transition
contract and delivery evidence are indexed under
`automation/integration/v10.1/` and `docs/delivery-provenance/v10.1/`.

> **Current transition lock:** The setup and run commands below are retained as repository-controller reference material. Do not execute them during H0, H1, or H2. Use `current-status.md` and the transition contract for the active boundary.

## Quick start

Run all commands from the actual Git repository root, `AZPR/`.

```bash
git rev-parse --show-toplevel
python3 automation/controller.py setup
python3 automation/smoke_test.py
```

Review the copied controller files, then make one manual setup commit so roadmap generation starts from a clean repository:

```bash
git add AGENTS.md automation docs/automation docs/audits .gitignore
git commit -m "Add bounded Codex autonomous-loop controller"
python3 automation/controller.py generate-roadmap
```

Review:

- `automation/roadmap.proposed.json`
- `automation/reports/roadmap-generation-report.md`

Then promote only after review:

```bash
python3 automation/controller.py validate-roadmap
python3 automation/controller.py promote-roadmap --confirm "PROMOTE ROADMAP"
```

Commit the controller bundle and active roadmap manually. Normal execution requires a clean repository.

Start one stage:

```bash
python3 automation/controller.py run
```

After Codex completes, review the isolated branch and commit. Merge it into `main`, switch back to `main`, and run:

```bash
python3 automation/controller.py reconcile --delete-branch
```

## Useful commands

```bash
python3 automation/controller.py status
python3 automation/controller.py validate-roadmap automation/roadmap.json
python3 automation/controller.py run --stage 001
python3 automation/controller.py reconcile
```

Appendix A normally launches through `run` when an audit authorizes it. It may also be invoked explicitly:

```bash
python3 automation/controller.py appendix A
```

Appendices B and C remain disabled by default. Do not enable them during initial MVP execution.

## When a run stops before commit

Inspect:

- `.codex-loop/results/`
- `.codex-loop/logs/`
- `git status`
- the recorded branch in `python3 automation/controller.py status`

Fix the controller or prompt metadata rather than bypassing a gate. To intentionally discard the entire recorded uncommitted branch:

```bash
python3 automation/controller.py abandon --confirm "ABANDON ACTIVE STAGE"
```

This command is destructive and should be used only after reviewing the branch.
