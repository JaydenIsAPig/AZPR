# AZ Permit Radar Domain Glossary

These terms are normative. Implemented lifecycle states and aggregate rules are documented in the current backend and business-logic snapshots; changes require tests and documentation reconciliation.

| Term | Definition | Boundary rule |
|---|---|---|
| Jurisdiction | An Arizona government jurisdiction represented in the source and permit domains | Not a Source or geographic customer preference |
| Source | Registered external publisher or feed plus approved access metadata | Not a file, import run, or Permit |
| Source Artifact | Immutable acquired file or raw payload with integrity and acquisition metadata | Never overwritten by parsing or correction |
| Import Batch | One retry-safe acquisition/processing execution and its outcome | Not the Source or an individual Permit |
| Source Record | A record as represented by a Source Artifact before canonical interpretation | Not automatically the canonical Permit |
| Permit | An observed government record traceable to source evidence | Not an Opportunity, Match, lead, or alert |
| Address | A source-observed or normalized location value with provenance/quality | Not a Parcel or stable Project identity by itself |
| Parcel Reference | A jurisdiction-qualified land identifier asserted for a Permit | Not an address string or independent Project |
| Geocode Result | Provider-attributed coordinates with timestamp, quality, and confidence | Never an unattributed replacement for source evidence |
| Permit Duplicate Candidate | A reviewable relationship between two Permits supported by layered evidence | Not an automatic merge or deletion instruction |
| Project | A possible grouping of related records or Permits | Never inferred merely because one Permit exists |
| Party | A person or organization asserted by source data | Not a platform Customer unless explicitly linked |
| Project Classification | A controlled classification value describing interpreted project type | Not a versioned result or observed fact |
| Trade Tag | A stable trade classification used by classifications, customer preferences, Opportunities, and Match explanations | Not a free-form source label |
| Classification Result | A versioned interpretation with method, evidence, provenance, confidence, and review status | Not an observed fact or Opportunity by itself |
| Opportunity | A customer-independent, source-attributed projection derived from one or more source-backed Permits and Classifications | Not a Customer Match and never contains customer configuration |
| Customer Account | A platform business account receiving configured product behavior | Distinct from a Party named in source data |
| Customer Trade Preference | A Customer Account's enabled/disabled preference for one Trade Tag | Does not modify the Trade Tag catalog |
| Service Territory | Customer-owned geographic scope expressed by validated-origin radius, city/jurisdiction, ZIP set, or reserved polygon reference | Not a Jurisdiction entity and does not modify Permit geography |
| Territory Evaluation | Customer-isolated deterministic result containing inclusion, distance/unit, matched rule, exclusion reason, and verification status | Not a shared Opportunity fact or legal-boundary determination |
| Customer Filter | Customer-owned valuation, confidence, date, or exclusion constraints | Not a global Opportunity rule |
| Notification Preference | Customer-owned channel destination and explicit consent evidence | Not a delivery attempt or proof of current authorization by itself |
| Customer Match | The explainable relation between one Opportunity and one Customer/configuration | Not a Notification or shared Opportunity |
| Match Explanation | Recorded/reproducible trade, geography, filters, score components, exclusions, freshness, and confidence supporting a Match | Never only an unexplained score |
| Match Score Version | Governed deterministic weights and freshness boundaries used to calculate a Match's exact 100-point component sum | Not an AI model version; prior scored explanations remain reproducible |
| Notification Intent | The idempotent decision to communicate about a Customer Match through an eligible channel | Distinct from each provider attempt |
| Notification Attempt | One channel-specific delivery attempt concerning a Customer Match | Provider submission is not proof of delivery; a retry is a new attempt |
| Lead State | Customer-owned workflow state inside an Opportunity Match | Cannot mutate another Customer or shared Permit/Opportunity |
| Review Task | Internal work to review a precisely typed domain subject and record resolution | Does not become or directly mutate its subject |
| Domain Event | A fact emitted within the modular monolith about a domain state change | Not automatically an external integration contract |
| Integration Event | A stable event contract used across module or external boundaries | Published reliably when required, using an outbox |
| Transactional Outbox | Persisted record of an asynchronous side effect committed with domain state | Prevents lost state-to-message transitions; consumers remain idempotent |
| Deterministic-Derived Value | A value reproducibly calculated by versioned code/rules | Must be distinguishable from source-observed and AI-derived data |
| AI-Derived Value | A value inferred through an approved AI adapter for unresolved language ambiguity | Requires provenance, model/classifier version, confidence/review metadata |
| MVP | Minimum Viable Product | Never abbreviates Model–View–Presenter in this project |

## Usage rules

- Use “Customer Match” on first mention when “Match” could be ambiguous.
- Use “Notification Intent” and “Notification”/“Notification Attempt” explicitly when discussing idempotency and delivery.
- Qualify values as source-observed, normalized, deterministic-derived, or AI-derived.
- Create an ADR or glossary revision if one term gains two incompatible meanings.
