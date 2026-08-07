# H0 infrastructure tests

`run_idempotence.py` is an explicit state-changing test harness. It performs a
read-only preflight, applies `qualification-prepare.yml` twice, and requires the
second recap to report `changed=0`. It never interprets that result as AZPR
qualification.

Use only an approved qualification host or a disposable validator. The runner
requires a confirmation phrase and records hashes of captured output rather
than committing raw terminal output. Formal Linux verifier runs remain outside
this harness.

Repository-level failure-path and authority tests live in
`tests/test_h0_ansible_contract.py` and
`tests/test_h0_ansible_live_paths.py` and run without Ansible or host mutation.
They cover fail-closed recap evaluation, atomic hash-only evidence, reviewer
passwd-home consistency, the bounded reset contract, and the named live
failure gates. Destructive reset-preservation and network-isolation behavior
must still be exercised only on a named disposable guest.
