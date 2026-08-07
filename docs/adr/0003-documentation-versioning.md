# ADR-0003: Documentation Versioning and Current-State Governance

- **Status:** Accepted
- **Date:** 2026-07-16
- **Deciders:** Project owner
- **Supersedes:** None
- **Superseded by:** None

## Context

The audit found no repository-native architecture or business documentation and identified the risk of external documents becoming ambiguously current. The project needs human-readable snapshots while retaining Git as the primary implementation history. Documents must also distinguish actual implementation from approved plans.

## Decision

Maintain five authoritative snapshot families in `docs/current/`: project structure, backend structure, business logic, business data, and frontend design. Each current document has a semantic `major.minor` version and metadata declaring its document ID, version, current status, implementation status, and approval date.

For a material update:

1. Validate the proposed replacement.
2. Move the prior current file into its matching `docs/legacy/<document-id>/` directory.
3. Change the archived copy's `document_status` to `superseded` while preserving its version.
4. Create the new version in `docs/current/` with `document_status: current`.
5. Create or update the corresponding version log in `docs/logs/`.
6. Update references to the prior filename.
7. Run `python3 scripts/check_docs.py` and confirm exactly one current document per family.

Major versions represent a changed contract, scope, or document structure that requires deliberate migration/review. Minor versions represent compatible material additions or clarifications. Typo-only changes may retain the version when they do not change meaning and are recorded in Git.

Documentation uses explicit status language: implemented, partially implemented, planned, proposed, and not selected. A current document is authoritative but may describe planned behavior; `document_status` and `implementation_status` are separate concepts.

## Consequences

### Positive

- Exactly one discoverable authority exists per document family.
- Historical snapshots remain readable alongside Git history.
- Planned architecture cannot silently masquerade as implemented behavior.

### Negative or trade-offs

- Material changes require coordinated file moves, logs, and link updates.
- Filename links change when versions advance.

### Risks and mitigations

- **Risk:** Multiple files are marked current. **Mitigation:** Repository validation fails.
- **Risk:** Archived files retain current status. **Mitigation:** Validation scans `docs/current/` and `docs/legacy/`.
- **Risk:** Broken versioned links. **Mitigation:** Validation checks local Markdown links.

## Alternatives considered

### Unversioned canonical filenames

Rejected because the approved charter requires versioned snapshots and legacy history.

### Git history only

Rejected because human-readable milestone snapshots and change logs are an explicit project requirement.

## Validation and compliance

The repository check validates required metadata, filename/version agreement, uniqueness/current placement, business-data JSON Schema conformance, corresponding logs, and local links.

## Related documents

- [Documentation update checklist](../governance/documentation-update-checklist.md)
- [Definition of done](../governance/definition-of-done.md)
- [Project structure](../current/project-structure-v1.13.md)
