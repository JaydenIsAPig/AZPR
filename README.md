# AZ Permit Radar

AZ Permit Radar is an Arizona-specific permit intelligence and opportunity-alert platform. The repository implements a framework-independent domain kernel, scheduled/manual immutable raw acquisition, deterministic fixture parsing, Permit/address normalization, layered duplicate review, correction/merge history, logs, and metrics. No approved live municipal connector, production geocoder, dashboard, authentication, AI provider, notification delivery, payment, durable database, or production deployment is implemented.

## Authoritative documentation

- [Project structure](docs/current/project-structure-v1.18.md)
- [Backend structure](docs/current/backend-structure-v1.12.md)
- [Business logic](docs/current/business-logic-v1.12.md)
- [Business data](docs/current/business-data-v1.7.json)
- [Frontend design](docs/current/frontend-design-v1.1.md)
- [Domain glossary](docs/governance/domain-glossary.md)
- [Architecture decisions](docs/adr/README.md)
- [Repository audit](docs/audits/repository-audit.md)
- [Contribution rules](CONTRIBUTING.md)
- [Source onboarding checklist](docs/governance/source-onboarding-checklist.md)
- [Source acquisition runbook](docs/runbooks/source-acquisition.md)
- [Source parsing runbook](docs/runbooks/source-parsing.md)
- [Permit normalization runbook](docs/runbooks/permit-normalization.md)

## Documentation validation

The domain kernel requires Python 3.12 or newer. Run from the repository root with `python3` resolving to a compatible interpreter:

```sh
PYTHONPATH=src python3 -m unittest discover -s tests -v
python3 scripts/check_docs.py
python3 -m json.tool docs/current/business-data-v1.7.json >/dev/null
python3 -m json.tool docs/schema/business-data.schema.json >/dev/null
git diff --check
```
