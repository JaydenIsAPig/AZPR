# Runbooks

- [Source acquisition failure and recovery](source-acquisition.md) covers the implemented raw fake/manual acquisition slice and clearly marks production-only capabilities as unimplemented.
- [Source parsing](source-parsing.md) covers deterministic processing, quarantine, import reports, and versioned reprocessing for archived artifacts.
- [Permit normalization and duplicate review](permit-normalization.md) covers normalized facts, address review, corrections, probable duplicates, manual decisions, and supersession.
- [H0 Ansible integration-manager execution](ansible-qualification-environment.md) provides the authoritative qualification-only execution sequence, expected outputs, test matrix, failure handling, bounded reset, and handoff to independent verification.

Future runbooks are still required for durable ingestion replay, low-confidence review, notification delivery failure, security/privacy incidents, backup/restore, and other operational behavior when those capabilities exist.
