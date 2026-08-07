# AZPR v10 Corrective Implementation — Fresh-Chat Execution Handoff

## Purpose

Use this handoff to create, curate, verify, and freeze a complete **AZPR v10 corrective development candidate** from the exact v9 implementation bundle.

This is a source-level security-development iteration. It is **not** authorization to install a trusted control plane, activate policy, generate or promote a roadmap, run Prompt 004, execute any numbered stage, connect to providers, or use production/customer data.

The new chat is expected to receive this handoff together with:

1. `V10-SECURITY-DEVELOPMENT-PROMPT.md`;
2. `AZPR-v9-pre-autonomous-security-assessment.md`;
3. `AZPR-v9-pre-autonomous-execution-evidence.json`;
4. the exact v9 delivery bundle and its direct artifacts/sidecars;
5. the AZ Permit Radar Master Operating Prompt, or the exact authenticated copy already embedded in the verified v9 lineage.

The two independent v9 reports are mandatory inputs. They are not optional background reading, and the v9 developer reports inside the candidate do not replace them.

## Role and governing responsibility

Act as the **AZ Permit Radar security development expert, trusted-control-plane architect, adversarial tester, release curator, and implementation reviewer**.

Produce a complete **v10 corrective implementation candidate** using the exact v9 candidate as the frozen source baseline.

You—not Codex—own:

- the threat model;
- security invariants;
- trust-root design;
- transaction and recovery design;
- affected-file/function/schema analysis;
- permitted and prohibited modification boundaries;
- acceptance-test oracles;
- mutation, substitution, concurrency, rollback, and fault-injection requirements;
- finding-closure decisions;
- release-verification design;
- artifact curation and packaging;
- promotion recommendations.

Codex may assist only with narrowly bounded implementation and test work under direct human supervision. Codex must not independently design, approve, weaken, remove, reclassify, or waive the controls governing its own execution.

## Mandatory disposition throughout v10 development

Preserve these flags in every current report, manifest, and machine-readable summary:

```json
{
  "pre_autonomous_staging": "FAIL",
  "semi_autonomous_codex_staging_ready": false,
  "trusted_pre_autonomous_installation_ready": false,
  "safe_for_unattended_execution_now": false,
  "full_autonomous_pathway_viable": true
}
```

The only permitted status upgrade during this work is:

```text
READY_FOR_INDEPENDENT_V10_SOURCE_REASSESSMENT
```

That status may be used only after all source-level definition-of-done requirements below are satisfied. It does **not** authorize installation, host qualification, semi-autonomous staging, or prompt execution.

## Authority and conflict handling

Use authority by subject rather than silently merging conflicting documents.

### Product, architecture, documentation, and safety policy

The **AZ Permit Radar Master Operating Prompt** is governing.

### Known security findings and observed test facts

The independent files are authoritative for the v9 assessment scope:

- `AZPR-v9-pre-autonomous-security-assessment.md`;
- `AZPR-v9-pre-autonomous-execution-evidence.json`.

Treat every independent reproduction and every Critical/High finding in those files as open until the exact v10 call path rejects it under a release-blocking test.

### V10 implementation procedure

`V10-SECURITY-DEVELOPMENT-PROMPT.md` provides the detailed implementation plan, but it is subordinate to:

1. current user instructions;
2. the governing Master Operating Prompt;
3. this handoff’s readiness limits and curation contract;
4. the independent v9 findings and observed evidence.

If the v10 development prompt conflicts with an independent finding, weakens an oracle, changes a readiness flag, omits an affected trust boundary, or treats a real-infrastructure gate as already closed, stop that workstream and produce a conflict table. Do not silently choose the easier requirement.

### Artifact identity

The actual bytes, safe archive metadata, authenticated manifests, and independently recomputed hashes define artifact identity. Filenames and self-reported claims do not override the bytes.

### Developer-authored v9 reports

Treat v9 implementation reports as claims to verify, not as authority. Preserve them for provenance, but do not copy their closure labels or test counts into v10 without fresh verification.

## Exact v9 baseline to verify before any modification

