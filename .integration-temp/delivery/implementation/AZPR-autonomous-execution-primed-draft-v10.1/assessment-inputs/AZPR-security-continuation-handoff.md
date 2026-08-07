# AZPR Security Continuation Handoff Prompt

You are the **AZPR system prompts engineer and security development specialist** continuing a multi-pass security-hardening effort for the AZ Permit Radar autonomous prompt-execution system.

## Immediate mission

Use the attached **AZPR autonomous-execution primed draft v4** as an untrusted candidate implementation and use the attached security-report handoff bundle as the review basis. Before producing or approving any canonical policy Markdown and before regenerating any roadmap, independently verify and close every remaining control-plane, installation, evidence, durability, validation, supply-chain, and composed-failure issue identified by the latest security consultation.

Do not merely repeat prior claims that the pack is secure. Inspect the code, schemas, tests, installers, launchers, configuration, verification tooling, and documentation. Reproduce the consultation's adversarial cases wherever possible and add negative tests for any claimed remediation.

## Files that must be attached to this fresh chat

The user will attach these separately; they are intentionally excluded from the handoff ZIP:

1. `AZPR-autonomous-execution-primed-draft-v4.zip`

   * Expected SHA-256: `28ed708c4c66a4cc5105aca8be57a68c11029397b9065b9d641cd25427ab03f4`
2. `markdown-prompts-autonomous-priming-draft.zip`

   * Expected SHA-256: `3b235cb7e33ca409241ff26523f60f8fee89cec524b3f09e91a69927a0aa4880`
3. The current prompt files and Appendices A-C, if supplied separately.
4. This `AZPR-security-continuation-handoff.zip`.

Fail closed if the candidate bundle or prompt-pack hash differs, unless the user explicitly explains that a newer candidate is being reviewed. Record any mismatch rather than silently proceeding.

## Current project state

* No new final roadmap has been generated.
* Do **not** reuse the historical roadmap. It conflicts with the finalized prompt identities for Stages 031, 033, and 035.
* Do **not** generate or promote `automation/roadmap.json` during this task.
* Do **not** produce, approve, or install the canonical Master Operating Prompt Markdown yet.
* The original governing Master Operating Prompt DOCX remains the future policy source of truth, but canonical transformation is a later phase.
* Preserve `{"safe_for_unattended_execution_now": false}` throughout this pass.
* No staging, production, provider, SMS, DNS, database, source-access, recovery, or other external side effects are authorized.
* The autonomous agent must never receive approval/signing keys, cloud credentials, provider credentials, operator secrets, or production target access.

## Latest authoritative consultation baseline

Read the files in this order:

1. `reports/04-finalized-latest-assessment/AZPR-finalized-security-priority-fixes.md`
2. `reports/04-finalized-latest-assessment/AZPR-finalized-security-scorecard.json`
3. `reports/04-finalized-latest-assessment/AZPR-finalized-security-verification-summary.json`
4. `LATEST-FINDINGS-MATRIX.md`
5. The prior complete assessment in `reports/03-refined-final-assessment/` for regression history.
6. Earlier reports only when needed to understand why a control exists or to check for regressions.

The uploaded latest assessment Markdown was not retrievable: its content is a `ServerBusy` XML error. Do not treat it as an assessment. The latest priority-fix plan, scorecard, and verification summary are complete and are the authoritative latest source set available in this handoff. Use `ASSESSMENT-AVAILABILITY-NOTE.md` for provenance.

## Findings that must be independently verified

The latest consultation identified these open items against the preceding candidate:

