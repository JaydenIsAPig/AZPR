---
document_id: project-structure-log
version: 1.15
approved_on: 2026-08-11
---
# Project Structure Log v1.15

- Added inert Swift source for a noneditable approval review window and
  Touch-ID-protected Secure Enclave P-256 decision signature.
- Added a Python helper process, host trust, ECDSA assertion, canonical record,
  atomic replay ledger, and exact pre-action reverification boundary.
- Added assertion/request/trust/execution schemas, a null-valued trust template,
  cross-language golden vectors, software tests, and hardware-test contracts.
- Separated execution-run, evidence, outcome, and commit-eligibility records;
  no Git action is performed by these guards.
- Added ADR-0012 as a narrow source-placement supersession of ADR-0009 and kept
  the SHA-bound v10.1 transition contract and H0 transport ticket unchanged.
- Recorded that installation path, ownership, signing identity, host-state
  paths, subject, key creation, enrollment, activation, H0-T02, and all Git
  mutations remain deferred.
