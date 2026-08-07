# H0 Ansible integration-manager execution runbook

## Document status

- **Lifecycle position:** H0, before formal Linux qualification and before
  `INT-00`.
- **Current disposition:** `H0_ANSIBLE_PREPARATION_INCOMPLETE` until live
  check mode and two-apply idempotence pass on an approved reachable target.
- **Owner:** Ansible integration manager for qualification preparation.
- **Governing contract:**
  `infrastructure/ansible/h0-qualification-contract.json`.
- **Evidence classification:** Ansible output is non-authoritative provisioning
  evidence. It is never a qualification or approval result.

## Goal and required outcome

Reproducibly prepare a disposable or explicitly human-approved Ubuntu Linux
environment for independent AZPR v10.1 qualification. A successful H0 Ansible
run must:

1. bind the exact candidate, prompt, dependency locks, and offline wheels;
2. request only the allowlisted Linux state under `/srv/azpr-validator`;
3. pass repository, inventory, syntax, check-mode, failure-path, and
   idempotence validation;
4. leave the frozen candidate read-only and credentials absent;
5. stop before the independent AZPR verifier, human approval, audit decision,
   mapping approval, or controller activation.

The final successful Ansible output is a second apply with `changed=0`,
`unreachable=0`, `failed=0`, plus a seal observation. It does not make the host
qualified. Formal qualification follows as a separate workflow.

## Authority and scope

### In scope

- One `qualification` inventory only.
- Python 3.12 and hash-pinned `ansible-core 2.21.2`.
- Ubuntu 24 on AArch64 with a non-root reviewer at UID/GID 1000.
- Four roles: baseline, offline validation runtime, bounded filesystem, and
  isolation policy.
- Preflight, prepare, seal, and bounded reset playbooks.
- Exactly three privileged task names: approved validation package
  installation, creation of `/srv/azpr-validator`, and removal of that exact
  root during reset.
- Non-secret, hash-bound provisioning evidence.

### Out of scope

- Staging or production inventories.
- Product deployment or production authorization.
- SSH-key creation, unmanaged transport credentials, or secret distribution.
- Running or adjudicating the AZPR verifier from Ansible.
- Environment approval, audit verdicts, mapping approval, or activation of
  prompts, policy, roadmap, materialization, controllers, or `INT-00`.
- Rewriting frozen inputs, historical reports, or the preserved 527-row
  prequalification mapping.

## Execution topology and filesystem structure

Run Ansible **inside the Linux guest** with `ansible_connection=local`. The
macOS host or another approved laboratory owns only guest lifecycle and input
transfer. Do not convert this runbook to ad hoc host-to-guest SSH.

```text
approved host laboratory
  -> disposable or approved Ubuntu guest
       -> /home/ubuntu/azpr-h0-control/      writable H0 control checkout
       -> /srv/azpr-approved-inputs/         immutable approved inputs
            -> source-tree/                  read-only frozen candidate
            -> validation-wheelhouse/        Linux AArch64 wheels
       -> /srv/azpr-validator/               disposable Ansible output
            -> runtime/
            -> work/
            -> evidence/

Ansible requested state
  -> independent environment observation
  -> independent formal AZPR verifier Runs A and B
  -> human/audit decision
  -> regenerated and approved final mapping
  -> INT-00 eligibility
```

The H0 control checkout and frozen candidate tree are different inputs. The
control checkout needs limited write access for `.integration-temp`; the
candidate tree must not be writable by the reviewer.

## Completed stop-before-execution safeguards

The integration manager must verify that both safeguards below remain present
and regression-tested before running a state-changing playbook:

1. `infrastructure/ansible/tests/run_idempotence.py` uses the Python boolean
   `False`, requires explicit successful recaps for preflight and both applies,
   and fails closed on missing, nonzero, failed, unreachable, or non-idempotent
   results.
2. In
   `infrastructure/ansible/roles/azpr_validator_isolation/tasks/main.yml`,
   generated `HOME` is derived from the configured reviewer's `getent_passwd`
   home. Preflight, baseline, seal, and focused tests require the configured
   `ubuntu` reviewer, UID/GID 1000, passwd home, and generated `HOME` to agree.

