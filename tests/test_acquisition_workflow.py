import json
import tempfile
import threading
import unittest
from pathlib import Path

from az_permit_radar.application.acquisition import (
    AcquisitionError,
    AcquisitionFailureCategory,
    RawAcquisition,
    RequestPolicy,
    RetryPolicy,
    ScheduledAcquisitionWorkflow,
)
from az_permit_radar.domain.acquisition import (
    AcquisitionJobStatus,
    AcquisitionOutcome,
)
from az_permit_radar.domain.errors import ConcurrencyConflict
from az_permit_radar.domain.events import ArtifactAcquired
from az_permit_radar.domain.ingestion import ImportBatchStatus
from az_permit_radar.domain.source_registry import (
    AccessReviewStatus,
    AcquisitionMethod,
    AuthenticationRequirement,
    EndpointConfiguration,
    SourceFileType,
    SourceHealthStatus,
    SourceProfile,
)
from az_permit_radar.domain.value_objects import (
    IdempotencyKey,
    JurisdictionId,
    SourceId,
)
from az_permit_radar.infrastructure.source_acquisition import (
    FakeConnector,
    FileSystemImmutableArtifactStore,
    InMemoryAcquisitionLogger,
    InMemoryAcquisitionMetrics,
    InMemoryAcquisitionState,
)

from tests.support import LATER, NOW


def source_profile(*, enabled: bool = True) -> SourceProfile:
    return SourceProfile(
        source_id=SourceId("source-workflow"),
        jurisdiction_id=JurisdictionId("jurisdiction-tucson"),
        jurisdiction="City of Tucson",
        source_name="Synthetic scheduled export",
        acquisition_method=AcquisitionMethod.FILE_DOWNLOAD,
        endpoint=EndpointConfiguration("https://example.test/permits.csv"),
        file_type=SourceFileType("text/csv", ".csv"),
        schedule="0 6 * * *",
        time_zone="America/Phoenix",
        authentication_requirement=AuthenticationRequirement.NONE,
        parser_identifier="synthetic-csv",
        parser_version="1.0.0",
        expected_date_fields=("issued_date",),
        expected_unique_identifiers=("permit_number",),
        historical_availability="synthetic test history",
        known_limitations=("not production data",),
        enabled=enabled,
        health_status=(SourceHealthStatus.UNKNOWN if enabled else SourceHealthStatus.DISABLED),
        access_review_status=AccessReviewStatus.APPROVED,
        operational_owner="test-operations",
    )


def policy(*, attempts: int = 1, request_limit: int = 3) -> RequestPolicy:
    return RequestPolicy(
        user_agent="AZPermitRadar/0.1 (+operations@example.test)",
        timeout_seconds=5,
        max_requests_per_run=request_limit,
        max_response_bytes=10_000,
        retry=RetryPolicy(max_attempts=attempts, initial_backoff_seconds=0),
    )


def raw(content: bytes = b"permit_number,issued_date\nT26-1,2026-07-16\n") -> RawAcquisition:
    return RawAcquisition(
        content=content,
        media_type="text/csv",
        source_reference="https://example.test/permits.csv",
        acquired_at=NOW,
        metadata=(("request-id", "request-001"),),
        status_code=200,
        etag='"fixture-v1"',
        last_modified="Fri, 17 Jul 2026 12:00:00 GMT",
    )


class FailingArtifactStore:
    def put(self, **kwargs: object) -> object:
        del kwargs
        raise OSError("synthetic storage failure")


class CountingArtifactStore:
    def __init__(self, delegate: FileSystemImmutableArtifactStore) -> None:
        self._delegate = delegate
        self.calls = 0

    def put(self, **kwargs: object) -> object:
        self.calls += 1
        return self._delegate.put(**kwargs)  # type: ignore[arg-type]


class BarrierConnector:
    method = AcquisitionMethod.FILE_DOWNLOAD

    def __init__(self, barrier: threading.Barrier, response: RawAcquisition) -> None:
        self._barrier = barrier
        self._response = response

    def download_file(self, request: object) -> RawAcquisition:
        del request
        self._barrier.wait(timeout=5)
        return self._response


