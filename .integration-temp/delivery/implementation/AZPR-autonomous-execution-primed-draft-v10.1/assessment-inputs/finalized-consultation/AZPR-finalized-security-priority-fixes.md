# AZPR Finalized Security Priority Fixes

**Current decision:** `NOT_READY`  
**Required safety flag:** `{"safe_for_unattended_execution_now": false}`

## P0 — Must close before any controller dry run

### P0.1 Complete the signed operation/evidence lifecycle
**Affected:** `trusted-controller/controller.py`, `trusted-controller/evidence_registry.py`, `external-capability-runner/capability_runner.py`, evidence/roadmap/run-manifest schemas.

Implement an immutable controller-owned operation registration before external apply. Bind stage, environment, repository commit/tree, plan, capability manifest, target attestation, target, exact operation set, nonce, expiry and expected signer role. Put the same identifiers inside signed evidence. Consume/register the nonce atomically and make evidence-ID attachment a controller-owned post-operation state transition rather than a mutable roadmap edit.

**Exit tests:** valid round trip succeeds; absent/unrelated/reused nonce, wrong commit/tree/stage/environment/target/operation/plan/manifest/attestation, stale evidence, replay, collision and rollback all fail.

### P0.2 Install immutable trust roots
**Affected:** trusted controller launcher, validation launcher, runtime signing material, Git binary, anchor helper, keyrings, schemas, runtime root.

Provide a root-owned launcher and signed installation manifest that pins exact paths, hashes, ownership and modes. Remove production use of `AZPR_TRUSTED_GIT`, `AZPR_RUN_SIGNING_*`, `AZPR_RUNTIME_ROOT`, `AZPR_JOURNAL_ANCHOR_COMMAND` and approval/evidence keyring environment overrides.

**Exit tests:** caller-selected or writable/wrong-owner/wrong-hash binaries, keys, keyrings, schemas, anchors and runtime roots are rejected before execution.

### P0.3 Make nonce/state durability recoverable
**Affected:** `NonceLedger`, `SignedJournal`, external anchor integration.

Use a single authoritative transactional store or a recoverable two-phase protocol. External anchoring must be mandatory and pinned in production. Define signed recovery/migration events.

**Exit tests:** kill/fault injection before and after every database, journal, fsync and anchor step never permits replay and never permanently bricks the controller.

### P0.4 Eliminate validation snapshot TOCTOU
**Affected:** `trusted-validation-runner/trusted_validation_runner.py`.

Validate an immutable commit/tree plus bounded diff in a dedicated locked checkout, or copy through descriptor-relative O_NOFOLLOW file descriptors with pre/post fstat identity checks.

**Exit tests:** continuous regular-file/symlink/hardlink/inode swaps cannot alter snapshot contents or copy ignored secrets.

### P0.5 Establish the canonical governing policy
**Affected:** governing Master Operating Prompt and `automation/policy/AZPR-master-operating-prompt.md`.

Do not hash an unapproved condensed rewrite. Create a canonical machine-readable policy with a signed owner-approved transformation/completeness record.

**Exit tests:** section-by-section equivalence is reviewed; any omitted/changed clause changes the approved policy identity and blocks execution.

## P1 — Required before roadmap promotion

### P1.1 Bound and limit every controller input/output
Cap stdout/stderr while streaming, cap JSON before parse, add maxItems/maxLength to every result field, strictly schema `approval` and `external_plan`, and redact before all persistence.

### P1.2 Bind evidence trust roots to policy identity
Include evidence keyring/schema/install hashes and ownership in signed policy identity. Read evidence once from an O_NOFOLLOW descriptor.

### P1.3 Produce a self-consistent installation bundle
Replace all placeholders, correct the trusted runner hash, remove `__pycache__`, generate hash-locked dependencies, SBOM/provenance, root-owned install instructions and a signed installation receipt.

### P1.4 Harden operator tools
Use create-once O_NOFOLLOW writes for public/private keys and all operator outputs; verify ownership, hardlink count and post-open identity.

### P1.5 Enforce true diff budgets
Measure added, deleted and binary patch bytes plus untracked files; retain separate file-count/path-depth/total-result budgets.

### P1.6 Expand mandatory adversarial tests
Move the 10 reproduced tests into the verifier and add interruption tests between validation, report creation, commit, state update and nonce consumption.

## P2 — Defense in depth and operational readiness

- Implement signed policy migration, journal recovery and disaster-recovery procedures.
- Prove clean-room restore of state, nonce ledgers, evidence registry, anchors and repository binding.
- Add independent build provenance, reproducible artifacts and key rotation/revocation drills.
- Perform real application checks for customer isolation, source legality, consent, duplicate suppression, migration rollback, backups, data minimization and provider terms.
- Require a human-reviewed staging dry-run dossier before any live credential or target is available.

## Roadmap regeneration gate

Regenerate `automation/roadmap.json` **only after all P0 fixes and P1.1-P1.3 are complete**. The generated roadmap must be bound to the exact repaired hashes and must resolve stages 031, 033 and 035 to the finalized audit/plan-only prompts. Do not reuse the supplied historical roadmap.

## Final promotion checklist

- [ ] All P0 findings closed by adversarial tests.
- [ ] No caller-selectable production trust roots.
- [ ] Canonical governing policy approved and pinned.
- [ ] Exact operation/nonce/evidence lifecycle passes end-to-end.
- [ ] Immutable validation snapshot race tests pass.
- [ ] No placeholders, stale hashes, pycache, unhashed dependencies or unsafe operator writes.
- [ ] Final roadmap catalog matches 001-038 and A-C byte-for-byte.
- [ ] Clean-host isolated non-production dry run passes.
- [ ] Independent reassessment finds no open CRITICAL/HIGH findings.
- [ ] Only then may `safe_for_unattended_execution_now` be reconsidered.
