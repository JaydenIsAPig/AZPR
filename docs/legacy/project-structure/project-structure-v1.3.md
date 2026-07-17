---
document_id: project-structure
version: 1.3
document_status: superseded
implementation_status: partially implemented
approved_on: 2026-07-17
---

# Project Structure v1.3

## Status statement

**Implemented:** documentation governance; Python 3.12 domain/application contracts; source registry; scheduled/manual acquisition jobs; raw fetch/validation/hashing; immutable local archival; atomic in-memory acquisition metadata; Import Batch creation; duplicate suppression; reprocessing; outbox events; processing decisions; structured logs/metrics; and deterministic/concurrent tests.

**Partially implemented:** the raw acquisition vertical slice is complete against fake/manual connectors and local adapters. No live municipal connector, external scheduler, durable database/outbox publisher, production object store, parser, web/API transport, authentication, dashboard, or notification delivery is selected.

## Current repository structure

```text
AZPR/
├── docs/
│   ├── current/                    # authoritative v1.3 snapshots
│   ├── governance/
│   │   └── source-onboarding-checklist.md
│   ├── legacy/                     # superseded v1.0-v1.2 snapshots
│   ├── logs/
│   └── runbooks/source-acquisition.md
├── src/az_permit_radar/
│   ├── application/
│   │   └── acquisition.py          # jobs, workflow ports, policies, logs, metrics
│   ├── domain/
│   │   ├── acquisition.py          # AcquisitionJob and AcquisitionRecord
│   │   ├── ingestion.py            # artifact metadata and Import Batch lifecycle
│   │   └── source_registry.py
│   └── infrastructure/
│       └── source_acquisition.py    # local state/store/log/metric/fake/manual adapters
└── tests/
    ├── test_acquisition_workflow.py
    ├── test_source_acquisition.py
    └── fixtures/manual/
```

The remaining domain/application modules retain the structure described in [project structure v1.2](project-structure-v1.2.md).

## Dependency direction

```text
infrastructure -> application -> domain
tests ---------> infrastructure/application/domain

domain -X-> application or infrastructure
application -X-> infrastructure
```

Domain and application contracts remain standard-library-only. Blob storage and acquisition metadata persistence are separate injectable ports. Connectors return raw bytes and safe response facts only; parsing remains downstream.

## Implemented acquisition ownership

| Path | Responsibility |
|---|---|
| `domain/acquisition.py` | Job lifecycle, trigger, attempt count, idempotency identity, immutable result |
| `domain/ingestion.py` | Immutable artifact metadata, artifact-acquired event, batch acquired/duplicate/failed/skipped/reprocess states |
| `application/acquisition.py` | Job creation, fetch/retry/validation/hash/archive workflow, state/storage/log/metric ports |
| `infrastructure/source_acquisition.py` | Lock-serialized in-memory transactions, source+digest uniqueness, outbox/processing queue, atomic filesystem blob store |
| `tests/test_acquisition_workflow.py` | Success, duplicate, changed content, failures, retries, concurrency, disabled source, reprocessing |

## Validation

```sh
PYTHONPATH=src python3 -m unittest discover -s tests -v
python3 scripts/check_docs.py
python3 -m compileall -q src tests
git diff --check
```

## Related documents

- [Backend structure v1.3](../backend-structure/backend-structure-v1.3.md)
- [Business logic v1.3](../business-logic/business-logic-v1.3.md)
- [Project structure log](../../logs/project-structure-log-v1.3.md)