class BlockingConnector:
    method = AcquisitionMethod.FILE_DOWNLOAD

    def __init__(self, entered: threading.Event, release: threading.Event) -> None:
        self._entered = entered
        self._release = release

    def download_file(self, request: object) -> RawAcquisition:
        del request
        self._entered.set()
        if not self._release.wait(timeout=5):
            raise AssertionError("blocking connector was not released")
        return raw()


class AcquisitionWorkflowTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.state = InMemoryAcquisitionState((source_profile(),))
        self.logs = InMemoryAcquisitionLogger()
        self.metrics = InMemoryAcquisitionMetrics()
        self.store = CountingArtifactStore(
            FileSystemImmutableArtifactStore(self.root / "artifacts")
        )
        self.workflow = ScheduledAcquisitionWorkflow(
            state=self.state,
            artifact_store=self.store,  # type: ignore[arg-type]
            logger=self.logs,
            metrics=self.metrics,
            now=lambda: NOW,
            sleep=lambda _seconds: None,
            monotonic=lambda: 1.0,
        )

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_successful_scheduled_acquisition_archives_and_enqueues_once(self) -> None:
        job = self.workflow.create_scheduled_job(
            source_id=SourceId("source-workflow"),
            scheduled_for=NOW,
        )
        same_job = self.workflow.create_scheduled_job(
            source_id=SourceId("source-workflow"),
            scheduled_for=NOW,
        )
        self.assertEqual(job.acquisition_job_id, same_job.acquisition_job_id)
        connector = FakeConnector(method=AcquisitionMethod.FILE_DOWNLOAD, outcomes=(raw(),))

        execution = self.workflow.run_job(
            job_id=job.acquisition_job_id,
            connector=connector,
            policy=policy(),
        )

        self.assertEqual(execution.record.outcome, AcquisitionOutcome.ARCHIVED)
        self.assertEqual(execution.batch.status, ImportBatchStatus.ACQUIRED)
        self.assertTrue(execution.processing_enqueued)
        self.assertEqual(self.state.processing_batch_ids, (execution.batch.import_batch_id,))
        self.assertTrue(any(isinstance(event, ArtifactAcquired) for event in self.state.outbox_events))
        self.assertEqual(execution.artifact.response_metadata.status_code, 200)  # type: ignore[union-attr]
        self.assertEqual(execution.artifact.response_metadata.etag, '"fixture-v1"')  # type: ignore[union-attr]
        stored_job = self.state.get_job(job.acquisition_job_id)
        self.assertEqual(stored_job.status, AcquisitionJobStatus.ARCHIVED)  # type: ignore[union-attr]
        profile = self.state.get(SourceId("source-workflow"))
        self.assertEqual(profile.health_status, SourceHealthStatus.HEALTHY)  # type: ignore[union-attr]
        self.assertEqual(profile.last_successful_acquisition, NOW)  # type: ignore[union-attr]
        self.assertEqual(
            self.metrics.counters[
                ("acquisition_jobs_completed_total", (("outcome", "archived"),))
            ],
            1,
        )

    def test_exact_duplicate_creates_terminal_batch_without_processing(self) -> None:
        first = self.workflow.create_scheduled_job(
            source_id=SourceId("source-workflow"), scheduled_for=NOW
        )
        second = self.workflow.create_scheduled_job(
            source_id=SourceId("source-workflow"), scheduled_for=LATER
        )
        first_execution = self.workflow.run_job(
            job_id=first.acquisition_job_id,
            connector=FakeConnector(method=AcquisitionMethod.FILE_DOWNLOAD, outcomes=(raw(),)),
            policy=policy(),
        )
        second_execution = self.workflow.run_job(
            job_id=second.acquisition_job_id,
            connector=FakeConnector(method=AcquisitionMethod.FILE_DOWNLOAD, outcomes=(raw(),)),
            policy=policy(),
        )

        self.assertEqual(second_execution.record.outcome, AcquisitionOutcome.DUPLICATE)
        self.assertEqual(second_execution.batch.status, ImportBatchStatus.DUPLICATE)
        self.assertEqual(
            second_execution.batch.duplicate_of_artifact_id,
            first_execution.record.artifact_id,
        )
        self.assertFalse(second_execution.processing_enqueued)
        self.assertEqual(self.store.calls, 1)
        self.assertEqual(
            self.metrics.counters[
                ("acquisition_jobs_completed_total", (("outcome", "duplicate"),))
            ],
            1,
        )
        self.assertEqual(self.state.processing_batch_ids, (first_execution.batch.import_batch_id,))
        acquired_events = [
            event for event in self.state.outbox_events if isinstance(event, ArtifactAcquired)
        ]
        self.assertEqual(len(acquired_events), 1)

    def test_changed_content_creates_new_artifact_and_processing_batch(self) -> None:
        jobs = [
            self.workflow.create_scheduled_job(
                source_id=SourceId("source-workflow"), scheduled_for=scheduled
            )
            for scheduled in (NOW, LATER)
        ]
        executions = [
            self.workflow.run_job(
                job_id=jobs[0].acquisition_job_id,
                connector=FakeConnector(
                    method=AcquisitionMethod.FILE_DOWNLOAD, outcomes=(raw(b"first"),)
                ),
                policy=policy(),
            ),
            self.workflow.run_job(
                job_id=jobs[1].acquisition_job_id,
                connector=FakeConnector(
                    method=AcquisitionMethod.FILE_DOWNLOAD, outcomes=(raw(b"changed"),)
                ),
                policy=policy(),
            ),
        ]
        self.assertEqual(
            [execution.record.outcome for execution in executions],
            [AcquisitionOutcome.ARCHIVED, AcquisitionOutcome.ARCHIVED],
        )
        self.assertNotEqual(executions[0].record.artifact_id, executions[1].record.artifact_id)
        self.assertEqual(len(self.state.processing_batch_ids), 2)

    def test_timeout_fails_job_batch_updates_health_and_is_observable(self) -> None:
        job = self.workflow.create_scheduled_job(
            source_id=SourceId("source-workflow"), scheduled_for=NOW
        )
        timeout = AcquisitionError(
            AcquisitionFailureCategory.TIMEOUT,
            "source request timed out",
            retryable=True,
        )
        with self.assertRaises(AcquisitionError) as raised:
            self.workflow.run_job(
                job_id=job.acquisition_job_id,
                connector=FakeConnector(
                    method=AcquisitionMethod.FILE_DOWNLOAD,
                    outcomes=(timeout,),
                ),
                policy=policy(attempts=1),
            )
        self.assertEqual(raised.exception.category, AcquisitionFailureCategory.TIMEOUT)
        result = self.state.get_result(job.acquisition_job_id)
        self.assertEqual(result.outcome, AcquisitionOutcome.FAILED)  # type: ignore[union-attr]
        batch = self.state.get_batch(result.import_batch_id)  # type: ignore[union-attr]
        self.assertEqual(batch.status, ImportBatchStatus.FAILED)  # type: ignore[union-attr]
        profile = self.state.get(SourceId("source-workflow"))
        self.assertEqual(profile.health_status, SourceHealthStatus.FAILING)  # type: ignore[union-attr]
        self.assertTrue(any(entry.failure_category == "timeout" for entry in self.logs.entries))
        self.assertEqual(
            self.metrics.counters[("acquisition_failures_total", (("category", "timeout"),))],
            1,
        )

    def test_invalid_content_is_not_stored_or_processed(self) -> None:
        job = self.workflow.create_scheduled_job(
            source_id=SourceId("source-workflow"), scheduled_for=NOW
        )
        invalid = RawAcquisition(
            b"<html>not a CSV export</html>",
            "text/html",
            "https://example.test/error",
            NOW,
            status_code=200,
        )
        with self.assertRaises(AcquisitionError) as raised:
            self.workflow.run_job(
                job_id=job.acquisition_job_id,
                connector=FakeConnector(
                    method=AcquisitionMethod.FILE_DOWNLOAD,
                    outcomes=(invalid,),
                ),
                policy=policy(),
            )
        self.assertEqual(raised.exception.category, AcquisitionFailureCategory.INVALID_CONTENT)
        result = self.state.get_result(job.acquisition_job_id)
        self.assertEqual(result.response_metadata.content_type, "text/html")  # type: ignore[union-attr]
        self.assertIsNotNone(result.content_digest)  # type: ignore[union-attr]
        self.assertEqual(self.state.processing_batch_ids, ())
        self.assertFalse((self.root / "artifacts").exists())

    def test_storage_failure_records_failed_job_and_batch(self) -> None:
        workflow = ScheduledAcquisitionWorkflow(
            state=self.state,
            artifact_store=FailingArtifactStore(),  # type: ignore[arg-type]
            logger=self.logs,
            metrics=self.metrics,
            now=lambda: NOW,
            monotonic=lambda: 1.0,
        )
        job = workflow.create_scheduled_job(
            source_id=SourceId("source-workflow"), scheduled_for=NOW
        )
        with self.assertRaises(AcquisitionError) as raised:
            workflow.run_job(
                job_id=job.acquisition_job_id,
                connector=FakeConnector(method=AcquisitionMethod.FILE_DOWNLOAD, outcomes=(raw(),)),
                policy=policy(),
            )
        self.assertEqual(raised.exception.category, AcquisitionFailureCategory.ARTIFACT_STORAGE)
        result = self.state.get_result(job.acquisition_job_id)
        self.assertEqual(result.failure_category, "artifact_storage")  # type: ignore[union-attr]
        self.assertEqual(self.state.processing_batch_ids, ())

    def test_failed_job_can_be_retried_without_duplicate_processing(self) -> None:
        job = self.workflow.create_scheduled_job(
            source_id=SourceId("source-workflow"), scheduled_for=NOW
        )
        timeout = AcquisitionError(
            AcquisitionFailureCategory.TIMEOUT,
            "source request timed out",
            retryable=True,
        )
        with self.assertRaises(AcquisitionError):
            self.workflow.run_job(
                job_id=job.acquisition_job_id,
                connector=FakeConnector(
                    method=AcquisitionMethod.FILE_DOWNLOAD,
                    outcomes=(timeout,),
                ),
                policy=policy(attempts=1),
            )
        execution = self.workflow.run_job(
            job_id=job.acquisition_job_id,
            connector=FakeConnector(method=AcquisitionMethod.FILE_DOWNLOAD, outcomes=(raw(),)),
            policy=policy(),
        )
        self.assertEqual(execution.record.outcome, AcquisitionOutcome.ARCHIVED)
        self.assertEqual(execution.record.attempt, 2)
        results = self.state.list_results(job.acquisition_job_id)
        self.assertEqual(
            [result.outcome for result in results],
            [AcquisitionOutcome.FAILED, AcquisitionOutcome.ARCHIVED],
        )
        self.assertNotEqual(results[0].import_batch_id, results[1].import_batch_id)
        self.assertEqual(self.state.processing_batch_ids, (execution.batch.import_batch_id,))

    def test_concurrent_same_content_archives_once_and_marks_other_duplicate(self) -> None:
        jobs = [
            self.workflow.create_scheduled_job(
                source_id=SourceId("source-workflow"), scheduled_for=scheduled
            )
            for scheduled in (NOW, LATER)
        ]
        barrier = threading.Barrier(2)
        executions: list[object] = []
        failures: list[BaseException] = []

        def run(job_index: int) -> None:
            try:
                executions.append(
                    self.workflow.run_job(
                        job_id=jobs[job_index].acquisition_job_id,
                        connector=BarrierConnector(barrier, raw()),
                        policy=policy(),
                    )
                )
            except BaseException as error:  # test captures thread failures for assertion
                failures.append(error)

        threads = [threading.Thread(target=run, args=(index,)) for index in range(2)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=5)

        self.assertEqual(failures, [])
        outcomes = {execution.record.outcome for execution in executions}  # type: ignore[union-attr]
        self.assertEqual(outcomes, {AcquisitionOutcome.ARCHIVED, AcquisitionOutcome.DUPLICATE})
        self.assertEqual(len(self.state.processing_batch_ids), 1)
        self.assertEqual(
            len([event for event in self.state.outbox_events if isinstance(event, ArtifactAcquired)]),
            1,
        )

    def test_concurrent_claim_of_same_job_is_rejected_and_logged(self) -> None:
        job = self.workflow.create_scheduled_job(
            source_id=SourceId("source-workflow"), scheduled_for=NOW
        )
        entered = threading.Event()
        release = threading.Event()
        first_failures: list[BaseException] = []

        def run_first() -> None:
            try:
                self.workflow.run_job(
                    job_id=job.acquisition_job_id,
                    connector=BlockingConnector(entered, release),
                    policy=policy(),
                )
            except BaseException as error:
                first_failures.append(error)

        thread = threading.Thread(target=run_first)
        thread.start()
        self.assertTrue(entered.wait(timeout=5))
        with self.assertRaises(ConcurrencyConflict):
            self.workflow.run_job(
                job_id=job.acquisition_job_id,
                connector=FakeConnector(method=AcquisitionMethod.FILE_DOWNLOAD, outcomes=(raw(),)),
                policy=policy(),
            )
        release.set()
        thread.join(timeout=5)
        self.assertEqual(first_failures, [])
        self.assertTrue(any(entry.outcome == "concurrent" for entry in self.logs.entries))

    def test_disabled_source_creates_skipped_batch_without_fetch(self) -> None:
        self.state.save(source_profile(enabled=False))
        job = self.workflow.create_scheduled_job(
            source_id=SourceId("source-workflow"), scheduled_for=NOW
        )
        connector = FakeConnector(method=AcquisitionMethod.FILE_DOWNLOAD, outcomes=(raw(),))
        execution = self.workflow.run_job(
            job_id=job.acquisition_job_id,
            connector=connector,
            policy=policy(),
        )
        self.assertEqual(execution.record.outcome, AcquisitionOutcome.DISABLED)
        self.assertEqual(execution.batch.status, ImportBatchStatus.SKIPPED)
        self.assertEqual(connector.calls, [])
        self.assertEqual(self.state.processing_batch_ids, ())

    def test_manual_reprocessing_uses_archived_artifact_without_refetching(self) -> None:
        acquisition_job = self.workflow.create_scheduled_job(
            source_id=SourceId("source-workflow"), scheduled_for=NOW
        )
        acquired = self.workflow.run_job(
            job_id=acquisition_job.acquisition_job_id,
            connector=FakeConnector(method=AcquisitionMethod.FILE_DOWNLOAD, outcomes=(raw(),)),
            policy=policy(),
        )
        reprocessing_job = self.workflow.create_manual_reprocessing_job(
            artifact_id=acquired.record.artifact_id,  # type: ignore[arg-type]
            requested_at=LATER,
            idempotency_key=IdempotencyKey("manual-reprocess-001"),
        )
        reprocessed = self.workflow.run_job(
            job_id=reprocessing_job.acquisition_job_id,
            policy=policy(),
        )
        self.assertEqual(reprocessed.record.outcome, AcquisitionOutcome.REPROCESSED)
        self.assertEqual(reprocessed.batch.status, ImportBatchStatus.ACQUIRED)
        self.assertEqual(reprocessed.batch.reprocess_of_artifact_id, acquired.record.artifact_id)
        self.assertEqual(len(self.state.processing_batch_ids), 2)
        self.assertEqual(
            len([event for event in self.state.outbox_events if isinstance(event, ArtifactAcquired)]),
            1,
        )

    def test_completed_job_replay_is_idempotent_and_logs_exclude_configuration(self) -> None:
        job = self.workflow.create_scheduled_job(
            source_id=SourceId("source-workflow"), scheduled_for=NOW
        )
        connector = FakeConnector(method=AcquisitionMethod.FILE_DOWNLOAD, outcomes=(raw(),))
        first = self.workflow.run_job(
            job_id=job.acquisition_job_id,
            connector=connector,
            policy=policy(),
        )
        replayed = self.workflow.run_job(
            job_id=job.acquisition_job_id,
            connector=connector,
            policy=policy(),
        )
        self.assertEqual(first.record, replayed.record)
        self.assertEqual(len(connector.calls), 1)
        serialized_logs = json.dumps([entry.as_dict() for entry in self.logs.entries])
        self.assertNotIn("AZPermitRadar/0.1", serialized_logs)
        self.assertNotIn("https://example.test/permits.csv", serialized_logs)
        self.assertNotIn("request-id", serialized_logs)
        self.assertTrue(any(entry.outcome == "archived" for entry in self.logs.entries))


if __name__ == "__main__":
    unittest.main()
