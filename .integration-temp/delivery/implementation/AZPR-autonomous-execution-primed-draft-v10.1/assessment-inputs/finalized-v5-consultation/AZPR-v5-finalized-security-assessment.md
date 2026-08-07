# AZPR v5 Finalized Security Assessment

Generated: `2026-07-27T00:53:28.658318+00:00`

## Executive verdict

**Promotion decision:** `NOT_READY`

```json
{"safe_for_unattended_execution_now": false}
```

The v5 draft is a meaningful improvement over v4 and is appropriately packaged as a setup-blocked implementation candidate. It is **not genuinely safe for controlled autonomous prompt execution**. The independent review reproduced **five failures in five targeted adversarial tests**, including two critical trust-boundary failures:

1. an agent can hide persistent worktree artifacts through Git exclude metadata so they evade path enforcement, validation, clean-worktree checks, and abandonment cleanup; and
2. the root installer accepts private signing keys that are readable by the configured non-root agent.

Three additional high-severity failures leave supply-chain attestations, external-runner authorization roots, and the governing canonical policy insufficiently bound. Because any shared critical control-plane defect makes all prompts unacceptable for unattended execution, all 41 prompt records remain `UNACCEPTABLE_FOR_UNATTENDED_EXECUTION` even though their text is generally strong.

Do **not** install this candidate as a trusted production control plane, generate/promote a roadmap, execute Prompt 004, run an autonomous repository stage, or register/apply an external operation until P0 and P1 fixes are independently retested.

## Scope and governing method

The review followed `Pasted markdown.md` as the mandatory independent protocol and treated `AZ-Permit-Radar-Master-Operating-Prompt.docx` as the governing product, architecture, safety, and implementation policy. The primary candidate was `AZPR-autonomous-execution-primed-draft-v5(1).zip`; the separate v5 reports ZIP was treated as supporting evidence rather than proof.

Work performed:

- safe ZIP metadata inspection and fresh extraction;
- top-level and security-critical SHA-256 hashing;
- complete internal manifest verification;
- byte-for-byte prompt archive/overlay comparison;
- comparison against the v4 candidate;
- schema, controller, runtime, installer, validator, evidence, external-runner, operator-tool, and test call-path review;
- submitted verifier and test execution;
- a separate temporary adversarial harness outside the candidate tree;
- prompt-by-prompt metadata/control review for 001–038 and Appendices A–C;
- historical and v4 regression classification;
- architecture, project-safety, and promotion assessment.

## Artifact identity

| Input | Size | SHA-256 | Result |
|---|---:|---|---|
| `AZPR-autonomous-execution-primed-draft-v5(1).zip` | 606883 | `35526b87501d54c661bfbeb1556268b12191ca4d9e5b4333511cbd5b0c168914` | Sidecar match; 147 safe members |
| `AZPR-autonomous-execution-primed-draft-v5-reports(1).zip` | 32593 | `d28a6e3b98ed9b07c6faa6e1d66c75db77d68db8f128ad8ce2471e38dfca52ce` | Sidecar match; 19 safe members |
| `AZPR-autonomous-execution-primed-draft-v5.zip(1).sha256` | 112 | `b2921bf72f6b7876b11644bd395ea1857d4d654af614f62d1e8a5e4163a9cc05` | Sidecar text names the candidate ZIP and matches its SHA-256 |
| `AZPR-autonomous-execution-primed-draft-v5-reports.zip(1).sha256` | 120 | `d51361c04b39d94bc1e847e43153c95c309f0e9caad3fc77d1a61eb4f234ebcf` | Sidecar text names the reports ZIP and matches its SHA-256 |
| `Pasted markdown.md` | 11600 | `36f637230dfa6014b45186f3df1e854de4740fcb25e7a2eb226071d948282331` | Governing review protocol |
| `AZ-Permit-Radar-Master-Operating-Prompt.docx` | 8409 | `37800ebde204070d1ac20c2cfff5c809ee4f318cfcc44312514c393077334ae6` | Governing project policy source |
| Embedded prompt ZIP | — | `3b235cb7e33ca409241ff26523f60f8fee89cec524b3f09e91a69927a0aa4880` | 41 files; byte-identical to repository overlay |

