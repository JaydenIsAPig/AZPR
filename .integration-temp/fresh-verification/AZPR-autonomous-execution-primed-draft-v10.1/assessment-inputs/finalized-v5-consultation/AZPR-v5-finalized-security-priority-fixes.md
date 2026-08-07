# AZPR v5 Finalized Security Priority Fixes

Generated: `2026-07-27T00:53:28.658318+00:00`

## Required disposition

`NOT_READY`

```json
{"safe_for_unattended_execution_now": false}
```

Do not regenerate the roadmap, approve a canonical policy, execute Prompt 004, install the production control plane, or run autonomous stages until every P0 and P1 item below passes its exit tests and a new independent review.

## P0 — Critical blockers

### P0.1 Eliminate Git-metadata and ignored-file control bypasses

**Finding:** `AZPR-V5-01`  
**Components:** `trusted-controller/secure_runtime.py`, `trusted-controller/controller.py`, `trusted-validation-runner/trusted_validation_runner.py`, repository ownership/setup.

Implementation requirements:

- Make `.git` and worktree administrative metadata controller-owned and non-writable to the agent UID/GID.
- Capture a pre-run cryptographic inventory of security-relevant Git metadata and require an exact post-run match.
- Explicitly reject changes to `.git/info/exclude`, `.git/config`, attributes, refs, hooks, index, alternates, objects/info, worktree metadata, and exclude sources.
- Replace ignore-aware untracked discovery with an independent no-follow filesystem inventory that classifies every path, then deliberately excludes only controller-approved local artifacts.
- Ensure path budgets, validation snapshots, clean-worktree checks, tree digests, commit inventory, abandon, and reconcile all use the same complete candidate path set.
- Treat `.gitignore`/attributes modifications as ordinary changed files and recalculate ignored-path visibility before acceptance.

Exit tests:

- reproduce the v5 harness case and verify it blocks;
- try `.git/info/exclude`, local config, global excludes, nested worktree metadata, `.gitignore`, and attributes variants;
- prove an ignored executable/config/secret cannot persist after success, failure, abandon, or interruption;
- prove the agent UID cannot write Git metadata.

### P0.2 Enforce private-key confidentiality against the actual agent identity

**Finding:** `AZPR-V5-02`  
**Components:** `trusted-installation/install.py`, trusted installation schema/manifest, key custody procedures.

Implementation requirements:

- Add secret-specific validators requiring root-owned, single-link regular files with mode exactly 0600 or stricter.
- Evaluate POSIX ACLs, supplementary groups, mount/namespace exposure, and parent traversal.
- Before activation, fork/drop to the configured agent UID/GID and prove every private key and controller-only state path is unreadable/unopenable.
- Stop recording or exposing unnecessary private-key paths to the agent environment.
- Prefer hardware-backed signing or a narrow broker so the agent never shares a filesystem namespace with raw private keys.

Exit tests:

- reject 0644/0640/ACL-readable keys;
- prove the exact Codex child cannot read runtime, evidence, installation, release, or operator keys;
- prove stolen public metadata cannot reveal a readable secret path;
- exercise rotation/revocation and compromised-key recovery.

## P1 — High-severity blockers

### P1.1 Bind supply-chain attestations to exact installed artifacts

**Finding:** `AZPR-V5-03`

- Recompute and compare SBOM/provenance hashes with attestation fields.
- Bind provenance to exact requirements input, lock, mirror inventory/attestation/public key, wheelhouse contents, two resolution passes, Dockerfile, image digest, and installed Python runtime.
- Include verified identities in the signed installation manifest and receipt.
- Reject stale, extra, missing, or unrelated supply-chain documents.

Exit: all one-byte substitution, stale-attestation, wrong-image, wrong-lock, wrong-mirror, and wrong-wheelhouse tests fail before installation writes.

### P1.2 Remove configurable production authorization trust roots

**Finding:** `AZPR-V5-04`

- Generate production external-runner config from installer-verified components.
- Require exact path/hash/key-ID equality with the installation manifest.
- Pin each adapter as an installed component; prohibit arbitrary production adapter/keyring paths.
- Make runtime load the manifest component directly rather than trust a path string inside config.

Exit: substituted config/keyring/key/schema/adapter/controller key/evidence key fails at installation and runtime.

### P1.3 Preserve the Master Operating Prompt exactly

**Finding:** `AZPR-V5-05`

- Use the exact DOCX hash or a deterministic lossless extraction as the enforcement authority.
- Bind every source paragraph to exact canonical spans and hashes; require canonical span completeness and reject unmapped normative text.
- Generate a deterministic review diff and require independent signatures over all exact artifacts.
- Remove free-form “meaning preserved” mappings as sufficient proof of completeness.

Exit: truncated, reordered, omitted, contradictory, one-heading, and unauthorized-expanded policies are rejected.

## P2 — Verification and operational hardening

### P2.1 Expand the security verifier and regression suite

**Finding:** `AZPR-V5-06`

Add the five independent harness cases plus mutation tests, and require fresh-extraction execution with exact test IDs/results in `FINAL-VERIFICATION.json`.

### P2.2 Make activation and receipt recovery unambiguous

**Finding:** `AZPR-V5-07`

- Verify every private/public pair before writes.
- Add activation intent/state and deterministic recovery.
- Prevent a nonzero installer exit from silently leaving a newly active generation without a final receipt.
- Execute kill/fault injection after every write, fsync, rename, lock, history, and receipt boundary.

### P2.3 Correct the reports-bundle manifest scope

**Finding:** `AZPR-V5-08`

Generate a dedicated `SHA256SUMS.json` for the reports ZIP whose inventory exactly matches that archive, or replace it with an explicit signed reference to the full candidate manifest. Add bundle name/type and expected inventory count to prevent cross-bundle reuse.

Exit: the reports archive verifies with zero missing, extra, or mismatched members.

### P2.4 Complete real clean-room qualification

After code fixes:

- use a dedicated host and exact root/non-root identities;
- verify bundle release authenticity from a pretrusted organizational key;
- qualify hardware-backed key custody and remote rollback-resistant anchor;
- build/verify the real offline mirror, wheelhouse, SBOM, provenance, and pinned validation image;
- qualify exact Codex/container binaries;
- run branch/reset/detached-HEAD/force-push/stale-audit/roadmap/prompt mutation tests;
- run symlink/hardlink/path-depth/file-count/output/evidence exhaustion tests;
- run external-operation partial/failure/rollback/interruption and evidence collision/replay tests.

## Final promotion checklist

- [ ] `AZPR-V5-01` closed and adversarially tested.
- [ ] `AZPR-V5-02` closed and exact agent secret denial proven.
- [ ] `AZPR-V5-03` closed with exact supply-chain binding.
- [ ] `AZPR-V5-04` closed; runtime uses only manifest-pinned trust roots.
- [ ] `AZPR-V5-05` closed; governing policy is exact/lossless and hash-bound.
- [ ] All new regression and mutation tests pass from a fresh release extraction.
- [ ] Root installer kill/recovery matrix passes.
- [ ] Real remote anchor and exact installed binaries are qualified.
- [ ] No active roadmap exists before Prompt 004 approval and one-use authorization.
- [ ] Regenerated roadmap has exact bounded paths and passes independent review.
- [ ] Final independent assessment reports zero open Critical/High findings.
- [ ] Only then may `safe_for_unattended_execution_now` be reconsidered.
