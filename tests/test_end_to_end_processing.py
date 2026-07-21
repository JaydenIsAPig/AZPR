import tempfile
import threading
import unittest
from decimal import Decimal
from pathlib import Path

from az_permit_radar.application.acquisition import AcquisitionError, AcquisitionFailureCategory, RawAcquisition, RequestPolicy, RetryPolicy, ScheduledAcquisitionWorkflow
from az_permit_radar.application.classification import ClassificationPolicy, PermitClassificationService
from az_permit_radar.application.geography import GeographyQueryService, _haversine_km
from az_permit_radar.application.normalization import PermitNormalizationWorkflow
from az_permit_radar.application.opportunity_matching import ExplainableMatchGenerator, OpportunityGenerator
from az_permit_radar.application.parsing import SourceParserPipeline
from az_permit_radar.application.processing import AuthoritativeBatchParser, EndToEndPermitProcessingWorkflow, ProcessingOutcome, ProcessingRunStatus, ProcessingStage
from az_permit_radar.domain.customer import CustomerAccount, CustomerTradePreference, NotificationPreference, ServiceTerritory
from az_permit_radar.domain.deduplication import ManualDuplicateDecision
from az_permit_radar.domain.errors import ConcurrencyConflict
from az_permit_radar.domain.ingestion import ImportBatchStatus, RetryDisposition
from az_permit_radar.domain.notification import NotificationChannel
from az_permit_radar.domain.source_registry import AccessReviewStatus, AcquisitionMethod, AuthenticationRequirement, EndpointConfiguration, Jurisdiction, SourceFileType, SourceHealthStatus, SourceProfile
from az_permit_radar.domain.value_objects import CalendarDate, CustomerAccountId, EmailAddress, GeographicCoordinates, IdempotencyKey, JurisdictionId, SourceId, TradeTagId
from az_permit_radar.infrastructure.opportunity_matching import InMemoryOpportunityMatchStore, InMemoryOpportunityStore, load_projection_policy, load_publication_eligibility_policy, load_score_policy
from az_permit_radar.infrastructure.permit_classification import InMemoryClassificationState, SchemaConstrainedAIClassifier, VersionedPermitRuleEngine
from az_permit_radar.infrastructure.permit_normalization import ArizonaPermitRecordNormalizer, InMemoryJurisdictionResolver, InMemoryNormalizationLogger, InMemoryNormalizationMetrics, InMemoryNormalizationUnitOfWork, NullGeocoder
from az_permit_radar.infrastructure.processing import InMemoryProcessingRunStore, InMemoryProcessingTraceLogger, load_processing_consistency_policy
from az_permit_radar.infrastructure.source_acquisition import FakeConnector, FileSystemImmutableArtifactStore, InMemoryAcquisitionLogger, InMemoryAcquisitionMetrics, InMemoryAcquisitionState
from az_permit_radar.infrastructure.source_parsing import FileSystemArtifactReader, InMemoryParsingLogger, InMemoryParsingMetrics, InMemoryRejectionReporter, InMemorySourceRecordRepository, tucson_fixture_parser_definition
from tests.support import LATER, NOW


SOURCE_ID = SourceId("source-e2e")
JURISDICTION_ID = JurisdictionId("jurisdiction-tucson")
EVALUATED = CalendarDate.from_iso("2026-07-20")


def profile() -> SourceProfile:
    return SourceProfile(
        source_id=SOURCE_ID,
        jurisdiction_id=JURISDICTION_ID,
        jurisdiction="City of Tucson",
        source_name="Synthetic end-to-end fixture",
        acquisition_method=AcquisitionMethod.FILE_DOWNLOAD,
        endpoint=EndpointConfiguration("https://example.test/e2e.csv"),
        file_type=SourceFileType("text/csv", ".csv"),
        schedule="0 6 * * *",
        time_zone="America/Phoenix",
        authentication_requirement=AuthenticationRequirement.NONE,
        parser_identifier="synthetic-tucson-permit-csv",
        parser_version="1.1.0",
        expected_date_fields=("issued_date",),
        expected_unique_identifiers=("permit_number",),
        historical_availability="synthetic fixture only",
        known_limitations=("not production data",),
        enabled=True,
        health_status=SourceHealthStatus.UNKNOWN,
        access_review_status=AccessReviewStatus.APPROVED,
        operational_owner="test-operations",
    )


