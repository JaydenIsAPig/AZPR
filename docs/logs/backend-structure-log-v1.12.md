---
document_id: backend-structure-log
version: 1.12
approved_on: 2026-07-20
---
# Backend Structure Log v1.12

- Required explicit access context on customer query and command messages.
- Added anti-enumeration not-found behavior and distinct unauthenticated/forbidden errors.
- Added scoped Match/configuration repositories, atomic customer updates, and customer-only recalculation.
- Added a separate permissioned internal query path.
