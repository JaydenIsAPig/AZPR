# Documentation and Version Audit

**Audit date:** 2026-07-16
**Audited revision:** `f61530365f6ccaaa2e2f677a9aea7ed5da05c932`

## Conclusion

The repository has no architecture, business logic, business data, frontend design, roadmap, change-log, legacy, or ADR documents. Consequently, there are no duplicate or conflicting repository documents—but there is also no repository-designated authoritative product or architecture record.

The supplied *AZ Permit Radar — Codex Master Operating Prompt* is the only substantive product/architecture charter and is stored outside the repository at audit time. Its prescribed `docs/current`, `docs/logs`, `docs/legacy`, and `docs/adr` hierarchy does not exist. This audit introduces `docs/audits/` only; it does not pretend to create the missing current snapshots or make product decisions.

## Document inventory

| Document class | Expected by charter | Actual current | Duplicate/obsolete/conflict result |
|---|---|---|---|
| Repository entry point | Informative README | `README.md` (2 lines) | Unique but materially incomplete |
| Master product/architecture charter | Needed as authority | Supplied DOCX outside repository | Ambiguously current because it has no repository version, owner metadata, or adoption record |
| Project structure | `docs/current/project-structure-vX.Y.md` | Missing | No duplicate; no current version |
| Backend structure | `docs/current/backend-structure-vX.Y.md` | Missing | No duplicate; no current version |
| Business logic | `docs/current/business-logic-vX.Y.md` | Missing | No duplicate; no current version |
| Business data | `docs/current/business-data-vX.Y.json` | Missing | No duplicate; no current version |
| Frontend design | `docs/current/frontend-design-vX.Y.md` | Missing | No duplicate; no current version |
| Corresponding change logs | `docs/logs/*-log-vX.Y.md` | Missing | No log versions |
| Legacy snapshots | `docs/legacy/<class>/` | Missing | No historical document snapshots |
| Architecture decisions | `docs/adr/` | Missing | No recorded decisions |
| Roadmap/milestones | Pilot scope implied by charter | Missing | No current roadmap to conflict with |
| Audit records | `docs/audits/` (task-required) | Created by this audit | These are findings, not current architecture snapshots |

## Authority and version observations

- Git history is minimal and unambiguous: `aad534b` introduced `.gitattributes` and `README.md`; `f615303` introduced `.gitignore`. Neither commit contains product documentation or implementation.
- There are no tags, stashes, submodules, alternate local/remote branches, or legacy document directories in the inspected repository.
- `README.md:1-2` does not identify the external charter, current versions, status, or documentation navigation.
- `.gitignore:33` ignores files ending in `.log`; this does **not** conflict with the charter's proposed change-log filenames because those end in `.md`, but the naming distinction should remain explicit.
- The charter uses `docs/adr/` in its displayed hierarchy. Adopting a different ADR path would create avoidable ambiguity and should require an explicit decision.

## Issues

### DV-01 — Master charter is external and not repository-versioned

- **Severity:** High
- **Evidence:** The supplied DOCX contains the substantive product definition and architecture rules, while the tracked repository contains no copy, link, checksum, version, status, owner, or adoption ADR.
- **Likely effect:** A fresh clone lacks the governing requirements; different DOCX copies may diverge without detectable review history.
- **Recommended action:** Adopt a reviewable repository representation of the charter with version/status/owner/effective-date metadata, preserve the original source as appropriate, and link it from `README.md`. Record adoption in Git history.
- **Milestone:** M0

### DV-02 — Required current document set is completely missing

- **Severity:** High
- **Evidence:** No `docs/current/` directory or expected project-structure, backend-structure, business-logic, business-data, or frontend-design files exist.
- **Likely effect:** Architecture and business decisions will be implicit in code or spread across conversations, making consistency review impossible.
- **Recommended action:** Create initial `v0.1` current snapshots after M0 decisions, explicitly describing actual state and planned boundaries. Do not document unimplemented features as present.
- **Milestone:** M0-M1

