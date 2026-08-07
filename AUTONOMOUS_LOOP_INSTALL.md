# Install the Autonomous Codex Loop in AZPR

> **Repository-controller reference only.** Do not execute this installation guide during staged-hybrid phases H0, H1, or H2. It does not install or activate the v10.1 external trusted controller. ADR-0009 requires both controllers to remain inert through repository integration, followed by read-only qualification, a single-writer fence, signed state snapshot, independent cutover audit, and separate human approval before external control.

## 1. Copy the bundle into the repository root

The `AZPR/` folder in this bundle is a merge overlay. Copy its contents into the real `AZPR/` Git repository. Do not create `AZPR/AZPR/`.

Expected paths include:

- `AZPR/AGENTS.md`
- `AZPR/automation/controller.py`
- `AZPR/automation/numbered/`
- `AZPR/automation/appendices/`
- `AZPR/docs/automation/`

## 2. Initialize local runtime state

From the real repository root:

```bash
git rev-parse --show-toplevel
python3 automation/controller.py setup
python3 automation/smoke_test.py
```

The Git root must end in `/AZPR`. Setup creates `.codex-loop/` and adds it to `.gitignore`.

## 3. Commit the controller foundation

Review the files first, then commit them manually:

```bash
git add AGENTS.md AUTONOMOUS_LOOP_INSTALL.md automation docs/automation docs/audits .gitignore
git commit -m "Add bounded Codex autonomous-loop controller"
```

The controller intentionally requires a clean repository before roadmap generation or stage execution.

## 4. Generate a proposed roadmap

```bash
python3 automation/controller.py generate-roadmap
```

Codex reads all numbered prompts and appendices in read-only mode. It returns a schema-constrained proposal. The controller writes:

- `automation/roadmap.proposed.json`
- `automation/reports/roadmap-generation-report.md`

Appendix B and C are excluded from normal execution and remain hard-locked.

## 5. Review and promote the roadmap

```bash
python3 automation/controller.py validate-roadmap
python3 automation/controller.py promote-roadmap --confirm "PROMOTE ROADMAP"
```

Review the diff and commit the approved roadmap manually:

```bash
git add automation/roadmap.json automation/roadmap.proposed.json automation/reports/roadmap-generation-report.md
git commit -m "Approve autonomous MVP roadmap"
```

## 6. Run one stage

```bash
python3 automation/controller.py run
```

The controller creates a branch such as `automation/stage-001-...`, invokes Codex, independently reruns validation, writes run records, and creates one commit.

Review the branch before merging:

```bash
git status
git show --stat
git diff main...HEAD
```

Merge using your normal Git workflow. Return to `main`, then reconcile:

```bash
python3 automation/controller.py reconcile --delete-branch
```

No next stage can begin until reconciliation succeeds.

## 7. Audit corrections

When a formal audit returns `PASS_WITH_REQUIRED_CORRECTIONS` and explicitly authorizes Appendix A, the next normal `run` launches Appendix A. After its branch is merged and reconciled, the controller requires the same audit to rerun.

A `BLOCKED` audit never launches Appendix A automatically.

## 8. Keep Appendix B and C disabled

Do not change these defaults during the numbered MVP roadmap:

```json
"appendix_locks": {
  "B": {"enabled": false},
  "C": {"enabled": false}
}
```

Appendix B requires the completed numbered roadmap, final audit PASS, two manual approval files, a manually enabled controller lock, and an exact confirmation phrase. Appendix C has a separate lock and approval. Neither runs automatically.

## 9. Check status any time

```bash
python3 automation/controller.py status
```

Local runtime details and raw results are stored under `.codex-loop/` and are not committed.
