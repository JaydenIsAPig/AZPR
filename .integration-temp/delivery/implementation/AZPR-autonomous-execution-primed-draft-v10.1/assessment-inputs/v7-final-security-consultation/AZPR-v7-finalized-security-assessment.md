# AZPR v7 Finalized Security Assessment

**Review date:** July 27, 2026  
**Candidate:** `AZPR-autonomous-execution-primed-draft-v7`  
**Governing policy:** `AZ Permit Radar Master Operating Prompt(3).docx`  
**Independent verdict:** **NOT READY AS AN IMPLEMENT-AS-IS PRE-AUTONOMOUS BUNDLE**

```json
{"safe_for_unattended_execution_now": false, "trusted_pre_autonomous_installation_ready": false}
```

## Executive decision

V7 is a materially improved **security-remediation source baseline**, but it is not yet safe to install as the trusted control plane or to hand to Codex as an implement-as-is pre-autonomous bundle. Human-supervised Codex may be used only in an isolated, non-privileged remediation branch to build a v8 correction; it must not invoke the root installer, approve policy, execute Prompt 004, generate/promote the roadmap, run autonomous stages, or register/apply external operations.

The candidate's own verification is substantial: the full submitted suite passed **77 tests plus 23 subtests**, and the separate five-case phase-boundary harness passed. The actual uploaded governing DOCX also closes the v6 rendering concern: the candidate extractor preserved **227 source units, 276 Word tabs, and 19 explicit line breaks**, with no unsupported normative parts detected.

Those strengths do not overcome the independent failures. Three critical defects remain in the trusted boundary:

1. The privileged installer does not require or verify the clean-room qualification receipt.
2. The clean-room verifier can sign a receipt over fabricated, unsigned, semantically empty evidence.
3. Successful Codex descendant processes can survive controller return and act after the approved execution window.

Two additional high-severity defects permit a bidirectional pipe deadlock outside the internal timeout and leave the agent handoff filesystem without enforced resource quotas.

### Phase decisions

| Phase | Decision | Meaning |
|---|---|---|
| Manual document and source review | **ALLOWED** | Review, patch development, and offline artifact preparation only. |
| Human-supervised Codex remediation | **CONDITIONAL** | Only in an isolated non-root branch to implement the P0/P1 corrections; no trusted installation or stage execution. |
| Install v7 as trusted control plane | **NOT READY** | F01-F05 must be closed and independently retested first. |
| Approve canonical policy / execute Prompt 004 | **BLOCKED** | Exact render exists, but approval and trusted installation are absent. |
| Generate or promote roadmap | **BLOCKED** | No active approved policy or trusted installation; shared critical defects remain. |
| Controlled autonomous dry run | **NOT READY** | Process lifetime, qualification, I/O, and resource controls are incomplete. |
| Unattended or production execution | **NOT READY** | Explicitly forbidden. |

## Scope and methodology

The review followed the supplied continuation protocol rather than treating the developer reports as proof. Work included:

- safe archive metadata inspection and fresh extraction;
- SHA-256 sidecar, delivery manifest, and internal manifest verification;
- byte-for-byte prompt copy comparison;
- review of all numbered prompts 001-038 and Appendices A-C;
- source-level tracing of the trusted controller, runtime, installer, clean-room verifier, policy extractor, key lifecycle, adapters, schemas, and tests;
- execution of the submitted test suite and phase-boundary harness;
- extraction of the actual governing DOCX with the submitted tool;
- independent black-box tests for process descendants, fabricated qualification evidence, pipe deadlock, installer gate enforcement, and delivery completeness;
- regression classification for the original 20 findings and v6 findings;
- separate assessment of pre-autonomous implementation readiness and unattended execution safety.

## Artifact identity and integrity

### Top-level inputs

