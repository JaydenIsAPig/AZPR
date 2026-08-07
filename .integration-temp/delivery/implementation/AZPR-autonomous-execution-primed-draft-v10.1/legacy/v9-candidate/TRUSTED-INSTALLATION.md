# AZPR v8 Trusted Installation Model

V8 is an unsigned corrective development candidate and must not be installed until independent source approval and real qualification evidence exist.

## Authorization boundary

The privileged installer requires a fresh, one-use, independently dual-signed qualification installation authorization. Verification is read-only and precedes recovery, key access and every write. The authorization binds the exact archive and bundle tree, installer/schema identities, semantic receipt, host identity, tools, execution/quota profiles, image and report hashes, policy source/status, environment, expiry, sequence, nonce and signer roles.

## Installation phases

- `QUALIFICATION_ONLY`: installs the verified control-plane generation without canonical derivatives; production launchers reject it.
- `POLICY_ACTIVATED`: later authorization must bind the independently approved canonical-policy record and exact derivatives.

## Execution boundary

Every production run uses a dedicated cgroup and PID/mount/network namespaces, a privileged start barrier, privilege drop, no-new-privileges, cgroup resource limits, quota-controlled tmpfs handoff, whole-tree termination, write-surface sealing and no-follow result import.

## Still required

Dedicated-host execution must prove the exact kernel, cgroup delegation, namespace/LSM/capability/mount policy, key custody, remote anchor, supply chain, fault recovery and exact Codex behavior. Source tests cannot substitute for that evidence.
