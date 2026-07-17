# Documentation Update Checklist

Use this checklist for every material product, architecture, business-rule, business-data, frontend, or operational change.

## Determine impact

- [ ] Identify affected current document families.
- [ ] Identify affected ADRs, runbooks, audits, README/contribution guidance, schemas, and links.
- [ ] State what is implemented, partially implemented, planned, proposed, and not selected.
- [ ] Confirm the change does not invent behavior or values that lack approval.
- [ ] Decide whether an ADR is required for a consequential or difficult-to-reverse choice.

## Prepare a new current version

- [ ] Select a major or minor version under [ADR-0003](../adr/0003-documentation-versioning.md).
- [ ] Validate the replacement before promotion.
- [ ] Move the prior current file to `docs/legacy/<document-id>/`.
- [ ] Mark the archived copy `document_status: superseded`.
- [ ] Create the replacement in `docs/current/` with `document_status: current`.
- [ ] Ensure document ID, version metadata, filename, and approval date agree.
- [ ] Update the corresponding log with evidence, status changes, and affected links.
- [ ] Update cross-document and README links.

## Content checks

- [ ] Preserve the approved domain language and core concept separation.
- [ ] Separate actual state from planned state.
- [ ] List unresolved decisions as `not selected`; do not silently choose values.
- [ ] Keep source-specific behavior out of shared domain descriptions.
- [ ] Describe configurable business data separately from domain invariants.
- [ ] Reconcile security, privacy, consent, provenance, idempotency, observability, tests, and failure paths where relevant.
- [ ] Add or update runbooks only for behavior that exists or is explicitly marked planned.

## Validate and report

- [ ] Run `python3 scripts/check_docs.py`.
- [ ] Run `python3 -m json.tool docs/current/business-data-vX.Y.json >/dev/null` for changed JSON.
- [ ] Run `python3 -m json.tool docs/schema/business-data.schema.json >/dev/null` when the schema changes.
- [ ] Run `git diff --check`.
- [ ] Report files added, modified, and moved; behavior status changes; commands/results; versions changed; assumptions; risks; and deferred work.
