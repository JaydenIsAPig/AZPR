# Post-Prompt-10 Logic and Architecture Reconciliation Audit

- Audit date: 2026-07-20
- Repository state: current working tree, including pre-existing tracked and untracked changes
- Scope: read-only implementation reconciliation; this report is the only file created by the audit
- Prior evidence: `conversation-archives/2026-07-20-post-prompt-10-audit-conversation.md`
- Governing instruction: `AZ Permit Radar Master Operating Prompt.docx`

## Executive result

**CORRECTIONS STILL REQUIRED**

## Prompt 10C remediation update — 2026-07-20

This update supersedes the original status of only the findings placed in the Prompt 10C execution scope. Other findings and the overall “corrections still required” result remain unchanged.

| ID | Updated status | Enforcement and regression evidence |
|---|---|---|
| F08 | **RESOLVED (in-memory boundary)** | Opportunity material-input fingerprint/revision comparison, immutable superseded projection history, stale active-Match marking, and classification/rule/fact/replay regressions |
| F12 | **RESOLVED** | Governed completeness fields exclude valuation; valuation contributes only to the value component; missing-valuation differential regression |
| F13 | **RESOLVED** | Governed `issued_on` → `applied_on` → unknown precedence; unknown earns zero; acquisition and processing remain separate; missing-date regression |
| F14 | **RESOLVED (in-memory boundary)** | Immutable policy, weights, customer trade/territory/filter/notification, distance/unit, freshness, threshold, calculation-time, Opportunity-revision, component, rule, and explanation snapshots retained in score history |

Validation after remediation: 134 tests pass; documentation/schema/link validation, JSON validation, syntax compilation, and `git diff --check` pass. No formatter, linter, or type checker is configured in the repository. Durable persistence/reprocessing remains outside this finding closure and is explicitly documented.

## Prompt 10D remediation update — 2026-07-20

This update supersedes the original status of the coherent-pipeline findings below. The overall audit remains **CORRECTIONS STILL REQUIRED** because authorization and other Prompt 10E/production concerns remain outside this correction.

| ID | Updated status | Enforcement and regression evidence |
|---|---|---|
| F09 | **RESOLVED (in-memory boundary)** | `InMemoryAcquisitionState` is the sole Import Batch/queue owner; parsing claims an authoritative working copy and atomically commits a terminal Batch or records an explicit failure under one lock. |
| F10 | **RESOLVED (in-memory boundary)** | Claim/finish/fail operations remove terminal Batches from the processing queue; continuous-path partial and unusable-artifact regressions assert the authoritative terminal state and empty queue. |
| F11 | **RESOLVED (in-memory boundary)** | One shared-lock normalization unit of work snapshots and rolls back Permit, duplicate-candidate, and Review Task state; an injected commit failure proves no partial state remains. |
| F16 | **RESOLVED (in-memory boundary)** | The synchronous application workflow and structured trace connect Source, Artifact/hash, Batch, Source Record, Permit, Classification Result, Opportunity, Customer, Match, and Review identifiers. A three-record/two-customer fixture produces six explainable Matches. |
| F17 | **RESOLVED (in-memory boundary)** | Correlated safe trace entries cover every processing stage, explicit exclusions/reviews/failures and retry disposition without logging source payloads, addresses, contact details, or secrets. Production telemetry sinks remain deferred. |
| F18 | **RESOLVED (in-memory boundary)** | Regressions now cover repeated full commands, concurrent correlation execution, exclusive Batch claims, concurrent Opportunity/Match uniqueness, normalization rollback, corrected replay, duplicate resolution replay, radius boundaries, and failure followed by retry. Durable adapter races remain a future production requirement. |

Prompt 10D validation: 146 tests pass; documentation/schema/link validation, governed JSON validation, syntax compilation, and `git diff --check` pass. No formatter, linter, or type checker is configured. The implemented transaction model is deliberately process-local and synchronous; database transactions, durable unique constraints, transactional outbox publication, worker leases, and production retry scheduling remain documented future work rather than implied behavior.

## Prompt 10E remediation update — 2026-07-20

This update supersedes the original status of the customer-authorization finding below. The overall audit remains **CORRECTIONS STILL REQUIRED** pending Prompt 10F/final reconciliation and later production selections.

| ID | Updated status | Enforcement and regression evidence |
|---|---|---|
| F15 | **RESOLVED (in-memory application boundary)** | Explicit authenticated actor/relationship/role/permission context; customer-scoped query and command services; scoped repository ports; separate permissioned internal path; anti-enumeration not-found policy; atomic scoped lead/configuration updates; customer-only recalculation; integration tests including deliberately leaky adapter defense. |
| F19 | **PARTIALLY RESOLVED** | Current architecture/frontend/business-data labels and links are synchronized at v1.12/v1.1/v1.7 and structural validation passes. Automated semantic label/implementation-claim validation remains future reconciliation work. |