Archive checks found no duplicate members, traversal paths, absolute paths, symlinks, devices, FIFOs, sockets, or other unsafe member types. The candidate manifest contains **146 authenticated entries** and verified with no missing, extra, or mismatched files. The complete 147-file inventory is in `AZPR-finalized-security-verification-summary.json`.

### Security-critical file hashes

| Path | Bytes | SHA-256 |
|---|---:|---|
| `trusted-installation/install.py` | 30142 | `494bf16f2b1cf673589edd472ec76d688b28a4ebbe7202fadc620e7b02d8a7d5` |
| `trusted-controller/controller.py` | 148422 | `afb2c37137e8c5527044285341064593c6135db305616a7f5d4bb32c3c641b39` |
| `trusted-controller/secure_runtime.py` | 65562 | `97e8ded35e5e3780b6f61ad8fd5ebf32b342b46412d0501be2e05efec1ce41ae` |
| `trusted-controller/evidence_registry.py` | 13218 | `840580423a60758f9222cc3f0f6fc86565ed3998a7e5a90ee69260a1c1980aa3` |
| `trusted-validation-runner/trusted_validation_runner.py` | 24120 | `7c4354544410db1dbe388c16179c7f15624819ec468a64bc93bdc4daa2d008b9` |
| `external-capability-runner/capability_runner.py` | 28503 | `f286cba260195e16c0a1178085667cfb89eeff415726b84b0c2774e9762d995b` |
| `external-capability-runner/secure_runtime.py` | 65562 | `97e8ded35e5e3780b6f61ad8fd5ebf32b342b46412d0501be2e05efec1ce41ae` |
| `VERIFY-AUTONOMOUS-DRAFT.py` | 11670 | `e5d2bbdce1bde1479fada154c0f06b159ed67fd44bda0e261feea44817af7c04` |
| `SHA256SUMS.json` | 20642 | `65c34091c9b5c7ce368767e9c73db2bb168db5b3fbc2e0eb15b50683d09cce8c` |
| `markdown-prompts-autonomous-priming-draft.zip` | 152720 | `3b235cb7e33ca409241ff26523f60f8fee89cec524b3f09e91a69927a0aa4880` |

### Candidate/baseline distinction

- **New finalized candidate:** v5 implementation ZIP and v5 reports ZIP.
- **Previous baseline:** v4 candidate used only for regression/diff context.
- **Historical authority:** original Master Operating Prompt and prior security handoff/report materials.
- **Generated outputs:** the four reports produced by this assessment.

Relative to v4, the clean v5 tree has 8 added, 1 removed, and 43 changed files. The 41 prompts themselves remain unchanged and internally consistent.

## Submitted verification versus independent verification

### Submitted checks

- `python VERIFY-AUTONOMOUS-DRAFT.py` returned a source-tree PASS with 146 manifest entries, 30 compiled Python files, 28 schemas, 4 semantic fixtures, 7 validation profiles, 38 numbered prompts, 3 appendices, and 57 security tests.
- `python -m pytest -q` produced `57 passed, 16 subtests passed`.
- No active roadmap or canonical policy is included, and the candidate preserves the false unattended-execution flag.

### Independent adversarial harness

The harness was created at `/mnt/data/azpr_v5_review/independent_v5_harness.py`, outside the candidate tree. Result: **5/5 reproduced**.

| Test | Outcome | Key observation |
|---|---|---|
| `world_readable_private_key_accepted` | `REPRODUCED` | Mode 0644 key accepted and readable by UID 65534 |
| `truncated_canonical_policy_passes_exact_once_gate` | `REPRODUCED` | 227 DOCX units accepted against a 40-byte contradictory policy |
| `git_info_exclude_hides_persistent_agent_file` | `REPRODUCED` | Hidden file omitted from diff/snapshot/status and survived `git clean -fd` |
| `installer_accepts_unbound_supply_chain_attestation` | `REPRODUCED` | Signed attestation accepted despite wrong SBOM/provenance hashes |
| `custom_runner_config_substitutes_approval_trust_root` | `REPRODUCED` | Runtime config keyring can differ from manifest-recorded component |

## Verified strengths

The following improvements are real and should be preserved:

