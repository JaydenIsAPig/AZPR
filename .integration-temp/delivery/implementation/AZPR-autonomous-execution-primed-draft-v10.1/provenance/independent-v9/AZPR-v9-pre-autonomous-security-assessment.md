# AZPR v9 Pre-Autonomous Security & Architecture Assessment

Generated: 2026-07-30T23:08:22.393009+00:00

## Executive decision

# **FAIL — NOT READY FOR PRE-AUTONOMOUS STAGING**

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

The v9 package is materially stronger than v8, but it is not safe to install as the trusted pre-autonomous control plane or to execute the numbered Codex prompts, even with a human supervising a staging environment. One independently reproduced Critical defect allows fabricated probe evidence to be authenticated by a caller-created probe key; two High implementation defects weaken bootstrap-root handling and make the official verifier require `/root`; and the real organization, host, signer, anchor, supply-chain, policy, and roadmap gates are intentionally absent.

The architecture still has a viable pathway to controlled autonomy. That pathway requires a v10 source correction, an independently reproducible non-root release gate, and real dedicated-host qualification before any numbered prompt is run.

## Scope and decision boundary

The review treated the Master Operating Prompt as governing product/architecture/safety policy and the original security-review prompt as the audit method. Self-reported PASS statements were not accepted as proof. The assessment included safe extraction, inventory/hash checks, prompt identity checks, source call-path tracing, selected submitted tests, independent adversarial harnesses, and review of operational qualification gaps.

This decision distinguishes:
- **Allowed now:** offline source inspection, unit-level corrective development, and preparation of a v10 candidate.
- **Not allowed:** root installation, trusted staging installation, canonical-policy activation, Prompt 004, roadmap generation/promotion, any numbered autonomous stage, external operations, credentials, provider access, or customer/production data.

## Artifact identity

| Artifact | Size | SHA-256 | Independent result |
|---|---:|---|---|
| `v9_deliverables(1).zip` | 1,250,456 | `ec74c0ee846f32eb40c42f55578a8a407cb27245cffbfbb67e08315e08c7e415` | Safe members; packaging defects noted |
| `AZPR-autonomous-execution-primed-draft-v9.zip` | 880,793 | `eeb5a826ab20aca7e4e618be435af2bbd51ca4d911dae3ff78d74a4d56e4f631` | Internal 233-entry manifest exact |
| `AZPR-autonomous-execution-primed-draft-v9-reports.zip` | 255,626 | `8206b3c91da3a9d545bc5744480439d11f6b61589fbb6365c64d0a74e786745b` | Safe package; self-reports treated as claims |
| Prompt archive bytes | 152,720 | `3b235cb7e33ca409241ff26523f60f8fee89cec524b3f09e91a69927a0aa4880` | 38 numbered + A-C, byte-identical; filename mismatch |


- The outer ZIP had 32 members and no unsafe archive path/type, but included 16 `__MACOSX/._*` metadata members.
- The implementation ZIP had 234 regular members: 233 authenticated entries plus `SHA256SUMS.json`.
- All internal implementation hashes matched independently.
- Seven of eight outer sidecars resolved and matched. The prompt sidecar references a filename absent from the delivery.
- Prompt bytes are unchanged from v8 and identical across copies. This is identity evidence, not execution authorization.

## Risk matrix

| ID | Severity | Likelihood | Impact | Risk | Status |
|---|---|---|---|---|---|
| AZPR-V9-IND-F01 | CRITICAL | HIGH | CRITICAL | Probe qualification trusts a caller-selected keyring and unpinned probe policy | OPEN_BLOCKER |
| AZPR-V9-IND-F02 | HIGH | MEDIUM | HIGH | Bootstrap authority manifest and authority key are read through symlinks | OPEN_BLOCKER |
| AZPR-V9-IND-F03 | HIGH | HIGH | HIGH | Official v9 verifier cannot run under the documented least-privilege source-review workflow | OPEN_BLOCKER |
| AZPR-V9-IND-F04 | HIGH | CERTAIN | HIGH | Mandatory real-world qualification and release-authority prerequisites are absent | OPEN_GATE |
| AZPR-V9-IND-F05 | MEDIUM | CERTAIN | MEDIUM | Prompt sidecar and delivery manifest reference a filename absent from the outer delivery | OPEN |
| AZPR-V9-IND-F06 | MEDIUM | CERTAIN | MEDIUM | Several governing promotion documents remain titled and worded as v8 inside v9 | OPEN |
| AZPR-V9-IND-F07 | MEDIUM | HIGH | HIGH | Release-blocking tests miss the trust-root and bootstrap-path cases found independently | OPEN |

