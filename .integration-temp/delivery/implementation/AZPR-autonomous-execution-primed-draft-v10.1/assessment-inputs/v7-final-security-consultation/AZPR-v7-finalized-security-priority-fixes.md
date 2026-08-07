# AZPR v7 Security Priority Fixes and Readiness Plan

## Current disposition

- **Install v7 as trusted control plane:** blocked.
- **Use v7 for autonomous or trusted dry-run execution:** blocked.
- **Use v7 as source for a supervised v8 remediation pass:** allowed only in a non-root isolated branch.
- **Unattended execution flag:** `false`.

## P0 — Must close before any trusted installation

### P0.1 Enforce qualification authorization inside the root installer

**Finding:** AZPR-V7-F01  
**Components:** `trusted-installation/install.py`, qualification schemas, installer receipt store.

The installer must require a one-use qualification authorization before it performs recovery, creates directories, reads private keys, or modifies trusted state. The authorization must be independently signed and bind:

- exact candidate ZIP and authenticated bundle-root hashes;
- installer source/version and installation manifest schema;
- dedicated-host identity and measured boot/OS policy where applicable;
- exact Codex, Git, Python, container engine, anchor helper, and adapter hashes;
- agent UID/GID and namespace/cgroup/mount/LSM configuration hashes;
- validation-image digest and registry proof;
- all qualification-report hashes and signer roles;
- canonical-policy source and record hashes;
- expiry, sequence, and one-use nonce.

**Exit tests**

1. Missing receipt fails before any write.
2. Wrong host, bundle, tool hash, report set, signer, expiry, policy, or nonce fails.
3. Reuse and rollback fail.
4. Fault injection at every pre-activation point leaves no trusted installation or consumed authorization ambiguity.

### P0.2 Replace shallow clean-room checks with semantic, signed verification

**Finding:** AZPR-V7-F02  
**Components:** `operator-tools/verify_v7_cleanroom_prerequisites.py`, schemas, report signers, test fixtures.

For every one of the 32 artifacts, define the actual expected schema, provenance, authorized signer role, cross-binding matrix, and reproducible measurement. Verify:

- signed reports from distinct authorized roles;
- executable and public-key parsing plus exact installed identity;
- keyring schema, unique keys, roles, revocation state, and quorum;
- SBOM format and linkage to build provenance and bundle;
- mirror/wheelhouse inventory and dependency-lock completeness;
- validation-image attestation, registry digest, Dockerfile, provenance, and SBOM linkage;
- host namespace/capability/group/ACL/mount/cgroup/LSM measurements;
- remote-anchor identity and challenge/response;
- fault-matrix raw evidence and report hashes;
- isolated target/provider evidence where required.

Delete the current synthetic “complete” fixture as an acceptance oracle. Preserve it as a negative adversarial corpus.

**Exit tests**

1. The reproduced fabricated corpus is rejected.
2. Every unsigned or self-declared PASS report is rejected.
3. Cross-substitution, stale evidence, wrong host, wrong bundle, and wrong image fail.
4. An independent verifier reproduces every PASS from immutable raw evidence.

### P0.3 Contain and terminate the complete Codex process tree

**Finding:** AZPR-V7-F03  
**Components:** `trusted-controller/secure_runtime.py`, controller lifecycle, handoff cleanup.

Use a dedicated cgroup and PID namespace per run. The controller must treat the complete execution unit—not the main PID—as the child. On success, failure, timeout, or interruption:

1. close agent input;
2. terminate/freeze the full cgroup;
3. wait until no processes remain;
4. revoke/unmount write access;
5. only then inspect/import results and validate the repository.

Do not rely only on `killpg`, because descendants may create new sessions or otherwise escape a process-group-only model.

**Exit tests**

- background shell, double-fork, `setsid`, inherited-FD, orphan, and fork-bomb variants;
- proof that no write occurs after controller completion;
- failure if cgroup emptiness cannot be proven;
- interruption between main PID exit and descendant teardown.

