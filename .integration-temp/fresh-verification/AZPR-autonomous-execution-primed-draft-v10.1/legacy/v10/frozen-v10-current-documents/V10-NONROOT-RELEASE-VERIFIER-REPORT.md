# V10 Non-Root Release Verifier Report

## Corrected v9 failure

The official v9 verifier hardcoded `TemporaryDirectory(..., dir='/root')` and failed under the documented unprivileged workflow.

## V10 verifier properties

- reviewer-owned mode-0700 temporary root selected from a safe `TMPDIR`;
- no `/root` access or effective UID 0 requirement;
- sanitized HOME, XDG, Python, Git, locale, and plugin environment;
- one release test per isolated process group;
- 180-second hard timeout per test;
- bounded stdout/stderr and descendant process-group termination;
- no bytecode/cache/platform metadata;
- Python syntax/AST checks;
- Draft 2020-12 schema checks and strict v10 schema requirement;
- exact prompt inventory and byte verification;
- hash-bound current-document index;
- authenticated internal manifest verification;
- source-tree mutation detection.

## Catalog

The release catalog contains 18 individually executed tests: 14 v10 source blockers and 4 inherited composed controls.

## Acceptance requirement

The same verifier must pass from the frozen source tree and a fresh read-only extraction under an unprivileged account. The final delivery includes both machine-readable outputs.
