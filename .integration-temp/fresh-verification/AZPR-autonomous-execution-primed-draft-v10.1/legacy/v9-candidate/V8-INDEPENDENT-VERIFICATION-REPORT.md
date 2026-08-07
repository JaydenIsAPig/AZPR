# AZPR v8 Independent-Style Development Verification Report

Generated: 2026-07-28

## Disposition

```json
{
  "safe_for_unattended_execution_now": false,
  "trusted_pre_autonomous_installation_ready": false
}
```

This report records development verification performed on the v8 corrective candidate. It is not an independent security-consultation approval, a clean-room qualification, an organization release signature, or authorization to install or execute the control plane.

## Governing baseline

The v7 release was verified at SHA-256 `84f36592d0dc910ae97055478944e6cab3ace212f9c80534283207b2cad19383`. The July 27, 2026 v7 consultation identified three Critical, two High, and two Medium findings. The supplied v8 corrective handoff required executable closure of P0/P1 controls while preserving false readiness flags, prompt identity, and all policy/roadmap/external-operation gates.

## Development verification performed

- Safe extraction and full v7-to-v8 source inventory.
- Python syntax and AST compilation.
- Draft 2020-12 schema meta-validation and cross-schema semantic fixtures.
- Byte-identical validation of all 41 prompt copies and the embedded prompt archive.
- One isolated process group per cataloged security test, with a hard timeout and bounded output.
- A separate six-case black-box boundary harness.
- Source-marker verification for installer authorization, semantic qualification, cgroup/namespace containment, nonblocking I/O, quota enforcement, key lifecycle, and fail-closed phase gates.
- Source-tree and final fresh-extraction verifier runs are required release artifacts and must match `FINAL-VERIFICATION.json` exactly.

## Finalized source-tree result

The frozen source tree completed the bundled verifier successfully with:

- 195 authenticated implementation files;
- 48 compiled Python files;
- 41 Draft 2020-12 schemas;
- 9 semantic positive/negative fixtures;
- 7 validation profiles;
- 38 numbered prompts and Appendices A-C;
- 84 cataloged tests, each run in a separate process group under a hard timeout;
- 6 separate black-box boundary cases;
- 75 mandatory source-control markers;
- unchanged prompt archive SHA-256 `3b235cb7e33ca409241ff26523f60f8fee89cec524b3f09e91a69927a0aa4880`.

The top-level source-verification record captures the machine-readable output. The final release must repeat the same verifier from a fresh extraction of the ZIP.

## Mandatory v7 finding results

| Finding | Development result | Qualification still required |
|---|---|---|
| AZPR-V7-F01 | One-use, dual-role installation authorization is verified before recovery or the first write. | Real independent signers, host identity, and immutable qualification artifacts. |
| AZPR-V7-F02 | The fabricated v7 corpus is rejected; a positive path requires strict schemas, distinct signed reports, raw evidence, revocation, probes, and exact cross-bindings. | Real host/tool/supply-chain evidence and independent reproduction. |
| AZPR-V7-F03 | Production target is gated into a dedicated cgroup and PID/mount/network namespaces; the full execution unit is terminated and proven empty before inspection. | Exact kernel, cgroup, namespace, mount, LSM, and Codex qualification. |
| AZPR-V7-F04 | stdin/stdout/stderr are multiplexed from process start under one total monotonic deadline. | Exact installed workloads and resource characterization. |
| AZPR-V7-F05 | Production handoff uses a quota-bound tmpfs plus entry/block/file/depth/path/type and cleanup budgets. | Root mount, exhaustion, concurrent-writer, interruption, and reboot tests. |
| AZPR-V7-F06 | Sequenced, dual-authorized, anchored, one-use transition state machine added. | Atomic deployment across real trust stores and a real rollback-resistant anchor. |
| AZPR-V7-F07 | Development delivery is self-contained and explicitly unsigned. | Organization release signing when an authorized signer exists. |

## Additional corrections found during v8

- **AZPR-V8-D01:** A qualification-only installation had to be separated from later canonical-policy activation. Production launchers reject `QUALIFICATION_ONLY` manifests.
- **AZPR-V8-D02:** Merely attesting namespace requirements was insufficient. The trusted process gate now enters PID, mount, and network namespaces before dropping privileges and executing Codex.

## Honest limitation

A passing source verifier proves only that the frozen source bundle satisfies its executable test oracles. It cannot prove the truth of host measurements, real key custody, remote anchoring, supply-chain provenance, production provider behavior, or application-level AZPR invariants. Those remain blocked qualification stages.
