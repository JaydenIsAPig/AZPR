# ADR-0004: Python 3.12 Framework-Independent Domain Kernel

- **Status:** Accepted
- **Date:** 2026-07-17
- **Deciders:** Project owner
- **Supersedes:** None
- **Superseded by:** None

## Context

The first domain-model implementation requires a language, but the repository previously left language and framework not selected. The project owner approved Python 3.12 with standard-library dataclasses, enums, protocols, and `unittest`, while requiring the choice to remain consistent and explicit. This stage must not introduce UI, external integrations, persistence infrastructure, or an application framework.

## Decision

Implement the pilot domain kernel and application ports in Python 3.12. The kernel uses only the Python standard library:

- frozen dataclasses for immutable value objects and provenance objects;
- mutable dataclass aggregate roots with guarded state transitions;
- enums for lifecycle states;
- protocols for repository and CQRS handler interfaces; and
- `unittest` for domain tests.

Use a `src/az_permit_radar` package layout. Domain modules must not import HTTP, database, AI, messaging, UI, or provider SDKs. Application command, query, and repository contracts may depend on domain types; the domain may not depend on application or infrastructure packages.

This decision selects the domain-kernel language and minimum supported Python version. It does **not** select a web framework, database/ORM, migration tool, package manager workflow, job runner, deployment target, artifact store, AI provider, notification provider, or frontend technology. Those remain not selected and require later decisions.

## Consequences

### Positive

- The domain model remains small, typed, testable, and free of infrastructure dependencies.
- Standard-library-only code avoids an early dependency and package-manager commitment.
- Protocol ports support later infrastructure adapters without coupling entities to external response models.

### Negative or trade-offs

- Python 3.12 must be available even when a workstation's default `python3` is older.
- Runtime type hints do not replace a future static type checker.
- Persistence mapping and serialization will require explicit adapters later.

### Risks and mitigations

- **Risk:** Framework or ORM concerns leak into dataclasses. **Mitigation:** Domain imports are restricted and covered by architecture tests.
- **Risk:** Later tooling assumes an older Python. **Mitigation:** `pyproject.toml` declares `requires-python = ">=3.12"` and validation reports the interpreter used.
- **Risk:** Standard-library tests are mistaken for full integration assurance. **Mitigation:** Documentation explicitly marks infrastructure and integrations unimplemented.

## Alternatives considered

### TypeScript domain kernel

Not selected because the owner approved Python 3.12 for this implementation. No comparative claim about a future frontend stack is made.

### Select a web framework now

Rejected for this stage because no transport behavior is required and framework selection would add scope and coupling.

### Platform-neutral specification only

Rejected because the task requires executable invariants, state transitions, repository contracts, CQRS messages, events, and unit tests.

## Domain-model deviations

No material deviation from the approved proposed domain distinctions was required. `ProjectClassification` and `ClassificationResult` make the earlier broad “Classification” concept precise; `LeadState` remains customer-scoped inside `OpportunityMatch`; `NotificationAttempt` is not combined with a match or preference.

## Validation and compliance

Run the unit suite with Python 3.12 and `PYTHONPATH=src`. Architecture tests verify required concrete concepts, prohibit ambiguous generic domain model names, and import CQRS/repository ports without infrastructure.

## Related documents

- [Project structure](../current/project-structure-v1.13.md)
- [Backend structure](../current/backend-structure-v1.12.md)
- [Business logic](../current/business-logic-v1.12.md)
- [Modular-monolith decision](0001-modular-monolith.md)