- complete safe archive inventory and matching sidecars/manifests;
- repaired semantic cross-schema references;
- descriptor-relative authenticated bundle reads;
- versioned generation staging and atomic active-lock replacement;
- installed absolute Codex identity with non-root UID/GID execution;
- duplicate key-ID, signer-ID, and Ed25519 fingerprint rejection;
- stronger approval, nonce, repository identity, roadmap/policy binding, and replay controls;
- serialized exact-head anchor acknowledgments at source level;
- atomic/resumable operation and evidence registry behavior;
- captured validation commit/tree identity;
- no-follow changed-file snapshot reads and bounded validation/evidence resources;
- Git hook/filter/signing/helper hardening;
- controller-owned audit materialization and explicit read-only audit prompts;
- clear absence of an active roadmap/canonical policy and explicit `safe_for_unattended_execution_now: false`.

These strengths do not compensate for the open critical/high findings.

## Findings

### AZPR-V5-01 — CRITICAL: Agent-writable Git exclude metadata bypasses path controls, validation, and cleanup

**Status:** `OPEN_REPRODUCED`  
**Confidence:** `HIGH`  
**Affected components:** `trusted-controller/secure_runtime.py`, `trusted-controller/controller.py`, `trusted-validation-runner/trusted_validation_runner.py`

**Evidence**

- Independent harness `git_info_exclude_hides_persistent_agent_file` reproduced the bypass: changed paths contained only `allowed.txt`; `hidden.py` was absent from the validation snapshot and `git status`; `git clean -fd` left it behind.
- `trusted-controller/secure_runtime.py:962-976` discovers untracked files using `git ls-files --others --exclude-standard`.
- `trusted-controller/secure_runtime.py:1053-1101` skips `.git` in topology inspection and tree hashing.
- `trusted-validation-runner/trusted_validation_runner.py:103-106` uses the same ignore-aware path discovery.
- `trusted-controller/controller.py:2013-2047` bases path allowlists and aggregate budgets on that incomplete changed-path set.

**Impact:** A controlled agent can persist executable code, configuration, local credentials, or other artifacts outside the committed diff and outside the validation snapshot. Audit agents can also alter `.git/info/exclude` without the controller detecting a repository-file change. This defeats the central claim that agent effects are bounded, validated, and committed.

**Exploit/failure scenario:** During an otherwise permitted stage, the agent modifies an allowed tracked file, creates `hidden.py`, and adds `hidden.py` to `.git/info/exclude`. The controller validates and commits the allowed file while the hidden file remains active in the worktree and survives abandonment cleanup.

**Required remediation:** Make Git metadata controller-owned and non-writable to the agent, fingerprint and verify all security-relevant `.git` metadata before and after every child run, reject any change to `.git/info/exclude`, attributes, config, refs, hooks, index, and worktree administrative files, and enumerate untracked paths with ignore rules disabled or with an independent filesystem walk. Cleanup must include ignored files only after a controller-owned allowlist/safety pass.

**Exit tests**

- Agent UID cannot modify any `.git` file or administrative worktree metadata.
- A hidden file added to `.git/info/exclude`, `.gitignore`, global excludes, or attributes is detected and blocks the stage.
- Validation snapshot and aggregate diff inventory match an independent no-follow filesystem inventory.
- Abandon/reconcile leaves no untracked or ignored agent-created artifact.
### AZPR-V5-02 — CRITICAL: Installer accepts private signing keys that the non-root agent can read

**Status:** `OPEN_REPRODUCED`  
**Confidence:** `HIGH`  
**Affected components:** `trusted-installation/install.py`, `trusted-controller/secure_runtime.py`, `trusted-controller/controller.py`

**Evidence**

- Independent harness `world_readable_private_key_accepted` created a root-owned mode `0644` private-key file. `safe_external()` accepted it and UID 65534 read the contents successfully.
- `trusted-installation/install.py:33-44` rejects symlinks, non-root ownership, and group/other write bits, but does not reject group/other read bits for private keys.
- `trusted-installation/install.py:248-251` applies that generic check to runtime, evidence, and installation private keys.
- `trusted-installation/install.py:288-289` records external components while asserting—without enforcing—that secrets are unreadable to the agent.
- `trusted-controller/secure_runtime.py:333-345` requires 0600 only when the controller later loads a key; that does not prevent the agent from reading the file directly.