After either safeguard changes, rerun all checks in **Repository gates** and
regenerate the mapping and readiness assessment before approval. Any regression
is a stop condition.

## Preconditions and immutable inputs

The integration manager must verify all of the following before execution:

- The worktree is clean or every change is represented by the current mapping.
- The target is explicitly disposable for engineering use, or its exact
  definition has human approval for formal preparation.
- Guest control transport works before network isolation:

  ```bash
  multipass exec <guest-name> -- true
  ```

- No forbidden credential environment variable is inherited by the session.
- The guest matches the inventory constraints in
  `infrastructure/ansible/inventories/qualification/group_vars/all.yml`.
- The exact input paths exist under `/srv/azpr-approved-inputs`.
- The extracted candidate tree is a directory and is not reviewer-writable.
- The Linux AArch64 validation wheelhouse contains all wheels named by
  `docs/delivery-provenance/v10.1/validation/wheelhouse-manifest.json`.
- The project-local Ansible wheelhouse contains the Linux AArch64 wheels named
  by `infrastructure/ansible/requirements/wheelhouse-manifest.json`.

Required archive bindings:

| Input | Required SHA-256 |
|---|---|
| `AZPR-autonomous-execution-primed-draft-v10.1.zip` | `618449d73fd921e0fb366c0aed8c9a666b2ead3847e529a6ced9692fe41e2b24` |
| `markdown-prompts-autonomous-priming-draft-v10.1.zip` | `3b235cb7e33ca409241ff26523f60f8fee89cec524b3f09e91a69927a0aa4880` |

Record the guest image identity, Multipass version, OS, kernel, architecture,
CPU, RAM, disk, filesystem, Python version, dependency hashes, reviewer
identity, and network policy. Do not populate the human approval file on
behalf of its approver.

## Method

Run every command from the root of the H0 control checkout inside the guest
unless a step explicitly names the host laboratory.

### 1. Create the pinned Ansible runtime

The wheelhouse must already be present locally. A formal run must not contact a
package index.

```bash
python3.12 -m venv .integration-temp/ansible/venv

.integration-temp/ansible/venv/bin/python -m pip install \
  --no-index \
  --no-cache-dir \
  --require-hashes \
  --find-links .integration-temp/ansible/wheelhouse \
  -r infrastructure/ansible/requirements/requirements-ansible.lock

.integration-temp/ansible/venv/bin/ansible --version
```

Expected runtime: Python 3.12 and `ansible-core 2.21.2`. Stop on a version or
hash mismatch.

### 2. Repository gates

```bash
python3 scripts/check_h0_ansible.py \
  --ansible-bin-dir .integration-temp/ansible/venv/bin

python3 scripts/check_v10_1_prompt_stage_pack.py
python3 scripts/check_v10_1_mapping_readiness.py
python3 scripts/check_docs.py
PYTHONPATH=src python3 -m pytest -q
PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_*.py'
PYTHONPYCACHEPREFIX=.integration-temp/pycache \
  python3 -m compileall -q src scripts tests infrastructure/ansible/tests
git diff --check
```

Required result: every command exits zero. The H0 checker must report a valid
static contract, one qualification inventory, successful inventory parsing,
and syntax success for all four playbooks. A readiness assessment may still
truthfully report live validation as pending at this point.

### 3. Review check mode

```bash
ANSIBLE_CONFIG=infrastructure/ansible/ansible.cfg \
.integration-temp/ansible/venv/bin/ansible-playbook \
  -i infrastructure/ansible/inventories/qualification/hosts.example.yml \
  infrastructure/ansible/playbooks/qualification-prepare.yml \
  --check --diff
```

Review all predicted changes and privilege use. Check mode is a review gate,
not execution proof. If `python3` or `python3-venv` is absent, install it only
through the allowlisted role while preparation networking or an independently
approved offline OS-package source is available. Networking is disabled later,
during the verifier window.

### 4. Apply twice and prove idempotence