Prompt 10E validation: 160 tests pass; customer-isolation, application-query, lead-state, matching, architecture, and full configured suites pass. Documentation/schema/link validation, governed JSON validation, syntax compilation, and `git diff --check` pass. No formatter, linter, or static/type checker is configured. Authentication provider, tokens/sessions/passwords, framework middleware, database authorization/row policies, security audit transport, and production persistence remain explicitly unimplemented.

The later v1.8 documentation does not demonstrate that the prior BLOCKED findings were corrected. Current code and direct temporary probes reproduce the core safety failures: Candidate Opportunities match; pending and 0.20-confidence Classifications match; probable-duplicate, voided, and superseded Permits can produce Opportunities and Customer Matches; canonical and duplicate Permits create two Matches for one Customer; and changed classification or corrected Permit facts return a stale Opportunity.

The acquisition implementation improved atomic metadata finalization and acquisition-level concurrency, but parsing still mutates a detached `ImportBatch`; the acquisition state remains `acquired`, and its processing queue retains the locally completed batch. Normalization still performs separate Permit, duplicate-candidate, and Review Task saves without a unit of work. No production persistence, worker, API, UI, authentication, or authorization implementation exists.

This is not a human-decision stop condition. The current authoritative documents do not materially contradict one another about a selected architecture or persistence technology; they overstate implemented safety behavior relative to code. The repository remains inspectable, all configured validations pass, and no destructive migration is implicated.

## Status and enforcement legend

- **RESOLVED:** verified through the real implementation path and an appropriate enforcement layer.
- **PARTIALLY RESOLVED:** meaningful enforcement exists, but the finding is not closed end to end.
- **OPEN:** current implementation reproduces the finding or lacks the required enforcement.
- **REGRESSED:** later repository work introduced or renewed a previously aligned condition.
- **UNVERIFIABLE:** repository evidence is insufficient to classify safely.
- **Domain invariant:** aggregate/value-object construction or state transition enforces behavior.
- **Application gate:** an application workflow rejects or suppresses behavior.
- **Repository constraint:** a repository implementation prevents an invalid or duplicate state.
- **Database constraint:** durable database enforcement. None exists in this repository.
- **Test only:** asserted in tests without corresponding production-path enforcement.
- **Documentation only:** claimed or planned in documents without corresponding implementation.

## Finding matrix