| Input | Bytes | SHA-256 | Result |
|---|---:|---|---|
| `AZPR-autonomous-execution-primed-draft-v7(2).zip` | 707770 | `84f36592d0dc910ae97055478944e6cab3ace212f9c80534283207b2cad19383` | Sidecar matched; safe archive metadata. |
| `AZPR-autonomous-execution-primed-draft-v7-reports(2).zip` | 34798 | `7c0ed92ec8c1293fbb0a84ef7238c4e088439c2efc642f13868cab6de407d6e6` | Sidecar matched; safe archive metadata. |
| `AZPR-v7-delivery-manifest(2).json` | 1828 | `2f26f2bb2a71ef181b3165d71ee931560a6bd982f8e6f3a7831bc5ed85cf9609` | Sidecar matched; two referenced report-verification files absent. |
| `AZ Permit Radar Master Operating Prompt(3).docx` | 8409 | `37800ebde204070d1ac20c2cfff5c809ee4f318cfcc44312514c393077334ae6` | Successfully processed by v7 exact extractor. |

### Archive and manifest results

- Candidate archive: **171 safe members**; no traversal, absolute paths, symlinks, devices, or special-file entries.
- Candidate internal manifest: **170 entries**, **0 mismatches**.
- Reports archive: **29 safe members**; no unsafe metadata.
- Reports internal manifest: **28 entries**, **0 mismatches**.
- Prompt set: **41 files**; embedded ZIP and repository-overlay copies are byte-identical.
- Embedded prompt archive SHA-256: `3b235cb7e33ca409241ff26523f60f8fee89cec524b3f09e91a69927a0aa4880`.
- No active canonical policy or active roadmap ships in the bundle; this is an intentional fail-closed gate.

## Governing-policy verification

The actual uploaded Master Operating Prompt defines the Arizona-specific permit-intelligence product, domain-driven modular monolith, deterministic-first processing, immutable source evidence, idempotency, explainability, documentation hierarchy, staged change protocol, validation requirements, and stop conditions.

The v7 prompt set materially preserves those policies. The independent exact-render test produced:

- source DOCX SHA-256: `37800ebde204070d1ac20c2cfff5c809ee4f318cfcc44312514c393077334ae6`;
- canonical text SHA-256: `5d2353d7f079addf873795a3f5a0ef6d41e1587115c1c20b47d7ea0172cee909`;
- 227 source units;
- 276 tabs;
- 19 explicit line breaks;
- no unsupported normative parts.

This closes the v6 source-extraction defect at implementation level. It does **not** constitute human approval of the canonical policy, an organizational signature, or permission to execute Prompt 004.

## Verified strengths

- Release sidecars and internal manifests are internally consistent.
- Prompt copies are byte-identical and unchanged from the prior prompt baseline.
- The bundle honestly preserves `safe_for_unattended_execution_now: false` and `trusted_pre_autonomous_installation_ready: false`.
- V7 repairs non-root handoff ownership, pre-side-effect Git graft/submodule rejection, identity-based cleanup, and Word tab/line-break preservation.
- Root-owned keys, journals, approvals, evidence, and controller state are separated from the agent handoff surface.
- Git execution, snapshot creation, aggregate diff budgets, evidence limits, redaction, signer-role separation, nonce replay, and immutable evidence controls remain materially stronger than early drafts.
- The submitted suite passed **77 tests and 23 subtests**; the five-case phase-boundary harness passed.
- Key-lifecycle and adapter-installation artifacts exist as useful scaffolding, although they are not yet fully enforced or qualified.

## Findings

### AZPR-V7-F01 — CRITICAL: Root installer does not enforce a clean-room qualification receipt

**Affected components:** trusted-installation/install.py, CLEANROOM-QUALIFICATION.md, PROMOTION-GATES.md

**Evidence**
- trusted-installation/install.py:534-550 defines every required installer argument but has no clean-room receipt, qualification-report set, host identity, or independent reassessment input.
- Independent static test confirmed `receipt_argument_present: false`.
- The documentation says qualification is mandatory, but direct installer invocation can bypass that sequencing rule.

**Impact:** A privileged operator or automation can convert the source bundle into an active trusted installation without proving the dedicated host, Codex isolation, remote anchor, supply chain, key custody, or independent qualification gates. Documentation is not an enforcement boundary.