def request_policy(*, attempts: int = 1) -> RequestPolicy:
    return RequestPolicy(
        user_agent="AZPermitRadar/0.1 (+operations@example.test)",
        timeout_seconds=5,
        max_requests_per_run=attempts,
        max_response_bytes=100_000,
        retry=RetryPolicy(max_attempts=attempts, initial_backoff_seconds=0),
    )


def raw(content: bytes) -> RawAcquisition:
    return RawAcquisition(
        content,
        "text/csv",
        "https://example.test/e2e.csv",
        NOW,
        status_code=200,
    )


def customer(value: str) -> CustomerAccount:
    account = CustomerAccount(CustomerAccountId(value), f"Business {value}", NOW)
    account.set_trade_preference(CustomerTradePreference(TradeTagId("trade-electrical")), NOW)
    account.set_service_territory(ServiceTerritory(jurisdiction_ids=frozenset({JURISDICTION_ID})), NOW)
    account.set_notification_preference(
        NotificationPreference(NotificationChannel.EMAIL, True, EmailAddress(f"{value}@example.com"), NOW, "consent-e2e"),
        NOW,
    )
    return account


THREE_RECORDS = b"""Permit Number,Issued Date,Valuation,Address,Description,Jurisdiction,Latitude,Longitude
E2E-001,2026-07-16,"$12,500.00","100 W Congress St, Tucson, AZ 85701",Electrical service upgrade,Tucson,32.2217,-110.9265
E2E-002,2026-07-17,,"200 E Broadway Blvd, Tucson, AZ 85701",Electrical interior remodel,Tucson,32.2220,-110.9250
E2E-003,2026-07-18,"$55,000.00","300 N Stone Ave, Tucson, AZ 85701",Electrical panel replacement,Tucson,32.2230,-110.9240
"""