## P1 — Must close before supervised stage execution

### P1.1 Make child I/O fully nonblocking and deadline-bound

**Finding:** AZPR-V7-F04

Register stdin, stdout, and stderr in one selector immediately after spawn. Stream bounded input only when writable while concurrently draining bounded output. The timeout must include input transfer, output collection, process wait, and teardown.

**Exit tests:** bidirectional pipe saturation, maximum valid input/output, early child exit, broken pipe, timeout, overflow, and descendant cleanup.

### P1.2 Enforce handoff filesystem quotas and bounded cleanup

**Finding:** AZPR-V7-F05

Provision each run on a quota-controlled mount/tmpfs with byte and inode limits. Enforce maximum entries, path depth, file size, total allocated blocks, and cleanup traversal. Reserve controller/journal storage separately. Bind the exact mount/quota configuration into the qualification report and installer authorization.

**Exit tests:** millions of files, sparse files, deep paths, concurrent creation during cleanup, full disk, full inode table, sockets/FIFOs/devices, hard links, and rename races.

### P1.3 Expand independent black-box regressions

Add the five independently reproduced cases to the mandatory release suite. The release must fail if:

- the installer accepts no qualification receipt;
- fabricated clean-room evidence is signed;
- any descendant survives normal completion;
- internal timeout is bypassed by pipe deadlock;
- handoff quotas are absent or ineffective.

Mutation tests should replace one artifact/component at a time and verify that every binding is actually consumed by the enforcing code.

## P2 — Defense in depth and operational completeness

### P2.1 Complete signed key rotation, revocation, and compromise recovery

**Finding:** AZPR-V7-F06

Implement an installed, sequenced, remote-anchored transition ledger. Bind old/new keyring hashes, roles, quorum, effective time, compromise status, nonce, and recovery policy. Apply transitions atomically across controller, approvals, evidence, installation, and adapters.

### P2.2 Repair and sign the delivery envelope

**Finding:** AZPR-V7-F07

Regenerate the reports after incorporating the actual governing DOCX. Include the two missing report-verification files or remove them from the manifest. Produce one complete delivery manifest and, when the organization is ready, sign it with an established release authority.

### P2.3 Perform dedicated-host and project qualification

After P0/P1 source fixes:

- build the real offline mirror, wheelhouse, SBOM, provenance, image, and registry proof;
- qualify namespaces, cgroups, capabilities, groups, ACLs, mounts, quotas, and LSM policy;
- deploy the remote rollback-resistant anchor;
- qualify hardware-backed/brokered signing;
- run installer fault points and recovery;
- prove Codex and descendants cannot access secrets;
- approve the exact canonical policy;
- execute Prompt 004 manually;
- generate the roadmap once and independently audit it;
- test the actual AZPR repository for isolation, authentication, migrations, backups, consent/suppression, PII, source terms, idempotency, and provider behavior.

## Final promotion checklist

Promotion to isolated autonomous dry runs requires all of the following:

- [ ] Zero open Critical or High findings.
- [ ] P0/P1 adversarial tests pass independently.
- [ ] Installer enforces an independently signed, one-use qualification authorization.
- [ ] Qualification reports are signed, semantically verified, and exactly cross-bound.
- [ ] Full process tree is contained and absent before validation.
- [ ] I/O timeout cannot be bypassed.
- [ ] Handoff storage and cleanup are quota-bounded.
- [ ] Dedicated-host installation and fault matrix pass.
- [ ] Remote anchor and key lifecycle are operational.
- [ ] Exact canonical policy is visually reviewed and independently approved.
- [ ] Prompt 004 is completed manually.
- [ ] Roadmap is generated once, independently reviewed, and promoted.
- [ ] Actual project security and business-behavior gates pass.
- [ ] Final independent assessment sets `safe_for_unattended_execution_now` only after all controls are proven.