**Impact:** The agent can steal controller runtime, evidence, or installation-authority private keys and then forge approvals, signed state/evidence, operation tickets, or future installation manifests. This collapses role separation and makes subsequent signatures untrustworthy.

**Exploit/failure scenario:** An operator supplies a common root-owned 0644 PEM. Installation succeeds. The non-root Codex child reads the PEM by absolute path and later fabricates controller-signed or evidence-signed artifacts.

**Required remediation:** Classify every secret input explicitly. Require regular file, root ownership, single link, mode exactly 0600 or stricter, and inaccessible parent traversal where appropriate. Verify unreadability by the configured agent UID/GID before activation. Prefer hardware-backed or brokered signing so private material is never readable from the agent namespace.

**Exit tests**

- Installer rejects 0644, 0640, ACL-readable, group-readable, and agent-readable private keys.
- Configured agent UID/GID cannot open any runtime, evidence, bundle, or installation signing key after installation.
- Key access denial is tested from the exact Codex sandbox/namespace.
- Compromised-key rotation and revocation are exercised.
### AZPR-V5-03 — HIGH: Validation-image attestation is not bound to the supplied SBOM or build provenance

**Status:** `OPEN_REPRODUCED`  
**Confidence:** `HIGH`  
**Affected components:** `trusted-installation/install.py`, `repository-overlay/automation/schemas/validation-image-attestation.schema.json`, `repository-overlay/automation/schemas/build-provenance.schema.json`

**Evidence**

- Independent harness `installer_accepts_unbound_supply_chain_attestation` passed schema validation and distinct-role signature verification while the attested SBOM and provenance hashes differed from the actual supplied files.
- `trusted-installation/install.py:252-265` verifies the wheelhouse against the lock and validates/signature-checks the attestation, but never compares `attestation.sbom_sha256` or `attestation.build_provenance_sha256` to the `--sbom` and `--build-provenance` inputs.
- The build-provenance document is schema-validated but is not cryptographically bound to the actual wheelhouse, lock, mirror inventory, or installed validation image by installer comparisons.

**Impact:** A signed attestation can approve one SBOM/provenance set while the installer records and uses another. Supply-chain review and validation-image approval can therefore be false even when the installer reports success.

**Exploit/failure scenario:** A stale or benign attestation is paired with a different SBOM/provenance file. The installer accepts both because each is individually well-formed and the attestation signatures are valid.

**Required remediation:** Compare every attested hash to the exact input bytes before any installation write. Recompute and compare the wheel inventory, lock hash, requirements input, mirror inventory/attestation/key, Dockerfile, SBOM, provenance, image digest, and reproducibility pass hashes. Include these verified identities in the signed installation manifest.

**Exit tests**

- Any one-byte mutation of SBOM or provenance blocks installation.
- Attestation for a different wheelhouse, lock, mirror, Dockerfile, or image blocks installation.
- Independent rebuilds produce exactly the signed inventory or fail promotion.
### AZPR-V5-04 — HIGH: Custom external-runner configuration can substitute the approval trust root

**Status:** `OPEN_REPRODUCED`  
**Confidence:** `HIGH`  
**Affected components:** `trusted-installation/install.py`, `external-capability-runner/capability_runner.py`, `repository-overlay/automation/schemas/external-runner-config.schema.json`

**Evidence**

- Independent harness `custom_runner_config_substitutes_approval_trust_root` showed the schema accepts a config whose `approval_keyring_path` differs from the installer-supplied and manifest-recorded `approval_keyring` component.
- `trusted-installation/install.py:290-293` accepts and installs a caller-supplied runner config without equality checks against the installed approval keyring, runtime public key, evidence keys, or adapter components.
- `external-capability-runner/capability_runner.py:311-327` loads the installed config in production.
- `external-capability-runner/capability_runner.py:384-400` uses `config["approval_keyring_path"]` to authorize manifests and attestations.

**Impact:** A setup error or malicious configuration can authorize real external actions using a keyring different from the one the installation manifest appears to pin. This reintroduces the prior caller-selectable external trust-root problem at installation time.

**Exploit/failure scenario:** The operator supplies a legitimate approval keyring as `--approval-keyring` but a custom config points to a different immutable root-owned keyring. The signed installation contains both, while runtime authorization follows the config-selected keyring.