**Failure scenario:** Invoke `install.py` directly with its ordinary artifact arguments and omit the clean-room receipt and qualification reports. The installer proceeds into bundle authentication and installation preparation rather than rejecting the missing phase authorization.

**Required remediation:** Require an unexpired, one-use, independently signed qualification authorization bound to the exact bundle hash, host identity, agent UID/GID, Codex binary hash, validation image digest, all qualification report hashes, policy source hash, installer version, and nonce. Verify it before recovery, directory creation, key reads, or any other state-changing operation.

**Exit tests**
- Installer without receipt fails before any write or nonce/state mutation.
- Receipt with wrong bundle, host, report set, signer role, expiry, or nonce fails.
- Same receipt cannot be reused.
- Fault injection proves no installation state appears before receipt verification.

### AZPR-V7-F02 — CRITICAL: Clean-room verifier signs fabricated evidence because it validates presence and shallow shape, not truth

**Affected components:** operator-tools/verify_v7_cleanroom_prerequisites.py, tests/test_v7_preautonomous_closures.py, FUTURE-QUALIFICATION-INPUTS.template.json

**Evidence**
- verify_v7_cleanroom_prerequisites.py:101-151 checks ownership, mode, hash, and shallow JSON fields; qualification reports need only a kind, PASS, false unattended flag, and nonempty 64-hex binding values.
- Lines 243-249 cryptographically check only three key pairs; keyrings need only a nonempty `keys` list.
- Lines 250-274 sign a receipt using the installation key after these shallow checks.
- Independent test supplied 32 root-owned fabricated artifacts, empty SBOM/provenance/attestations, malformed keyrings, fake executables, and six unsigned self-declared PASS reports. The verifier returned `COMPLETE_REQUIRED_INPUT_SET_VERIFIED_INSTALLATION_STILL_BLOCKED` and signed the receipt.
- The submitted test fixture encodes the same shallow success pattern, so the false-PASS behavior is not accidental test omission.

**Impact:** A signed clean-room receipt can falsely assert that all prerequisite evidence was verified. If F01 is repaired by merely requiring this receipt, the installer would gain a cryptographic-looking but semantically meaningless authorization token.

**Failure scenario:** Create files with the expected names, root ownership, safe modes, and self-consistent hashes. Put arbitrary 64-hex strings into unsigned report bindings. The verifier signs the resulting receipt even though no real host, namespace, supply-chain, image, provider, or rollback qualification occurred.

**Required remediation:** Define strict schemas and signer-role policies for each artifact; verify report signatures, provenance chains, exact cross-artifact bindings, public-key/keyring validity, executable identity, SBOM/provenance/attestation semantics, host measurements, and validation-image registry digest. Qualification reports must come from distinct authorized roles and contain observed test evidence, not self-declared PASS labels.

**Exit tests**
- Current fabricated 32-artifact corpus is rejected.
- Each report fails on unsigned, wrong signer, wrong host, stale, wrong bundle, wrong image, or missing evidence cases.
- Cross-substitution of any two artifacts is rejected.
- Independent verifier can reproduce reported measurements from immutable evidence.

### AZPR-V7-F03 — CRITICAL: Successful Codex descendants can outlive controller return and mutate after validation

**Affected components:** trusted-controller/secure_runtime.py:run_bounded_process, trusted-controller/controller.py, operator-tools/exercise_agent_handoff.py

**Evidence**
- secure_runtime.py:1311-1315 starts a new session, but lines 1340-1344 kill the process group only on timeout, overflow, or wait failure.
- On normal exit, lines 1338-1352 return without terminating or proving absence of descendants.
- Independent black-box child detached its standard streams, survived the parent process, and wrote `orphan survived after controller return` after `run_bounded_process` had returned.

**Impact:** A compromised or merely buggy Codex process can leave a background descendant inside the execution environment. It can race validation, mutate the repository after the controller captures results, interfere with cleanup, consume resources, or maintain access longer than the approved stage window.

**Failure scenario:** The main Codex process spawns a background child, closes inherited pipes, and exits zero. The controller validates/imports results and continues while the descendant later writes to the worktree or handoff surface.

