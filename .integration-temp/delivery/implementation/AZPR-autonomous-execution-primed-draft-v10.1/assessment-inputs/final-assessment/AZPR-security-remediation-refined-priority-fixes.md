# AZPR Refined Security Pack — Prioritized Promotion Fix Plan

Generated: 2026-07-24T21:43:04.281938+00:00

## Decision

Unattended execution remains blocked. Apply fixes in the order below because later controls rely on earlier roots of trust.

## P0.1 — Repair approval binding

**Problem:** approvals are required to contain their own final file hash.

**Implementation:**

1. Build a `base_policy_hashes` object that excludes approval documents.
2. Require approvals to bind:
   - stage or appendix ID;
   - exact target commit and tree;
   - exact roadmap, prompt, master prompt, controller, runtime, validation runner, schema, keyring, and policy hashes;
   - environment and required actions;
   - issue/expiry timestamps and nonce.
3. After verification, place each approval's file hash in the signed run manifest.
4. Reject any approval file path inside an agent-writable directory unless it is created and protected by an operator workflow.
5. Add positive and negative end-to-end tests.

**Exit test:** an operator can create a valid approval once; changing one byte of any bound artifact invalidates it; no self-reference is required.

## P0.2 — Make nonce use atomic

1. Acquire one exclusive lock before reading the ledger.
2. Verify the entire signed chain under that lock.
3. Reject an existing nonce.
4. Append, fsync the file, fsync its directory, and release the lock.
5. Prefer a uniqueness-enforced transactional database or platform keystore for high-consequence apply manifests.
6. Test with threads, processes, and two runner instances.

**Exit test:** exactly one of 100 simultaneous consumers succeeds.

## P0.3 — Bind state to repository and policy identity

Add these fields to every signed state transition:

- repository ID;
- base branch;
- reconciled commit and tree;
- roadmap SHA-256;
- prompt-catalog SHA-256;
- master-prompt SHA-256;
- controller/runtime/validation-runner versions and hashes;
- schema-set hash;
- previous journal head.

Before each action:

1. verify current HEAD and tree;
2. verify ancestry from every completed/reconciled stage;
3. verify all current policy hashes;
4. reject silent roadmap-version reuse;
5. require a signed policy-migration event for authorized changes.

## P0.4 — Secure trusted writes and path ownership

1. Open the repository root once as a trusted directory descriptor.
2. Create/open output files with descriptor-relative no-follow operations.
3. Reject symlink ancestors, hard links, devices, FIFOs, sockets, and non-regular leaves.
4. Use create-once semantics for run history and audit artifacts.
5. Split:
   - agent-writable paths;
   - controller-writable paths;
   - immutable historical paths.
6. Verify the agent diff before controller output is added.

## P0.5 — Harden Git execution

Use:

- a pinned absolute Git binary;
- a minimal environment;
- a trusted empty hooks directory;
- disabled signing, pager, editor, credential helpers, fsmonitor, and optional locks;
- explicit rejection of unsafe filters and config includes;
- `--no-verify` for trusted controller commits;
- NUL-delimited path parsing;
- a dedicated checkout controlled by the controller.

Add malicious hook/filter/config regression tests.

## P0.6 — Implement trusted external-evidence ingestion

Create a controller command that:

1. receives evidence from outside the repository;
2. securely opens it without following symlinks;
3. validates the exact evidence schema;
4. verifies allowed evidence signer identities and roles;
5. verifies evidence ID, target, environment, plan hash, target-attestation hash, source commit/tree, capability nonce, operation IDs, and timestamps;
6. checks the nonce and plan were previously registered;
7. stores evidence in immutable content-addressed storage;
8. records it in a signed evidence registry;
9. injects only a bounded verified envelope into the relevant audit prompt.

No release/canary audit may PASS without required evidence IDs.

## P0.7 — Pin the external runner trust domain

1. Remove or ignore caller-supplied config/schema/keyring paths in production mode.
2. Install a root-owned launcher with pinned hashes.
3. Verify ownership and mode of every path ancestor.
4. Use distinct keys for manifests, target attestations, evidence, and runtime journals.
5. Require one distinct signer per privileged role.
6. Execute only root-owned immutable adapters.
7. Treat rollback as failure/non-completion.
8. write evidence with create-once content-addressed semantics.

## P0.8 — Enforce Appendix A authorization

For any security-sensitive correction, require:

- signed authorization document;
- exact audit ID and audit report hash;
- exact correction IDs;
- exact allowed file paths;
- target commit/tree;
- policy hashes;
- approver roles/quorum;
- nonce and expiration.

The model-provided `human_authorization_id` is descriptive only and must never satisfy the gate by itself.

## P1 — Strengthen isolation and anti-abuse controls

1. Anchor signed-journal heads externally to prevent rollback.
2. Enforce aggregate actual-diff budgets, including untracked files and bytes.
3. Build validation snapshots from tracked files and authorized additions only.
4. Bound stdout/stderr, JSON size, evidence bytes, files, directories, depth, and inodes.
5. Lock the worktree during snapshot and validation or use an immutable dedicated checkout.
6. Strictly schema-validate all deployment plans, adapter requests/responses, audit results, and correction payloads.
7. Redact and cap all generated reports.
8. Bind exact target-attestation hashes.
9. Add create-once evidence indexes and retention policy.

## P2 — Supply-chain and operational assurance

1. Add package artifact hashes and an SBOM.
2. Pin trusted executables and container-engine version/hash.
3. Make the signing tool schema-aware, hash-displaying, confirmation-gated, and no-follow.
4. Document key generation, storage, rotation, revocation, quorum, and break-glass procedures.
5. Test all seven validation profiles against the actual repository stack.
6. Run a full disaster-recovery and failed-deployment exercise.
7. Obtain independent security review before enabling any external apply operation.

## Promotion gate

Promotion is allowed only after:

- all P0 findings are closed;
- no critical or high test is skipped;
- every prompt has execution confidence of at least 85;
- Stages 034 and 036 can consume verified immutable evidence;
- Appendix A rejects invented authorization IDs;
- a clean-room end-to-end run completes without credentials in the autonomous environment;
- a human reviewer signs the final roadmap, controller build, validation image, schemas, keyring policy, and external-runner installation manifest.
