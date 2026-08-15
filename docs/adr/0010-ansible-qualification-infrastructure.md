# ADR-0010: Ansible Qualification Infrastructure Before Formal Linux Qualification

- **Status:** Accepted
- **Date:** 2026-08-07
- **Deciders:** Project owner
- **Supersedes:** None
- **Superseded by:** None

## Context

ADR-0009 separates repository integration from qualification of the delivered
external controller and host-side components. The v10.1 security design also
requires actual host qualification to remain independent from source-level
verification. AZPR needs a reproducible Linux validation environment before
`INT-00`, but must not expand the trusted or authorization boundary merely by
adding infrastructure automation.

The preserved 527-row mapping was historical prequalification evidence. The
project owner selected `ce80d335...` as the pre-Ansible transition base and
deferred final mapping approval until the H0 infrastructure work is represented
in a regenerated exact mapping.

## Decision

Add a narrow Ansible project under `infrastructure/ansible/` during H0. It may
request the Linux account, package, offline Python runtime, workspace,
filesystem-mode, environment, and isolation state needed by the independent
AZPR verifier. It must not run or adjudicate that verifier, approve an
environment, activate a controller or prompt, materialize the integration
mapping, access a provider, or deploy production.

The directory remains separate from `automation/`, which owns repository
controller and prompt workflow concerns. There is one qualification inventory;
staging and production inventories are out of scope and cannot be selected by a
variable.

## Provisioning versus qualification

The required trust sequence is:

```text
Ansible requests state
  -> independent Linux observation
  -> official AZPR v10.1 verifier
  -> hash-bound machine evidence
  -> human/audit decision
```

`changed=0`, `failed=0`, syntax success, check mode, and idempotence are useful
provisioning evidence but never an AZPR qualification PASS.

## Privilege and secrets model

Privilege escalation is false by default. The machine contract allowlists only
installation of `python3`/`python3-venv`, creation of `/srv/azpr-validator`, and
removal of that exact root during reset. Each task explicitly becomes root and
is tagged for review. Candidate and prompt inputs live outside the reset root.

No private key, password, token, signer material, live receipt/ledger, customer
data, or production configuration is committed or generated. The inventory
uses an operator-mediated local connection inside the guest and creates no SSH
credential. Only approved offline bundles may supply dependencies during a
formal run.

## Multipass and environment separation

Multipass is one host laboratory, not the architecture or trust authority. The
playbooks contain no Multipass command or connection plugin and can run inside a
later approved Linux host. Qualification, staging, and production must
eventually use physically separate inventories; only qualification exists now.

## Validation requirements

The H0 checker enforces authority invariants, qualification-only inventory,
built-in modules, forbidden modules, explicit privilege, approval-template
inertness, and required failure gates. The pinned Ansible runtime must pass
inventory and syntax validation. Before H0 Ansible preparation can be marked
complete, a disposable or approved target must also pass check/diff review and
a two-apply test whose second recap has zero changes, failures, and unreachable
hosts.

Formal environment approval and the two independent 120/120 AZPR verifier runs
remain later gates. They cannot be inferred from Ansible evidence.

## Rejected alternatives

### Put Ansible under `automation/`

Rejected because it conflates deterministic host provisioning with controller,
prompt, and stage-transition authority.

### Run Ansible over an invented SSH key

Rejected because unmanaged credentials would enlarge the H0 trust boundary.

### Treat check mode or an idempotent recap as qualification

Rejected because both are self-observations by the provisioning mechanism.

### Add staging and production scaffolding now

Rejected because it expands scope and could make a qualification variable act
as an environment selector.

### Immediate application deployment

Rejected because H0 prepares only the validation host and has no production or
trusted-installer authority.

## Consequences

### Positive

- Linux qualification state becomes reviewable, reproducible, resettable, and
  independently measurable.
- Controller/prompt automation and host provisioning have explicit ownership.
- Offline dependency, candidate, reviewer, filesystem, credential, and network
  failures stop with actionable identifiers.
- Reset is bounded and cannot delete frozen inputs.

### Negative or trade-offs

- A separate pinned Ansible runtime and offline wheel bundle must be maintained.
- Local-to-guest operation requires an operator-mediated session and staging
  procedure.
- Host transport/security controls can block live idempotence even when all
  repository and syntax checks pass.

## Rollback

Remove only the H0 Ansible tree, its checker/tests/templates and
non-authoritative evidence, exact documentation references, and generated
mapping rows. Regenerate the mapping and assessment. Do not rewrite the
historical reports, immutable staging CSV, or preserved 527-row mapping.

## Related documents

- [ADR-0009](0009-staged-hybrid-controller-transition.md)
- [Project structure v1.17](../current/project-structure-v1.17.md)
- [Qualification runbook](../runbooks/ansible-qualification-environment.md)
- [Ansible implementation](../../infrastructure/ansible/README.md)
- [Validation evidence](../delivery-provenance/v10.1/validation/ansible/README.md)
- [Proposed ADR-0013 target fingerprint](0013-h0-live-target-fingerprint.md)
