# AZPR v8 Lingering Concerns and Closed Gates

These are not silently treated as source-code failures, but each remains a promotion blocker until independent evidence exists.

## Dedicated-host execution

- Real cgroup v2 delegation, `cgroup.kill`, PID/mount/network namespace creation, mount propagation, UID/GID/groups, capabilities, ACLs, quotas, LSM, and controller storage reservations must be tested on the exact host.
- The exact pinned Codex binary and all descendants must be proven unable to read host/controller secrets or write after completion.
- The root installer fault matrix must be executed with kill -9, reboot, disk-full, inode exhaustion, read-only filesystem, partial writes, and anchor outages.

## Qualification evidence

- The included positive qualification fixture is synthetic and must never be used for installation.
- Real reports require independent signers, raw evidence, fresh revocation state, reproducible measurements, and exact artifact bindings.
- Actual offline mirror, wheelhouse, lock, SBOM, provenance, image, and registry proof remain absent.

## Key lifecycle

- The transition state machine is executable but is not yet wired atomically into every real installed trust store.
- Hardware-backed or brokered signing, custody transition, emergency compromise response, and rollback-resistant remote anchoring remain unqualified.

## Policy and project gates

- The independent consultation verified the actual DOCX extraction as 227 units, 276 tabs, and 19 explicit breaks. That rendering is still unapproved and is not active.
- Prompt 004, roadmap generation/promotion, autonomous dry runs, external operations, and production/customer data remain blocked.
- The actual AZPR repository still needs customer-isolation, authentication, migrations, backups, consent/suppression, PII, source terms, idempotency, provider, and rollback testing.

## Release authority

No authorized organization release private key was available. SHA-256 manifests and sidecars establish delivery identity, not organizational approval.
