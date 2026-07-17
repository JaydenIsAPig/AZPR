# AZ Permit Radar

AZ Permit Radar is a planned Arizona-specific permit intelligence and opportunity-alert platform. The repository currently implements documentation governance and validation only; no product application, ingestion, dashboard, authentication, AI, notification, payment, or persistence behavior is implemented.

## Authoritative documentation

- [Project structure](docs/current/project-structure-v1.1.md)
- [Backend structure](docs/current/backend-structure-v1.1.md)
- [Business logic](docs/current/business-logic-v1.1.md)
- [Business data](docs/current/business-data-v1.0.json)
- [Frontend design](docs/current/frontend-design-v1.0.md)
- [Domain glossary](docs/governance/domain-glossary.md)
- [Architecture decisions](docs/adr/README.md)
- [Repository audit](docs/audits/repository-audit.md)
- [Contribution rules](CONTRIBUTING.md)

## Documentation validation

The domain kernel requires Python 3.12 or newer. Run from the repository root with `python3` resolving to a compatible interpreter:

```sh
PYTHONPATH=src python3 -m unittest discover -s tests -v
python3 scripts/check_docs.py
python3 -m json.tool docs/current/business-data-v1.0.json >/dev/null
python3 -m json.tool docs/schema/business-data.schema.json >/dev/null
git diff --check
```
