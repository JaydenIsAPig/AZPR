# Operator Authentication: Installation, Enrollment, Revocation, and Failure

## Status and authority

This runbook describes a future ceremony. The repository contains inert source
only. It does not authorize installation, Secure Enclave key creation,
enrollment, trust-record creation, controller activation, H0-T02, commit,
merge, or push.

The proposed installation identity is
`AZPR-H0-OPERATORAUTH-20260811-001`. A project-owner-approved immutable ticket
must exist before any ceremony begins. The AI and implementation developer must
not create or supply its approval. The current
`AZPR-H0-TRANSPORT-20260807-001` ticket must not be revised to add this work.

## Required ticket inputs

The installation ticket must bind all of the following exact values:

- host identity, macOS version, and architecture;
- built helper SHA-256 and `AZPR_OPERATOR_APPROVAL_HELPER_V1` build identity;
- code-signing identity and designated requirement, or an explicit H0-only
  unsigned hash-pin limitation;
- absolute installation path, owning UID/GID, and complete POSIX mode;
- application tag
  `com.azpermitradar.operator-approval.secure-enclave.p256.v1`;
- P-256 Secure Enclave algorithm and the permanent,
  `WhenUnlockedThisDeviceOnly`, `privateKeyUsage`, and `biometryCurrentSet`
  access-control attributes;
- absolute host-owned trust-record, replay-ledger, and lock paths outside the
  repository and AI-writable directories;
- authenticated operator subject and the existing role
  `Head of AZPR Operations`;
- enrollment, signature-verification, cancellation, and fallback-exclusion
  tests;
- revocation, removal, rollback, and recovery steps;
- prohibited password, Apple Watch, application-password, cached,
  unattended, bulk, and software-signer fallbacks.

Missing or changed values require a new approval identity. Do not infer a
subject, signing identity, path, owner, or permission mode from this template.

## Build and independent inspection

1. Begin from the exact approved source commit on a disposable build path.
2. Use compatible Xcode/Swift tooling and build the release helper for the
   ticketed architecture. Do not execute its enrollment API.
3. Format, build, and run Swift tests. Run the Python suites with exactly
   `cryptography==46.0.4` and compare the Swift/Python golden vector.
4. Inspect the final Mach-O, entitlements, linked frameworks, architecture,
   code signature, designated requirement, and SHA-256 independently.
5. Confirm the executable has no command-line or environment switch for a
   software signer and that normal decision startup cannot create a key.
6. Present those exact artifact facts in the installation ticket. A rebuild or
   byte change invalidates the digest and requires review again.

## Installation and enrollment ceremony

Run these steps only after independent approval of the new ticket:

1. Reobserve the approved host, OS, architecture, install destination,
   trust-state parent directories, owners, and permissions. Stop on drift.
2. Install only the hash-bound helper at the absolute approved path. Reject
   symlinks, nonregular files, group/world-writable content, unexpected owner
   or mode, signature failure, designated-requirement mismatch, or SHA drift.
3. Invoke a separately ticketed enrollment utility or ceremony entry point.
   The decision helper itself exposes no enrollment command. If the stable
   application tag already exists, stop; never replace it silently.
4. Create the P-256 key with `SecKeyCreateRandomKey` and the exact approved
   Secure Enclave/access-control attributes. Never request or export private
   key bytes.
5. Export the public key only in 65-byte ANSI X9.63 uncompressed form beginning
   with `0x04`; record its base64 bytes and exact SHA-256. Do not autodetect
   encodings.
6. Bind the approved subject and role to the public key, authenticator, helper
   path/hash/build/signature, enrollment time, and ACTIVE status in a canonical
   host-owned trust record. Write it atomically with the ticketed owner/mode.
7. Initialize the replay ledger and lock in their host-owned directory. Verify
   restart and concurrent-consumption failure paths before activation.
8. Perform separately recorded hardware tests: one approved signature, one
   rejected signature, cancel, timeout, lockout/unavailable Touch ID, password
   and Watch exclusion, fresh-context behavior, nonexportability, helper byte
   tamper rejection, and signature verification by Python.
9. Record truthful evidence. Do not activate the adapter unless all required
   tests pass and the active controller contract separately authorizes it.

## Normal decision behavior

The controller must complete preflight and validate the canonical manifest,
ticket, immutable review, evidence, and digest before opening the helper. The
helper displays all ticket facts as noneditable plain text. Approve and Deny
each create a fresh zero-reuse `LAContext` and require a successful
`SecKeyCreateSignature` operation. No default Approve control or remembered
authentication exists.

The controller verifies helper path/type/owner/mode/hash/signature/build, ACTIVE
trust, exact public key, every signed field, DER ECDSA signature, nonce,
timestamps, ticket digest, and role. Subject and role are read only from host
trust. Immediately before every material action it repeats ticket/review/trust/
signature/expiry checks, reobserves all targets, and atomically consumes the
action claim. Any mismatch stops without authority.

## Revocation and helper removal

Revocation, role change, helper replacement, trust-store edit, biometric
reenrollment, key rotation, or key replacement requires explicit new authority.

1. Stop controller use of the adapter before modifying trust.
2. Atomically change the exact trust record to `REVOKED` and set `revoked_at`.
   Python rejects both `REVOKED` and `ROTATING`; no rotation mode is currently
   governed.
3. Retain prior public assertion evidence and the old public key needed for
   audit according to the future retention policy. Never retain a private key.
4. Remove the installed helper and Secure Enclave key only if the approved
   revocation ticket explicitly lists those destructive actions and rollback
   expectations.
5. A replacement helper, key, subject, role, path, owner, mode, or designated
   requirement receives a new approval ID and new trust record. Do not mutate
   an ACTIVE identity in place.

## Failure and recovery matrix

| Observation | Required response |
|---|---|
| Cancel, close, or timeout | Record only a non-authorizing terminal event; execute nothing |
| Biometric cancel, failure, lockout, or unavailable Touch ID | Fail closed; do not offer password, Watch, or application fallback |
| Missing key or key lookup error | Stop; never create a replacement during decision handling |
| Fingerprint enrollment changed | Treat the `biometryCurrentSet` key as invalid; revoke and request a new enrollment ticket |
| Helper path, owner, mode, hash, build, or signature drift | Do not launch; quarantine only under separate host authority |
| Trust record missing, unsafe, noncanonical, revoked, or rotating | Stop before helper invocation |
| Noncanonical, polluted, excessive, crashed, signaled, or timed-out helper output | Stop; create no APPROVED record |
| Ticket/review/evidence/target drift or expiry | Stop; material authority changes require a new approval ID |
| Replay ledger/lock error or duplicate/concurrent claim | Stop; never reconstruct authority from repository files or model output |
| Action fails after authorization | Write truthful safe evidence/outcome; do not claim success or commit as success |

There is no recovery key or hardware-token implementation. Recovery means
revocation followed by a newly governed replacement ceremony, not bypassing
Touch ID or silently regenerating a key.

## H0 and production limitations

An explicitly approved hash-pinned unsigned helper may be evaluated only as an
H0 qualification limitation. It is not a production-ready autonomous trust
boundary. Production claims require an approved signing identity, designated
requirement, protected host install/trust/state ownership, hardware test
evidence, operator enrollment evidence, controller activation authority, and
independent qualification. Software tests and a successful Swift build prove
none of those host or biometric properties.
