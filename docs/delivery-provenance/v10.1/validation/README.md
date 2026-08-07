# AZPR v10.1 validation evidence

This directory contains original staging evidence, superseded macOS
diagnostics, and the current local Linux pre-qualification evidence. It grants
no runtime or production authority.

`AZPR-v10.1-staging-validation.json` and
`AZPR-v10.1-system-integration-handoff-summary.md` are preserved original H0
reports. Their dependency, test-count, mapping-hash, and next-action statements
describe the earlier stopped staging attempt and are not current status.

For the current preparation state, read these files together:

- `python-runtime-manifest.json`, `requirements-validation.lock`, and
  `wheelhouse-manifest.json` describe the local Linux ARM64 dependency and
  reviewer runtime;
- `delivery-verifier-attempts.json` binds the later source and fresh-extraction
  120/120 passes to raw stdout/stderr, network-state, and inventory evidence;
- `inventory-comparison.json` and `candidate-file-inventory.sha256` prove the
  two read-only trees were byte-identical before and after execution;
- `mapping-readiness-assessment.json` is the reproducible output of the current
  elementary mapping checker.

The earlier macOS files are retained byte-for-byte under `historical-macos/`.
They explain the host-dependent 16-test stop and 116/120 diagnostic suite, but
they are no longer the active readiness input.

The local Linux VM reproduced both exact verifier modes at 120/120 with the
network interface disabled, empty verifier stderr, UID 1000, no inherited
credentials, and no source mutation. Because this run preceded a valid
`INT-00`, retained only the Multipass image-hash prefix, and used a reviewer
that remained privilege-capable inside the guest, it is
`PASS_PREQUALIFICATION_ONLY`, not a formal `INT-01` result. It does not
authorize mapping approval, materialization, controller qualification, or
activation. The next governed move is `INT-00`, followed by a formal `INT-01`
rerun on the exact approved reviewer boundary.
