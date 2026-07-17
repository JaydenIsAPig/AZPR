# Technical Debt Register

**Audit date:** 2026-07-16
**Scope note:** Because the repository is pre-implementation, this register includes foundational gaps and risk controls required to prevent debt. “Not present” does not mean a broken implementation exists.

## Severity and milestone definitions

- **Critical:** Blocks safe operation of the pilot or threatens data integrity/consent.
- **High:** Blocks a charter-required capability or creates substantial security/rework risk.
- **Medium:** Impairs consistency, assurance, operability, or maintainability.
- **Low:** Localized hygiene with limited near-term impact.
- **M0:** Decisions and authoritative documentation.
- **M1:** Safe modular-monolith foundation.
- **M2:** Provenance-first ingestion.
- **M3:** Intelligence and explainable matching.
- **M4:** Controlled dashboard/notification delivery.
- **M5:** Pilot hardening and billing decision.

## Register

| ID | Severity | Debt / gap | Evidence | Likely effect | Recommended action | Milestone |
|---|---|---|---|---|---|---|
| TD-001 | Critical | No executable product | Only three scaffold files are tracked; reachable history contains no application files. | No pilot capability can operate or be tested. | Build one provenance-to-delivery vertical slice in milestone order. | M1-M4 |
| TD-002 | High | Stack and hosting are undecided | No manifests, source, ADRs, database, or deployment config exist. | Accidental technology choices and rework. | Decide and record stack, relational store, raw storage, jobs, hosting, and frontend via ADRs. | M0 |
| TD-003 | High | Master charter is outside version control | No product/architecture charter is tracked or linked by the README. | Governing requirements can drift or disappear. | Adopt a versioned repository authority with owner/status metadata. | M0 |
| TD-004 | High | No module boundaries or dependency enforcement | No bounded-context modules or architecture tests exist. | Domain concepts and external integrations may become tightly coupled. | Define modular-monolith boundaries, public interfaces, allowed dependencies, and boundary tests. | M1 |
| TD-005 | Critical | Core domain concepts lack separate models | No Permit, Opportunity, Customer Match, Notification, or Lead State types/schema exist. | A combined “lead” model could cause duplication, ownership ambiguity, and privacy defects. | Model identities, ownership, references, invariants, and lifecycles separately. | M1 |
| TD-006 | Critical | No immutable provenance chain | No Source, Artifact, Batch, Source Record, hashes, parser versions, or raw storage exist. | Facts cannot be traced/reproduced; corrections may overwrite evidence. | Implement immutable artifacts and versioned processing results before normalization. | M2 |
| TD-007 | Critical | No idempotency or database constraints | No schema, stable keys, uniqueness constraints, or retry tests exist. | Reimports/retries can duplicate permits, opportunities, matches, or alerts. | Design stable source keys, hashes, constraints, idempotency keys, and replay tests. | M2-M4 |
| TD-008 | High | No source-adapter boundary | No source registry, adapter interface, or shared domain layer exists. | First-source parsing may leak into domain logic and block additional sources. | Put access/parsing behind source-family adapters returning source-neutral records. | M2 |
| TD-009 | High | Business rules have no configuration model | No business-data file/schema or configuration service exists. | Trades, geography, thresholds, exclusions, and source behavior may be hard-coded. | Define validated, versioned configuration with stable IDs and effective/version metadata. | M0-M3 |
| TD-010 | High | Deterministic/AI boundary is absent | No classifier, AI adapter, provenance fields, confidence, or review workflow exists. | AI may be used for deterministic tasks or inferred data may masquerade as source fact. | Build deterministic parsing/classification first; isolate AI and persist model/prompt/classifier provenance and review state. | M3 |
| TD-011 | High | Match explanation contract is absent | No trade/geography/filter/score/exclusion/freshness explanation schema exists. | Unexplained scores erode trust and cannot be debugged. | Create a versioned explanation record and component-level tests. | M3 |
| TD-012 | Critical | Notification consent and delivery semantics are absent | No consent, intent, attempt, provider event, suppression, or channel model exists. | Unauthorized or duplicate contact; “sent” may be misreported as delivered. | Model consent basis and notification lifecycle; use idempotent intent plus auditable attempts. | M4 |
| TD-013 | Critical | No transactional outbox | No database/job/outbox infrastructure exists. | State may commit without its alert or alerts may send twice after failures. | Add a transactional outbox, idempotent consumers, retry/backoff, and dead-letter/triage behavior. | M4 |
| TD-014 | High | Authentication and authorization are unspecified | No requirements, identity provider decision, users/roles, policies, middleware, or tests exist. | Unsafe customer isolation and stalled delivery. | Decide auth architecture; implement least privilege and tenant/customer isolation with policy tests. | M0-M1 |
| TD-015 | High | Secrets/config management is minimal | `.gitignore:1-10` only ignores common filenames; no example contract, scanner, or runtime secret mechanism exists. | Secrets can be committed or environments can drift. | Add typed/validated configuration, sanitized example env, runtime secret storage, pre-commit/CI secret scanning, and rotation procedure. | M1 |
| TD-016 | High | No security/privacy baseline | No threat model, data classification, secure logging controls, audit policy, dependency/code scanning, or retention rules exist. | PII or credentials may leak and vulnerabilities may go undetected. | Threat-model the vertical slice; define data/retention/logging rules and automate dependency, code, and secret scans. | M1; M5 validation |
| TD-017 | High | No tests or validation toolchain | No formatter, linter, type checker, test runner, build, migration check, or CI exists. | Regressions and invalid migrations cannot be detected consistently. | Establish local and CI commands during scaffold creation; test domain, adapters, persistence, and failure paths. | M1 |
| TD-018 | High | No source monitoring or internal review | No freshness, batch health, parser drift, low-confidence queue, or runbook exists. | Silent stale/bad data can reach customers. | Add source SLIs, batch diagnostics, review queues, alerts, and operational runbooks. | M2-M4 |
| TD-019 | Medium | No observability contract | No structured logging, metrics, tracing/correlation IDs, health endpoints, or redaction rules exist. | Failures across ingestion, matching, and delivery are hard to diagnose safely. | Define correlation identifiers and sanitized logs/metrics for batches, records, matches, and notifications. | M1-M4 |
| TD-020 | High | No migration/backup/recovery strategy | No database or artifact-store tooling, backups, restore test, or destructive-migration policy exists. | Data loss or unsafe schema changes can block the pilot. | Adopt forward migration policy, backups, restoration rehearsal, and explicit approval for destructive changes. | M1; M5 test |
| TD-021 | Medium | No current architecture/business/frontend documents | Required `docs/current`, logs, legacy, and ADR hierarchy is absent. | Decisions and actual state will drift or become ambiguous. | Create v0.1 snapshots after decisions and enforce one current version per class. | M0-M1 |
| TD-022 | Medium | README is non-operational | `README.md:1-2` has only name and generic description. | Contributors cannot discover scope, status, setup, validation, or docs. | Add truthful status, scope/non-goals, setup, validation, and documentation navigation. | M0-M1 |
| TD-023 | Medium | No roadmap acceptance criteria | Pilot priorities exist only in the external charter. | Work may spread across placeholders instead of closing a vertical slice. | Publish M0-M5 roadmap with source/trade decisions, owners, exit criteria, and deferred scope. | M0 |
| TD-024 | Medium | Payment boundary is not represented | No billing module/interface exists, though the charter calls it a placeholder. | Future billing code may leak into customer/match models or be built before requirements. | Reserve only a documented boundary; defer implementation until requirements and security/compliance decisions exist. | M1 boundary; M5 decision |
| TD-025 | Medium | No legal/source-access decision record | No selected jurisdiction, terms/access analysis, rate limits, or retention policy exists. | Acquisition may violate restrictions or become operationally unreliable. | Select the pilot source and record access method, terms, frequency, retention, attribution, and escalation constraints. | M0 |
| TD-026 | Medium | No data-quality/deduplication specification | No normalization, external-ID, hash, correction, merge, or confidence policy exists. | False duplicates/merges and inconsistent opportunity derivation. | Define source-scoped identity and conservative normalization/dedup rules with fixtures and replay tests. | M2 |
| TD-027 | Medium | No accessibility/frontend quality baseline | No frontend or design/test configuration exists. | Dashboard may be inaccessible or inconsistent when introduced. | Define responsive/accessibility/browser support and automated/manual UI checks before dashboard delivery. | M4 |
| TD-028 | Medium | No environment or developer bootstrap | No runtime version, dependency manifest, local services, seed strategy, or commands exist. | Onboarding and CI are non-reproducible. | Pin tool versions and provide deterministic bootstrap without production mocks masquerading as real behavior. | M1 |