### Finding details

#### AZPR-V9-IND-F01 — CRITICAL: Probe qualification trusts a caller-selected keyring and unpinned probe policy

**Status:** `OPEN_BLOCKER`  
**Affected:** `operator-tools/verify_v9_cleanroom_prerequisites.py:50-68,217-242,253-290`, `operator-tools/v9_probe_boundary.py:62-85,95-202`, `operator-tools/v9_external_signer_client.py:75-82`, `trusted-installation/v9_binding.py:17-58`, `trusted-installation/install.py:583-602`

**Evidence.** Independent harness generated a fresh Ed25519 caller key and nine fabricated PASS envelopes. verify_probe_manifest accepted all 9. A mutated signature was rejected, proving the cryptography works but the trust root is caller-controlled. The signed receipt binds the envelope-manifest hash but not the probe-keyring hash or an approved probe-policy hash.

**Impact / failure scenario.** A qualification submitter supplies its own probe keyring and signs invented all-PASS observations. The verifier builds a receipt that an external signer cannot distinguish from evidence rooted in an approved probe service because the unsigned receipt omits the probe keyring and authoritative probe policy.

**Required remediation.** Pin and sign the probe keyring, probe policy, and probe-service identity/attestation; include their hashes in the canonical artifact set, receipt, installation authorization, and transition state. Make the external signer validate those bindings and have the installer reverify envelope signatures and policy identity.

#### AZPR-V9-IND-F02 — HIGH: Bootstrap authority manifest and authority key are read through symlinks

**Status:** `OPEN_BLOCKER`  
**Affected:** `trusted-installation/v9_binding.py:149-180`, `trusted-installation/install.py fixed bootstrap inputs`

**Evidence.** Independent harness passed symlink paths for both the signed bootstrap manifest and its Ed25519 authority public key. verify_bootstrap_roots accepted them. The four downstream root artifacts use hash_regular, but the bootstrap manifest/key use Path.read_bytes without O_NOFOLLOW or ownership/ancestor checks.

**Impact / failure scenario.** A provisioning mistake, writable ancestor, or privileged local compromise substitutes a symlinked authority key and matching signed manifest, redefining all supposedly pinned qualification and authorization roots.

**Required remediation.** Read both fixed bootstrap files with descriptor-based O_NOFOLLOW/openat2 resolution, require root ownership, one link, non-writable mode and trusted ancestors, compare inode metadata before/after, and reject symlink/hard-link/rename races.

#### AZPR-V9-IND-F03 — HIGH: Official v9 verifier cannot run under the documented least-privilege source-review workflow

**Status:** `OPEN_BLOCKER`  
**Affected:** `VERIFY-V9-CANDIDATE.py:149-171 (especially line 157)`, `README.md verifier instructions`

**Evidence.** On a fresh safe extraction with PYTHONDONTWRITEBYTECODE=1, python3 VERIFY-V9-CANDIDATE.py exited 1 with PermissionError creating /root/azpr-v9-test-... because TemporaryDirectory is hardcoded to dir='/root'.

**Impact / failure scenario.** Independent reviewers either cannot reproduce the release gate or must run the entire verifier as root, expanding the blast radius of test code and contradicting the least-privilege qualification design.

**Required remediation.** Use an explicitly created reviewer-owned temporary root or secure TMPDIR, isolate each test without requiring UID 0, and add a release-blocking test that runs the verifier as a dedicated unprivileged account from a fresh extraction.

#### AZPR-V9-IND-F04 — HIGH: Mandatory real-world qualification and release-authority prerequisites are absent

**Status:** `OPEN_GATE`  
**Affected:** `README.md`, `V9-KNOWN-LIMITATIONS-AND-QUALIFICATION-DEPENDENCIES.md`, `PROMOTION-GATES.md`

**Evidence.** The candidate is unsigned and explicitly has no dedicated hardened host, production external signer/HSM, qualified rollback-resistant anchor, real power/disk/inode/reboot fault matrix, reproducible supply-chain evidence, key ceremonies, active canonical policy, Prompt 004 result, or promoted roadmap.