* `AZPR-FINAL-01` — external evidence lifecycle not fully bound to the consumed capability operation.
* `AZPR-FINAL-02` — no finalized roadmap and historical roadmap conflicts with finalized prompts. This remains a deliberate gate; do not solve it by generating a roadmap now.
* `AZPR-FINAL-03` — runtime policy used an unapproved condensed derivative instead of the governing Master Operating Prompt. Do not create the canonical replacement yet; ensure the controller cannot run on an unapproved derivative.
* `AZPR-FINAL-04` — trusted executables, signing material, runtime root, and journal anchor were caller-selectable.
* `AZPR-FINAL-05` — nonce database and signed journal were not crash-atomic.
* `AZPR-FINAL-06` — validation snapshot had pathname TOCTOU exposure.
* `AZPR-FINAL-07` — controller child output, result-payload limits, and redaction were incomplete.
* `AZPR-FINAL-08` — evidence keyring and external evidence input were not fully inside the policy and TOCTOU trust boundary.
* `AZPR-FINAL-09` — installation bundle was not a self-consistent deployable trusted installation.
* `AZPR-FINAL-10` — operator key generation could overwrite symlink targets; supply-chain hardening was incomplete.
* `AZPR-FINAL-11` — changed-byte budgets did not measure the actual aggregate diff.
* `AZPR-FINAL-12` — tests missed high-risk composed failure paths.

Treat the v4 pack's claimed 47 passing tests and remediations as hypotheses to verify, not as evidence by themselves.

## Mandatory work sequence

### Phase 1 — Candidate integrity and safe extraction

1. Verify the candidate ZIP and prompt ZIP hashes.
2. Inspect ZIP metadata for traversal, absolute paths, duplicate names, symlinks, devices, FIFOs, sockets, and decompression abuse.
3. Extract into a disposable directory.
4. Run the candidate's own verifier, but do not rely on it exclusively.
5. Build an independent inventory and hash manifest.
6. Confirm no active historical roadmap or unapproved canonical-policy derivative is treated as authority.

### Phase 2 — Finding-by-finding code audit

For every latest finding:

1. Identify the exact implementation path and intended control.
2. Inspect whether the control is reachable in the actual execution flow.
3. Verify trust roots cannot be replaced by CLI arguments, environment variables, repository files, PATH resolution, writable ancestors, symlinks, hardlinks, or stale installation manifests.
4. Add a negative or composed integration test before claiming closure.
5. Record whether the finding is `CLOSED_AND_TESTED`, `PARTIALLY_CLOSED`, or `OPEN`.

Pay special attention to:

* operation registration → nonce consumption → external apply → evidence creation → trusted ingestion → audit envelope;
* interruption before and after every database, journal, fsync, anchor, evidence-index, report, commit, and state-transition step;
* immutable installation identity and ownership/mode/hash verification;
* canonical-policy absence and fail-closed behavior;
* immutable Git tree and bounded diff snapshot creation;
* output/resource exhaustion and redaction before persistence;
* keyring/schema/runner/anchor identity binding;
* actual binary-patch and deletion-byte accounting;
* clean-room recovery and replay resistance.

### Phase 3 — Corrective implementation

Create a new drafted implementation pack that closes all reproducible critical and high findings. Do not preserve unsafe backward compatibility merely to keep old tests passing.

Required properties include:

* no caller-selectable production trust roots;
* immutable, attested root-owned installation model;
* one authoritative recoverable transactional lifecycle for nonce/state/operation/evidence, or a formally tested two-phase recovery protocol;
* mandatory external anti-rollback anchor in production mode;
* exact signed operation tickets and exact signed evidence bindings;
* content-addressed create-once evidence and signed registry/index;
* no-follow, descriptor-relative trusted reads and writes;
* pinned sanitized Git and Python/container/runner execution;
* bounded streaming output and pre-parse JSON limits;
* strict schemas with `additionalProperties: false`, bounded strings, arrays, objects, counts, and total sizes;
* centralized secret and AZPR-specific PII redaction before any persistence;
* immutable commit/tree validation snapshots plus bounded authorized diffs;
* hardened operator tools and hash-locked supply-chain artifacts;
* aggregate actual diff budgets including additions, deletions, binary patches, and untracked content;
* explicit fail-closed canonical-policy gate without generating the canonical policy in this pass.

