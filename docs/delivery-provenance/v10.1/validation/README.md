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
environment approval, retained only the Multipass image-hash prefix, and used
a reviewer that remained privilege-capable inside the guest, it is
`PASS_PREQUALIFICATION_ONLY`, not either of the two formally accepted
independent Linux runs. It does not authorize mapping approval,
materialization, controller qualification, or activation.

The new `ansible/` subdirectory contains non-authoritative H0 provisioning
evidence only. The qualification-only inventory and all playbooks pass the
repository contract, inventory parser, and syntax checks with the pinned
project-local `ansible-core 2.21.2` runtime. Live check-mode and two-apply
idempotence are `BLOCKED_HOST_TRANSPORT`: two disposable Ubuntu guests received
addresses but were unreachable, and host firewall/network isolation was not
changed. These are not formal Run A or Run B results. The adjacent Linux
environment approval file is a null human-input template, not an approval.

Commit `ce80d335aef52c8900bd363bbcfacc1e497c0404` is the approved pre-Ansible
transition base. The next governed work is H0 Ansible live validation,
followed by formal Linux-environment
approval, two independently evidenced 120/120 runs, proof of independence,
audit-governance owner resolution, final exact mapping regeneration and human
approval, and only then `INT-00`.