**Impact / failure scenario.** Installing or executing prompts now converts synthetic/source-level claims into trusted state without the independent roots and host measurements those claims depend on.

**Required remediation.** Complete the v10 source fixes first, then perform organization signing, dedicated-host qualification, external signer and anchor qualification, supply-chain rebuild/SBOM/provenance, key custody, canonical-policy approval, manual Prompt 004, and independent roadmap review in that order.

#### AZPR-V9-IND-F05 — MEDIUM: Prompt sidecar and delivery manifest reference a filename absent from the outer delivery

**Status:** `OPEN`  
**Affected:** `markdown-prompts-autonomous-priming-draft-v8.zip.sha256`, `AZPR-v9-delivery-manifest.json`, `outer ZIP member markdown-prompts-autonomous-priming-draft-v8(3).zip`

**Evidence.** The prompt bytes match the expected SHA-256, but the sidecar target markdown-prompts-autonomous-priming-draft-v8.zip does not exist; the actual member has '(3)' in its name. Seven other sidecars resolve and match. The outer ZIP also contains 16 __MACOSX AppleDouble files.

**Impact / failure scenario.** Automated intake rejects the delivery or binds a missing path even though the intended bytes are present.

**Required remediation.** Repackage with canonical filenames, regenerate the manifest/sidecars, remove platform metadata, and verify names and hashes from a fresh extraction.

#### AZPR-V9-IND-F06 — MEDIUM: Several governing promotion documents remain titled and worded as v8 inside v9

**Status:** `OPEN`  
**Affected:** `PROMOTION-GATES.md`, `PRIORITY-FIX-DISPOSITION.md`, `LINGERING-CONCERNS.md`

**Evidence.** These files are shipped in the v9 implementation but retain v8 titles, v8 gate language, and v7/v8 disposition framing.

**Impact / failure scenario.** Operators apply stale hashes, stage names, or closure assumptions during promotion, creating documentation/version drift at a security gate.

**Required remediation.** Issue v9-specific replacements, retain old documents only under an explicit historical/legacy path, and validate that current operational docs contain the exact v9 candidate hashes and findings.

#### AZPR-V9-IND-F07 — MEDIUM: Release-blocking tests miss the trust-root and bootstrap-path cases found independently

**Status:** `OPEN`  
**Affected:** `tests/test_v9_security_closures.py:178-193`, `v9 release test catalog`

**Evidence.** Five selected v9 security tests passed individually, including content substitution and qualified-artifact symlink checks. However, the bootstrap test mutates a downstream root file only; it does not symlink the bootstrap manifest/authority key. No test rejects a caller-created probe keyring and arbitrary policy.

**Impact / failure scenario.** A green self-test report gives false assurance while the root-of-trust substitution paths remain executable.

**Required remediation.** Add independent negative tests for caller-generated probe roots/policies, signer inability to validate omitted bindings, bootstrap leaf/ancestor symlinks, hard links, ownership/mode, TOCTOU, and least-privilege verifier execution.

## Execution and stress-check evidence

| Check | Outcome | Evidence |
|---|---|---|
| Outer archive safe-member inspection | `PASS_WITH_PACKAGING_NOISE` | 32 members; no traversal, absolute path, device, hard-link, or symlink member. 16 __MACOSX AppleDouble metadata files present. |
| Outer SHA-256 | `PASS` | ec74c0ee846f32eb40c42f55578a8a407cb27245cffbfbb67e08315e08c7e415 |
| Implementation internal manifest | `PASS` | 233 entries, 233 files excluding manifest; no missing, extra, or mismatched files. |
| Prompt identity | `PASS_BYTES_ONLY` | 38 numbered prompts + Appendices A-C; SHA-256 3b235cb7e33ca409241ff26523f60f8fee89cec524b3f09e91a69927a0aa4880; unchanged v8 prompt archive. |
| Sidecar resolution | `FAIL_1_OF_8` | 7 valid; prompt sidecar references absent canonical name while '(3)' copy exists with matching bytes. |
| Official candidate verifier, fresh extraction, non-root | `FAIL` | PermissionError at VERIFY-V9-CANDIDATE.py:157 due hardcoded /root temporary directory. |
| Submitted test suite, direct shared-process run | `INCONCLUSIVE_PARTIAL` | 83 passed, 11 failed, 2 skipped in 42.65s. Several failures were caused by privilege assumptions and shared-tree permission mutation; therefore they were not all treated as product defects. |
| Selected v9 security tests, isolated nodes | `PASS` | 5/5 passed: no-secret probe does not execute targets; root/secret boundary claims fail; exact 39-artifact substitution fails; alias/symlink qualified artifacts fail; pinned downstream bootstrap-root content substitution fails. |
| Caller-selected probe-root adversarial harness | `FAIL_SECURITY` | All 9 fabricated envelopes accepted. Signature mutation was rejected. |
| Bootstrap symlink adversarial harness | `FAIL_SECURITY` | Both symlinked root-of-trust inputs accepted. |