**Required remediation:** Place each execution in a dedicated cgroup and PID/mount namespace; disallow escape primitives; on every completion path terminate the full cgroup/process tree, wait for zero remaining processes, then freeze or unmount the execution surface before validation/import. A successful main PID exit is not stage completion.

**Exit tests**
- Detached child, double-fork, setsid, shell background, and inherited-FD variants cannot survive controller completion.
- No repository write succeeds after the agent window closes.
- Controller fails closed if the cgroup cannot be proven empty.
- Cleanup occurs before validation and nonce/commit finalization.

### AZPR-V7-F04 — HIGH: Blocking stdin write can deadlock before timeout and output limits become active

**Affected components:** trusted-controller/secure_runtime.py:run_bounded_process, external-capability-runner/secure_runtime.py

**Evidence**
- secure_runtime.py:1316-1318 writes all input synchronously before stdout/stderr are made nonblocking and before the selector/deadline loop begins.
- Independent child wrote 2 MiB to stdout before reading stdin while the controller attempted to write 2 MiB to stdin. The internal one-second timeout never fired; an outer five-second timeout killed the harness with return code 124.

**Impact:** An agent or adapter can indefinitely block the trusted controller despite configured timeouts. This can strand branches, nonce/state transitions, run manifests, locks, or operator workflows and may combine with F03 descendants.

**Failure scenario:** Child fills its stdout pipe and waits for the parent to read; parent fills the child stdin pipe and waits for the child to read. Neither reaches the selector loop.

**Required remediation:** Use one nonblocking selector/event loop for stdin, stdout, and stderr from process start; write bounded chunks only when stdin is writable; enforce a monotonic deadline across spawn, input, output, wait, and teardown. Consider `communicate(timeout=...)` only if independent size enforcement remains robust.

**Exit tests**
- Bidirectional pipe saturation terminates within deadline.
- Large valid input/output within limits succeeds.
- Timeout teardown removes all descendants and closes all descriptors.

### AZPR-V7-F05 — HIGH: Per-run agent handoff storage and cleanup lack enforced resource quotas

**Affected components:** trusted-controller/controller.py, trusted-controller/secure_runtime.py, trusted-installation/install.py

**Evidence**
- The source creates randomized per-run HOME, TMPDIR, and output surfaces and performs no-follow cleanup, but no source-level byte, inode, file-count, path-depth, or mount quota is enforced for the full handoff tree.
- Cleanup recursively walks/removes agent-created content; a hostile tree can make teardown expensive or exhaust the host before bounded result import is reached.
- External host quotas are described as qualification concerns, but F01 means the installer does not require proof that they exist.

**Impact:** A supervised stage can exhaust disk space or inodes, delay cleanup, interfere with controller state durability, or deny service to the dedicated host even when stdout/result JSON limits are respected.

**Failure scenario:** Codex creates millions of small files or sparse/large files under HOME/TMPDIR while returning a small valid result. The controller must traverse or remove the tree and may run out of space first.

**Required remediation:** Run handoff roots on dedicated quota-enforced mounts or tmpfs with strict byte/inode limits, cap file count/path depth, reserve controller storage, and use identity-safe descriptor-relative deletion with bounded traversal. Installer qualification must attest these mounts and limits.

**Exit tests**
- File-count, inode, sparse-file, deep-tree, and concurrent-writer exhaustion cases are stopped within defined budgets.
- Controller journals and receipts remain writable under agent quota exhaustion.
- Cleanup time and traversal count are bounded and measured.

### AZPR-V7-F06 — MEDIUM: Signed key lifecycle is scaffolded but not an enforced operational state machine

**Affected components:** operator-tools/create_key_lifecycle_transition.py, schemas/key-lifecycle-transition.schema.json, trusted-controller, trusted-installation

**Evidence**
- V7 adds a schema and creation tool, and its own remediation status says the control is `PRIMED_SIGNED_TRANSITION_NOT_END_TO_END_QUALIFIED`.
- The bundle does not demonstrate installed one-use application, atomic signer-set transition, revocation propagation, compromise recovery, rollback resistance, or historical verification after rotation.