**Required remediation:** Generate production runner configuration inside the installer from verified component identities, or require exact equality between every config trust path/key ID/hash and the corresponding installation component. Pin every adapter as a named installation component and reject custom trust roots in production.

**Exit tests**

- A config referencing any unregistered or mismatched keyring/key/adapter is rejected.
- Runtime authorization demonstrably uses only the manifest-pinned approval keyring.
- Substituted config, schema, keyring, adapter, and target-attestation tests all fail closed.
### AZPR-V5-05 — HIGH: Canonical-policy gate proves source-unit listing, not semantic or textual preservation

**Status:** `OPEN_REPRODUCED`  
**Confidence:** `HIGH`  
**Affected components:** `operator-tools/create_canonical_policy_record.py`, `trusted-installation/install.py`, `repository-overlay/automation/schemas/canonical-policy-section-map.schema.json`

**Evidence**

- Independent harness `truncated_canonical_policy_passes_exact_once_gate` used the actual governing DOCX (227 deterministic source units) and a 40-byte policy saying `ALLOW EVERY ACTION WITHOUT RESTRICTION.` The record tool, schemas, distinct signer roles, and installer hash/count checks all accepted it when the map merely asserted meaning preservation.
- `operator-tools/create_canonical_policy_record.py:34-43` checks deterministic source-manifest identity and exact-once source-unit IDs, but does not bind units to canonical byte ranges or canonical text hashes.
- `trusted-installation/install.py:255-263` repeats hashes, counts, and exact-once IDs without comparing source text to canonical text.
- `canonical-policy-section-map.schema.json` records only a heading, review status, and note; it contains no canonical span/range/hash or machine-checkable equivalence evidence.

**Impact:** The installed “canonical” policy can omit, invert, or replace governing requirements while still satisfying the mechanical completeness gate. The Master Operating Prompt would no longer be reliably governing.

**Exploit/failure scenario:** Two signers accidentally approve a condensed or incomplete derivative whose section map claims every DOCX paragraph is represented under one heading. The controller binds future approvals to that derivative rather than the governing source.

**Required remediation:** Use the exact governing DOCX (or a deterministic lossless extraction) as the canonical authority. If a Markdown rendering is required, generate it deterministically and bind every source unit to exact canonical byte offsets and hashes, require complete canonical-span coverage with no unmapped normative text, and independently review a machine-generated diff. Do not permit free-form semantic substitutions to become the enforcement authority.

**Exit tests**

- A one-line, truncated, reordered, omitted, or contradictory canonical policy is rejected even with signed review claims.
- Every source unit and every canonical normative span is bijectively mapped and hash-bound.
- The controller policy identity includes the exact governing DOCX hash and deterministic rendering algorithm/version.
### AZPR-V5-06 — MEDIUM: Submitted verifier and tests miss the newly reproduced trust-boundary failures

**Status:** `OPEN_REPRODUCED`  
**Confidence:** `HIGH`  
**Affected components:** `VERIFY-AUTONOMOUS-DRAFT.py`, `tests/test_v5_security_closures.py`, `tests/test_finalized_composed_controls.py`

**Evidence**

- The clean verifier reported `PASS_IMPLEMENTATION_DRAFT_SETUP_BLOCKED`, 57 security tests, 28 schemas, 41 prompts, and all control markers.
- The submitted suite contains no test for `.git/info/exclude`, private-key read permissions, attestation-to-file hash equality, custom runner keyring substitution, or canonical text/span equivalence.
- The independent harness reproduced all five targeted failures while the submitted suite still passed.

**Impact:** The pack can present a strong PASS signal while decisive trust boundaries remain untested, increasing the risk of premature promotion after setup.

**Exploit/failure scenario:** An operator treats the verifier’s PASS as evidence that v4 findings are closed and proceeds to clean-room installation without testing the missing cases.

**Required remediation:** Add executable negative/composed tests for every finding in this assessment and make the verifier fail if those tests are absent or fail. Prefer behavior-based assertions over source-token markers.

**Exit tests**

- All five independent reproductions are converted into permanent regression tests and fail against v5.
- Verifier proves tests executed from a fresh extraction and reports exact test IDs.
- A mutation test confirms removal of each enforcement check makes the suite fail.
### AZPR-V5-07 — MEDIUM: Installation activation can precede final receipt and key-pair self-verification