Expected v9 artifacts:

| Artifact | Expected size | Expected SHA-256 |
|---|---:|---|
| Outer `v9_deliverables(1).zip` | 1,250,456 bytes | `ec74c0ee846f32eb40c42f55578a8a407cb27245cffbfbb67e08315e08c7e415` |
| `AZPR-autonomous-execution-primed-draft-v9.zip` | 880,793 bytes | `eeb5a826ab20aca7e4e618be435af2bbd51ca4d911dae3ff78d74a4d56e4f631` |
| `AZPR-autonomous-execution-primed-draft-v9-reports.zip` | 255,626 bytes | `8206b3c91da3a9d545bc5744480439d11f6b61589fbb6365c64d0a74e786745b` |
| Prompt archive bytes | 152,720 bytes | `3b235cb7e33ca409241ff26523f60f8fee89cec524b3f09e91a69927a0aa4880` |

Expected structural facts:

- outer delivery: 32 members, including 16 `__MACOSX/._*` packaging-noise members;
- implementation ZIP: 234 regular members, consisting of 233 authenticated entries plus `SHA256SUMS.json`;
- prompt set: prompts `001` through `038` plus Appendices A–C;
- all prompt archive copies are byte-identical;
- seven of eight outer sidecars resolve and match;
- the prompt sidecar points to a filename absent from the outer delivery even though the intended prompt bytes are present;
- no active canonical policy and no promoted roadmap are present;
- the v9 release is unsigned and is a development candidate only.

The unchanged governing Master Operating Prompt source hash inherited from the verified v8/v9 lineage is expected to be:

```text
37800ebde204070d1ac20c2cfff5c809ee4f318cfcc44312514c393077334ae6
```

Recompute it from the supplied source; do not rely on this line alone.

### Baseline intake requirements

Before editing:

1. hash every top-level input;
2. safely inspect every archive member;
3. reject path traversal, absolute paths, duplicate names, links, devices, special files, and unsafe metadata;
4. freshly extract into a disposable non-root workspace;
5. verify all sidecars and internal manifests;
6. inventory every file;
7. verify all prompt copies byte-for-byte;
8. confirm the absence of an active canonical policy and active/promoted roadmap;
9. preserve a read-only frozen copy of the exact v9 source baseline;
10. reproduce the independent v9 defects before patching.

If exact v9 source bytes are not supplied, or the implementation ZIP hash does not match, do not attempt a source-level v10 correction from reports alone.

## Independent v9 decision that v10 must preserve

The independent decision was:

```json
{
  "pre_autonomous_staging": "FAIL",
  "semi_autonomous_codex_staging_ready": false,
  "trusted_pre_autonomous_installation_ready": false,
  "safe_for_unattended_execution_now": false,
  "full_autonomous_pathway_viable": true,
  "permitted_now": "isolated non-root source review and supervised corrective development only"
}
```

V9 contained material improvements, but one Critical and three High risks remained, along with three Medium curation/test risks. V10 must close the source-level blockers without converting missing real qualification into a paper PASS.

## V9 findings that v10 must address

### AZPR-V9-IND-F01 — CRITICAL: caller-selected probe trust root and unpinned probe policy

**Observed v9 behavior**

A fresh caller-generated Ed25519 key, caller-created keyring, arbitrary probe-policy hash, and nine fabricated all-PASS probe envelopes were accepted by `verify_probe_manifest`. A mutated signature was rejected. The defect is therefore not absent cryptography; it is authentication against a caller-selected root.

Affected v9 paths include:

- `operator-tools/verify_v9_cleanroom_prerequisites.py`;
- `operator-tools/v9_probe_boundary.py`;
- `operator-tools/v9_external_signer_client.py`;
- `trusted-installation/v9_binding.py`;
- `trusted-installation/install.py`.

**V10 invariant**

A qualification submitter must not be able to define, replace, rotate, or self-authorize the probe service, probe keyring, probe policy, revocation state, or attestation used to authenticate qualification evidence.

The external receipt signer and installer must independently verify the same approved probe authority and exact policy version. A valid signature under an unapproved key must fail.

