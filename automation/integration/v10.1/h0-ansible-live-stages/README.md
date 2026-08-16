# AZPR H0 Ansible live-validation prompt pack

Status: **DRAFT PREPARATION ARTIFACT — NOT ACTIVE AUTHORITY**

This four-stage pack narrows the next H0 operation to a disposable Linux
qualification-preparation target: exact preflight, Ansible check/diff review,
one two-apply idempotence attempt, and read-only evidence reconciliation. It
does not qualify or approve an environment, run the AZPR verifier, seal a
network, activate a controller or the operator-approval adapter, or authorize
Git operations.

This pack is intentionally separate from `../prompt-stages/`. The existing
ten-stage `INT-00` through `INT-09` pack and its transition-contract binding
remain byte-independent and inactive.

## Operating rules

1. Run exactly one stage per invocation and never advance automatically.
2. Treat `operator-input.template.json` as a null-valued input contract, never
   as approval or proof of target ownership.
3. Require separately governed, unexpired authorization bound to the exact
   `DISPOSABLE_TEST` target and named stage before touching the guest.
4. Operate through `ansible_connection=local` inside the guest. Never create
   SSH credentials or modify host transport, firewall, VPN, route, or network
   extension state.
5. Keep `/srv/azpr-approved-inputs` immutable. The only material target of the
   two-apply stage is `/srv/azpr-validator` through the existing playbooks.
6. Retain hashes, exit codes, and recaps; do not copy raw command output,
   credential values, keys, or unnecessary personal data into results.
7. Ansible evidence is `NON_AUTHORITATIVE_PROVISIONING_EVIDENCE` and always has
   `qualification_effect=false`.
8. Do not create or modify a human approval file, the H0 transport ticket, the
   transition contract, a controller state file, or host trust state.
9. The operator-approval adapter must remain inactive and must not be selected
   as a workaround for absent live-validation authority.
10. Return exactly one JSON object matching `stage-result.schema.json`.

## Deterministic target fingerprint

`target-fingerprint-contract.json` defines
`AZPR_H0_TARGET_FINGERPRINT_V1`. ADR-0013 accepts the exact procedure, and the
ADR-0014 procedure-only decision `AZPR-H0-FINGERPRINTPROC-20260816-001`
approves its SHA-256
`d35da355850ee1440ea454c4e2663dae7fb15778bb2c935283ec16d7771f1d8a`. The
canonical approval reference is
`git:82ba27a1be4d1590e15f78a891568844639096dd:automation/approvals/procedure-decisions/AZPR_H0_TARGET_FINGERPRINT_V1.json`,
and its `authority_effect` is `false`. The protected contract and stage
manifest intentionally retain their static `PROPOSED_PENDING_HUMAN_APPROVAL`
markers; readiness derives from the committed ADR-0014 decision channel.
Procedure approval does not identify or authorize a target, approve an
environment, authorize execution, or activate a controller or adapter. The
exact ordered non-secret identity fields are:

1. `target_id` from `/proc/sys/kernel/hostname`;
2. `machine_id` from `/etc/machine-id`;
3. `operating_system_id` from `ID` in `/etc/os-release`;
4. `operating_system_version_id` from `VERSION_ID` in `/etc/os-release`;
5. `architecture` from `uname(2).machine`;
6. `reviewer_name`, `reviewer_uid`, `reviewer_gid`, and `reviewer_home` from
   `getpwnam(3)` for `ubuntu`.

Each value is observed inside the target's already-open local session,
independently of operator input. The contract defines normalization, required
H0 values, exact object-member order, compact JSON encoding, UTF-8 bytes with
no BOM or trailing newline, SHA-256, mismatch behavior, and the authority
boundary. `target-fingerprint-test-vectors.json` fixes the canonical bytes and
digest. `scripts/h0_target_fingerprint.py` implements the procedure without a
shell, network access, write, adapter, controller, or Ansible invocation.

## Human-owned operator input

The repository template remains schema-valid and non-authorizing. An authorized
human, not an agent, must create
`/private/tmp/azpr-h0-alv-operator-input.json` from that template. Before doing
so, the human must use the exact approved procedure reference and separately
authorize the exact disposable target. From the local session inside that target,
the human or their approved read-only operator process may run:

