---
document_id: project-structure
version: 1.4
document_status: superseded
implementation_status: partially implemented
approved_on: 2026-07-17
---

# Project Structure v1.4

## Status statement

**Implemented:** v1.3 acquisition plus a deterministic parser framework, fixture-only Tucson CSV mapping, immutable parsed-value provenance, row quarantine, Source Record history comparison, version-aware reprocessing, import reports, and parser logs/metrics.

**Partially implemented:** parsing is implemented for synthetic local fixtures only. No approved live Tucson/Pima source contract, durable parser unit of work, production archive reader, permit projection, external scheduler, web/API transport, authentication, dashboard, or notification delivery is selected.

## Current repository structure

```text
AZPR/
├── docs/
│   ├── current/                         # authoritative v1.4 snapshots
│   ├── legacy/                          # superseded snapshots
│   ├── logs/
│   └── runbooks/
│       ├── source-acquisition.md
│       └── source-parsing.md
├── src/az_permit_radar/
│   ├── application/
│   │   ├── acquisition.py
│   │   └── parsing.py                   # parser stages, pipeline, reports/log ports
│   ├── domain/
│   │   ├── ingestion.py                 # Source Record provenance and batch lifecycle
│   │   └── parsing.py                   # parsed values, issues, row/report outcomes
│   └── infrastructure/
│       ├── source_acquisition.py
│       └── source_parsing.py             # CSV stages, fixture parser, local adapters
└── tests/
    ├── fixtures/parser/
    └── test_source_parsing.py
```

The other modular-monolith contexts retain the structure described in [project structure v1.3](project-structure-v1.3.md).

## Dependency direction

```text
infrastructure -> application -> domain
tests ---------> infrastructure/application/domain

domain -X-> application or infrastructure
application -X-> infrastructure
```

Domain and application parsing contracts remain standard-library-only. Source-specific aliases and CSV behavior live in infrastructure. Acquisition connectors still return raw bytes only and never invoke parsers.

## Parser ownership

| Path | Responsibility |
|---|---|
| `domain/parsing.py` | Immutable `ParsedValue`, validation issue, row disposition, and `ImportReport` vocabulary |
| `domain/ingestion.py` | Source Record parser version, row provenance, parsed values/issues, batch counts |
| `application/parsing.py` | Stage interfaces and Source Artifact → Source Record orchestration |
| `infrastructure/source_parsing.py` | UTF-8, CSV, aliases, explicit dates/currency, stable keys, fixture/local adapters |
| `tests/test_source_parsing.py` | Fixture parsing, quarantine, duplicate/unchanged, reprocessing, checksum, observability |

The `synthetic-tucson-permit-csv` parser is test-only and is not an approved municipal source connector or factual production contract.

## Validation

```sh
PYTHONPATH=src python3 -m unittest discover -s tests -v
python3 scripts/check_docs.py
python3 -m compileall -q src tests
git diff --check
```

## Related current documents

- [Backend structure v1.4](../backend-structure/backend-structure-v1.4.md)
- [Business logic v1.4](../business-logic/business-logic-v1.4.md)
- [Business data v1.0](../business-data/business-data-v1.0.json)
- [Frontend design v1.0](../frontend-design/frontend-design-v1.0.md)
- [Project structure log](../../logs/project-structure-log-v1.4.md)
