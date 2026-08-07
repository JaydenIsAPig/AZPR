# AZPR v10.1 delivery provenance

Status: **PREPARATION EVIDENCE — NOT RUNTIME AUTHORITY**

This directory is the approved provenance destination for the AZPR v10.1
staged-hybrid integration decision. It preserves delivery identity, the
integration mapping, frozen reports, dependency evidence, and validation
results without making any delivered policy, roadmap, controller, installer,
provider, prompt, or production capability active.

The files below `frozen-delivery-reports/` are byte-exact delivery evidence.
Names such as `current-documents/` and statements inside those files describe
the delivered package only. They do not supersede the governed AZPR documents
under `docs/current/` and do not become repository authority by being retained
here.

## Staged-hybrid boundary

The transition is governed by ADR-0009 and
`automation/integration/v10.1/controller-transition-contract.json`:

1. **H0 — preparation:** inventory, map, preserve provenance, prepare the
   infrastructure-bound Ansible qualification environment, obtain independent
   Linux qualification evidence, and run read-only checks. No controller
   writer, and Ansible has no approval or qualification authority.
2. **H1 — repository integration:** after exact-hash human approval, apply the
   approved repository mapping on an isolated branch while both controllers
   remain inert. No controller writer.
3. **H2 — external qualification:** separately approve and qualify the external
   controller in read-only shadow mode on a hash-locked Linux runtime. No
   controller writer and no live-state transfer.
4. **H3 — controlled cutover:** only after all contract gates and a separate
   two-person cutover approval, atomically fence the repository controller and
   permit the external controller to become the sole writer.

At no point may both controllers write stage state or Git history. Runtime
state, secrets, keys, receipts, mutable ledgers, and `.codex-loop` state are not
transition artifacts.

## Staged prompt pack

The implementation transition is decomposed into ten fail-closed stages under
`automation/integration/v10.1/prompt-stages/`. The pack is a draft preparation
artifact, not active authority. It permits one named stage per invocation,
forbids automatic advancement, and leaves the selected 38 numbered prompts and
three appendices inactive until the approved H1 materialization stage.

Validate the pack before using its routing prompt or requesting mapping
approval:

```bash
.integration-temp/offline-validation/venv/bin/python \
  scripts/check_v10_1_prompt_stage_pack.py
```

The approved pre-Ansible transition base is
`ce80d335aef52c8900bd363bbcfacc1e497c0404`; its direct parent `d60e5d9...`
remains lineage, not the active transition base. The next lifecycle step is
H0 Ansible qualification-infrastructure preparation. `INT-00` remains blocked
until formal environment approval, two independently evidenced 120/120 Linux
runs, independence proof, audit-governance owner resolution, and final approval
of the regenerated exact mapping are complete. Until the first
controller-managed formal audit, the project owner approved
`docs/audits/README.md` as interim audit authority. `INT-04` must cause the
invoking controller to create the first immutable, commit-bound report and
controller-owned `docs/audits/index.json` together. The attached final-delivery
audit remains provenance only. The governance owner's actual name and role
must still be supplied; `[name/role]` is not a valid identity.

## Mapping assessment

Build the proposed mapping from the immutable staging mapping preserved beside
it as `integration/AZPR-v10.1-integration-path-mapping.staging-original.csv`:

```bash
./scripts/prepare_v10_1_mapping.py
```

Run the elementary structural-readiness assessment:

```bash
./scripts/check_v10_1_mapping_readiness.py
```

To retain a review copy of the result:

```bash
./scripts/check_v10_1_mapping_readiness.py \
  --output docs/delivery-provenance/v10.1/validation/mapping-readiness-assessment.json
```

Exit code zero means only that the mapping is structurally ready for review.
It does not mean the mapping is eligible for final approval, approve or
materialize the mapping, or mean that an external controller is qualified or
activatable. Final approval is deferred until the pre-`INT-00` H0 prerequisites
in the transition contract are independently evidenced. At that point, a human
approval must bind the exact post-Ansible mapping SHA-256 and approved base
commit in the approval location named by the transition contract. Codex does
not create that approval.

The human-created JSON at
`automation/approvals/v10.1-integration-path-mapping-approved.json` must set
`format_version` to `1.0`, `approval_kind` to
`AZPR_V10_1_INTEGRATION_MAPPING_APPROVAL`, and `approved` to `true`. It must
bind the assessment's exact `base_commit`, `mapping_sha256`, and
`transition_contract_sha256`, plus the contract's prompt archive SHA-256, the
SHA-256 of `automation/integration/v10.1/prompt-stages/SHA256SUMS.json`, the
SHA-256 of `validation/delivery-verifier-attempts.json`, a non-empty
`approved_by`, and a UTC `approved_at` timestamp. The checker parses and
compares every binding; file existence alone never satisfies the gate.
Replacing verifier evidence, changing the prompt pack, adding the Ansible
workstream, or regenerating the mapping invalidates an earlier approval target
and requires a new human review of the resulting hashes. The preserved
527-row `c84d45f...` mapping is historical prequalification evidence and must
not be approved as the current mapping.

## Validation runtime

The local Python 3.12 validation environment is intentionally ignored at
`.integration-temp/offline-validation/venv`. Its exact direct requirements,
complete transitive lock, and wheel hashes are recorded under `validation/`.
It was installed from the local wheelhouse with network indexes disabled and
hash checking required. Run repository checks with:

```bash
PYTHONPATH=src PYTHONNOUSERSITE=1 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 \
  .integration-temp/offline-validation/venv/bin/python -m pytest
```

The superseded macOS arm64 environment remains under
`validation/historical-macos/` as diagnostic provenance. The active validation
files now describe a local Ubuntu 24.04 ARM64 Multipass pre-qualification run:
both exact verifier modes passed 120/120 offline with unchanged, byte-identical
candidate trees. This closes the local reproducibility question only. It is not
one of the two formally accepted independent Linux runs because the environment
was not first approved and the local VM does not establish the independently
approved full host/image trust boundary.

## Contents

- `delivery-identity.json` binds the received archives and governing inputs by
  SHA-256.
- `automation/integration/v10.1/prompt-stages/` contains the inert transition
  router, ten bounded stage prompts, operator-input template, result schema,
  and byte-hash manifest.
- `integration/` contains the original inventory and reports, immutable
  historical prequalification mapping evidence, and the regenerable current
  structural-review mapping.
- `validation/` contains validation evidence and the reproducible dependency
  specification.
- `frozen-delivery-reports/` is one non-authoritative, byte-exact copy of the
  delivered report tree.