```bash
.integration-temp/offline-validation/venv/bin/python \
  scripts/h0_target_fingerprint.py observe
```

The human-supplied file must change `status` to
`SUPPLIED_REFERENCE_NOT_APPROVAL`; insert the normalized identity fields and
computed digest under `target`; truthfully set the two target-confirmation
booleans; and insert the separately governed reference, authorizer, issuance,
expiry, allowed stages, target digest, exact fingerprint-contract digest, and
procedure-approval assertion under `authorization_reference`. The check-mode
review remains false and null until a human reviews the exact H0-ALV-01 output.
The adapter booleans must remain unchanged. Validate without displaying the
file contents:

```bash
.integration-temp/offline-validation/venv/bin/python \
  scripts/h0_target_fingerprint.py validate-operator-input \
  --input /private/tmp/azpr-h0-alv-operator-input.json
```

This validation uses Draft 2020-12 JSON Schema with an enabled `date-time`
`FormatChecker`, recomputes the fingerprint, checks the contract hash and
authorization window, and returns only safe derived fields. A valid reference
still identifies and authorizes only the named stage attempt; it does not
approve or qualify the environment.

## Operator-assistance prompts

The source-only prompts under `operator-assistance/` automate the repetitive
read-only preparation around H0-ALV-00 without becoming stages or authority:

1. `H0-ALV-GUIDE-00` runs repository, contract, mapping, runtime,
   documentation, protected-hash, and inactive-adapter checks on the
   repository host. It stops for an attributable procedure-approval reference
   or for the human to deliberately enter the already-approved guest-local
   session.
2. `H0-ALV-GUIDE-01` is invoked by the human inside that local guest session.
   It performs deterministic fingerprint and platform/reviewer/runtime/input
   observations, then stops so the human can understand the exact target,
   decide whether to authorize it, and personally create the operator input.
3. `H0-ALV-GUIDE-02` returns to the repository host, validates the human file
   without displaying it, repeats drift and authority checks, and stops for a
   deliberate separate invocation of H0-ALV-00.

Every guide is `DRAFT_NOT_ACTIVE`, read-only, idempotent, and independently
invoked. The guides do not store resume state, enter a guest, create or infer
human authorization, create or modify the operator input, run Ansible, invoke
H0-ALV-00, or automatically start another prompt. Their results conform to
`operator-assistance-result.schema.json`; a result can describe the exact
human checkpoint but cannot satisfy it.

ADR-0014 provides the procedure-only approval channel used by
`H0-ALV-GUIDE-00`. Its canonical request, immutable review, schema,
non-authoritative template, and governed human-authored decision are committed
repository source. The read-only checker reports `APPROVED` and accepts only
`git:82ba27a1be4d1590e15f78a891568844639096dd:automation/approvals/procedure-decisions/AZPR_H0_TARGET_FINGERPRINT_V1.json`.
This repository-attributed decision approves only the exact procedure bytes.
It cannot approve a target or environment, authorize execution, activate an
adapter/controller, invoke a stage, or advance H0.

The irreducible human actions are limited to approving through an attributable
governed channel, deliberately entering the target-local session, deciding
whether the freshly observed guest is the intended disposable target,
authoring the operator input, confirming authorization attribution when it
cannot be checked automatically, and deliberately starting H0-ALV-00. All
technical validators and safe consistency checks remain agent-owned.

## Stage sequence

- `H0-ALV-00`: read-only authority, repository, runtime, input, and exact-target preflight.
- `H0-ALV-01`: run check mode with diff and bind the human review to exact output hashes.
- `H0-ALV-02`: run one bounded preflight/apply/apply sequence and require a zero-change second recap.
- `H0-ALV-03`: independently reconcile hashes and recaps without importing evidence or advancing H0.

## Validation

From the repository root:

```bash
python3 scripts/check_h0_ansible_live_prompt_pack.py
PYTHONPATH=src python3 -m pytest -q tests/test_h0_ansible_live_prompt_pack.py
```

The validator enforces the exact stage chain, inert authority, result schema,
required safety language, target-fingerprint contract and golden vector,
operator-input defaults, the exact three-guide assistance chain and human
checkpoint boundaries, and every hash in `SHA256SUMS.json`.
