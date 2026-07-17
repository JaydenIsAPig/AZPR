# Contributing to AZ Permit Radar

These rules apply equally to human contributors and Codex agents.

## Before changing files

1. Read the relevant files in `docs/current/`, accepted ADRs, the domain glossary, and applicable audits.
2. Inspect existing implementation and tests; do not assume a component is absent.
3. Report the current structure, conflicts, proposed files, tests, risks, and assumptions before implementation work.
4. Stop for a decision when a change would guess about authentication, authorization, billing, personal data, notification consent, source-access compliance, destructive migrations, record deletion, security controls, or customer-visible factual claims.

## Change rules

- Make the smallest coherent change that satisfies the approved task.
- Do not perform unrelated refactors or add speculative placeholders.
- Preserve the modular-monolith boundaries in [ADR-0001](docs/adr/0001-modular-monolith.md).
- Apply the deterministic-first rule in [ADR-0002](docs/adr/0002-deterministic-first-ai.md).
- Use the terms in the [domain glossary](docs/governance/domain-glossary.md). Never collapse Permit, Opportunity, Customer Match, Notification, and Customer Lead State.
- Keep source-specific access and parsing behind source adapters; do not embed it in shared domain logic.
- Keep business configuration versioned and validated. Keep invariants, permissions, consent enforcement, state transitions, idempotency, and database constraints in code/persistence controls.
- Never weaken validation to obtain a passing result.
- Never commit secrets or log authentication tokens, passwords, full phone numbers, or unnecessary personal data.

## Status language

Documentation must use these meanings:

- **Implemented:** present and verifiable in the repository.
- **Partially implemented:** some described behavior exists; the document must name both present and missing parts.
- **Planned:** approved direction with no implementation claim.
- **Proposed:** under review and not yet approved.
- **Not selected:** a decision or value remains intentionally open.

Future architecture must not be written in the present tense as if it exists.

## Documentation changes

Follow [ADR-0003](docs/adr/0003-documentation-versioning.md) and the [documentation update checklist](docs/governance/documentation-update-checklist.md). A material change to a current document must archive the prior version, create the new version, update the corresponding log and links, and leave exactly one version marked current.

## Completion

A contribution is complete only when it satisfies the [definition of done](docs/governance/definition-of-done.md), runs all applicable validations, and reports files changed, behavior changed, tests and results, documentation versions, risks, assumptions, and deferred work.