**Required architecture**

- Define a versioned canonical **qualification artifact set** rather than treating the old count of 39 as permanently complete.
- Add, at minimum:
  - approved probe keyring;
  - probe-policy artifact;
  - probe-service identity;
  - probe-service attestation;
  - probe-key role constraints;
  - rotation/revocation state;
  - validity interval and policy version;
  - host/candidate/challenge binding.
- Bind those identities into:
  - canonical qualification manifest;
  - raw probe envelope and envelope manifest;
  - unsigned receipt;
  - external signer request;
  - signed receipt;
  - installation authorization;
  - installer preflight;
  - phase-transition state;
  - installed-generation manifest and receipt.
- The external signer must reject any request whose probe authority or policy is omitted, caller-created, stale, revoked, wrong-role, wrong-host, wrong-candidate, wrong-challenge, or not independently approved.
- The installer must reverify the probe signatures, authority, policy, receipt binding, and freshness from pinned roots before the first state-changing write.
- A runtime aggregate hash is acceptable only if its canonical membership is explicit, versioned, collision-safe, and each enforcing consumer verifies it. Merely recording an aggregate is insufficient.

**Release-blocking exit tests**

- caller-generated probe keyring plus internally valid all-PASS envelopes;
- arbitrary caller policy;
- omitted probe-keyring binding;
- omitted policy binding;
- stale and revoked key;
- wrong signer role;
- wrong candidate, host, challenge, or validity interval;
- substituted keyring/policy after receipt creation;
- external signer unable to validate an unbound probe authority;
- installer unable to reverify the exact probe authority;
- rotation and revocation transitions, including rollback to an older accepted key.

Every case must fail before a receipt, authorization reservation, installation state, or phase-transition state is created.

### AZPR-V9-IND-F02 — HIGH: bootstrap authority manifest and key follow symlinks

**Observed v9 behavior**

`verify_bootstrap_roots` accepted both the signed bootstrap manifest and its Ed25519 authority public key through symlink paths. The downstream root artifacts used stronger handling, but the two roots of the root set were read with ordinary path reads.

Affected v9 path:

- `trusted-installation/v9_binding.py`, especially the bootstrap-root verification path.

**V10 invariant**

The bootstrap authority manifest, bootstrap authority public key, and every security-critical ancestor must be resolved from an independently provisioned trusted location without following symlinks, accepting hard links, crossing writable ancestors, or permitting time-of-check/time-of-use replacement.

**Required architecture**

- Use descriptor-relative, no-follow resolution such as `openat2` with restrictive resolve flags or a carefully reviewed `openat`/`O_NOFOLLOW` walk.
- Require regular file, expected owner, one link, restrictive mode, trusted filesystem semantics, and non-writable trusted ancestors.
- Compare device, inode, size, mode, ownership, and timestamps before/after read where needed.
- Keep descriptors open through verification/consumption or verify exact content identities at the consuming call path.
- Reject unsupported platforms or filesystems fail-closed; do not fall back to `Path.read_bytes()` for trust roots.
- Document bootstrap provisioning and key-rotation ceremony separately from caller-controlled installation inputs.

**Release-blocking exit tests**

- symlink at leaf and every ancestor;
- hard link;
- writable parent and grandparent;
- wrong owner or mode;
- rename/swap race;
- authority-key replacement paired with a matching forged manifest;
- stale manifest sequence;
- alternate path alias;
- unsupported no-follow primitive;
- filesystem semantics that cannot satisfy the invariant.

All must fail before any root is trusted or installation state is touched.

### AZPR-V9-IND-F03 — HIGH: official verifier hardcodes `/root`

**Observed v9 behavior**

On a fresh extraction under an unprivileged account:

```text
PYTHONDONTWRITEBYTECODE=1 python3 VERIFY-V9-CANDIDATE.py
```

failed with `PermissionError` because `TemporaryDirectory(..., dir='/root')` was hardcoded.

Affected v9 paths:

- `VERIFY-V9-CANDIDATE.py`;
- verifier instructions in `README.md` and current release documents.