**Status:** `OPEN_CODE_REVIEW`  
**Confidence:** `MEDIUM_HIGH`  
**Affected components:** `trusted-installation/install.py`

**Evidence**

- `trusted-installation/install.py:297-300` signs the manifest with the supplied private key but does not verify it with the supplied installation public key before activation.
- `trusted-installation/install.py:304-310` activates the generation and lock before creating the final receipt.
- `trusted-installation/install.py:312-314` removes only the staging directory on exception; it does not revert an already activated lock or explicitly report an activated-but-unreceipted state.

**Impact:** A mismatched key pair can activate an installation that production loaders cannot verify. A post-activation receipt failure can make the installer return failure even though the active generation changed, creating operator ambiguity and incomplete audit evidence.

**Exploit/failure scenario:** The public and private installation keys do not match, or the receipt directory/write fails after lock replacement. The command exits unsuccessfully after selecting a new generation.

**Required remediation:** Before any write, sign and verify challenges for every private/public pair. Define a recoverable activation transaction with pre-activation intent, post-activation receipt, explicit state reconciliation, and deterministic rollback or completion after interruption.

**Exit tests**

- Mismatched runtime, evidence, and installation key pairs are rejected before staging.
- Kill/fault injection after every linearly ordered activation step yields one unambiguous recoverable state.
- A receipt failure cannot silently leave a changed active generation.


### AZPR-V5-08 — MEDIUM: Reports archive contains a manifest for a different inventory

**Status:** `OPEN_REPRODUCED`  
**Confidence:** `HIGH`  
**Affected components:** `AZPR-autonomous-execution-primed-draft-v5-reports(1).zip`, `SHA256SUMS.json`

**Evidence**

- The reports ZIP contains 19 files, including `SHA256SUMS.json`.
- That manifest lists 146 entries from the full implementation candidate. Eighteen listed files are present in the reports ZIP and match their hashes, but **128 listed files are absent**.
- The reports ZIP sidecar correctly authenticates the ZIP itself; the defect is that the enclosed manifest is not scoped to the reports archive and therefore cannot verify its inventory.

**Impact:** Operators can incorrectly interpret the enclosed manifest as a complete integrity proof for the reports bundle. This weakens artifact identity and creates ambiguity between the implementation pack and supporting report pack, although it does not directly alter executable candidate code.

**Failure scenario:** A reviewer validates the reports ZIP using its enclosed `SHA256SUMS.json`, sees extensive missing-file failures, and cannot determine whether the reports archive is truncated, stale, or intentionally partial.

**Required remediation:** Give the reports bundle its own manifest with exactly its own files, or omit the full-candidate manifest and include an explicit reference to the candidate ZIP hash/manifest. Name the manifest scope and bundle identity in the schema.

**Exit tests**

- The reports manifest inventory equals the reports ZIP inventory exactly, excluding only the manifest itself.
- Every listed hash verifies and no absent or unlisted member exists.
- A verifier distinguishes implementation-bundle and reports-bundle manifests by signed bundle identity.

## Prompt completeness and consistency

All 38 numbered prompts and Appendices A–C were inventoried. Filenames, IDs, titles, kinds, effort labels, instruction-integrity rules, external-capability boundaries, stop conditions, validation expectations, and controller handoff language are generally consistent. Read-only audits explicitly require controller-owned materialization and prohibit repository edits.

However, the candidate intentionally includes **no active finalized roadmap**. Therefore the review could not bind each prompt to executable controller metadata for exact prerequisites, sandbox, context files, validation profile, allowed paths, forbidden paths, approval/audit gate hashes, external capabilities, or commit outcomes. More importantly, the shared critical defects invalidate controller enforcement regardless of prompt wording.

Result across all 41 prompts:

- `ACCEPTABLE`: 0
- `CONDITIONAL`: 0
- `UNACCEPTABLE_FOR_UNATTENDED_EXECUTION`: 41

Detailed per-prompt scores and rationales are in `AZPR-finalized-security-scorecard.json`.

## Historical regression status