### Interpretation of the test results

The candidate's self-generated reports claim 96 tests, 23 subtests, and six black-box cases. Those counts were treated as claims until independently reproduced. The official verifier could not complete under the documented non-root workflow. A direct all-at-once pytest run is not a valid substitute for the candidate's intended one-process-per-test isolation because some tests change file permissions; it was useful only as a diagnostic. Five selected source-level controls passed in isolated invocations, but the independent trust-root cases were absent from the test catalog and failed.

No privileged installer, cgroup/namespace boundary, real Codex binary, real external signer/HSM, remote anchor, power-loss/disk-full/reboot matrix, supply-chain rebuild, or AZPR application repository was available in this sandbox. Those checks remain unperformed—not assumed to pass.

## V8 blocker regression status

| Prior finding | Status | Independent v9 disposition |
|---|---|---|
| AZPR-V8-F01 | `PARTIALLY_CLOSED` | Direct root execution/private receipt-key exposure is removed, but caller-selected probe trust can still fabricate qualification evidence. |
| AZPR-V8-F02 | `PARTIALLY_CLOSED` | Global lock and anchored transaction source exist; full 20-process/fault reproduction was not completed independently in this environment. |
| AZPR-V8-F03 | `PARTIALLY_CLOSED` | Exact 39 artifacts are bound, but probe keyring/policy/service identity are omitted and bootstrap authority paths are weak. |
| AZPR-V8-F04 | `PARTIALLY_CLOSED` | Anchored signed journal source exists; only a TEST ONLY file anchor is supplied and real rollback-resistant service is absent. |
| AZPR-V8-F05 | `CLOSED_SOURCE_LEVEL` | First install is forced to QUALIFICATION_ONLY and policy activation is a separate transition in source/tests; real host exercise remains. |
| AZPR-V8-F06 | `PARTIALLY_CLOSED` | Raw-evidence derivation logic exists; no independent real-machine evidence set is supplied. |
| AZPR-V8-F07 | `PARTIALLY_CLOSED` | Atomic ten-store epoch tool exists but is not integrated/exercised across real consumers. |
| AZPR-V8-F08 | `NOT_CLOSED` | Real host, organization release, supply-chain, key-custody, signer, anchor, and application evidence remain absent. |

## Prompt and project-architecture assessment

- The prompt archive is structurally complete: numbered prompts `001`–`038` and Appendices A–C.
- All 38 numbered prompts remain marked normal-execution eligible; all three appendices require explicit invocation and are not normal-execution eligible.
- The formal audit stages remain textually read-only, and the prompts retain strong instruction-integrity language, deterministic-first behavior, bounded product scope, domain distinctions, documentation reconciliation, and stop/escalation rules.
- Those prompt strengths cannot compensate for a shared Critical control-plane defect. Under the original promotion rule, all 41 artifacts remain **`UNACCEPTABLE_FOR_UNATTENDED_EXECUTION` as a system**, regardless of their prompt-text quality.
- No active canonical policy or promoted roadmap is present. This is correct for a development candidate, but it means the bundle cannot yet provide Codex with the authoritative execution context required for semi-autonomous staging.
- Current prompt-content security confidence: **86/100**. Current end-to-end execution confidence: **41/100**. Shared status: **UNACCEPTABLE_FOR_UNATTENDED_EXECUTION**.