| ID | Finding | Status | Severity | Present enforcement | Missing enforcement | Corrective prompt |
|---|---|---|---|---|---|---|
| F01 | Candidate Opportunities can reach matching | **OPEN** | Critical | Application gate rejects only `suppressed`/`expired` | Require `published` before matching; terminally exclude prior Matches if unpublished | 10B |
| F02 | Pending-review or low-confidence Classifications can reach publication/matching | **OPEN** | Critical | Optional customer minimum-confidence filter only | Governed publication threshold and accepted-review gate independent of customer configuration | 10B |
| F03 | Probable duplicates can reach matching | **OPEN** | Critical | Duplicate Review Task exists in normalization | Pending duplicate-candidate gate in Opportunity generation and matching | 10B |
| F04 | Voided/superseded Permits can produce Opportunities or Matches | **OPEN** | Critical | Permit transition invariants protect later corrections | Eligibility gate on Permit lifecycle/authority status | 10B |
| F05 | Canonical and duplicate Permits can create multiple Matches for one Customer | **OPEN** | Critical | Match ID is unique only per Opportunity+Customer in one in-memory map | Canonical lineage uniqueness and pending/merged duplicate suppression | 10B |
| F06 | `ClassificationAssertion` and `ClassificationResult` are disconnected | **OPEN** | High | Separate domain validation exists for each type | Conversion/persistence/review bridge and one authoritative classification flow | 10C |
| F07 | Review Tasks use inconsistent subject types/identifiers | **OPEN** | High | Review Task requires nonblank subject fields | Typed referential integrity between `subject_type` and `subject_id` | 10C |
| F08 | Existing Opportunities remain stale after classification/parser/rule/fact changes | **OPEN** | High | Stable Permit-derived Opportunity ID prevents duplicates | Version/fingerprint comparison and update/rebuild policy | 10C |
| F09 | Import Batch state is mutated on detached copies or disagrees across repositories | **OPEN** | High | Acquisition metadata is lock-serialized within `InMemoryAcquisitionState` | Shared batch state/UoW across acquisition and parsing | 10D |
| F10 | Acquisition/parsing queues retain failed or completed batches | **OPEN** | High | Acquisition enqueues only newly archived/reprocessed batches | Claim/ack/fail queue lifecycle and terminal-state removal | 10D |
| F11 | Normalization can leave partial Permit/Review/duplicate state | **OPEN** | High | Individual in-memory saves are lock/deepcopy based | Atomic normalization unit of work and rollback/transaction | 10D |
| F12 | Valuation is double-counted through value and completeness scoring | **OPEN** | Medium | Score sum and component bounds are domain-validated | Independent completeness definition or explicit governed overlap | 10E |
| F13 | Missing source dates are represented as fresh | **OPEN** | High | Freshness thresholds are versioned | Unknown-source-date representation and non-fresh scoring rule | 10E |
| F14 | Historical explanations omit customer filters, thresholds, territory, or policy snapshot | **PARTIALLY RESOLVED** | High | Score/config version and prior explanations are retained in memory | Immutable configuration/filter/territory/policy snapshot per explanation | 10E |
| F15 | Customer-scoped reads/writes lack authorization boundaries | **OPEN** | Critical | Geography compares supplied customer IDs | Authenticated principal/authorization policy and scoped repositories/handlers | 10E |
| F16 | No continuous Artifact-to-Customer-Match trace | **OPEN** | High | Individual entities contain several provenance IDs | Executable workflow, authoritative classification bridge, and durable trace query | 10D |
| F17 | Failure observability is incomplete | **PARTIALLY RESOLVED** | High | Acquisition, parsing, and normalization logs/metrics exist | Classification/matching/projection failure and suppression telemetry | 10E |
| F18 | Concurrency and replay tests are insufficient | **PARTIALLY RESOLVED** | High | Acquisition concurrency and local replay tests exist | Cross-stage, normalization, projection, matching, and durable uniqueness races | 10E |
| F19 | Documentation contains stale claims, filenames, or visible version labels | **REGRESSED** | Medium | Link targets and structural documentation checks pass | Semantic link-label/version validation and evidence-based implementation claims | 10E |
| F20 | No production persistence, worker, API, or UI exists | **PARTIALLY RESOLVED** | High | Current docs and README now disclose the limitation | Production selections and implementations remain absent | none |

## Detailed reconciliation evidence

### F01 — Candidate Opportunities reach matching — OPEN

- **Implementation inspected:** `OpportunityStatus` and `_OPPORTUNITY_TRANSITIONS` in `src/az_permit_radar/domain/opportunity.py:23`; `ExplainableMatchGenerator.generate` and `_exclusions` in `src/az_permit_radar/application/opportunity_matching.py:134` and `:160`.
- **Actual behavior:** `_exclusions` rejects only `SUPPRESSED` and `EXPIRED`; `CANDIDATE` and `PUBLISHED` both proceed. A temporary probe produced a Match for each status.
- **Tests inspected:** `OpportunityGenerationMatchingTests.test_exclusions_cover_account_trade_geography_value_filters_and_suppression`, `.test_existing_match_is_terminally_excluded_when_opportunity_is_suppressed`, and `.test_positive_match_scores_100_and_has_full_explanation` in `tests/test_opportunity_generation_matching.py`. No test requires publication.
- **Enforcement:** application gate for two terminal statuses only; no domain/repository/database publication constraint. The v1.8 phrase “suppressed and expired Opportunities are not matchable” is implemented, but it is weaker than a publication gate.
- **Required action:** make `PUBLISHED` the sole matchable status and regression-test Candidate-to-Published behavior.

### F02 — Pending-review and low-confidence Classifications reach matching — OPEN

- **Implementation inspected:** `ClassificationResult.review_status` and `accept`/`reject` in `src/az_permit_radar/domain/classification.py:100`; `OpportunityGenerator.generate` in `src/az_permit_radar/application/opportunity_matching.py:73`; `ExplainableMatchGenerator._exclusions` at `:160`; governed thresholds in `docs/current/business-data-v1.3.json:20`.
- **Actual behavior:** Opportunity generation reads classification IDs, categories, trades, and confidence but never checks `review_status` or the governed `review_confidence` of `0.80`. Matching checks confidence only if an individual Customer configures `minimum_confidence`. Probes matched a default-pending result and a confidence `0.20` result; an accepted result also matched.
- **Tests inspected:** `ClassificationSubsystemTests.test_ai_cannot_overwrite_deterministic_and_low_confidence_creates_review` proves task creation only; `OpportunityGenerationMatchingTests.test_positive_match_scores_100_and_has_full_explanation` uses a pending `ClassificationResult`; no test proves governed publication suppression.
- **Enforcement:** domain review transition plus optional customer application filter; no governed application/repository/database gate.
- **Required action:** define and enforce eligible review statuses and governed confidence before Opportunity publication/matching.