**Impact:** Key compromise or routine rotation may require unsafe manual edits or leave different components trusting inconsistent signer sets.

**Failure scenario:** An approval or evidence key is revoked while a pending operation or journal references the old key. Components apply the transition in different orders or accept replayed transition files.

**Required remediation:** Implement a signed, sequenced, one-use transition ledger bound to current and next keyring hashes, required roles, effective time, compromise flag, and remote anchor. Apply atomically across controller, evidence, approval, installation, and adapter trust stores with recovery tests.

**Exit tests**
- Normal rotation preserves historical verification.
- Emergency revocation blocks new signatures immediately without rewriting history.
- Replay, rollback, split-brain, wrong-role, and interrupted transitions fail closed.

### AZPR-V7-F07 — MEDIUM: Delivery evidence is incomplete and supporting reports are stale about the governing DOCX

**Affected components:** AZPR-v7-delivery-manifest.json, AZPR-autonomous-execution-primed-draft-v7-reports.zip, V7-INDEPENDENT-VERIFICATION-REPORT.md

**Evidence**
- The seven-entry delivery manifest references `AZPR-v7-reports-verification.json` and `AZPR-v7-reports-fresh-extraction-verification.json`, but neither file was uploaded or included in the reports ZIP.
- The delivery notes and reports say the actual Master Operating Prompt DOCX was unavailable, but it was supplied with this review. Independent extraction now proves 227 source units, 276 tabs, and 19 explicit breaks with no unsupported normative parts.

**Impact:** Operators cannot reproduce every declared delivery hash from the delivered package and may rely on stale evidence about a now-available governing input. This weakens release traceability, though it does not by itself create code execution.

**Failure scenario:** A later reviewer verifies the delivery manifest and cannot locate two referenced artifacts, or assumes the policy extractor remains synthetic-only because the bundled report was not regenerated after the DOCX became available.

**Required remediation:** Regenerate one self-contained signed delivery envelope after all review inputs are frozen. Include every referenced verification artifact, exact uploaded DOCX hash, independent extraction outputs, and an organization release signature or explicit unsigned-development status.

**Exit tests**
- Every manifest entry resolves within the delivery or an explicitly named external input set.
- Fresh extraction reproduces all hashes and reports.
- No report contains stale input-availability statements.

## Regression status — original blockers