## Hard-coded and source-specific logic disposition

No hard-coded business rules or embedded source-specific logic were found because no application code exists. The controls below should be used when code arrives:

- Business configuration: trade taxonomy, jurisdiction/geographic rules, opportunity thresholds, exclusions, freshness windows, review thresholds, and notification policy must be validated and versioned rather than scattered as literals.
- Source adapters: endpoints, field names, access schedules, pagination, source-specific statuses, and parser mappings belong in the Source Registry/Permit Ingestion adapters—not Permit Intelligence or Opportunity Matching.
- Domain invariants remain code: provenance requirements, immutability, ownership, permission checks, legal state transitions, idempotency, and database constraints should not become casually editable configuration.

## Exit criteria for closing the highest-risk items

1. A fresh environment can run one documented validation command suite and reproduce the application/test setup.
2. One pilot source can be replayed without duplicates and every permit traces to immutable evidence and a processing version.
3. Permit, opportunity, match, notification attempt, and customer lead state have distinct identities, persistence, and lifecycle tests.
4. Every customer match exposes its trade, geography, filter, score, exclusion, freshness, and confidence reasoning.
5. Email/SMS delivery is outbox-backed, consent-aware, idempotent, observable, and safely retryable.
6. Customer data is isolated by authorization tests; secrets/PII are excluded from logs and automated scanning is active.
7. Documentation describes actual state, exactly one current version exists per required class, and ADRs capture consequential choices.