For an engineering target:

```bash
python3 infrastructure/ansible/tests/run_idempotence.py \
  --inventory infrastructure/ansible/inventories/qualification/hosts.example.yml \
  --ansible-playbook .integration-temp/ansible/venv/bin/ansible-playbook \
  --environment-scope DISPOSABLE_TEST \
  --confirm 'APPLY H0 QUALIFICATION PREPARATION' \
  --output /srv/azpr-validator/evidence/idempotence-result.json
```

Use `HUMAN_APPROVED_QUALIFICATION` only after an authorized human has approved
the exact environment definition. The runner executes preflight, first apply,
and second apply. Required second recap:

```text
changed=0  unreachable=0  failed=0
```

The evidence JSON must state
`classification=NON_AUTHORITATIVE_PROVISIONING_EVIDENCE`, contain no secret or
raw sensitive data, and bind outputs by hash rather than copying full logs.

### 5. Seal the verifier window

Open and retain the local guest operator session before disabling networking;
network isolation can terminate host-mediated `multipass exec` transport. An
authorized operator—not Ansible—establishes the approved no-network state.
Then run locally in the retained session:

```bash
ANSIBLE_CONFIG=infrastructure/ansible/ansible.cfg \
.integration-temp/ansible/venv/bin/ansible-playbook \
  -i infrastructure/ansible/inventories/qualification/hosts.example.yml \
  infrastructure/ansible/playbooks/qualification-seal.yml \
  -e azpr_network_seal_confirmation=NETWORK_DISABLED_BY_OPERATOR
```

Expected result: no default route, no forbidden credential environment,
correct ownership and modes, and a candidate tree not writable by the
reviewer. Independently measure those facts again; do not promote the Ansible
recap to qualification evidence.

### 6. Hand off to formal qualification

Outside Ansible, the approved verifier owner must produce:

- formal Linux Run A: exactly 120/120, exit zero, expected stderr state, no
  candidate mutation, and hash-bound evidence;
- formal Linux Run B with the same result on a separately created validator,
  or after destruction and recreation from the approved immutable definition;
- independent environment measurements and proof of run independence;
- a human-created environment approval and the applicable formal audit result.

A second verifier invocation on the same unchanged guest is not independent.

### 7. Reconcile governed evidence and mapping

After reviewed evidence or safeguard changes are imported, use the
controller-owned workflow to regenerate the mapping, then run:

```bash
python3 scripts/prepare_v10_1_mapping.py
python3 scripts/check_v10_1_mapping_readiness.py
python3 scripts/check_v10_1_prompt_stage_pack.py
python3 scripts/check_docs.py
PYTHONPATH=src python3 -m pytest -q
git diff --check
```

Review the new mapping row count and exact SHA-256. Final mapping approval must
occur after H0 evidence is complete. The controller owns branch creation,
independent validation, run records, staging, and commit creation.

## Expected outputs and acceptance rules

| Output | Owner | Required result | Authority effect |
|---|---|---|---|
| H0 contract report | Repository checker | Contract/inventory/syntax `PASS` | None |
| Check-mode review | Ansible integration manager | Exit zero; expected bounded diff | None |
| Idempotence result | Ansible integration manager | Second apply `changed=0`, `unreachable=0`, `failed=0` | None |
| Seal observation | Ansible integration manager | Exit zero after operator-confirmed isolation | None |
| Environment observation | Independent verifier owner | Matches approved definition | Supports human decision only |
| Linux Run A and Run B | Independent verifier owner | Each 120/120 and exit zero | Qualification evidence |
| Environment approval | Authorized human | Complete, attributable, exact environment binding | Environment definition only |
| Formal audit | Audit-governance owner | Applicable governed verdict | Lifecycle gate |
| Mapping assessment | Controller | Regenerated, deterministic, fully bound | Supports final mapping approval |

Ansible completion alone must leave `INT-00` blocked.

## Verification tests

### Existing tests that must remain green

- `tests/test_h0_ansible_contract.py`: authority denial, inventory scope,
  forbidden modules, privilege allowlist, failure gates, and inert approval
  template.