### DV-03 — Change-log and legacy workflow is absent

- **Severity:** Medium
- **Evidence:** No `docs/logs/` or `docs/legacy/` hierarchy exists and no document lifecycle automation/checklist exists.
- **Likely effect:** Future “current” files may multiply, old references may persist, or context behind version changes may be lost.
- **Recommended action:** Establish the charter-prescribed directories and a documented promotion procedure; validate that exactly one current file exists per class and that links resolve.
- **Milestone:** M0-M1

### DV-04 — No ADRs capture consequential choices

- **Severity:** High
- **Evidence:** No `docs/adr/` directory exists; language, framework, database, raw storage, job model, hosting, and frontend approach are undecided in-repository.
- **Likely effect:** Foundational choices can be made accidentally by scaffolding and become expensive to reverse.
- **Recommended action:** Create ADRs for the minimum consequential decisions before implementation, including rejected alternatives and operational/security consequences.
- **Milestone:** M0

### DV-05 — README is obsolete as a project entry point

- **Severity:** Medium
- **Evidence:** `README.md:1-2` says only `# AZPR` and `Personal Business venture`; it omits the charter's product definition, Arizona scope, pilot status, non-goals, setup, validation, and documentation links.
- **Likely effect:** Readers can mistake the repository's maturity, purpose, or scope and cannot find authoritative material.
- **Recommended action:** Update after initial decisions with actual-state language, concise scope/non-goals, documentation map, prerequisites, setup, and validation commands.
- **Milestone:** M0-M1

### DV-06 — Roadmap and milestone acceptance criteria are missing

- **Severity:** Medium
- **Evidence:** The external charter states a narrow pilot priority, but no repository roadmap identifies the source, trades, owners, dependencies, risks, or acceptance criteria.
- **Likely effect:** Work may spread across future features instead of completing one reliable vertical slice.
- **Recommended action:** Create a current roadmap using the M0-M5 sequence in the repository audit, with explicit exit criteria and deferred non-goals.
- **Milestone:** M0

### DV-07 — Documentation truthfulness has no automated check

- **Severity:** Medium
- **Evidence:** No CI, link checker, schema validation for business data, current-version uniqueness check, or documentation review rule exists.
- **Likely effect:** Version references, JSON data, and implementation-status claims may drift unnoticed.
- **Recommended action:** Add lightweight CI checks for Markdown links, required metadata, one-current-version-per-class, JSON schema/format validity, and references to current filenames.
- **Milestone:** M1

## Proposed initial document authority map

| Concern | Proposed authority | Notes |
|---|---|---|
| Product definition, scope, non-goals, principles | Repository version of the master charter | Single normative source; changes reviewed explicitly |
| Actual module/file layout | `docs/current/project-structure-v0.1.md` | Must describe current, not aspirational, state |
| Backend boundaries and integrations | `docs/current/backend-structure-v0.1.md` | Link relevant ADRs |
| Rules and workflows | `docs/current/business-logic-v0.1.md` | Distinguish decided, configurable, and unresolved rules |
| Taxonomies/source/geography config | `docs/current/business-data-v0.1.json` plus schema | Stable identifiers and version metadata |
| Dashboard interaction/design | `docs/current/frontend-design-v0.1.md` | Do not select Model–View–Presenter/BLoC by terminology accident |
| Consequential decisions | `docs/adr/NNNN-*.md` | Status, context, decision, consequences |
| Human-readable deltas | `docs/logs/` | Complements rather than replaces Git history |
| Superseded snapshots | `docs/legacy/<class>/` | Never ambiguously labeled current |
| Reconnaissance findings | `docs/audits/` | Non-authoritative evidence and recommendations |

## Versioning recommendation

Start the missing current snapshots at `v0.1`, not `v1.0`, because the repository is pre-implementation and major choices remain open. Increment the snapshot version only for a material reviewed change, archive the replaced file, update its matching log and all references atomically, and keep exactly one current filename for each document class. Record implementation history in Git; do not use versioned documents as a substitute for commits.