class EndToEndHarness:
    def __init__(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.state = InMemoryAcquisitionState((profile(),))
        self.acquisition_logs = InMemoryAcquisitionLogger()
        self.acquisition = ScheduledAcquisitionWorkflow(
            state=self.state,
            artifact_store=FileSystemImmutableArtifactStore(self.root / "artifacts"),
            logger=self.acquisition_logs,
            metrics=InMemoryAcquisitionMetrics(),
            now=lambda: NOW,
            sleep=lambda _seconds: None,
            monotonic=lambda: 1.0,
        )
        self.source_records = InMemorySourceRecordRepository()
        self.parser_pipeline = SourceParserPipeline(
            definition=tucson_fixture_parser_definition(parser_version="1.1.0"),
            artifact_reader=FileSystemArtifactReader(self.root / "artifacts"),
            source_records=self.source_records,
            rejection_reporter=InMemoryRejectionReporter(),
            logger=InMemoryParsingLogger(),
            metrics=InMemoryParsingMetrics(),
            now=lambda: NOW,
        )
        self.batch_parser = AuthoritativeBatchParser(self.state, self.source_records, now=lambda: NOW)
        self.normalization_state = InMemoryNormalizationUnitOfWork()
        self.normalization = PermitNormalizationWorkflow(
            normalizer=ArizonaPermitRecordNormalizer(),
            jurisdictions=InMemoryJurisdictionResolver(
                {SOURCE_ID: Jurisdiction(JURISDICTION_ID, "City of Tucson", "AZ")},
                {JURISDICTION_ID: ("Tucson",)},
            ),
            geocoder=NullGeocoder(),
            permits=self.normalization_state.permits,
            duplicate_candidates=self.normalization_state.duplicate_candidates,
            reviews=self.normalization_state.reviews,
            unit_of_work=self.normalization_state,
            logger=InMemoryNormalizationLogger(),
            metrics=InMemoryNormalizationMetrics(),
            now=lambda: NOW,
        )
        self.classifications = InMemoryClassificationState()
        self.classification = PermitClassificationService(
            VersionedPermitRuleEngine(),
            None,
            ClassificationPolicy(Decimal("0.60"), Decimal("0.80"), Decimal("0.80")),
            self.classifications,
        )
        self.opportunity_store = InMemoryOpportunityStore()
        self.match_store = InMemoryOpportunityMatchStore()
        eligibility = load_publication_eligibility_policy("docs/current/business-data-v1.7.json")
        self.opportunities = OpportunityGenerator(
            self.opportunity_store,
            eligibility,
            self.classifications,
            self.match_store,
            load_projection_policy("docs/current/business-data-v1.7.json"),
        )
        self.matches = ExplainableMatchGenerator(
            self.match_store,
            GeographyQueryService(),
            load_score_policy("docs/current/business-data-v1.7.json"),
            eligibility,
            self.classifications,
            self.opportunity_store,
        )
        self.run_store = InMemoryProcessingRunStore()
        self.trace_log = InMemoryProcessingTraceLogger()
        self.workflow = EndToEndPermitProcessingWorkflow(
            acquisition=self.acquisition,
            acquisition_state=self.state,
            parser=self.batch_parser,
            parser_pipeline=self.parser_pipeline,
            source_records=self.source_records,
            normalization=self.normalization,
            classification=self.classification,
            opportunities=self.opportunities,
            matches=self.matches,
            policy=load_processing_consistency_policy("docs/current/business-data-v1.7.json"),
            run_store=self.run_store,
            logger=self.trace_log,
            now=lambda: NOW,
        )

    def replace_classification(self, service: PermitClassificationService) -> None:
        self.classification = service
        self.workflow = EndToEndPermitProcessingWorkflow(
            acquisition=self.acquisition,
            acquisition_state=self.state,
            parser=self.batch_parser,
            parser_pipeline=self.parser_pipeline,
            source_records=self.source_records,
            normalization=self.normalization,
            classification=self.classification,
            opportunities=self.opportunities,
            matches=self.matches,
            policy=load_processing_consistency_policy("docs/current/business-data-v1.7.json"),
            run_store=self.run_store,
            logger=self.trace_log,
            now=lambda: NOW,
        )

    def close(self) -> None:
        self.temporary.cleanup()

    def command(self, content: bytes, correlation: str, *, when=NOW, customers=None):
        job = self.acquisition.create_scheduled_job(source_id=SOURCE_ID, scheduled_for=when)
        connector = FakeConnector(method=AcquisitionMethod.FILE_DOWNLOAD, outcomes=(raw(content),))
        result = self.workflow.run(
            correlation_id=correlation,
            acquisition_job_id=job.acquisition_job_id,
            connector=connector,
            policy=request_policy(),
            customers=customers or (customer("customer-a"),),
            evaluated_on=EVALUATED,
        )
        return result, connector


class EndToEndProcessingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.harness = EndToEndHarness()

    def tearDown(self) -> None:
        self.harness.close()

    def test_three_records_trace_continuously_to_two_customer_matches(self):
        result, _ = self.harness.command(
            THREE_RECORDS,
            "correlation-success",
            customers=(customer("customer-a"), customer("customer-b")),
        )
        self.assertEqual(result.status, ProcessingRunStatus.COMPLETED)
        self.assertEqual(len(result.records), 3)
        self.assertTrue(all(item.outcome is ProcessingOutcome.MATCH_CREATED for item in result.records))
        self.assertTrue(all(len(item.match_ids) == 2 for item in result.records))
        self.assertEqual(len(self.harness.match_store.items), 6)
        self.assertEqual(self.harness.state.processing_batch_ids, ())
        self.assertEqual(self.harness.state.get_batch(result.import_batch_id).status, ImportBatchStatus.COMPLETED)
        self.assertTrue(all(entry.correlation_id == result.correlation_id for entry in self.harness.trace_log.entries))
        matching_entries = [entry for entry in self.harness.trace_log.entries if entry.stage is ProcessingStage.MATCHING]
        self.assertTrue(all(entry.source_id and entry.artifact_id and entry.artifact_hash and entry.import_batch_id and entry.source_record_id and entry.permit_id and entry.classification_result_id and entry.opportunity_id and entry.match_id for entry in matching_entries))
        missing_value = next(permit for permit in self.harness.normalization_state.permits.permits if permit.permit_number == "E2E-002")
        self.assertIsNone(missing_value.valuation)

    def test_malformed_row_produces_partially_failed_authoritative_batch(self):
        content = THREE_RECORDS + b"?,2026-07-18,$100,Unknown,Electrical,Tucson,32.22,-110.92\n"
        result, _ = self.harness.command(content, "correlation-partial")
        self.assertEqual(result.status, ProcessingRunStatus.PARTIALLY_FAILED)
        self.assertEqual(sum(item.outcome is ProcessingOutcome.FAILED for item in result.records), 1)
        batch = self.harness.state.get_batch(result.import_batch_id)
        self.assertEqual(batch.status, ImportBatchStatus.PARTIALLY_FAILED)
        self.assertEqual(self.harness.state.processing_batch_ids, ())

    def test_unusable_artifact_fails_authoritative_batch_and_acknowledges_queue(self):
        result, _ = self.harness.command(
            b"wrong,column\nx,y\n",
            "correlation-unusable-artifact",
        )
        self.assertEqual(result.status, ProcessingRunStatus.FAILED)
        self.assertEqual(result.failure_stage, ProcessingStage.PARSING)
        batch = self.harness.state.get_batch(result.import_batch_id)
        self.assertEqual(batch.status, ImportBatchStatus.FAILED)
        self.assertEqual(batch.retry_disposition, RetryDisposition.TERMINAL)
        self.assertEqual(batch.failure_category, "format")
        self.assertEqual(self.harness.state.processing_batch_ids, ())
        self.assertEqual(self.harness.source_records.records, ())

    def test_injected_normalization_failure_rolls_back_all_normalized_state(self):
        self.harness.normalization_state.fail_next_commit = True
        result, _ = self.harness.command(THREE_RECORDS.splitlines(keepends=True)[0] + THREE_RECORDS.splitlines(keepends=True)[1], "correlation-rollback")
        self.assertEqual(result.status, ProcessingRunStatus.FAILED)
        self.assertEqual(result.records[0].final_stage, ProcessingStage.NORMALIZATION)
        self.assertEqual(self.harness.normalization_state.permits.permits, ())
        self.assertEqual(self.harness.normalization_state.duplicate_candidates.candidates, ())
        self.assertEqual(self.harness.normalization_state.reviews.tasks, {})

    def test_repeated_end_to_end_command_is_a_noop(self):
        job = self.harness.acquisition.create_scheduled_job(source_id=SOURCE_ID, scheduled_for=NOW)
        connector = FakeConnector(method=AcquisitionMethod.FILE_DOWNLOAD, outcomes=(raw(THREE_RECORDS),))
        arguments = dict(
            correlation_id="correlation-replay",
            acquisition_job_id=job.acquisition_job_id,
            connector=connector,
            policy=request_policy(),
            customers=(customer("customer-a"),),
            evaluated_on=EVALUATED,
        )
        first = self.harness.workflow.run(**arguments)
        counts = (len(self.harness.source_records.records), len(self.harness.opportunity_store.items), len(self.harness.match_store.items), len(self.harness.trace_log.entries))
        replay = self.harness.workflow.run(**arguments)
        self.assertEqual(first, replay)
        self.assertEqual(len(connector.calls), 1)
        self.assertEqual(counts, (len(self.harness.source_records.records), len(self.harness.opportunity_store.items), len(self.harness.match_store.items), len(self.harness.trace_log.entries)))

    def test_address_and_low_confidence_records_end_in_explicit_review_traces(self):
        address_content = b"""Permit Number,Issued Date,Valuation,Address,Description,Jurisdiction
E2E-ADDRESS,2026-07-16,$1000,Unresolved site near parcel 123,Electrical service upgrade,Tucson
"""
        address_result, _ = self.harness.command(address_content, "correlation-address-review")
        self.assertEqual(address_result.records[0].outcome, ProcessingOutcome.REVIEW_REQUIRED)
        self.assertEqual(address_result.records[0].final_stage, ProcessingStage.GEOCODING)
        self.assertTrue(address_result.records[0].review_task_ids)

        low_confidence_state = InMemoryClassificationState()
        ai = SchemaConstrainedAIClassifier(
            lambda _: {"assertions": [{"tag": "low_voltage", "value": True, "confidence": "0.70", "evidence": "ambiguous controls"}]},
            provider="fixture",
            model_version="1",
            classifier_version="1",
        )
        self.harness.replace_classification(PermitClassificationService(
            VersionedPermitRuleEngine(),
            ai,
            ClassificationPolicy(Decimal("0.60"), Decimal("0.80"), Decimal("0.80")),
            low_confidence_state,
        ))
        header = THREE_RECORDS.splitlines(keepends=True)[0]
        low_content = header + b'E2E-LOW,2026-07-16,$1000,"600 E 22nd St, Tucson, AZ 85713",Electrical unusual controls,Tucson,32.2050,-110.9500\n'
        low_result, _ = self.harness.command(low_content, "correlation-low-confidence", when=LATER)
        self.assertEqual(low_result.records[0].outcome, ProcessingOutcome.REVIEW_REQUIRED)
        self.assertEqual(low_result.records[0].final_stage, ProcessingStage.REVIEW_REQUIREMENT)
        self.assertTrue(low_result.records[0].review_task_ids)
        self.assertTrue(any(entry.stage is ProcessingStage.REVIEW_REQUIREMENT for entry in self.harness.trace_log.entries))

    def test_probable_then_superseded_duplicate_replay_has_one_active_outcome(self):
        content = b"""Permit Number,Issued Date,Valuation,Address,Description,Jurisdiction,Latitude,Longitude
E2E-DUP-A,2026-07-16,$1000,"700 E Broadway Blvd, Tucson, AZ 85719",Electrical upgrade,Tucson,32.2217,-110.9265
E2E-DUP-B,2026-07-16,$1000,"700 East Broadway Boulevard, Tucson, AZ 85719",Electrical upgrade,Tucson,32.2217,-110.9265
"""
        first, _ = self.harness.command(content, "correlation-probable-duplicate")
        self.assertEqual(first.records[0].outcome, ProcessingOutcome.MATCH_CREATED)
        self.assertEqual(first.records[1].outcome, ProcessingOutcome.REVIEW_REQUIRED)
        candidate = self.harness.normalization_state.duplicate_candidates.candidates[0]
        self.harness.normalization.decide_duplicate(
            candidate.candidate_id,
            decision=ManualDuplicateDecision.MERGE,
            actor_id="reviewer-e2e",
            rationale="same municipal Permit",
        )
        superseded = self.harness.normalization_state.permits.get(candidate.permit_id)
        self.assertEqual(superseded.status.value, "superseded")

        reprocess_job = self.harness.acquisition.create_manual_reprocessing_job(
            artifact_id=first.artifact_id,
            requested_at=LATER,
            idempotency_key=IdempotencyKey("reprocess-superseded-duplicate"),
        )
        replay = self.harness.workflow.run(
            correlation_id="correlation-superseded-replay",
            acquisition_job_id=reprocess_job.acquisition_job_id,
            policy=request_policy(),
            customers=(customer("customer-a"),),
            evaluated_on=EVALUATED,
        )
        self.assertEqual(replay.status, ProcessingRunStatus.COMPLETED)
        self.assertEqual(len(self.harness.opportunity_store.items), 1)
        self.assertEqual(len(self.harness.match_store.items), 1)

    def test_exact_radius_boundary_is_included_in_continuous_trace(self):
        origin = GeographicCoordinates(Decimal("32.1217"), Decimal("-110.9265"))
        destination = GeographicCoordinates(Decimal("32.2217"), Decimal("-110.9265"))
        measured = _haversine_km(
            str(origin.latitude), str(origin.longitude),
            str(destination.latitude), str(destination.longitude),
        )
        boundary_customer = customer("boundary")
        boundary_customer.set_service_territory(
            ServiceTerritory(
                radius_center=origin,
                radius_km=measured,
                origin_coordinates_validated=True,
            ),
            NOW,
        )
        header = THREE_RECORDS.splitlines(keepends=True)[0]
        content = header + b'E2E-BOUNDARY,2026-07-16,$1000,"800 E Broadway Blvd, Tucson, AZ 85719",Electrical upgrade,Tucson,32.2217,-110.9265\n'
        result, _ = self.harness.command(content, "correlation-radius-boundary", customers=(boundary_customer,))
        self.assertEqual(result.records[0].outcome, ProcessingOutcome.MATCH_CREATED)
        match = next(iter(self.harness.match_store.items.values()))
        territory = match.explanation.territory_evaluation_snapshot
        self.assertEqual(territory.distance, measured)
        self.assertEqual(territory.distance_unit, "km")

    def test_retryable_acquisition_failure_then_success_is_observable(self):
        job = self.harness.acquisition.create_scheduled_job(source_id=SOURCE_ID, scheduled_for=NOW)
        connector = FakeConnector(
            method=AcquisitionMethod.FILE_DOWNLOAD,
            outcomes=(
                AcquisitionError(AcquisitionFailureCategory.TIMEOUT, "fixture timeout", retryable=True),
                raw(THREE_RECORDS),
            ),
        )
        result = self.harness.workflow.run(
            correlation_id="correlation-retry",
            acquisition_job_id=job.acquisition_job_id,
            connector=connector,
            policy=request_policy(attempts=2),
            customers=(customer("customer-a"),),
            evaluated_on=EVALUATED,
        )
        self.assertEqual(result.status, ProcessingRunStatus.COMPLETED)
        self.assertEqual(len(connector.calls), 2)
        self.assertTrue(any(entry.outcome == "retrying" for entry in self.harness.acquisition_logs.entries))

    def test_concurrent_same_command_and_processing_claim_do_not_duplicate_outcomes(self):
        job = self.harness.acquisition.create_scheduled_job(source_id=SOURCE_ID, scheduled_for=NOW)
        connector = FakeConnector(method=AcquisitionMethod.FILE_DOWNLOAD, outcomes=(raw(THREE_RECORDS),))
        results = []
        failures = []
        def run():
            try:
                results.append(self.harness.workflow.run(
                    correlation_id="correlation-concurrent",
                    acquisition_job_id=job.acquisition_job_id,
                    connector=connector,
                    policy=request_policy(),
                    customers=(customer("customer-a"),),
                    evaluated_on=EVALUATED,
                ))
            except BaseException as error:
                failures.append(error)
        threads = [threading.Thread(target=run) for _ in range(2)]
        for thread in threads: thread.start()
        for thread in threads: thread.join(timeout=5)
        self.assertEqual(failures, [])
        self.assertEqual(results[0], results[1])
        self.assertEqual(len(connector.calls), 1)
        self.assertEqual(len(self.harness.opportunity_store.items), 3)
        self.assertEqual(len(self.harness.match_store.items), 3)

        next_job = self.harness.acquisition.create_scheduled_job(source_id=SOURCE_ID, scheduled_for=LATER)
        acquired = self.harness.acquisition.run_job(job_id=next_job.acquisition_job_id, connector=FakeConnector(method=AcquisitionMethod.FILE_DOWNLOAD, outcomes=(raw(THREE_RECORDS + b"\n"),)), policy=request_policy())
        self.harness.state.claim_processing(acquired.batch.import_batch_id, "claim-one")
        with self.assertRaises(ConcurrencyConflict):
            self.harness.state.claim_processing(acquired.batch.import_batch_id, "claim-two")

    def test_corrected_replay_advances_projection_without_duplicate_active_match(self):
        header = THREE_RECORDS.splitlines(keepends=True)[0]
        before = header + b'E2E-CORRECT,2026-07-16,"$12,500.00","500 E 22nd St, Tucson, AZ 85713",Electrical service upgrade,Tucson,32.2050,-110.9600\n'
        after = header + b'E2E-CORRECT,2026-07-16,"$550,000.00","500 E 22nd St, Tucson, AZ 85713",Corrected electrical service upgrade,Tucson,32.2050,-110.9600\n'
        first, _ = self.harness.command(before, "correlation-before", when=NOW)
        second, _ = self.harness.command(after, "correlation-after", when=LATER)
        self.assertEqual(first.status, ProcessingRunStatus.COMPLETED)
        self.assertEqual(second.status, ProcessingRunStatus.COMPLETED)
        self.assertEqual(len(self.harness.opportunity_store.items), 1)
        self.assertEqual(len(self.harness.match_store.items), 1)
        opportunity = next(iter(self.harness.opportunity_store.items.values()))
        match = next(iter(self.harness.match_store.items.values()))
        self.assertEqual(opportunity.projection_revision, 2)
        self.assertEqual(len(opportunity.projection_history), 1)
        self.assertEqual(match.explanation.opportunity_revision, 2)
        self.assertEqual(len(match.score_history), 1)


if __name__ == "__main__":
    unittest.main()