### F03 — Probable duplicates reach matching — OPEN

- **Implementation inspected:** `PermitDuplicateCandidate`/`DuplicateCandidateStatus.PENDING_REVIEW` in `src/az_permit_radar/domain/deduplication.py:31`; `PermitNormalizationWorkflow.normalize` in `src/az_permit_radar/application/normalization.py:199`; Opportunity/match inputs in `src/az_permit_radar/application/opportunity_matching.py:73` and `:134`.
- **Actual behavior:** normalization saves the incoming Permit before creating a pending duplicate candidate and Review Task. Neither Opportunity generation nor matching receives or queries duplicate-candidate state. A probe held a `pending_review` candidate while creating two Opportunities and two Matches for one Customer.
- **Tests inspected:** `PermitNormalizationTests.test_address_variants_create_probable_duplicate_review_not_silent_merge` asserts two Permits and a pending candidate; no Prompt-10 test carries that state into matching.
- **Enforcement:** normalization workflow/documentation only at the matching boundary; no gate or constraint.
- **Required action:** prevent pending probable duplicates from Opportunity generation/matching until an explicit distinct decision.

### F04 — Voided/superseded Permits produce Opportunities and Matches — OPEN

- **Implementation inspected:** `PermitStatus`, `Permit.void`, and `Permit.supersede` in `src/az_permit_radar/domain/permit.py:173`, `:379`, and `:430`; `OpportunityGenerator.generate` and `ExplainableMatchGenerator._exclusions` in `src/az_permit_radar/application/opportunity_matching.py`.
- **Actual behavior:** Permit methods protect later mutation but do not prevent downstream derivation. Probes created and matched Opportunities from both `voided` and `superseded` Permits with no exclusion rule.
- **Tests inspected:** `PermitTests.test_voided_permit_cannot_be_corrected` and `PermitNormalizationTests.test_manual_merge_retains_decision_and_supersession_history` test state transitions only; Prompt-10 tests use only active Permits.
- **Enforcement:** domain mutation invariant only; missing downstream application/repository/database eligibility enforcement.
- **Required action:** block non-canonical and voided lifecycle states before Opportunity generation and matching.

### F05 — Canonical and duplicate Permits create multiple Customer Matches — OPEN

- **Implementation inspected:** Permit-derived Opportunity ID in `OpportunityGenerator.generate` (`src/az_permit_radar/application/opportunity_matching.py:77`) and Opportunity+Customer Match ID at `:155`; `InMemoryOpportunityMatchStore.find_for` in `src/az_permit_radar/infrastructure/opportunity_matching.py:35`.
- **Actual behavior:** different Permit IDs always create different Opportunity IDs; each can create a separate Match for the same Customer. A probe produced two Opportunities and two Matches while the duplicate candidate remained pending.
- **Tests inspected:** `OpportunityGenerationMatchingTests.test_replay_is_idempotent_and_two_customers_remain_isolated` proves one Opportunity can match two Customers, not that one Customer is protected from canonical/duplicate Permits.
- **Enforcement:** in-memory identity convention only; no canonical-lineage or database uniqueness constraint.
- **Required action:** define the canonical match identity/lineage and enforce it in both application logic and durable persistence later.

### F06 — Classification models are disconnected — OPEN

- **Implementation inspected:** `ClassificationAssertion` and `ClassificationResult` in `src/az_permit_radar/domain/classification.py:53` and `:107`; `PermitClassificationService.classify` in `src/az_permit_radar/application/classification.py:49`; `OpportunityGenerator.generate` type/logic in `src/az_permit_radar/application/opportunity_matching.py:73`; `ClassificationResultRepository` in `src/az_permit_radar/application/repositories.py:67`.
- **Actual behavior:** the current classifier returns `ClassificationAssertion` objects; the Opportunity generator requires `ClassificationResult`. No application converter or assertion repository exists. Passing actual classifier output into generation raises `AttributeError: 'ClassificationAssertion' object has no attribute 'permit_id'`.
- **Tests inspected:** all six `ClassificationSubsystemTests` in `tests/test_classification_subsystem.py` and all Prompt-10 tests. They test the two paths separately and never bridge them.
- **Enforcement:** separate domain invariants and test-only coverage; no integrated application/repository path.
- **Required action:** select one authoritative persisted classification aggregate or implement an explicit, versioned conversion/review workflow.

### F07 — Review Task subject type and identifier disagree — OPEN

