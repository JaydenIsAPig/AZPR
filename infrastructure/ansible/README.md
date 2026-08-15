# AZPR H0 Ansible qualification infrastructure

Status: **H0 provisioning implementation — not qualification authority**

This tree reproducibly requests machine state for the Linux environment used
to qualify the frozen AZPR v10.1 delivery. It does not approve the environment,
run or adjudicate the AZPR verifier, activate a prompt/policy/roadmap/controller,
materialize the integration mapping, install production services, or authorize
production.

The boundary is deliberately explicit:

```text
Multipass or another approved host laboratory  ->  VM/host lifecycle
Ansible                                        ->  requested Linux state
independent Linux observation + AZPR verifier  ->  qualification evidence
human/audit decision                           ->  acceptance or rejection
```

An Ansible recap, including `changed=0` and `failed=0`, is non-authoritative
provisioning evidence only.

## Layout and responsibility

- `inventories/qualification/` is the only H0 inventory. No staging or
  production inventory is permitted.
- `qualification-preflight.yml` performs read-only identity, platform, input,
  and hash checks.
- `qualification-prepare.yml` applies the four narrow roles.
- `qualification-seal.yml` checks the requested reviewer, credential, network,
  mode, and read-only boundaries immediately before an independent verifier
  window. It does not run the verifier.
- `qualification-reset.yml` removes only `/srv/azpr-validator`; candidate and
  prompt inputs remain outside that root.
- `h0-qualification-contract.json` is the machine-readable authority and
  failure-path contract enforced by `scripts/check_h0_ansible.py`.

The roles separate the requested baseline, offline Python runtime, disposable
filesystem, and environment-isolation policy. They use only
`ansible.builtin.*`; there are no shell/command/raw/script tasks or third-party
collections.

## Runtime

The review runtime is Python 3.12 plus `ansible-core==2.21.2`. The direct input,
fully pinned lock, and macOS ARM64/Linux AArch64 wheel hashes are under
`requirements/`. Build or install the runtime only into an ignored,
project-local directory such as `.integration-temp/ansible/venv`. A formal
qualification run must install from a separately approved offline wheel bundle;
it must not contact a package index.

Example review installation after the manifested wheels are present locally:

```bash
python3.12 -m venv .integration-temp/ansible/venv
.integration-temp/ansible/venv/bin/python -m pip install \
  --no-index --no-cache-dir --require-hashes \
  --find-links .integration-temp/ansible/wheelhouse \
  -r infrastructure/ansible/requirements/requirements-ansible.lock
```

No Ansible runtime or downloaded wheel is committed.

## Control and privilege model

The qualification inventory uses `ansible_connection=local` inside the guest.
An operator stages the repository and approved input bundle, opens a controlled
session, and invokes the pinned runtime there. This model creates no SSH key and
is portable to a later approved Linux host; Multipass is not embedded in any
role.

Default privilege escalation is disabled. Three task names are allowlisted by
the machine contract: install the approved `python3`/`python3-venv` packages,
create `/srv/azpr-validator`, and remove exactly that root during reset. Each is
individually tagged, explicitly becomes root, and has a bounded rollback.

## Review and execution sequence

The source-only prompt pack at
`automation/integration/v10.1/h0-ansible-live-stages/` provides four inert,
single-invocation prompts for exact-target preflight, check/diff review, one
two-apply attempt, and read-only evidence reconciliation. Validate it with
`scripts/check_h0_ansible_live_prompt_pack.py`. Its existence grants no target
authority and it cannot activate the operator-approval adapter, qualify the
environment, seal networking, run the AZPR verifier, or advance H0.

The proposed `AZPR_H0_TARGET_FINGERPRINT_V1` procedure is part of that inert
pack. `scripts/h0_target_fingerprint.py` observes its fixed non-secret Linux
identity fields locally, serializes exact canonical bytes, and calculates
SHA-256. Its contract and golden vector remain pending human approval. A
fingerprint identifies a target but does not authorize it; exact-stage target
authority remains a separate human-owned input.

Three optional, inert prompts under
`automation/integration/v10.1/h0-ansible-live-stages/operator-assistance/`
automate repository readiness, guest-local observation, and operator-input
validation/handoff. They are not Ansible playbooks or H0-ALV stages. Each runs
in one explicitly named context and ends at a human checkpoint; none can enter
a guest, create approval or operator input, invoke H0-ALV-00, or advance to the
next prompt automatically.

Before any state-changing playbook:

```bash
python3 scripts/check_h0_ansible.py \
  --ansible-bin-dir .integration-temp/ansible/venv/bin

python3 scripts/check_h0_ansible_live_prompt_pack.py

ANSIBLE_CONFIG=infrastructure/ansible/ansible.cfg \
  .integration-temp/ansible/venv/bin/ansible-playbook \
  -i infrastructure/ansible/inventories/qualification/hosts.example.yml \
  infrastructure/ansible/playbooks/qualification-prepare.yml \
  --check --diff
```

Check mode is a review aid, not execution proof. A state-changing run must use
an explicitly approved or disposable qualification target and the idempotence
runner, which requires the exact confirmation phrase:

```bash
python3 infrastructure/ansible/tests/run_idempotence.py \
  --inventory infrastructure/ansible/inventories/qualification/hosts.example.yml \
  --ansible-playbook .integration-temp/ansible/venv/bin/ansible-playbook \
  --environment-scope DISPOSABLE_TEST \
  --confirm 'APPLY H0 QUALIFICATION PREPARATION'
```

After preparation, an operator establishes the approved verifier-window network
state. `qualification-seal.yml` requires the explicit
`NETWORK_DISABLED_BY_OPERATOR` confirmation and observes the absence of a
default route. Independent evidence must measure the resulting state again.

## Reset and rollback

The reset playbook refuses any root other than `/srv/azpr-validator` and never
targets `/srv/azpr-approved-inputs`. Repository rollback removes only this
Ansible tree, its checker/tests/templates/evidence, exact documentation
references, and its generated mapping rows, followed by mapping regeneration.
It never rewrites historical reports or the preserved 527-row mapping.

## Remaining human gates

The environment approval, formal Linux Run A, formal Linux Run B, independence
proof, audit-governance owner, and final exact mapping approval remain separate
human/evidence gates. `INT-00` remains blocked until the transition contract
records all of them.