| # | Prior issue | Status | Basis |
|---:|---|---|---|
| 1 | Approval documents previously required their own final hash. | `CLOSED_AND_TESTED` | Approval signing/verification uses canonical unsigned payloads and submitted regression coverage passes. |
| 2 | Nonce consumption was not atomic across concurrent runs. | `CLOSED_AND_TESTED` | Durable event-store design and concurrency tests close duplicate use; remote-anchor qualification remains separate. |
| 3 | Signed state was not bound to exact repository HEAD/tree and roadmap/policy hashes. | `CLOSED_AND_TESTED` | State/approval bindings cover exact repository and governing hashes; active policy/roadmap are intentionally absent. |
| 4 | No trusted external-evidence ingestion and immutable registration path existed. | `CLOSED_AND_TESTED` | Immutable evidence lifecycle and collision/replay controls are present; real adapter qualification remains gated. |
| 5 | Controller-owned writes could follow repository symlinks. | `CLOSED_AND_TESTED` | No-follow identity checks and controller-owned roots are implemented and tested. |
| 6 | Git operations could execute repository-controlled hooks, filters, signing tools, helpers, or hostile configuration. | `CLOSED_AND_TESTED` | Pinned/sanitized Git execution and topology checks pass submitted and independent graft checks. |
| 7 | External-runner trust roots were caller-selectable. | `CLOSED_AND_TESTED` | Production configuration is installer-generated and custom runner config is rejected. |
| 8 | Appendix A accepted an identifier without cryptographically verified human authorization. | `CLOSED_AND_TESTED` | Appendix A explicitly requires controller-verified, signed, expiring, one-use authorization bound to exact corrections. |
| 9 | Signed journals lacked rollback/truncation resistance. | `PARTIALLY_CLOSED` | Signed durable events and anchor protocol exist; real remote rollback-resistant anchor remains an external qualification gate. |
| 10 | Agent-writable and controller-owned paths were not fully separated. | `PARTIALLY_CLOSED` | Per-run handoff separation is improved, but F03 permits descendant lifetime beyond the controller window. |
| 11 | Path budgets did not cap the aggregate actual diff and untracked files. | `CLOSED_AND_TESTED` | Aggregate path/diff/untracked controls and identity ledgers are present. |
| 12 | Validation snapshots could include ignored secrets and local artifacts. | `CLOSED_AND_TESTED` | Descriptor-based snapshots and ignored-secret protections are covered by submitted regressions. |
| 13 | Child stdout/stderr and evidence resources were insufficiently bounded. | `PARTIALLY_CLOSED` | Output/evidence limits exist, but F04 and F05 expose blocking input and handoff filesystem resource gaps. |
| 14 | Signer-role separation could be satisfied without one distinct signer per required role. | `CLOSED_AND_TESTED` | Distinct signer/key role enforcement was repaired in prior iterations and regression tests pass. |
| 15 | External adapter verification had path ownership and TOCTOU weaknesses. | `PARTIALLY_CLOSED` | Source-level manifest binding is improved; real installed adapter and isolated-target qualification remain pending. |
| 16 | ROLLED_BACK could be represented as an apply success. | `CLOSED_AND_TESTED` | Result-state handling distinguishes rollback from success. |
| 17 | Signed evidence files could be overwritten. | `CLOSED_AND_TESTED` | Write-once evidence identity and collision controls are present. |
| 18 | Generated reports and result payloads lacked strict limits and centralized redaction. | `CLOSED_AND_TESTED` | Central limits/redaction are implemented for controller outputs and evidence. |
| 19 | Security tests did not cover the highest-risk trust boundaries. | `PARTIALLY_CLOSED` | Coverage expanded to 77 tests and 23 subtests, but F02/F03/F04 are absent and the clean-room fixture institutionalizes a false PASS. |
| 20 | Supply-chain and operator-tool hardening was incomplete. | `PARTIALLY_CLOSED` | Supply-chain scaffolding is stronger, but real artifacts/signature and enforced qualification remain absent; F01/F02 are shared blockers. |

## Regression status — v6 findings

| Finding | Status | Basis |
|---|---|---|
| AZPR-V6-I01: Non-root Codex handoff permissions and ownership. | `PARTIALLY_CLOSED` | Writable handoff paths are repaired and submitted handoff tests pass, but F03 leaves descendants alive after successful main-process exit. |
| AZPR-V6-I02: Clean-room prerequisite checker accepted incomplete evidence. | `REGRESSION` | The exact 32-item set is required, but F02 proves semantic fabrication is accepted and signed. |
| AZPR-V6-I03: Git graft/replacement metadata accepted before side effects. | `CLOSED_AND_TESTED` | Independent graft test and submitted topology suite pass. |
| AZPR-V6-I04: Submodule/nested repository rejection and identity-safe cleanup. | `CLOSED_AND_TESTED` | Pre-side-effect rejection and exact stage-created ledger tests pass at source level. |
| AZPR-V6-I05: DOCX exact extraction omitted tabs and line breaks. | `CLOSED_AND_TESTED` | Actual uploaded DOCX rendered 227 units with 276 tabs and 19 breaks; unsupported normative parts list was empty. |
| AZPR-V6-I06: Missing black-box mutation/component-substitution testing. | `PARTIALLY_CLOSED` | V7 adds a five-case process harness, but it misses F02/F03/F04 and installer gate bypass. |
| AZPR-V6-I07: Key rotation/revocation/compromise recovery incomplete. | `PARTIALLY_CLOSED` | Schema/tool exist; F06 remains. |
| AZPR-V6-I08: Dedicated-host, supply-chain, remote-anchor, provider, and application qualification missing. | `NOT_CLOSED` | These are external phase gates and remain absent; F01 means they are not installer-enforced. |


## Prompt-set assessment