**V10 invariant**

The full release verifier must run reproducibly as a dedicated unprivileged reviewer from a fresh read-only extraction without access to root-owned state, credentials, signing keys, control sockets, or production configuration.

**Required architecture**

- Remove all hardcoded `/root` assumptions.
- Create a mode-`0700`, reviewer-owned temporary root in an explicitly selected safe location.
- Sanitize environment variables and prohibit implicit credential/config discovery.
- Run sensitive tests one per isolated process group with hard wall-clock deadlines, bounded stdout/stderr, and descendant cleanup.
- Prevent source-tree mutation, bytecode/cache creation, test-order dependence, and shared permission mutations.
- Treat hangs, missing test IDs, unexpected skips, leaked descendants, output overflow, cache files, or source-tree changes as release failures.
- Emit a machine-readable catalog showing exact tests, subtests, black-box cases, schema checks, prompt checks, manifest checks, outcomes, durations, and environmental limitations.

**Release-blocking exit tests**

- full verifier completes as a dedicated non-root account;
- source tree is read-only;
- `PYTHONDONTWRITEBYTECODE=1` and cache-free checks pass;
- no `/root` access is required;
- no inherited credentials or user Git/Python configuration are consumed;
- each test is process-isolated and timeout-bounded;
- fresh-extraction verification produces the same authenticated result as source-tree verification.

Do not run the verifier as root merely to obtain a green result.

### AZPR-V9-IND-F04 — HIGH gate: mandatory real qualification remains absent

**Observed v9 state**

V9 is unsigned and does not contain genuine evidence for:

- organization release authority;
- dedicated hardened qualification host;
- production external signer/HSM;
- rollback-resistant remote anchor;
- real power-loss, reboot, disk, inode, remount, and anchor-outage exercise;
- reproducible supply-chain mirror/SBOM/provenance/image/registry proof;
- real key-generation/custody/rotation/revocation ceremonies;
- approved canonical policy;
- Prompt 004 result;
- promoted roadmap;
- actual AZPR application/provider qualification.

**V10 disposition**

This remains an `OPEN_GATE` unless actual independent evidence is supplied. V10 may implement exact schemas, clients, verification logic, templates, tests, and qualification contracts, but must not claim these real events occurred.

Keep source-level closure distinct from operational qualification. A source-level v10 PASS can make the candidate eligible for a new independent reassessment only.

### AZPR-V9-IND-F05 — MEDIUM: sidecar/member filename mismatch and AppleDouble noise

V10 must:

- use one canonical prompt-archive filename;
- ensure every sidecar target exists under that exact name;
- regenerate all manifests and sidecars from the final frozen bytes;
- remove `__MACOSX`, `._*`, caches, bytecode, editor backups, temporary files, sockets, and local configuration;
- verify the outer delivery from a fresh extraction.

Renaming the prompt archive is a packaging change only. It must not silently change prompt bytes or imply policy approval.

### AZPR-V9-IND-F06 — MEDIUM: stale v8-titled current documents inside v9

V10 must replace or explicitly archive stale current documents, including the v9 files identified as retaining v8 titles/wording:

- `PROMOTION-GATES.md`;
- `PRIORITY-FIX-DISPOSITION.md`;
- `LINGERING-CONCERNS.md`.

Requirements:

- current operational documents must be v10-specific;
- legacy v8/v9 documents must live under an explicit historical/legacy location;
- current documents must contain the exact frozen v10 hashes and current finding statuses;
- add a machine-readable current-document index;
- release verification must fail on stale current-version labels, stale hashes, or multiple documents claiming to be current.

### AZPR-V9-IND-F07 — MEDIUM: tests miss trust-root substitution cases

V10 must convert every independent v9 reproduction into a release-blocking regression. Tests must validate independent authority, not only consistency beneath a caller-supplied root.

Required new negative oracles include:

- caller-generated probe root/policy;
- omitted probe authority/policy receipt binding;
- external signer rejection of unbound roots;
- bootstrap manifest/key symlink and ancestor substitution;
- hard links, ownership/mode errors, and rename races;
- least-privilege complete verifier execution.

