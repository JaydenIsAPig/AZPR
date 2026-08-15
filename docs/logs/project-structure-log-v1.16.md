---
document_id: project-structure-log
version: 1.16
approved_on: pending
---
# Project Structure Log v1.16

- Added an inert deterministic H0 target-fingerprint contract, implementation,
  and golden vector; the procedure remains pending human approval.
- Fixed the nine independently observed non-secret identity fields, narrow
  normalization, exact member order, canonical UTF-8 JSON bytes, SHA-256, and
  fail-closed mismatch/unavailable-field behavior.
- Added Draft 2020-12 operator-input validation with an enabled `date-time`
  `FormatChecker`, exact procedure/target hash comparison, and authorization
  window checks without displaying authorization text or credential values.
- Preserved the authority boundary: a fingerprint identifies a target but
  never authorizes it, and the operator-approval adapter remains inactive.
- Recorded that ADR-0013, the exact fingerprint procedure, and exact live
  target authorization require separate human action before H0-ALV-00.
