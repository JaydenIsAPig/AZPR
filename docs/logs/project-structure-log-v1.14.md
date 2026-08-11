---
document_id: project-structure-log
version: 1.14
approved_on: 2026-08-07
---
# Project Structure Log v1.14

- Added the controller-side approval checkpoint boundary without activating the
  repository or external controller.
- Added version-controlled stage manifests, strict action/evidence validation,
  canonical ticket serialization, SHA-256 review binding, and immutable review
  projections.
- Separated authenticated decisions, execution authorizations, execution runs,
  evidence bundles, and outcome records.
- Required exact target revalidation, expiry enforcement, and trusted adapter
  reverification before execution.
- Defined immutable base approval IDs, `-RNN` simple revisions, new IDs for
  material authority changes, and delta tickets only for out-of-scope
  remediation.
- Recorded that `AZPR-H0-TRANSPORT-20260807-001` has a valid ticket but no
  authenticated decision, so H0-T02 remains stopped.
