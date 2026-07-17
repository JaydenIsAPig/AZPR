# Definition of Done

A change is done only when every applicable item below is satisfied. Documentation-only work may mark application-specific items not applicable, but must not claim application behavior.

## Scope and behavior

- The approved outcome works and no unauthorized scope was added.
- Implemented, partially implemented, planned, proposed, and not-selected states are explicit.
- Failure paths are handled or explicitly blocked with an owned follow-up.
- Idempotency and retry safety are considered for acquisition, processing, events, and delivery.
- Security, authorization, privacy, consent, source-access compliance, and destructive actions are resolved rather than guessed.
- Operationally relevant behavior has sanitized observability and a runbook.

## Architecture and domain

- Modular-monolith boundaries and dependency direction are preserved.
- Permit, Opportunity, Customer Match, Notification, and Customer Lead State remain distinct.
- Source artifacts and provenance remain immutable/traceable.
- Source-specific logic stays in adapters.
- Business rules are configurable where approved; invariants remain enforced.
- AI use complies with deterministic-first policy and preserves derivation metadata.

## Quality

- Relevant formatter, linter, static/type checks, unit tests, integration tests, build, migration validation, architecture tests, and security checks pass.
- Tests are not weakened or production behavior mocked to force success.
- Accessibility and browser/responsive checks pass when frontend behavior changes.
- New dependencies and operational costs are approved and documented.

## Documentation and handoff

- Current documents match actual and planned state.
- Material document changes follow the versioning workflow and update logs/links.
- ADRs and runbooks are updated where required.
- `python3 scripts/check_docs.py` and `git diff --check` pass.
- The completion report lists files added/modified/moved, behavior changes, validation commands/results, documentation versions, assumptions, remaining risks, and deferred work.