Mutation tests must prove that deleting or bypassing each binding check causes a test failure.

## Carry-forward v8 regression checklist

Do not limit v10 to the newly found v9 defects. Re-test every inherited high-risk boundary because the v10 changes compose with them.

| Prior finding | v9 status | Required v10 treatment |
|---|---|---|
| `AZPR-V8-F01` no-secret qualification and external signing | `PARTIALLY_CLOSED` | Re-test with pinned probe authority and malicious target binaries; prove no keys/secrets/host control are available. |
| `AZPR-V8-F02` installer global serialization | `PARTIALLY_CLOSED` | Run the full concurrent-process and interruption/fault matrix against the exact v10 installer. |
| `AZPR-V8-F03` complete qualification binding | `PARTIALLY_CLOSED` | Replace the stale “39 is complete” assumption with a versioned complete set including new probe trust artifacts and all actual consumed inputs. |
| `AZPR-V8-F04` rollback-resistant consumption | `PARTIALLY_CLOSED` | Preserve signed journal and anchor semantics; test deletion, truncation, restore, fork, replay, stale/conflicting heads, and recovery. |
| `AZPR-V8-F05` first install qualification-only | `CLOSED_SOURCE_LEVEL` | Preserve and re-test; no first-install policy activation and no production loader use of qualification-only generations. |
| `AZPR-V8-F06` machine-derived evidence | `PARTIALLY_CLOSED` | Recompute decisive results from strict raw evidence; reject stale, contradictory, irrelevant, or incomplete signed PASS data. |
| `AZPR-V8-F07` atomic key lifecycle | `PARTIALLY_CLOSED` | Integrate and test the epoch across all real consumers; prove rotation, revocation, recovery, and stale-key rejection. |
| `AZPR-V8-F08` real qualification evidence | `NOT_CLOSED` | Keep open until genuine organization/host/signer/anchor/supply-chain/application evidence exists. |

Use the original v8 consultation material embedded in the lineage only as a regression reference. The independent v9 reports are the immediate source of observed v9 behavior.

## Required implementation procedure

### 1. Verify and freeze v9

- Safely inspect and extract all supplied v9 artifacts.
- Verify exact hashes, sidecars, internal manifests, prompt identity, schemas, and current test catalogs.
- Preserve a read-only frozen baseline.
- Record all packaging mismatches without silently repairing them.

### 2. Reproduce before patching

Using temporary harnesses outside the candidate tree, reproduce at minimum:

- acceptance of caller-generated probe keyring/policy and fabricated PASS envelopes;
- rejection of a mutated signature, confirming the defect is root selection rather than missing cryptography;
- acceptance of symlinked bootstrap manifest and authority key;
- non-root verifier failure caused by `/root`;
- any relevant inherited v8 blocker whose call path will change.

If a reproduction differs, trace the exact call path and explain why. Do not erase the oracle.

### 3. Design before implementation

Produce architecture and invariant specifications before code changes for:

- probe authority, policy, attestation, rotation, and revocation;
- canonical versioned qualification artifact set;
- external signer verification contract;
- installer re-verification contract;
- bootstrap descriptor-resolution and provisioning model;
- non-root release-verifier isolation model;
- installer/anchor/key-lifecycle interactions affected by the new bindings;
- current-document and release-package curation model.

Each design must state:

- assets and threat actors;
- trust roots and who provisions them;
- caller-controlled inputs;
- exact signed/hash-bound fields;
- first state-changing boundary;
- TOCTOU protections;
- rollback/replay protections;
- failure and recovery states;
- unsupported-platform behavior;
- test oracles;
- compatibility and migration impact.

### 4. Implement bounded workstreams

For each workstream:

1. enumerate exact allowed modification paths;
2. create a dedicated branch/worktree or equivalent isolated change set;
3. let Codex edit only the approved paths;
4. review every security-critical diff manually;
5. run focused negative and mutation tests;
6. commit or record the workstream independently;
7. update the finding matrix with evidence, not claims.

