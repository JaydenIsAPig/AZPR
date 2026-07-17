---
document_id: project-structure
version: 1.1
document_status: superseded
implementation_status: partially implemented
approved_on: 2026-07-17
---

# Project Structure v1.1

## Status statement

**Implemented:** Documentation governance and validation; a Python 3.12 framework-independent domain kernel; application repository ports; lightweight CQRS messages; domain unit tests.
**Partially implemented:** The modular-monolith backend has domain and application-contract foundations but no application handlers or infrastructure.
**Planned:** Persistence, migrations, source adapters, web/API transport, authentication, AI/provider adapters, matching execution, notifications, dashboard, deployment, CI, and operational tooling.

## Current repository structure

```text
AZPR/
├── CONTRIBUTING.md
├── README.md
├── pyproject.toml                  # Python >=3.12; no runtime dependencies
├── docs/
│   ├── adr/                        # accepted decisions and template
│   ├── audits/                     # point-in-time audit evidence
│   ├── current/                    # exactly one current version per family
│   ├── governance/                 # glossary, checklists, contributor rules
│   ├── legacy/                     # superseded current snapshots
│   ├── logs/                       # version histories
│   ├── runbooks/                   # operational procedures when behavior exists
│   └── schema/                     # governed business-data schema
├── scripts/
│   └── check_docs.py               # documentation governance validation
├── src/az_permit_radar/
│   ├── application/
│   │   ├── commands.py             # write messages and handler protocol
│   │   ├── queries.py              # read messages and handler protocol
│   │   └── repositories.py         # persistence ports only
│   └── domain/
│       ├── classification.py
│       ├── customer.py
│       ├── errors.py
│       ├── events.py
│       ├── ingestion.py
│       ├── matching.py
│       ├── notification.py
│       ├── opportunity.py
│       ├── permit.py
│       ├── review.py
│       ├── source_registry.py
│       └── value_objects.py
└── tests/                          # standard-library domain unit tests
```

No UI, external integration, database, ORM, migration, web framework, application command/query handler, deployment, or production runtime is implemented.

## Implemented dependency direction

```text
tests -> application contracts -> domain
tests ---------------------------> domain

domain -X-> application, infrastructure, framework, provider SDK
```

The domain package uses Python standard-library modules only. Application ports depend on domain types. No infrastructure package exists yet.

## Planned bounded contexts

The contexts approved by [ADR-0001](../../adr/0001-modular-monolith.md) remain the intended modular-monolith boundaries. The current domain files group the minimum pilot model by cohesive domain concern; they are not microservices and do not claim complete bounded-context implementation.

Exact database, web framework, package-management workflow, job runner, artifact store, deployment target, and frontend structure remain **not selected**.

## Directory ownership

| Path | Ownership and rule | Status |
|---|---|---|
| `src/az_permit_radar/domain/` | Entities, aggregates, value objects, events, invariants, domain errors | Implemented for minimum pilot model |
| `src/az_permit_radar/application/` | CQRS messages and repository/handler ports | Implemented as contracts only |
| `tests/` | Domain invariant, transition, and architecture-contract tests | Implemented |
| `docs/current/` | Authoritative actual/planned snapshots | Implemented |
| `docs/logs/` | Human-readable snapshot history | Implemented |
| `docs/legacy/` | Superseded snapshots, never current | Implemented |
| `docs/adr/` | Consequential architecture decisions | Implemented |
| `docs/audits/` | Evidence/recommendations, not current authority | Implemented |
| `docs/runbooks/` | Operational recovery procedures | Governed placeholder; no product runbooks |
| Infrastructure/application handler/UI paths | To be selected and created only when authorized | Planned |

## Validation

The domain suite requires Python 3.12:

```sh
PYTHONPATH=src python3 -m unittest discover -s tests -v
python3 scripts/check_docs.py
git diff --check
```

## Related current documents

- [Backend structure v1.1](../backend-structure/backend-structure-v1.1.md)
- [Business logic v1.1](../business-logic/business-logic-v1.1.md)
- [Business data v1.0](../../current/business-data-v1.0.json)
- [Frontend design v1.0](../../current/frontend-design-v1.0.md)
- [Project structure log](../../logs/project-structure-log-v1.1.md)
- [Python domain-kernel decision](../../adr/0004-python-domain-kernel.md)
