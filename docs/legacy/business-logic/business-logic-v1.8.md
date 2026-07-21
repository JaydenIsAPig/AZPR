---
document_id: business-logic
version: 1.8
document_status: superseded
implementation_status: partially implemented
approved_on: 2026-07-20
---
# Business Logic v1.8

## Opportunity rules

- One initial stable Opportunity is generated per normalized Permit; applicable Classifications contribute categories and trades.
- Wording attributes claims to the source Permit record and removes phone/email-like contact text.
- Suppressed and expired Opportunities are not matchable.

## Eligibility and exclusions

- Customer must be active, have an enabled overlapping trade, and pass service territory evaluation.
- Minimum/maximum value, allowed value bands, excluded Permit types/projects, minimum confidence, and issue-date filters are deterministic gates.
- Notification settings affect readiness score but lack of a channel does not fabricate consent or independently create a notification.
- The same Opportunity may create separate customer-owned Matches; IDs and explanations are scoped by Customer Account.

## Score v1.0.0

Weights total exactly 100: trade 35, geography 30, value 15, completeness 10, freshness 5, notification readiness 5. Components are bounded from 0 to their governed weights and the total must equal their sum. Full freshness is at most 30 days; partial freshness is at most 90 days.

Replay with unchanged score/configuration returns the existing Match. Recalculation retains prior explanations. Dismissed or terminal Matches remain terminal. Existing active Matches become excluded when suppression or a hard exclusion later applies.

## Related documents at supersession

- [Project structure v1.8](../project-structure/project-structure-v1.8.md)
- [Backend structure v1.8](../backend-structure/backend-structure-v1.8.md)
- [Business data v1.3](../business-data/business-data-v1.3.json)
- [Business logic log](../../logs/business-logic-log-v1.8.md)