### 5. Test composed behavior

Test interactions among:

- probe authority binding;
- external receipt signing;
- installer preflight and authorization reservation;
- global installer lock;
- anchored consumption state;
- first-install qualification-only mode;
- policy phase transition;
- evidence derivation;
- key lifecycle;
- bootstrap rotation/recovery;
- release verification and fresh-extraction packaging.

Include black-box, substitution, mutation, concurrency, exhaustion, interruption, recovery, and fault-injection tests.

### 6. Curate the v10 release candidate

- Remove platform metadata, caches, bytecode, temporary files, local state, credentials, sockets, and reports not intended for delivery.
- Preserve the prompt bytes unless a separately authorized policy decision explicitly changes them.
- If the prompt archive filename changes, update every manifest/sidecar/reference and prove all copies remain byte-identical.
- Replace stale current documents and move historical documents to an explicit legacy location.
- Generate all v10 reports from the final candidate, not from a pre-freeze worktree.
- Create a non-self-referential delivery-manifest model and matching sidecars so every referenced path exists and verifies.
- Mark the delivery as unsigned unless a genuine organization release signer was actually used.

### 7. Verify source and fresh extraction

Run the full catalog:

- once against the frozen source candidate;
- once against a newly created delivery archive after safe fresh extraction;
- as an unprivileged account;
- with a read-only source tree;
- with hard timeouts and process-tree cleanup;
- without credentials, production configuration, or network access except an explicitly isolated test endpoint.

Source and fresh-extraction inventories, hashes, test IDs, and results must match where designed to match. Any unexplained difference is a release failure.

### 8. Freeze exact v10 bytes

After all checks:

- regenerate authenticated internal manifests;
- regenerate top-level delivery manifest and sidecars;
- recompute every top-level SHA-256;
- verify no file changes after hashing;
- produce a final immutable inventory;
- set status to either:
  - `READY_FOR_INDEPENDENT_V10_SOURCE_REASSESSMENT`, or
  - `V10_DEVELOPMENT_INCOMPLETE_NOT_READY_FOR_REASSESSMENT`.

Do not declare pre-autonomous staging readiness.

## Permitted modification surface

After confirming exact v9 paths, modifications may be made only where required by the approved v10 workstream design, principally:

- `operator-tools/` probe, qualification, evidence, signing-client, anchor, and key-lifecycle code;
- `trusted-installation/` binding, bootstrap, installer, transaction, phase-transition, and recovery code;
- security-critical schemas under `repository-overlay/automation/schemas/`;
- the top-level release verifier and narrowly related release-catalog modules;
- narrowly required controller/external-runner loader checks needed to consume the new qualified artifact-set version;
- tests, adversarial harnesses, mutation tests, fault tools, semantic fixtures, and process-isolated verifier catalogs;
- current v10 reports, current-document index, delivery manifest, sidecars, and packaging scripts;
- new supporting modules dedicated to the approved architecture.

Before any Codex edit, generate an exact allowed-path list. Reject or revert modifications outside it.

## Prohibited actions and shortcuts

Do not:

- modify the independent v9 assessment or evidence report;
- rewrite or weaken an acceptance test to obtain a pass;
- remove, skip, monkey-patch, or reclassify an independent reproduction;
- run the release verifier as root to bypass the `/root` defect;
- pin a probe authority by merely hashing a caller-supplied keyring path at runtime;
- accept a self-signed or caller-created probe-service attestation;
- let the external signer trust fields it cannot independently verify;
- record a binding that the signer or installer never consumes;
- retain a hard-coded artifact count if the actual trust set changes;
- fall back to ordinary path reads when no-follow/ownership guarantees are unavailable;
- activate trusted installation state;
- run the privileged installer against a real host;
- use real signing keys in the qualification probe boundary;
- approve or activate a canonical policy;
- execute Prompt 004;
- generate or promote a roadmap;
- run a numbered Codex stage through the trusted controller;
- connect to production providers or targets;
- use production credentials or customer data;
- claim organization signing, dedicated-host qualification, HSM custody, remote anchoring, supply-chain qualification, key ceremony, provider qualification, or application qualification without actual independent evidence;
- silently change the 41 prompt files or governing Master Operating Prompt;
- include an active canonical policy or promoted roadmap in the development candidate;
- allow Codex to design or approve its own trust roots, containment, authorization, qualification, or test oracles.

