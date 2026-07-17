---
document_id: project-structure
version: 1.0
document_status: superseded
implementation_status: implemented
approved_on: 2026-07-16
---

# Project Structure v1.0

## Status statement

**Implemented:** The repository contains documentation governance, audit records, a JSON Schema, and a documentation validation script.
**Planned:** All application, test, deployment, database, and operational code described below.
**Partially implemented:** None.

## Current repository structure

```text
AZPR/
├── .gitattributes
├── .gitignore
├── CONTRIBUTING.md
├── README.md
├── docs/
│   ├── adr/                    # ADR index, template, and accepted decisions
│   ├── audits/                 # point-in-time audit evidence
│   ├── current/                # exactly one current version per document family
│   ├── governance/             # glossary, checklists, and completion rules
│   ├── legacy/                 # superseded current-document versions
│   ├── logs/                   # version histories for current-document families
│   ├── runbooks/               # operational procedures when operations exist
│   └── schema/                 # documentation data schemas
└── scripts/
    └── check_docs.py           # documentation governance validator
```

No application source, package manifest, database, migrations, tests, CI/CD, infrastructure, or deployment directories are implemented.

## Planned structural principles

The application is planned as a domain-driven modular monolith under [ADR-0001](../../adr/0001-modular-monolith.md). Exact source-directory names, language, framework, package manager, database, and deployment layout are **not selected**. They require ADRs before scaffolding.

When implementation begins, the structure must make these bounded contexts explicit without implying that each is a deployable service:

- Identity and Access
- Customer Configuration
- Source Registry
- Permit Ingestion
- Permit Intelligence
- Geography
- Opportunity Matching
- Lead Workflow
- Notification
- Analytics and Operations
- Billing placeholder

External systems must be reached through adapters owned by the appropriate module. Shared code must remain small and must not become a home for source-specific parsing or business rules.

## Directory ownership

| Path | Purpose | Status |
|---|---|---|
| `docs/current/` | Authoritative current snapshots | Implemented |
| `docs/logs/` | Human-readable snapshot history | Implemented |
| `docs/legacy/` | Superseded snapshots | Implemented; currently empty by design |
| `docs/adr/` | Consequential architecture decisions | Implemented |
| `docs/audits/` | Evidence and recommendations, not current authority | Implemented |
| `docs/runbooks/` | Operational response procedures | Implemented as a governed placeholder; no operational runbooks exist |
| `docs/schema/` | Machine-readable schemas for governed data | Implemented |
| `docs/governance/` | Cross-cutting contributor rules | Implemented |
| `scripts/` | Repository validation and maintenance utilities | Implemented for documentation checks only |
| Application/test/deployment paths | To be selected after technology ADRs | Planned |

## Related current documents

- [Backend structure v1.0](../backend-structure/backend-structure-v1.0.md)
- [Business logic v1.0](../business-logic/business-logic-v1.0.md)
- [Business data v1.0](../../current/business-data-v1.0.json)
- [Frontend design v1.0](../../current/frontend-design-v1.0.md)
- [Project structure log](../../logs/project-structure-log-v1.0.md)
