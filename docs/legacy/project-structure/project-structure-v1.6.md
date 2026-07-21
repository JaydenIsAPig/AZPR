---
document_id: project-structure
version: 1.6
document_status: superseded
implementation_status: partially implemented
approved_on: 2026-07-17
---

# Project Structure v1.6

## Status statement

**Implemented:** v1.5 behavior plus a deterministic-first Permit classification vertical slice with per-tag provenance, a provider-neutral AI adapter, confidence-based review tasks, labeled human decisions, and fixed evaluation fixtures.

**Partially implemented:** persistence remains in-memory/local. No live AI provider, automatic retraining, durable classification unit of work, review UI/API, or production classifier telemetry is selected.

## Classification ownership

| Path | Responsibility |
|---|---|
| `domain/classification.py` | Assertions, origins, rule/model provenance, human labeled decisions |
| `application/classification.py` | Deterministic-first orchestration, precedence, thresholds, review creation |
| `infrastructure/permit_classification.py` | Versioned Arizona pilot rules, business-data loader, schema-constrained AI adapter, precision report |
| `tests/fixtures/classification/evaluation-v1.json` | Fixed labeled evaluation set |
| `tests/test_classification_subsystem.py` | Determinism, AI safety, review, provenance, evaluation tests |

Dependency direction remains `infrastructure -> application -> domain`. Provider SDKs are not dependencies of the domain or application layers.

## Validation

```sh
PYTHONPATH=src python3 -m unittest discover -s tests -v
python3 scripts/check_docs.py
python3 -m compileall -q src tests
git diff --check
```

## Related current documents

- [Backend structure v1.6](../backend-structure/backend-structure-v1.6.md)
- [Business logic v1.6](../business-logic/business-logic-v1.6.md)
- [Business data v1.1](../business-data/business-data-v1.1.json)
- [Frontend design v1.0](../frontend-design/frontend-design-v1.0.md)
- [Project structure log](../../logs/project-structure-log-v1.6.md)