- **Implementation inspected:** `PermitClassificationService.classify` at `src/az_permit_radar/application/classification.py:68`; `ReviewSubjectType` and `ReviewTask` in `src/az_permit_radar/domain/review.py:13` and `:41`.
- **Actual behavior:** a low-confidence assertion creates `subject_type=classification_result` while `subject_id` is the Permit ID. The probe returned `classification_result / permit-classify`. Address and duplicate tasks use address and candidate IDs consistently, so this is specific to classification orchestration.
- **Tests inspected:** `ClassificationSubsystemTests.test_ai_cannot_overwrite_deterministic_and_low_confidence_creates_review` asserts only task count; it does not assert subject referential consistency. `PermitNormalizationTests.test_address_resolution_failure_creates_reviewable_state_without_logging_address` and `.test_address_variants_create_probable_duplicate_review_not_silent_merge` demonstrate the consistent cases.
- **Enforcement:** nonblank domain invariant only; no typed identifier or repository referential constraint.
- **Required action:** create a real Classification Result before opening its task, or use `PERMIT`/Permit ID until such a result exists.

### F08 — Opportunities stay stale after upstream change — OPEN

- **Implementation inspected:** `OpportunityGenerator.generate` at `src/az_permit_radar/application/opportunity_matching.py:73`, especially the unconditional existing return at `:79-81`; `Opportunity` projection fields in `src/az_permit_radar/domain/opportunity.py:38`.
- **Actual behavior:** Opportunity identity depends only on Permit ID. Existing rows are returned without comparing classification IDs/version, trade tags, parser version, Permit version/facts, or source record lineage. Probes confirmed stale classification IDs, stale trade tags, stale value, and stale description after changed classification/rule inputs and corrected facts.
- **Tests inspected:** `OpportunityGenerationMatchingTests.test_opportunity_contains_safe_source_backed_projection_and_replays` verifies unchanged replay only. `PermitNormalizationTests.test_changed_fingerprint_for_same_external_id_records_correction_snapshot` does not connect correction to Opportunity regeneration.
- **Enforcement:** in-memory idempotency convention and test only; no invalidation/version constraint.
- **Required action:** persist an input fingerprint/version set and deterministically update/rebuild or suppress stale projections.

### F09 — Import Batch state diverges across acquisition and parsing — OPEN

- **Implementation inspected:** `InMemoryAcquisitionState.get_batch` deep copy in `src/az_permit_radar/infrastructure/source_acquisition.py:130`; `SourceParserPipeline.parse` mutating its supplied batch in `src/az_permit_radar/application/parsing.py:235`; `ImportBatchRepository` in `src/az_permit_radar/application/repositories.py:50` is not used by either integrated path.
- **Actual behavior:** an acquisition-created batch was fetched and parsed. The local copy became `completed`; `InMemoryAcquisitionState` still returned `acquired`.
- **Tests inspected:** `AcquisitionWorkflowTests.test_successful_scheduled_acquisition_archives_and_enqueues_once` and `SourceParsingTests.test_fixture_batch_accepts_valid_rows_and_quarantines_only_bad_rows` test separate batch instances. No cross-workflow handoff test exists.
- **Enforcement:** acquisition-local lock/transaction only; missing shared repository/UoW and durable concurrency control.
- **Required action:** make parsing claim and persist the authoritative batch through the same state boundary.

### F10 — Processing queue retains terminal batches — OPEN

- **Implementation inspected:** enqueue operations and `processing_batch_ids` in `src/az_permit_radar/infrastructure/source_acquisition.py:204`, `:244`, and `:323`; `AcquisitionState` protocol in `src/az_permit_radar/application/acquisition.py:544` has no dequeue/ack/fail operation.
- **Actual behavior:** after the detached batch completed parsing, the acquisition queue still contained its ID. Failed acquisition batches are not enqueued, but an already-enqueued batch has no claim/ack removal lifecycle.
- **Tests inspected:** `AcquisitionWorkflowTests.test_exact_duplicate_creates_terminal_batch_without_processing`, `.test_failed_job_can_be_retried_without_duplicate_processing`, and `.test_manual_reprocessing_uses_archived_artifact_without_refetching`; none consume/ack the queue. Parsing failure tests mutate only local batches.
- **Enforcement:** enqueue decision only; no queue lifecycle/repository/database constraint.
- **Required action:** add atomic claim, lease/retry, acknowledgement, and terminal failure handling with cross-stage tests.

### F11 — Normalization persistence is non-atomic — OPEN