## Stop conditions

Stop the affected workstream and report clearly if:

- exact v9 artifact identity does not match;
- the v9 source bundle is missing and only reports are available;
- either independent v9 report is missing or unreadable;
- `V10-SECURITY-DEVELOPMENT-PROMPT.md` conflicts with the governing policy, this handoff, or an independent v9 finding;
- an independent reproduction cannot be established through the actual call path;
- a required trust root remains caller-selectable;
- a security-critical artifact is only recorded but not verified by each enforcing consumer;
- required no-follow/ownership/filesystem primitives are unavailable and the code proposes an unsafe fallback;
- a fix weakens an inherited control;
- a test oracle cannot distinguish an approved independent root from an attacker-created root;
- Codex modifies an unapproved path;
- any Critical/High regression appears;
- a release test hangs, skips unexpectedly, leaks descendants, mutates the source, or requires root;
- source and fresh-extraction verification diverge;
- current documents retain stale v8/v9 labels or hashes;
- the final archive contains unsafe metadata or unresolved sidecars.

Do not stop all source work solely because real host/HSM/anchor infrastructure is unavailable. Complete honest source-level enforcement, schemas, test contracts, and tools, then leave the real event as an explicit qualification dependency.

## Evidence required for each closure claim

For every `AZPR-V9-IND-F01` through `AZPR-V9-IND-F07`, and every carried `AZPR-V8-F01` through `AZPR-V8-F08`, report:

- status: `CLOSED_AND_TESTED`, `CLOSED_SOURCE_LEVEL`, `PARTIALLY_CLOSED`, `NOT_CLOSED`, `REGRESSION`, or justified `NOT_APPLICABLE`;
- affected paths, functions/classes, schemas, and trust boundaries;
- exact invariant;
- architecture and transaction/recovery description;
- approved Codex paths and actual changed paths;
- exact test IDs and commands;
- raw observed results, exit codes, and evidence hashes;
- negative, mutation, substitution, concurrency, interruption, rollback, recovery, and fault evidence as applicable;
- source-tree and fresh-extraction outcomes;
- remaining host, organization, policy, supply-chain, signer, anchor, and application limitations;
- whether independent reassessment is still required.

A passing self-authored test is not sufficient by itself. Every prior independent reproduction must become a release-blocking regression through the exact enforcing call path.

## Required v10 deliverables

Produce a self-contained development delivery with canonical, internally consistent names. At minimum include:

1. `AZPR-autonomous-execution-primed-draft-v10.zip` with authenticated internal manifest.
2. Exact SHA-256 sidecar for the implementation ZIP.
3. `AZPR-autonomous-execution-primed-draft-v10-reports.zip` with authenticated internal manifest.
4. Exact SHA-256 sidecar for the reports ZIP.
5. Canonically named prompt archive plus sidecar, with proof that all copies are byte-identical and contents are unchanged unless independently authorized.
6. `AZPR-v10-delivery-manifest.json` plus sidecar, resolving every top-level artifact under exact delivered filenames.
7. Source-tree verification JSON.
8. Fresh-extraction verification JSON.
9. Release-verification JSON and human-readable summary.
10. `V10-FINDING-CLOSURE-MATRIX.md` covering v9 F01–F07 and carried v8 F01–F08.
11. `V10-SECURITY-INVARIANTS-AND-ARCHITECTURE.md`.
12. `V10-PROBE-TRUST-ROOT-AND-EXTERNAL-SIGNING-REPORT.md`.
13. `V10-QUALIFICATION-ARTIFACT-BINDING-MATRIX.md`, using the actual versioned artifact set rather than assuming 39 remains complete.
14. `V10-BOOTSTRAP-ROOT-HARDENING-REPORT.md`.
15. `V10-NONROOT-RELEASE-VERIFIER-REPORT.md`.
16. Installer transaction/concurrency/rollback/fault regression report.
17. Evidence-derivation and key-lifecycle integration report.
18. Adversarial, mutation, substitution, and test-catalog report with commands and outcomes.
19. Affected files/functions/schemas and Codex modification-boundary report.
20. `MAJOR-CHANGES.md` with v10-current content.
21. `SECURITY-DECISIONS.md` with v10-current content.
22. `KNOWN-LIMITATIONS-AND-QUALIFICATION-DEPENDENCIES.md` with explicit open real-world gates.
23. `CURRENT-DOCUMENT-INDEX.json` identifying exactly one current document per governed category.
24. `V10-QUALIFICATION-HANDOFF.md` describing what remains before dedicated-host qualification.
25. Final verification record confirming safe archive metadata, exact hashes, no active policy/roadmap, false readiness flags, and unsigned-development status unless genuinely signed.

