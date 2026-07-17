---
document_id: project-structure
version: 1.5
document_status: current
implementation_status: partially implemented
approved_on: 2026-07-17
---

# Project Structure v1.5

## Status statement

**Implemented:** v1.4 acquisition/parsing plus deterministic Source Record-to-Permit normalization, Arizona-style address normalization, geocoding ports/provenance, exact/probable duplicate handling, review tasks, correction snapshots, manual decisions, merge evidence, and supersession history.

**Partially implemented:** the vertical slice is proven with local/in-memory adapters and synthetic fixtures. No approved live municipal source, real geocoder, durable normalization transaction, production database, scheduler/worker, Permit classification execution, web/API transport, authentication, dashboard, or notification delivery is selected.

## Current repository structure

```text
AZPR/
├── docs/
│   ├── current/                         # authoritative v1.5 snapshots
│   ├── legacy/                          # superseded snapshots
│   ├── logs/
│   └── runbooks/
│       ├── source-acquisition.md
│       ├── source-parsing.md
│       └── permit-normalization.md
├── src/az_permit_radar/
│   ├── application/
│   │   ├── acquisition.py
│   │   ├── parsing.py
│   │   └── normalization.py             # Permit workflow, geocoder/jurisdiction ports
│   ├── domain/
│   │   ├── ingestion.py
│   │   ├── parsing.py
│   │   ├── permit.py                    # normalized facts, evidence, history
│   │   └── deduplication.py             # probable candidates/manual decisions
│   └── infrastructure/
│       ├── source_acquisition.py
│       ├── source_parsing.py
│       └── permit_normalization.py       # deterministic Arizona/local adapters
└── tests/
    ├── test_source_parsing.py
    └── test_permit_normalization.py
```

The other modular-monolith contexts retain the structure described in [project structure v1.4](../legacy/project-structure/project-structure-v1.4.md).

## Dependency direction

```text
infrastructure -> application -> domain
tests ---------> infrastructure/application/domain

domain -X-> application or infrastructure
application -X-> infrastructure
```

Domain/application normalization contracts remain standard-library-only. Deterministic Arizona formatting and local/fake geocoding adapters live in infrastructure. Source Artifacts and Source Records remain separate immutable/provenance concepts from normalized Permits.

## Normalization ownership

| Path | Responsibility |
|---|---|
| `domain/permit.py` | Normalized Permit/Address facts, source evidence, correction/merge/supersession history |
| `domain/deduplication.py` | Layered duplicate evidence, probable candidate lifecycle, retained manual decisions |
| `application/normalization.py` | Exact/correction/probable workflows, review tasks, geocoder and persistence ports |
| `infrastructure/permit_normalization.py` | Deterministic field/address/parcel mappings and in-memory/fake adapters |
| `tests/test_permit_normalization.py` | Unit/address variants, missing IDs, corrections, geocoding, duplicates, manual decisions |

## Validation

```sh
PYTHONPATH=src python3 -m unittest discover -s tests -v
python3 scripts/check_docs.py
python3 -m compileall -q src tests
git diff --check
```

## Related current documents

- [Backend structure v1.5](backend-structure-v1.5.md)
- [Business logic v1.5](business-logic-v1.5.md)
- [Business data v1.0](business-data-v1.0.json)
- [Frontend design v1.0](frontend-design-v1.0.md)
- [Project structure log](../logs/project-structure-log-v1.5.md)