- **Implementation inspected:** sequential saves in `PermitNormalizationWorkflow.normalize` and `.decide_duplicate` at `src/az_permit_radar/application/normalization.py:225-354`; independent in-memory stores in `src/az_permit_radar/infrastructure/permit_normalization.py:529`, `:563`, and `:575`.
- **Actual behavior:** a temporary injected Review Store failure after probable-duplicate detection left two Permits and one duplicate candidate persisted with no Review Task. Other failure orderings can leave different partial combinations.
- **Tests inspected:** all nine `PermitNormalizationTests`; none inject repository failures or assert rollback/atomicity. Backend log v1.5 explicitly called the durable normalization unit of work deferred.
- **Enforcement:** separate repository operations only; no application UoW or database transaction.
- **Required action:** commit Permit, candidate, Review Task, decision, and related outbox events atomically.

### F12 — Valuation affects two score components — OPEN

- **Implementation inspected:** `OpportunityGenerator._completeness` in `src/az_permit_radar/application/opportunity_matching.py:122`; value/completeness scoring in `_explanation` at `:191`; weights in `docs/current/business-data-v1.3.json:35`.
- **Actual behavior:** valuation presence grants the 15-point value component and also contributes one of five fields used to classify completeness, potentially affecting another 5-10 points. The policy and docs do not state this overlap as intentional.
- **Tests inspected:** `OpportunityGenerationMatchingTests.test_positive_match_scores_100_and_has_full_explanation` asserts the sum only; no test proves component independence or approves overlap.
- **Enforcement:** score arithmetic/domain sum invariant; missing governed semantic constraint.
- **Required action:** remove valuation from completeness or explicitly approve, document, and regression-test the overlap.

### F13 — Missing source dates appear fresh — OPEN

- **Implementation inspected:** freshness fallback in `OpportunityGenerator.generate` at `src/az_permit_radar/application/opportunity_matching.py:85-86`; freshness scoring in `_explanation` at `:195-196`.
- **Actual behavior:** when both Permit dates are missing, `recorded_at` (normalization/recording time) becomes `source_freshness_date`. A probe with no source date reported the normalization date as freshness and would receive recent-source points.
- **Tests inspected:** Prompt-10 fixtures always set `issued_on`; no missing-date freshness test exists.
- **Enforcement:** application fallback only; it enforces the incorrect semantic. No source-date/unknown freshness distinction.
- **Required action:** retain `None`/unknown source freshness and score it according to an explicit governed rule.

### F14 — Historical explanations are incomplete snapshots — PARTIALLY RESOLVED

- **Implementation inspected:** `MatchExplanation` and `OpportunityMatch.recalculate` in `src/az_permit_radar/domain/matching.py:40` and `:158`; explanation construction in `src/az_permit_radar/application/opportunity_matching.py:191`.
- **Actual behavior:** prior explanations, score version, matched rule strings, and a Customer version integer are retained. `relevant_filters` is only `("customer filters passed",)`; actual valuation thresholds, allowed bands, permit/project exclusions, confidence/date filters, full territory configuration, and the score-policy weights/boundaries are not snapshotted.
- **Tests inspected:** `OpportunityGenerationMatchingTests.test_configuration_and_score_rule_changes_recalculate_with_history` checks history length/version only.
- **Enforcement:** domain invariant/history in memory; missing immutable configuration snapshot and durable persistence.
- **Required action:** store the exact evaluated configuration and policy snapshot (or immutable version references that remain resolvable).

### F15 — Customer authorization boundaries are absent — OPEN

- **Implementation inspected:** `GeographyQueryService.evaluate` ID equality check in `src/az_permit_radar/application/geography.py:77`; unimplemented CQRS messages in `src/az_permit_radar/application/queries.py` and `commands.py`; generic repositories in `src/az_permit_radar/application/repositories.py`.
- **Actual behavior:** callers supply both the requesting ID and Customer object; no authenticated principal, authorization policy, handler, scoped repository, database row policy, or customer write guard exists. The geography equality check is a useful invariant, not authorization.
- **Tests inspected:** `GeographyTerritoryTests.test_queries_are_customer_isolated` checks only the supplied-ID comparison; `OpportunityGenerationMatchingTests.test_replay_is_idempotent_and_two_customers_remain_isolated` checks identity/data separation, not access control.
- **Enforcement:** application invariant and tests only; no authorization or durable isolation layer.
- **Required action:** define principal/role policy, customer-scoped handlers/repositories, and unauthorized read/write integration tests before user-facing work.

### F16 — No continuous Artifact-to-Match trace — OPEN

