# Formal Audit Reports

The controller stores immutable, commit-addressed formal audit reports in this directory and maintains `index.json` after the first audit.

Audit agents are read-only. The controller writes and commits their report output.

## Interim authority before the first controller-managed audit

For the v10.1 staged-hybrid integration, the project owner approved this file
as the interim audit authority until `INT-04`. The governance owner's actual
name and role must be supplied through the non-secret operator input before
`INT-00` can complete; the placeholder `[name/role]` is not a valid identity.

While `index.json` is absent:

- no prior delivery, security, reconciliation, or model-generated report is
  promoted to a formal `PASS`;
- applicable prior reports are evidence only and must be read directly;
- `INT-04` is the first integration formal audit and must return exactly
  `PASS`, `PASS_WITH_REQUIRED_CORRECTIONS`, or `BLOCKED`;
- the invoking Python controller, not the audit agent, must create the first
  immutable report and `index.json` atomically in the same controlled commit.

The initial index structure is the controller-owned shape implemented by
`automation/controller.py::write_audit_artifacts`: format version `1.0` and an
`audits` array whose entries bind stage ID, title, verdict, audited commit,
report path, creation time, and structured corrections. Audit result input is
validated against `automation/result.schema.json`. The attached v10.1 final
delivery audit remains non-authoritative delivery provenance.
