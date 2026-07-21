# ADR-0002: Deterministic-First AI Usage

- **Status:** Accepted
- **Date:** 2026-07-16
- **Deciders:** Project owner
- **Supersedes:** None
- **Superseded by:** None

## Context

Permit source data contains both structured values and ambiguous language. The platform must remain reproducible, explainable, safe, and cost-conscious. AI inference is inappropriate for permissions, consent, calculations, constraints, and other deterministic or high-impact operations, but may help when language ambiguity cannot be resolved reliably with deterministic logic.

## Decision

Use deterministic code before AI for structured parsing, date and currency handling, deduplication, address normalization, geographic inclusion, permissions, authentication, billing, notification consent, calculations, database constraints, workflow transitions, and destructive operations.

AI may be introduced only for documented language ambiguity after deterministic approaches are assessed. AI is accessed through an adapter and may not become the authority for observed source facts. Each AI-derived value must retain source/evidence provenance, provider/model identifier and version, prompt or classifier version, confidence where meaningful, review status, and timestamps.

AI output must be schema-validated and failure-safe. Low-confidence or safety-relevant outcomes require a planned review/suppression policy before customer delivery. No provider, model, prompt, threshold, or classifier is selected by this ADR.

## Consequences

### Positive

- Reproducibility and explainability are the default.
- AI cost and operational dependence remain bounded.
- Source facts and inferred values remain distinguishable.

### Negative or trade-offs

- Deterministic parsers and rule sets require maintenance.
- Some ambiguous records may remain unclassified pending review.
- Provenance/version storage adds model and operational complexity.

### Risks and mitigations

- **Risk:** AI becomes an undocumented fallback. **Mitigation:** Require adapter use, derivation metadata, and tests for deterministic coverage.
- **Risk:** Model changes silently alter classifications. **Mitigation:** Version results and preserve prior processing outcomes.
- **Risk:** Inference is presented as fact. **Mitigation:** Separate observed, normalized, deterministic-derived, and AI-derived fields in contracts and UI.

## Alternatives considered

### AI-first extraction

Rejected because it reduces reproducibility and creates unnecessary cost and ambiguity for structured data.

### No AI under any circumstance

Rejected as a permanent rule because genuinely ambiguous permit descriptions may benefit from bounded, reviewable inference.

## Validation and compliance

Future tests must prove deterministic handling of enumerated categories, schema validation of AI output, provenance retention, versioned reprocessing, and safe behavior on timeout, malformed output, low confidence, and provider failure.

## Related documents

- [Business logic](../current/business-logic-v1.12.md)
- [Backend structure](../current/backend-structure-v1.12.md)
- [Domain glossary](../governance/domain-glossary.md)