| ID | Prior finding | Status | Basis |
|---|---|---|---|
| R01 | Approval documents required their own final hash | `CLOSED_AND_TESTED` | Approval/signature records bind immutable unsigned payloads and candidate tests reject tampering, wrong stage/commit/environment/policy, expiry, and replay. |
| R02 | Nonce consumption was not atomic across concurrent runs | `CLOSED_AND_TESTED` | SQLite-backed nonce consumption and submitted multi-thread/process tests pass. |
| R03 | Signed state lacked exact repository/roadmap/policy binding | `CLOSED_AND_TESTED` | Run/state identities include exact commit/tree and policy/roadmap identities; mutation cases are covered. |
| R04 | No trusted external-evidence ingestion and immutable registration path | `CLOSED_AND_TESTED` | Operation registry, signed evidence ingestion, content-addressed objects, replay checks, and resumable attachment are implemented and tested. |
| R05 | Controller-owned writes could follow repository symlinks | `CLOSED_AND_TESTED` | No-follow writes and ancestor/leaf checks are present with symlink tests. |
| R06 | Git operations could execute hostile hooks, filters, helpers, or configuration | `PARTIALLY_CLOSED` | Hooks/filters/signing/helpers are hardened, but AZPR-V5-01 proves writable Git exclude metadata can still bypass repository controls. |
| R07 | External-runner trust roots were caller-selectable | `PARTIALLY_CLOSED` | Production launchers pin installation identity, but AZPR-V5-04 shows the installed custom runner config can select a different approval keyring. |
| R08 | Appendix A lacked cryptographically verified human authorization | `CLOSED_AND_TESTED` | Appendix A authorization schema, signatures, validity, binding, and nonce checks are present and tested. |
| R09 | Signed journals lacked rollback/truncation resistance | `PARTIALLY_CLOSED` | Exact anchor receipts and serialized recovery are improved and source-tested; a real independently administered remote anchor is absent and unqualified. |
| R10 | Agent-writable and controller-owned paths were not fully separated | `NOT_CLOSED` | AZPR-V5-01 shows `.git` control metadata can remain agent-writable and unmeasured; AZPR-V5-02 shows agent-readable controller secrets can be accepted. |
| R11 | Path budgets did not cap aggregate actual diff and untracked files | `PARTIALLY_CLOSED` | Aggregate budgets exist, but ignored files can be removed from the measured set through `.git/info/exclude`. |
| R12 | Validation snapshots could include ignored secrets and local artifacts | `CLOSED_AND_TESTED` | Snapshot construction excludes ignored/local artifacts and uses bounded no-follow reads. AZPR-V5-01 is a distinct persistence/omission bypass, not inclusion of ignored secrets. |
| R13 | Child stdout/stderr and evidence resources were insufficiently bounded | `CLOSED_AND_TESTED` | Process groups, timeouts, output byte caps, file counts, depth, JSON and evidence quotas are enforced and tested. |
| R14 | Signer-role separation could use one key for multiple roles | `CLOSED_AND_TESTED` | Duplicate signer IDs and raw Ed25519 key fingerprints are rejected; distinct signer roles are required. |
| R15 | External adapter verification had ownership and TOCTOU weaknesses | `CLOSED_AND_TESTED` | Production adapter paths are root-owned/non-writable, opened once, hashed by descriptor, and executed through the verified descriptor. |
| R16 | ROLLED_BACK could be represented as apply success | `CLOSED_AND_TESTED` | External result states distinguish complete, failed, partial, interrupted, and rollback outcomes. |
| R17 | Signed evidence files could be overwritten | `CLOSED_AND_TESTED` | Content-addressed create-once evidence objects and collision/replay checks are implemented. |
| R18 | Reports/results lacked limits and centralized redaction | `CLOSED_AND_TESTED` | Bounded outputs, schemas, and centralized redaction are present. |
| R19 | Security tests missed highest-risk trust boundaries | `NOT_CLOSED` | AZPR-V5-06: five independently reproduced trust-boundary failures are absent from the submitted 57-test suite. |
| R20 | Supply-chain and operator-tool hardening was incomplete | `NOT_CLOSED` | AZPR-V5-02, AZPR-V5-03, AZPR-V5-05, and AZPR-V5-07 leave key custody, artifact binding, governing-policy integrity, and installation recovery incomplete. |

### v4 finding regression status