- `tests/test_v10_1_mapping_readiness.py`: mapping determinism, worktree
  binding, H0 contract state, and transition-gate behavior.
- `scripts/check_h0_ansible.py`: static contract plus real inventory and
  playbook-syntax validation when given the pinned Ansible runtime.
- `scripts/check_v10_1_prompt_stage_pack.py`: prompt-pack hash and inert-stage
  validation.
- `scripts/check_docs.py`: current-document uniqueness, schema checks, logs,
  and local links.
- Entire repository unit suite under both pytest and unittest.

### Tests required before the first live run

Create focused tests with no external side effects:

1. **Idempotence result construction:** use a fake `ansible-playbook` executable
   or mocked subprocess results to produce valid recaps and prove that the
   runner writes valid JSON, uses a real Python boolean, and exits zero only
   when the second apply has zero changes/failures/unreachable hosts.
2. **Idempotence negative cases:** independently vary second-run `changed`,
   `failed`, `unreachable`, missing recap, and nonzero exit values; each must
   fail closed.
3. **Reviewer-home consistency:** assert that the environment file HOME,
   username, UID, GID, ownership, and passwd-derived home agree. Reject
   `/home/oai` when the reviewer is `ubuntu`.
4. **Evidence safety:** assert atomic output, classification, hash-only captured
   stdout/stderr, absence of credential values, and no qualification effect.

### Disposable live tests required before formal use

1. Reachable local-in-guest inventory and fact gathering.
2. Preflight success using exact staged hashes.
3. Check mode and reviewed bounded diff.
4. First apply success and second apply zero-change idempotence.
5. Wrong candidate hash, wrong prompt hash, missing wheel, wrong reviewer,
   wrong Python, inherited credential, and writable candidate failures.
6. Seal failure while a default route exists, followed by seal success only
   after operator-confirmed isolation.
7. Reset refusal for any root other than `/srv/azpr-validator`.
8. Reset success removes only `/srv/azpr-validator` and preserves all of
   `/srv/azpr-approved-inputs` byte-for-byte.
9. Interrupted apply recovery by rerunning preflight and preparation without
   editing the frozen candidate.

Do not turn destructive or network-isolation cases into ordinary host-side
unit tests. Run them only on a named disposable guest with explicit operator
authorization.

## Failure handling and recovery

- **Host transport failure:** preserve the error and stop. Repair the approved
  Multipass or laboratory transport; do not create unmanaged SSH credentials,
  weaken the firewall, or alter the preserved preliminary validator.
- **Hash/input failure:** restage the approved immutable input. Never edit the
  frozen candidate to match an expected hash.
- **Version/platform failure:** recreate the guest from the approved definition
  or obtain a new human approval; do not weaken the assertion.
- **Credential failure:** clear the operator environment and recreate the
  session. Never record the credential value.
- **Interrupted preparation:** rerun preflight and the idempotence workflow.
- **Reset:** run `qualification-reset.yml` only for the exact approved root.
  It must preserve `/srv/azpr-approved-inputs`.
- **Unrelated test failure:** stop with `BLOCKED`; do not weaken tests or claim
  readiness.

## Completion checklist

H0 Ansible preparation is complete only when every item is true:

- [ ] Both mandatory code corrections and their regression tests pass.
- [ ] Exact guest definition and input hashes are recorded.
- [ ] Repository, mapping, prompt-pack, documentation, inventory, syntax, and
      complete test-suite gates pass.
- [ ] Check-mode review passes on the intended target.
- [ ] First apply succeeds and second apply reports zero changes/failures/
      unreachable hosts.
- [ ] Seal checks pass after separately authorized network isolation.
- [ ] Provisioning evidence is non-secret, hash-bound, and explicitly
      non-authoritative.

Lifecycle progression additionally requires independent Runs A and B, proof of
independence, human environment approval, audit governance, regenerated mapping
approval, and an updated transition contract. Until then, retain
`H0_ANSIBLE_PREPARATION_INCOMPLETE` and keep `INT-00` blocked.