The product architecture remains aligned with the governing modular-monolith model and narrow Arizona pilot. No product code was executed, so customer isolation, authorization, source provenance, idempotency, migrations, backup/restore, notification consent/suppression, provider terms, and PII behavior remain outside proven scope.

## Required remediation plan

### P0 — Must be closed before any trusted staging installation

1. **Pin probe-service trust.**
   - Add the probe keyring, authoritative probe policy, probe-service identity/attestation, and rotation/revocation state to the canonical qualified artifact set.
   - Bind them in the receipt, external-signing request/policy, installation authorization, and phase journal.
   - Reverify probe signatures and policy identity at installation.
   - **Exit test:** a fresh caller keyring and arbitrary policy must be rejected even when every envelope is internally valid; key rotation, revocation, stale policy, wrong host, and wrong candidate must also fail.

2. **Harden bootstrap root file handling.**
   - Use `O_NOFOLLOW`/descriptor-relative resolution for the manifest and authority key; enforce root ownership, one link, restrictive mode, trusted ancestors, and before/after inode identity.
   - **Exit test:** symlink/hard-link/ancestor substitution, writable parent, rename race, key replacement, and stale sequence all fail closed.

3. **Make the release verifier reproducible as non-root.**
   - Remove `dir='/root'`, create a secure reviewer-owned temporary root, isolate each test, and preserve cache-free/fresh-extraction checks.
   - **Exit test:** a dedicated unprivileged account completes all cataloged tests, subtests, black-box cases, schema checks, prompt checks, and manifest checks from a read-only fresh extraction.

4. **Add independent negative tests for P0.1–P0.3.**
   - The tests must assert trust-root provenance, not merely internal consistency beneath a supplied root.

### P1 — Must be complete before semi-autonomous Codex staging

1. Produce an organization-signed v10 release and immutable delivery manifest.
2. Qualify a dedicated host with the exact kernel/container/Codex/toolchain and prove cgroup, namespace, mount, UID/GID, LSM, quota, output, inode, disk, and cleanup containment.
3. Deploy and independently qualify the external receipt signer/HSM and rollback-resistant remote anchor.
4. Complete the power-loss, kill-9, reboot, disk-full, inode-full, read-only-remount, concurrent recovery, and anchor-outage matrix.
5. Produce reproducible supply-chain mirror, lock, SBOM, provenance, image attestation, and registry proof.
6. Perform key-generation/custody/rotation/revocation ceremonies and integrate atomic epochs across real consumers.
7. Approve the exact canonical policy derived from the Master Operating Prompt; then execute Prompt 004 manually.
8. Generate and independently review the roadmap against all 41 prompt files before any normal stage is eligible.

### P2 — Packaging and documentation

1. Repackage with canonical prompt ZIP naming and matching sidecar; remove `__MACOSX`.
2. Replace stale v8-titled promotion/disposition/lingering documents with v9/v10 current versions, keeping historical copies in a clearly marked legacy area.
3. Add a machine-readable current-document index and fail the release if stale version labels or hashes remain.

## Promotion checklist

Pre-autonomous staging may be reconsidered only when all are true:

- [ ] No open Critical or High source-level finding.
- [ ] Non-root independent verifier passes from a fresh, read-only extraction.
- [ ] Probe roots/policy/service identity are independently pinned and transitively signed.
- [ ] Bootstrap root symlink/ownership/TOCTOU tests pass.
- [ ] Organization release signature verifies against a separately provisioned root.
- [ ] Dedicated-host, signer, anchor, fault, supply-chain, and key-custody qualification evidence is real and independently verified.
- [ ] Canonical policy is approved; Prompt 004 is manually complete.
- [ ] Roadmap is generated, hash-bound, and independently reviewed against all 41 prompt bytes.
- [ ] Isolated non-production dry runs prove application-level authentication, customer isolation, migrations, backup/restore, consent/suppression, PII, source terms, idempotency, provider behavior, and rollback.
- [ ] `safe_for_unattended_execution_now` remains false until a later independent promotion review explicitly changes it.

## Final conclusion

**Pre-autonomous staging: FAIL.**  
**Semi-autonomous Codex deployment in staging: NOT AUTHORIZED.**  
**Full-autonomous pathway: VIABLE, but only after P0 source corrections and P1 real-world qualification.**

The correct next use of this bundle is as the immutable baseline for v10 corrective development, not as the trusted installer or execution control plane.