| Finding | Status | Basis |
|---|---|---|
| AZPR-V4-01 | `CLOSED_AND_TESTED` | Schema references resolve and semantic fixtures execute. |
| AZPR-V4-02 | `CLOSED_AND_TESTED` | Installer reads only a signed, exact-inventory, immutable bundle; root-installed qualification remains pending. |
| AZPR-V4-03 | `PARTIALLY_CLOSED` | Codex identity and non-root launch are pinned, but AZPR-V5-02 can expose signing keys to that same agent identity. |
| AZPR-V4-04 | `CLOSED_AND_TESTED` | Duplicate cryptographic key material under aliases is rejected. |
| AZPR-V4-05 | `NOT_CLOSED` | AZPR-V5-05 reproduces acceptance of a 40-byte contradictory canonical policy mapped to all 227 source units. |
| AZPR-V4-06 | `PARTIALLY_CLOSED` | Concurrency handling is source-tested; production remote anchor remains absent/unqualified. |
| AZPR-V4-07 | `CLOSED_AND_TESTED` | Evidence attachment is transactional/resumable and submitted interruption tests pass. |
| AZPR-V4-08 | `CLOSED_AND_TESTED` | Validation records use captured commit/tree identity. |
| AZPR-V4-09 | `CLOSED_AND_TESTED` | Production launchers clear development roots and direct source entrypoints require explicit test mode. |
| AZPR-V4-10 | `PARTIALLY_CLOSED` | Versioned activation is improved, but AZPR-V5-07 and the unexecuted root kill matrix leave recovery ambiguity. |
| AZPR-V4-11 | `NOT_CLOSED` | AZPR-V5-03 demonstrates missing attestation-to-artifact binding; real reproducible build qualification is also absent. |

## Architecture and project-safety assessment

No real project roadmap is included, so sequencing cannot yet be promoted. The prompt pack itself contains strong domain and operational safeguards: bounded-context preservation, immutable provenance, customer isolation, deterministic-before-AI behavior, consent/suppression gates, disabled SMS activation, read-only audits, backup/restore requirements, and plan-only staging/production stages.

The following project-level risks remain promotion blockers:

- hidden ignored files can create unreviewed code/config drift and false-PASS validation;
- compromised signing keys can fabricate approvals, evidence, audit state, or operation tickets;
- a derivative canonical policy can drift from the governing Master Operating Prompt;
- supply-chain reports can describe artifacts other than those installed/validated;
- an external runner can authorize actions from a different keyring than the manifest suggests;
- no root-installed exact-binary qualification, remote anchor, real dependency mirror/wheelhouse/SBOM/image, hardware-backed key custody, or actual repository execution was performed;
- no Prompt 004 decision or exact regenerated roadmap exists;
- provider/source terms, customer isolation, notification consent/suppression, duplicate prevention, backup/restore, migration/rollback, PII redaction, and production target controls remain future project-stage obligations rather than proven current behavior.

## Final promotion decision

`NOT_READY`

The v5 artifact may be used only as **remediation source material in an isolated review environment**. It is not approved for trusted autonomous dry runs, controlled unattended execution, production installation, roadmap generation/promotion, Prompt 004, or any external side effect.

Promotion requires:

1. closure and independent adversarial retest of every Critical and High finding;
2. conversion of the independent reproductions into permanent tests;
3. a clean root-installed qualification of exact artifacts, accounts, binaries, keys, remote anchor, container image, dependency mirror, wheelhouse, SBOM, and provenance;
4. exact governing-policy preservation and approval;
5. Prompt 004 completion and approval;
6. single-use signed roadmap regeneration, exact roadmap review, and independent reassessment with no open Critical/High issues.

## Environmental limitations and assumptions

- The root installer was not run against `/opt/azpr`, `/etc/azpr`, or `/var/lib/azpr` on a dedicated clean-room host.
- No real Codex binary, container engine/image, provider adapter, service account, hardware key, remote anchor, dependency mirror, or customer data was used.
- Interruption/kill testing of every installer and remote-anchor boundary was not performed.
- The Master Operating Prompt was inspected as the supplied governing DOCX; no canonical policy was approved or installed.
- The reports ZIP was treated as developer-authored supporting evidence, not independent proof.
- Findings marked `OPEN_CODE_REVIEW` are grounded in traced control flow but were not exercised through a full privileged installation.