- **Implementation inspected:** Source Artifact/Record/Permit provenance in `src/az_permit_radar/domain/ingestion.py` and `permit.py`; disconnected classification flow (F06); separate stores in `src/az_permit_radar/infrastructure/source_acquisition.py`, `source_parsing.py`, `permit_normalization.py`, and `opportunity_matching.py`.
- **Actual behavior:** individual IDs can represent Artifact -> Source Record -> Permit and Opportunity -> Match segments, but no executable workflow, shared repository, or trace query connects all segments. Actual classifier output cannot enter Opportunity generation.
- **Tests inspected:** Prompt 5-10 workflow suites are stage-local. No test starts with an acquired Artifact and asserts a resulting Customer Match with complete provenance.
- **Enforcement:** domain provenance fields only; no integrated application/repository/database trace.
- **Required action:** implement one coherent vertical workflow and trace query, initially in memory if necessary and later with durable constraints.

### F17 — Failure observability is incomplete — PARTIALLY RESOLVED

- **Implementation inspected:** acquisition log/metrics ports in `src/az_permit_radar/application/acquisition.py`; parsing log/metrics in `application/parsing.py`; normalization log/metrics in `application/normalization.py`; classification and matching services have no corresponding observability ports.
- **Actual behavior:** acquisition, parser, and normalization paths emit structured operational records for many success/failure cases. Classification catches broad AI exceptions into `failed_closed` without a log/metric; projection/matching have no structured failure, exclusion, stale-input, or suppression telemetry.
- **Tests inspected:** `AcquisitionWorkflowTests.test_timeout_fails_job_batch_updates_health_and_is_observable`, `SourceParsingTests.test_unusable_artifact_fails_whole_batch_and_is_observable`, and normalization logging tests provide partial coverage. Prompt-8/10 tests do not assert operational telemetry.
- **Enforcement:** application adapters/tests in three stages; missing later-stage observability and production sink.
- **Required action:** add safe structured events/metrics for classification, review suppression, projection, matching, and replay/staleness failures.

### F18 — Concurrency/replay coverage is incomplete — PARTIALLY RESOLVED

- **Implementation inspected:** lock-based acquisition state, parsing/normalization stores, and Opportunity/Match stores; all Prompt 5-10 tests.
- **Actual behavior:** acquisition now has same-content and same-job concurrency tests. Parsing tests parser-version replay, and matching tests unchanged replay/config-score recalculation. There are no races for queue claim, Source Record uniqueness, normalization exact/probable duplicate decisions, Opportunity regeneration, Match uniqueness/recalculation, or any durable store.
- **Tests inspected:** `AcquisitionWorkflowTests.test_concurrent_same_content_archives_once_and_marks_other_duplicate`, `.test_concurrent_claim_of_same_job_is_rejected_and_logged`, `SourceParsingTests.test_reprocessing_with_new_parser_version_creates_new_results`, and Prompt-10 replay tests.
- **Enforcement:** lock-based in-memory repository plus tests; no database constraints or cross-stage concurrency suite.
- **Required action:** add targeted races/replays at each identity boundary and repeat them against the eventual production persistence adapter.

### F19 — Documentation drift regressed — REGRESSED

- **Implementation inspected:** all current documents, logs v1.3-v1.8, frontend log v1.0, ADRs 0001-0004, README, and `scripts/check_docs.py`.
- **Actual behavior:** `docs/current/frontend-design-v1.0.md:56-59` visibly labels Project/Backend/Business Logic as v1.5 and Business Data as v1.0 while links target v1.8/v1.3. These labels were aligned when frontend v1.0 was created and became stale as later targets advanced. Current v1.8 project/backend/business-logic documents claim stable generation, eligibility gates, replay, and recalculation without disclosing the reproduced candidate/classification/Permit/duplicate/staleness failures. `scripts/check_docs.py` validates link existence, not visible label/target agreement or implementation claims.
- **Tests inspected:** the configured documentation script passed; that pass does not cover semantic label consistency. No documentation consistency unit test exists.
- **Enforcement:** documentation-only claims and structural check only.
- **Required action:** after code corrections, reconcile implementation statements; immediately add a semantic visible-label/target version check so future version advances cannot repeat this drift.

### F20 — Production persistence, worker, API, and UI remain absent — PARTIALLY RESOLVED

- **Implementation inspected:** `pyproject.toml`, repository tree, ADR-0004, `README.md:3`, `docs/current/project-structure-v1.8.md:14`, and `docs/current/frontend-design-v1.0.md:13`.
- **Actual behavior:** the code is a standard-library domain/application kernel with in-memory adapters and local fixture/file tooling. No database/ORM/migration, production worker, web/API framework, authentication, authorization, frontend application, browser test, deployment, or production connector exists.
- **Tests inspected:** all 117 tests use domain objects, fakes, fixtures, temporary local files, or in-memory stores. There is no production end-to-end suite.
- **Enforcement:** the limitation is now disclosed in current docs/README, which partially resolves the wording risk. The capability gap is real and intentionally not selected by ADR-0004.
- **Required action:** keep the limitation explicit. Production selections require later ADRs and scoped implementation; do not imply readiness before those exist.

