# AZPR v10 Major Changes

## 1. Probe authority is no longer caller-selected

V10 introduces an independently signed qualification-trust manifest that pins the approved probe keyring, policy, service identity, service attestation, revocation state, validity interval, host, candidate, challenge, and sequence. Internally valid signatures under an unapproved caller-created key are rejected.

## 2. Trust binding is enforced end-to-end

The cleanroom verifier, external receipt signer, installation authorization, installer preflight, phase transition, installed-generation manifest, and installation receipt bind the same canonical qualification-trust identity. The signer reconstructs the binding independently; the installer re-verifies the trust artifacts and every probe envelope before authorization reservation.

## 3. Qualification artifact set is explicit and versioned

The fixed v9 39-artifact assumption is replaced by `AZPR_V10_QUALIFICATION_ARTIFACT_SET` version `2.0`, containing exactly 48 named security-critical artifacts. Missing, extra, aliased, substituted, writable, symlinked, or changed artifacts fail closed.

## 4. Bootstrap roots use no-follow descriptor reads

The bootstrap authority manifest, authority public key, and trusted ancestors use descriptor-relative `O_NOFOLLOW` walks, regular-file and link-count checks, owner/mode checks, before/after inode metadata comparison, and fail-closed unsupported-platform behavior.

## 5. Release verification is non-root and process-isolated

`VERIFY-V10-CANDIDATE.py` uses a reviewer-owned mode-0700 temporary root, sanitized environment, one test per process group, hard timeouts, bounded output, descendant cleanup, source-mutation detection, cache rejection, strict schema checks, prompt-byte verification, current-document verification, and internal-manifest verification. No `/root` path or root state is required.

## 6. Independent findings became release blockers

The caller-created probe-root, arbitrary-policy, omitted-binding, revoked/wrong-role key, bootstrap symlink/hard-link/writable-ancestor, and non-root-verifier cases are release-blocking tests. Inherited concurrency, rollback/recovery, qualification-only first-install, evidence derivation, and atomic key-lifecycle controls are also re-tested.

## 7. Release curation is canonical

Stale v8/v9 operational documents are archived under `legacy/v9-candidate/`. Current v10 documents are hash-indexed; prompt bytes remain unchanged; AppleDouble/platform metadata and unresolved aliases are excluded from the final delivery.
