---
document_id: project-structure
version: 1.2
document_status: superseded
implementation_status: partially implemented
approved_on: 2026-07-17
---

# Project Structure v1.2

## Status statement

**Implemented:** documentation governance; Python 3.12 domain and application contracts; source-profile and acquisition contracts; standard-library fake/manual connectors; local immutable artifact storage; structured acquisition logs; and unit tests.

**Partially implemented:** the modular monolith now has one narrow raw-acquisition slice, but no approved live Tucson/Pima connector, parser, persistent database, scheduler, web/API transport, authentication, outbox, dashboard, or notification delivery.

## Current repository structure

```text
AZPR/
├── docs/
│   ├── current/                    # authoritative versioned snapshots
│   ├── governance/
│   │   └── source-onboarding-checklist.md
│   ├── legacy/                     # superseded snapshots
│   ├── logs/                       # snapshot histories
│   └── runbooks/
│       └── source-acquisition.md
├── src/az_permit_radar/
│   ├── application/
│   │   ├── acquisition.py          # acquisition policies, ports, failures, coordinator
│   │   ├── commands.py
│   │   ├── queries.py
│   │   └── repositories.py
│   ├── domain/
│   │   ├── ingestion.py            # immutable SourceArtifact metadata
│   │   └── source_registry.py       # SourceProfile and source lifecycle
│   └── infrastructure/
│       └── source_acquisition.py    # fake/manual/store/log adapters
└── tests/
    ├── fixtures/manual/             # approved local test inputs only
    └── test_source_acquisition.py
```

The remaining domain modules and governed documentation directories retain the layout recorded in [project structure v1.1](project-structure-v1.1.md).

## Dependency direction

```text
infrastructure -> application -> domain
tests ---------> infrastructure/application/domain

domain -X-> application or infrastructure
application -X-> infrastructure
```

Domain and application contracts use only the Python standard library. Infrastructure adapters implement application ports and contain filesystem I/O. Connectors return raw bytes and transport metadata only; parsing remains outside acquisition adapters.

## Source-acquisition ownership

| Path | Responsibility | Status |
|---|---|---|
| `domain/source_registry.py` | Source description, parser contract metadata, access/health state | Implemented |
| `application/acquisition.py` | Connector interfaces, request/retry policy, failure taxonomy, orchestration ports | Implemented |
| `infrastructure/source_acquisition.py` | Deterministic fake, manual fixture reader, local artifact store, log sinks | Implemented for tests/local operation |
| Live Tucson/Pima adapter | Approved remote contract, pagination, provider-specific request behavior | Not selected / not implemented |
| Parser | Raw artifact to Source Records | Planned and intentionally separate |

## Validation

Run with Python 3.12 or newer:

```sh
PYTHONPATH=src python3 -m unittest discover -s tests -v
python3 scripts/check_docs.py
python3 -m compileall -q src tests
git diff --check
```

## Related current documents

- [Backend structure v1.2](../backend-structure/backend-structure-v1.2.md)
- [Business logic v1.2](../business-logic/business-logic-v1.2.md)
- [Business data v1.0](../../current/business-data-v1.0.json)
- [Frontend design v1.0](../../current/frontend-design-v1.0.md)
- [Project structure log](../../logs/project-structure-log-v1.2.md)
