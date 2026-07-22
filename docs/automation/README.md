# AZ Permit Radar Autonomous Agent Loop

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
