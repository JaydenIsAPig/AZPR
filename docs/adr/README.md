# Architecture Decision Records

ADRs capture consequential, durable decisions. Accepted ADRs are normative within their scope. Current snapshots in `docs/current/` describe the combined actual and planned state and link relevant decisions.

## Index

| ADR | Status | Decision |
|---|---|---|
| [0000](0000-template.md) | Template | ADR format |
| [0001](0001-modular-monolith.md) | Accepted | Domain-driven modular monolith |
| [0002](0002-deterministic-first-ai.md) | Accepted | Deterministic-first AI usage |
| [0003](0003-documentation-versioning.md) | Accepted | Documentation versioning and current-file governance |
| [0004](0004-python-domain-kernel.md) | Accepted | Python 3.12 framework-independent domain kernel |
| [0005](0005-authoritative-classification-result.md) | Accepted | Authoritative Classification Result and central fail-closed publication eligibility |
| [0006](0006-versioned-opportunity-projections.md) | Accepted | Versioned Opportunity projections and complete Match evaluation snapshots |
| [0007](0007-in-memory-processing-unit-of-work.md) | Accepted | Authoritative Batch ownership and process-local processing unit of work |
| [0008](0008-customer-scoped-access-context.md) | Accepted | Customer-scoped access context, anti-enumeration, and separate internal path |
| [0009](0009-staged-hybrid-controller-transition.md) | Accepted | Staged repository-to-external controller transition with single-writer cutover |
| [0010](0010-ansible-qualification-infrastructure.md) | Accepted | H0 Ansible host provisioning remains separate from independent Linux qualification |
| [0011](0011-digest-bound-approval-checkpoints.md) | Accepted | Manifest-driven, digest-bound approval tickets with separate decisions and outcomes |
| [0012](0012-macos-secure-enclave-operator-approval.md) | Accepted | Inert macOS Secure Enclave and Touch ID operator-approval source boundary |
| [0013](0013-h0-live-target-fingerprint.md) | Proposed | Deterministic H0 live-target identity fingerprint with no authority effect |
| [0014](0014-repository-governed-procedure-approval.md) | Accepted | Repository-attributed approval channel for the exact inert H0 fingerprint procedure only |

Use the next available four-digit number. ADRs are immutable after acceptance except for typo/link corrections; changed decisions receive a new ADR that supersedes the old one.