## Required probe results

All probes ran with Python 3.12, `PYTHONDONTWRITEBYTECODE=1`, and `PYTHONPATH=src`; they created no repository files.

| Probe | Observed result |
|---|---|
| Canonical Permit | Candidate Opportunity created and matched |
| Superseded Permit | Opportunity created; Match created; no exclusions |
| Voided Permit | Opportunity created; Match created; no exclusions |
| Probable duplicate | Candidate remained `pending_review`; same Customer received two Matches |
| Pending-review Classification | Match created |
| Confidence below governed threshold | Confidence `0.20` matched despite governed review threshold `0.80` |
| Approved Classification | Match created (expected positive control) |
| Candidate Opportunity | Match created |
| Published Opportunity | Match created (expected positive control) |
| Repeated unchanged generation | Same Opportunity ID; one stored Opportunity |
| Changed classification version/trades | Existing Opportunity retained stale classification IDs/trades |
| Corrected normalized facts | Existing Opportunity retained stale value/description |
| Missing publication/Permit dates | Normalization/recorded date became source freshness date |
| Two Customers, same Opportunity | Two distinct Customer-owned Match IDs (expected isolation behavior) |
| One Customer, canonical and duplicate Permits | Two Opportunities and two Matches |
| Classifier-to-Opportunity bridge | `ClassificationAssertion` caused `AttributeError` because generator expects `ClassificationResult` |
| Acquisition-to-parsing batch handoff | Local batch `completed`; acquisition state `acquired`; queue still contained batch ID |
| Normalization repository failure | Review save failure left two Permits and one duplicate candidate with no Review Task |

## Documentation consistency result

- Current family filenames and link targets exist, and exactly one current file per family is structurally present.
- The separately supplied `/Users/jayden/Downloads/project-structure-v1.8.md` is byte-for-byte identical to `docs/current/project-structure-v1.8.md` (same SHA-256).
- Frontend related-document visible labels are stale even though their link targets exist:
  - visible `Project structure v1.5` -> `project-structure-v1.8.md`
  - visible `Backend structure v1.5` -> `backend-structure-v1.8.md`
  - visible `Business logic v1.5` -> `business-logic-v1.8.md`
  - visible `Business data v1.0` -> `business-data-v1.3.json`
- v1.8 documents accurately disclose in-memory persistence/no production worker/API/UI, but overstate safety and replay behavior by omitting the reproduced eligibility and stale-projection failures.

## Validation results

| Category | Command/evidence | Result |
|---|---|---|
| Documentation checks | Python 3.12 `scripts/check_docs.py` | **PASS** — structural current-family, schema, log, and local-link checks |
| JSON Schema validation | Included in `scripts/check_docs.py` against `docs/schema/business-data.schema.json` | **PASS** |
| JSON syntax | `python -m json.tool` for current business data and schema | **PASS** |
| Unit/architecture/in-memory workflow tests | `PYTHONPATH=src python -m unittest discover -s tests -v` | **PASS — 117/117** |
| Separate production integration tests | No configured external database/worker/API/UI integration suite | **NOT CONFIGURED** |
| Formatter check mode | No formatter or formatter configuration in repository | **NOT CONFIGURED** |
| Linter | No linter or linter configuration in repository | **NOT CONFIGURED** |
| Static/type analysis | No static/type checker configuration in repository | **NOT CONFIGURED** |
| Build/package validation | `pyproject.toml` has no build-system/tool command; no build command documented | **NOT CONFIGURED** |
| Migration validation | No database or migration tool exists | **NOT CONFIGURED** |
| Repository secret scan | No configured secret scanner/baseline/CI command exists | **NOT CONFIGURED** |
| Whitespace/error markers | `git diff --check` | **PASS** |

Passing tests do not resolve the audit findings because the unsafe cases are absent from the suite. Passing documentation checks do not validate visible link labels or implementation truthfulness.

## Corrective execution plan

Only remaining work is listed; the superseding remediation updates above retain the completed Prompt 10B-10E evidence.

1. **Prompt 10F — final reconciliation**
   - Execute the next governed correction prompt without expanding authentication or persistence scope implicitly.
2. **Later production phase (not a Prompt 10 correction)**
   - Select durable persistence, worker, API/auth, UI, deployment, and migrations through accepted decisions before claiming production readiness.

## Proceed decision

**RUN PROMPT 10F**

Prompt 10E now has a tested customer-scoped authorization contract and a documented Prompt 11 authentication seam. Prompt 10F is the next governed correction; authentication implementation, production persistence, and framework middleware remain explicitly deferred.
