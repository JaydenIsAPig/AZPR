# Autonomous Execution Policy

## Purpose

This policy lets a person use Codex to complete one narrow AZ Permit Radar roadmap stage at a time without giving one uninterrupted agent authority over the whole product.

The loop is reusable: future roadmap versions may replace the numbered prompt files and regenerate a proposed roadmap, while the controller, audit rules, branch protocol, approval model, and appendix locks remain stable.

## Controller-owned responsibilities

The Python controller owns:

- selecting the next eligible action;
- checking prerequisites, audits, approvals, and locks;
- creating one isolated Git branch;
- invoking Codex with the mapped reasoning effort and least-privilege sandbox;
- independently rerunning roadmap-defined validation;
- enforcing changed-path boundaries;
- writing immutable audit reports and indexes;
- writing human-readable run history and current status;
- creating one dedicated commit;
- stopping for human review and merge;
- reconciling the merge before another stage begins.

Codex does not own Git commits or merges.

## Normal lifecycle

1. The person starts on a clean base branch.
2. `controller.py run` chooses one eligible numbered stage, Appendix A correction, or mandatory audit rerun.
3. The controller creates an isolated branch.
4. Codex inspects and performs only that prompt.
5. The controller reruns required validation.
6. The controller checks changed paths and structure.
7. The controller creates one commit.
8. The person reviews and merges the branch.
9. `controller.py reconcile` verifies the commit is in the base branch.
10. Only then may the next stage begin.

## Audit behavior

Formal audits run with a read-only Codex sandbox. Codex returns report Markdown through the structured result; the controller writes the report and audit index, then commits only those controlled records.

- PASS: progression may continue when other gates are met.
- PASS WITH REQUIRED CORRECTIONS: Appendix A may run only when every blocking correction authorizes `APPENDIX_A`.
- BLOCKED: stop for human action.

Appendix A does not complete or skip the audit. After its correction commit is merged, the same audit automatically becomes the next required action.

## Appendix B and C safety

Appendix B and C are excluded from normal execution and from the numbered roadmap.

Appendix B requires:

- all numbered stages reconciled;
- the final numbered audit as the latest PASS;
- a project-review approval file;
- a separate SMS-canary approval file;
- the Appendix B lock manually changed from false to true;
- the exact explicit command confirmation.

Appendix C requires:

- reconciled COMPLETED Appendix B;
- deployed/canary evidence;
- a separate Appendix C audit approval;
- its lock manually changed from false to true;
- a separate exact command confirmation.

Appendix C is never launched automatically after Appendix B.

## Human review remains mandatory

The controller reduces repetitive work; it does not replace human judgment. Review every branch diff, audit verdict, ADR proposal, provider choice, source-access decision, migration, authentication change, deployment change, and production-side effect.