All 41 prompt texts are substantially aligned with the governing Master Operating Prompt: they preserve bounded-context language, deterministic-first processing, source provenance, idempotency, customer isolation, explicit pre-change reports, validation, documentation reconciliation, and stop conditions. Audit prompts are framed as read-only and controller-owned materialization is explicit.

Nevertheless, all 41 are classified `UNACCEPTABLE_FOR_UNATTENDED_EXECUTION` in this candidate. This is a shared control-plane result, not a claim that each prompt is poorly written. Execution confidence is below 60 because F01-F05 can invalidate qualification, leave post-validation processes alive, deadlock the controller, or exhaust the host. No active approved policy or roadmap exists, so path budgets, prerequisites, sequencing, and exact controller envelopes cannot yet be verified against a final execution plan.

## Architecture, product, and operational concerns

The implementation bundle alone cannot prove application-level safety. The following remain legitimate external qualification or project gates:

- dedicated-host root installation and fault-point qualification;
- proof that the exact Codex process and every descendant cannot access host secrets;
- Linux namespaces, capabilities, supplementary groups, ACLs, mounts, cgroups, quotas, and LSM policy;
- hardware-backed or externally brokered signing and compromise recovery;
- remote rollback-resistant journal anchoring;
- real approved offline mirror, wheelhouse, SBOM, provenance, validation image, and registry digest;
- production provider or isolated external-target testing;
- independent approval of the extracted canonical policy;
- Prompt 004 and independently reviewed roadmap generation;
- actual AZPR repository tests for customer isolation, authentication, migrations, backups, consent, suppression, PII, source terms, duplicate prevention, and application behavior.

These external gates are not defects merely because they are absent from a source bundle. F01 and F02 are defects because the code currently allows installation or signed qualification without enforcing truthful completion of those gates.

## Test execution and observed outcomes

| Test | Outcome |
|---|---|
| Sidecar and SHA-256 verification | PASS for candidate, reports, and delivery manifest. |
| Safe archive extraction | PASS; no unsafe members. |
| Candidate internal manifest | PASS, 170/170. |
| Reports internal manifest | PASS, 28/28. |
| Prompt duplicate comparison | PASS, 41/41 byte-identical. |
| Submitted pytest suite | PASS: 77 tests, 23 subtests. |
| Submitted phase-boundary harness | PASS: 5/5 cases. |
| Actual governing DOCX extraction | PASS: 227 units, 276 tabs, 19 breaks. |
| Detached descendant survival | FAIL REPRODUCED. |
| Fabricated 32-artifact clean-room evidence | FAIL REPRODUCED; signed receipt produced. |
| Bidirectional stdin/stdout deadlock | FAIL REPRODUCED; outer timeout return code 124. |
| Installer qualification-receipt enforcement | FAIL REPRODUCED; no receipt argument/gate. |
| Delivery manifest completeness | FAIL REPRODUCED; two referenced files absent. |
| Monolithic fresh-extraction verifier | Environmental limitation: exceeded the 15-minute tool ceiling. Its static checks, full pytest suite, reports verifier, and phase harness were run separately. |

## Final promotion decision

**Decision:** `NOT_READY`

**Pre-autonomous implementation disposition:** `NOT_READY_AS_IMPLEMENT_AS_IS_BUNDLE`

**Allowed use:** `MANUAL_NON_PRIVILEGED_REMEDIATION_BASELINE_ONLY`

A v8 implementation-only correction should close F01-F05 and complete independent regression coverage before any trusted installation. After that, a dedicated-host clean-room qualification must use real signed evidence, an approved canonical policy, and an independently reviewed roadmap before isolated autonomous dry runs are considered.

## Remaining assumptions and limitations

- No root installer was run on a dedicated host during this review.
- No actual Codex binary, namespace/LSM policy, remote anchor, HSM/broker, provider, validation registry, or production application repository was available.
- The organization did not provide a release signature; none was fabricated.
- The full monolithic verifier exceeded the tool execution ceiling, so its constituent checks were run independently.
- Conclusions about application business behavior remain unverified until the real AZPR repository and infrastructure exist.