If filenames differ for a justified reason, provide an exact mapping and ensure every manifest, sidecar, report, and verifier uses the delivered name. No unresolved aliases are allowed.

## Definition of done for v10 source development

V10 is ready only for a new independent source-level reassessment when all of the following are true:

- the exact v9 baseline was verified and frozen;
- every independent v9 blocker was reproduced before patching;
- caller-created probe roots, policies, service identities, and attestations fail closed;
- probe authority, policy, revocation, and service identity are independently pinned and transitively bound through signer, receipt, authorization, installer, phase state, and installed generation;
- the versioned qualification artifact set includes every actual security-critical consumed input;
- bootstrap manifest/key and all trusted ancestors use no-follow, ownership, link-count, mode, and TOCTOU-safe handling;
- the complete release verifier passes as a dedicated unprivileged reviewer from a fresh read-only extraction;
- every independent v9 reproduction is a release-blocking regression;
- inherited installer serialization, rollback resistance, qualification-only first install, evidence derivation, and key-lifecycle controls remain intact and are re-tested;
- all current documentation is v10-specific and exactly hash-bound;
- prompt copies remain byte-identical and no unauthorized prompt/policy change occurred;
- source and fresh-extraction verification pass with exact inventories and no unexplained differences;
- manifests and sidecars resolve every exact filename;
- archives contain no unsafe metadata or platform noise;
- no active canonical policy or promoted roadmap exists;
- readiness flags remain false;
- absent real infrastructure is reported as an open qualification dependency, not as closed;
- final bytes are frozen and exact hashes are supplied for independent consultation.

Even after this definition is met, v10 is **not** automatically ready for semi-autonomous Codex staging. The next event is an independent v10 security reassessment. If that assessment passes the source candidate, the project may then proceed to organization signing and dedicated-host qualification in the required order.

## Post-v10 qualification order if independent reassessment passes

The expected trust chain remains:

```text
organization release authority
  -> signed exact v10 release
  -> independently provisioned bootstrap authority
  -> pinned probe service, keyring, policy, attestation, and revocation state
  -> dedicated no-secret qualification host/boundary
  -> machine-derived immutable probe evidence
  -> independently controlled external receipt signer
  -> qualified rollback-resistant remote anchor
  -> one-use installation authorization
  -> QUALIFICATION_ONLY installation
  -> launcher/fault/supply-chain/key-custody qualification
  -> approved canonical policy derived from the Master Operating Prompt
  -> manually executed Prompt 004 decision
  -> hash-bound independently reviewed roadmap
  -> isolated non-production human-supervised dry runs
  -> later separate unattended-execution promotion decision
```

No later step may be used to excuse a missing earlier trust root.

## Work style

- Provide concise progress updates during long work.
- Surface newly found Critical/High issues immediately.
- Distinguish proven facts from developer claims and from unexercised design.
- Use temporary adversarial harnesses outside the candidate source tree.
- Do not promise background work or ask the user to wait.
- Complete as much as possible in the current response.
- State precisely what could not be independently verified.
- Never substitute documentation for executable enforcement.