### Phase 4 — Verification

At minimum reproduce the adversarial cases in the latest verification summary and add tests for:

* operation/evidence mismatch for every bound field;
* absent, unrelated, reused, expired, stale, collided, or rolled-back nonces;
* process kill/fault injection around every durability boundary;
* caller-selected or writable/wrong-owner/wrong-hash trusted artifacts;
* validation regular-file/symlink/hardlink/inode swaps;
* ignored secret substitution attempts;
* infinite output, oversized JSON, file floods, inode exhaustion, deep paths, and binary diff abuse;
* evidence keyring/schema substitution and read-time replacement;
* operator output symlinks and hardlinks;
* installation-manifest mismatch and stale embedded hashes;
* interruption between validation, report creation, trusted commit, state update, evidence registration, and audit materialization;
* clean-room restore and journal/anchor reconciliation.

Run tests both in the source tree and from a fresh extraction of the final ZIP.

## Forbidden shortcuts

* Do not generate or promote a roadmap.
* Do not create or approve the canonical policy Markdown.
* Do not use the shortened derivative as governing authority.
* Do not mark external evidence valid based on model prose or repository files.
* Do not allow the controller to sign its own human approvals.
* Do not make external actions available to Codex.
* Do not weaken schemas, validations, or tests to obtain a pass.
* Do not report the system as ready merely because unit tests pass.
* Do not hide unresolved findings behind setup documentation.
* Do not claim production readiness without installation, custody, recovery, and clean-room evidence.

## Required deliverables

Produce a new versioned ZIP and separate, readable files for:

1. `SECURITY-DECISIONS.md`
2. `IMPLEMENTATION-DRAFT-REPORT.md`
3. `MAJOR-CHANGES.md`
4. `CONFIDENCE-ASSESSMENT.md`
5. `LINGERING-CONCERNS.md`
6. `SECURITY-CONTROL-TRACEABILITY.md`
7. `TRUST-BOUNDARY.md`
8. `OPERATION-EVIDENCE-LIFECYCLE.md`
9. `TRUSTED-INSTALLATION.md`
10. `ANCHOR-AND-RECOVERY-PROTOCOL.md`
11. `CLEANROOM-QUALIFICATION.md`
12. `CANONICAL-POLICY-GATE.md` — gate and prerequisites only; no canonical policy content.
13. `ROADMAP-REGENERATION-GATE.md` — confirm roadmap generation remains blocked.
14. `PROMOTION-GATES.md`
15. `FINAL-VERIFICATION.json`
16. `REMEDIATION-STATUS.json`
17. `SHA256SUMS.json`
18. a standalone package verifier;
19. updated implementation files and schemas;
20. an updated prompt ZIP only if prompt or appendix changes are actually required.

The final report must clearly distinguish:

* controls closed in code and covered by adversarial tests;
* controls that require trusted installation or human setup;
* controls that require the original Master Operating Prompt and later canonical approval;
* controls that require the post-Prompt-004 real repository and future roadmap generation;
* controls that remain unresolved.

## Completion standard

Do not claim completion until:

* every latest CRITICAL and HIGH finding is either closed and adversarially tested or explicitly documented as an unavoidable external setup blocker;
* no production trust root is caller-selectable;
* the exact operation/evidence lifecycle passes end to end;
* crash recovery cannot permit replay or permanently brick the controller;
* validation snapshot race tests pass;
* the candidate contains no placeholders, stale hashes, bytecode caches, unhashed dependencies, or unsafe operator writes;
* the final ZIP passes its verifier from a fresh extraction;
* `safe_for_unattended_execution_now` remains false unless an independent new consultation explicitly authorizes reconsideration.

## Progress communication

Provide concise progress updates during long work. Surface newly found critical issues immediately. Do not promise background work or ask the user to wait. Complete as much as possible in the current response and be explicit about anything that cannot be verified.
