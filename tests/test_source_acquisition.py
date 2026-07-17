import hashlib
import json
import tempfile
import unittest
from dataclasses import fields
from pathlib import Path

from az_permit_radar.application.acquisition import (
    AcquisitionCoordinator,
    AcquisitionError,
    AcquisitionFailureCategory,
    AcquisitionLogEntry,
    FileDownloadConnector,
    HtmlPageConnector,
    HttpApiConnector,
    ManuallyUploadedFileConnector,
    RawAcquisition,
    RequestPolicy,
    RetryPolicy,
)
from az_permit_radar.domain.errors import InvariantViolation
from az_permit_radar.domain.source_registry import (
    AccessReviewStatus,
    AcquisitionMethod,
    AuthenticationRequirement,
    EndpointConfiguration,
    SourceFileType,
    SourceHealthStatus,
    SourceProfile,
)
from az_permit_radar.domain.value_objects import ContentDigest, ImportBatchId, JurisdictionId, SourceId
from az_permit_radar.infrastructure.source_acquisition import (
    FakeConnector,
    FileSystemImmutableArtifactStore,
    InMemoryAcquisitionLogger,
    InMemorySourceProfileRegistry,
    JsonLinesAcquisitionLogger,
    ManualFixtureConnector,
)

from tests.support import LATER, NOW


FIXTURE_ROOT = Path(__file__).parent / "fixtures" / "manual"


def profile(
    *,
    method: AcquisitionMethod = AcquisitionMethod.FILE_DOWNLOAD,
    access_review: AccessReviewStatus = AccessReviewStatus.APPROVED,
) -> SourceProfile:
    return SourceProfile(
        source_id=SourceId("source-test"),
        jurisdiction_id=JurisdictionId("jurisdiction-tucson"),
        jurisdiction="City of Tucson",
        source_name="Test permit export",
        acquisition_method=method,
        endpoint=EndpointConfiguration(
            None if method is AcquisitionMethod.MANUAL_UPLOAD else "https://example.test/permits.csv"
        ),
        file_type=SourceFileType("text/csv", ".csv"),
        schedule="0 6 * * *",
        time_zone="America/Phoenix",
        authentication_requirement=AuthenticationRequirement.NONE,
        parser_identifier="tucson-csv",
        parser_version="1.0.0",
        expected_date_fields=("issued_date",),
        expected_unique_identifiers=("permit_number",),
        historical_availability="fixture covers one day",
        known_limitations=("test data only",),
        enabled=True,
        health_status=SourceHealthStatus.UNKNOWN,
        access_review_status=access_review,
        operational_owner="data-operations",
    )


def request_policy(**overrides: object) -> RequestPolicy:
    values: dict[str, object] = {
        "user_agent": "AZPermitRadar/0.1 (+operations@example.test)",
        "timeout_seconds": 5.0,
        "max_requests_per_run": 3,
        "max_response_bytes": 10_000,
        "retry": RetryPolicy(max_attempts=3, initial_backoff_seconds=0.1),
    }
    values.update(overrides)
    return RequestPolicy(**values)  # type: ignore[arg-type]


class SourceProfileTests(unittest.TestCase):
    def test_all_required_connector_interfaces_are_explicit(self) -> None:
        self.assertTrue(hasattr(FileDownloadConnector, "download_file"))
        self.assertTrue(hasattr(HttpApiConnector, "request_api"))
        self.assertTrue(hasattr(HtmlPageConnector, "fetch_page"))
        self.assertTrue(hasattr(ManuallyUploadedFileConnector, "read_uploaded_file"))

    def test_profile_supports_all_required_registry_fields(self) -> None:
        field_names = {field.name for field in fields(SourceProfile)}
        self.assertTrue(
            {
                "jurisdiction",
                "source_name",
                "acquisition_method",
                "endpoint",
                "file_type",
                "schedule",
                "time_zone",
                "authentication_requirement",
                "parser_identifier",
                "parser_version",
                "expected_date_fields",
                "expected_unique_identifiers",
                "historical_availability",
                "known_limitations",
                "enabled",
                "last_attempted_acquisition",
                "last_successful_acquisition",
                "health_status",
                "access_review_status",
                "operational_owner",
            }
            <= field_names
        )

    def test_network_profile_requires_an_endpoint(self) -> None:
        with self.assertRaises(InvariantViolation):
            SourceProfile(
                **{
                    **{
                        field.name: getattr(profile(), field.name)
                        for field in fields(SourceProfile)
                    },
                    "endpoint": EndpointConfiguration(),
                }
            )

    def test_endpoint_rejects_credentials_and_secret_headers(self) -> None:
        with self.assertRaises(InvariantViolation):
            EndpointConfiguration("https://user:password@example.test/permits")
        with self.assertRaises(InvariantViolation):
            EndpointConfiguration(
                "https://example.test/permits", headers=(("Authorization", "secret"),)
            )
        with self.assertRaises(InvariantViolation):
            EndpointConfiguration(
                "https://example.test/permits", query_parameters=(("api_key", "secret"),)
            )

    def test_registry_lists_profiles_deterministically(self) -> None:
        registry = InMemorySourceProfileRegistry((profile(),))
        self.assertEqual(registry.list_profiles(), (profile(),))

    def test_request_policy_requires_safe_explicit_limits_and_user_agent(self) -> None:
        with self.assertRaises(ValueError):
            request_policy(user_agent="")
        with self.assertRaises(ValueError):
            request_policy(user_agent="agent\r\nInjected: value")
        with self.assertRaises(ValueError):
            request_policy(timeout_seconds=0)
        with self.assertRaises(ValueError):
            request_policy(max_requests_per_run=0)
        with self.assertRaises(ValueError):
            RetryPolicy(max_attempts=0)


class AcquisitionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.registry = InMemorySourceProfileRegistry((profile(),))
        self.logs = InMemoryAcquisitionLogger()
        self.store = FileSystemImmutableArtifactStore(self.root / "artifacts")
        self.sleeps: list[float] = []
        self.coordinator = AcquisitionCoordinator(
            registry=self.registry,
            artifact_store=self.store,
            logger=self.logs,
            now=lambda: NOW,
            sleep=self.sleeps.append,
            monotonic=lambda: 1.0,
        )

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_fake_connector_archives_raw_bytes_with_checksum_and_policy(self) -> None:
        raw = RawAcquisition(b"raw,permit\n1,yes\n", "text/csv", "fake:test", NOW)
        connector = FakeConnector(method=AcquisitionMethod.FILE_DOWNLOAD, outcomes=(raw,))
        policy = request_policy()

        result = self.coordinator.acquire(
            source_id=SourceId("source-test"),
            import_batch_id=ImportBatchId("batch-test"),
            connector=connector,
            policy=policy,
        )

        expected = hashlib.sha256(raw.content).hexdigest()
        self.assertEqual(result.artifact.content_digest, ContentDigest("sha256", expected))
        self.assertEqual(Path(result.artifact.storage_reference.removeprefix("file://")).read_bytes(), raw.content)
        self.assertIs(connector.calls[0].policy, policy)
        self.assertTrue(result.artifact_created)
        self.assertEqual(self.logs.entries[-1].outcome, "succeeded")
        updated = self.registry.get(SourceId("source-test"))
        self.assertEqual(updated.last_successful_acquisition, NOW)  # type: ignore[union-attr]

    def test_same_bytes_are_idempotent_and_never_overwritten(self) -> None:
        raw = RawAcquisition(b"same bytes", "text/plain", "fake:test", NOW)
        connector = FakeConnector(method=AcquisitionMethod.FILE_DOWNLOAD, outcomes=(raw,))
        first = self.coordinator.acquire(
            source_id=SourceId("source-test"),
            import_batch_id=ImportBatchId("batch-one"),
            connector=connector,
            policy=request_policy(),
        )
        second = self.coordinator.acquire(
            source_id=SourceId("source-test"),
            import_batch_id=ImportBatchId("batch-two"),
            connector=connector,
            policy=request_policy(),
        )
        self.assertTrue(first.artifact_created)
        self.assertFalse(second.artifact_created)
        self.assertEqual(first.artifact.storage_reference, second.artifact.storage_reference)
        self.assertNotEqual(first.artifact.artifact_id, second.artifact.artifact_id)

    def test_retryable_failure_obeys_retry_and_request_limit(self) -> None:
        timeout = AcquisitionError(
            AcquisitionFailureCategory.TIMEOUT,
            "source request timed out",
            retryable=True,
        )
        raw = RawAcquisition(b"eventual success", "text/plain", "fake:test", NOW)
        connector = FakeConnector(
            method=AcquisitionMethod.FILE_DOWNLOAD,
            outcomes=(timeout, raw),
        )
        result = self.coordinator.acquire(
            source_id=SourceId("source-test"),
            import_batch_id=ImportBatchId("batch-retry"),
            connector=connector,
            policy=request_policy(max_requests_per_run=2),
        )
        self.assertEqual(result.attempts, 2)
        self.assertEqual(self.sleeps, [0.1])
        self.assertEqual([entry.outcome for entry in self.logs.entries], ["retrying", "succeeded"])

    def test_request_limit_stops_retry_and_records_failure_category(self) -> None:
        timeout = AcquisitionError(
            AcquisitionFailureCategory.TIMEOUT,
            "source request timed out",
            retryable=True,
        )
        connector = FakeConnector(method=AcquisitionMethod.FILE_DOWNLOAD, outcomes=(timeout,))
        with self.assertRaises(AcquisitionError) as raised:
            self.coordinator.acquire(
                source_id=SourceId("source-test"),
                import_batch_id=ImportBatchId("batch-limited"),
                connector=connector,
                policy=request_policy(max_requests_per_run=1),
            )
        self.assertEqual(raised.exception.category, AcquisitionFailureCategory.REQUEST_LIMIT)
        self.assertEqual(len(connector.calls), 1)
        self.assertEqual(self.logs.entries[-1].failure_category, "request_limit")
        updated = self.registry.get(SourceId("source-test"))
        self.assertEqual(updated.health_status, SourceHealthStatus.FAILING)  # type: ignore[union-attr]

    def test_pending_access_review_blocks_connector_and_is_logged(self) -> None:
        self.registry.save(profile(access_review=AccessReviewStatus.PENDING))
        raw = RawAcquisition(b"must not run", "text/plain", "fake:test", NOW)
        connector = FakeConnector(method=AcquisitionMethod.FILE_DOWNLOAD, outcomes=(raw,))
        with self.assertRaises(AcquisitionError) as raised:
            self.coordinator.acquire(
                source_id=SourceId("source-test"),
                import_batch_id=ImportBatchId("batch-blocked"),
                connector=connector,
                policy=request_policy(),
            )
        self.assertEqual(raised.exception.category, AcquisitionFailureCategory.ACCESS_REVIEW)
        self.assertEqual(connector.calls, [])
        self.assertEqual(self.logs.entries[-1].attempt, 0)

    def test_manual_fixture_connector_reads_only_approved_fixture_directory(self) -> None:
        manual_profile = profile(method=AcquisitionMethod.MANUAL_UPLOAD)
        self.registry.save(manual_profile)
        connector = ManualFixtureConnector(FIXTURE_ROOT)
        fixture = FIXTURE_ROOT / "tucson-permits.csv"
        result = self.coordinator.acquire(
            source_id=SourceId("source-test"),
            import_batch_id=ImportBatchId("batch-manual"),
            connector=connector,
            policy=request_policy(),
            uploaded_file=fixture,
        )
        stored = Path(result.artifact.storage_reference.removeprefix("file://"))
        self.assertEqual(stored.read_bytes(), fixture.read_bytes())

        outside = self.root / "outside.csv"
        outside.write_text("not approved", encoding="utf-8")
        with self.assertRaises(AcquisitionError) as raised:
            self.coordinator.acquire(
                source_id=SourceId("source-test"),
                import_batch_id=ImportBatchId("batch-outside"),
                connector=connector,
                policy=request_policy(),
                uploaded_file=outside,
            )
        self.assertEqual(raised.exception.category, AcquisitionFailureCategory.MANUAL_INPUT)

    def test_artifact_store_rejects_incorrect_checksum(self) -> None:
        with self.assertRaises(AcquisitionError) as raised:
            self.store.put(
                source_id=SourceId("source-test"),
                content=b"content",
                digest=ContentDigest("sha256", "0" * 64),
                media_type="text/plain",
            )
        self.assertEqual(raised.exception.category, AcquisitionFailureCategory.ARTIFACT_STORAGE)


class StructuredLoggerTests(unittest.TestCase):
    def test_json_lines_logger_emits_machine_readable_record(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "acquisition.jsonl"
            logger = JsonLinesAcquisitionLogger(path)
            entry = AcquisitionLogEntry(
                event="source_acquisition",
                source_id="source-test",
                import_batch_id="batch-test",
                occurred_at=LATER.value.isoformat(),
                outcome="failed",
                attempt=1,
                failure_category="timeout",
                message="source request timed out",
            )
            logger.record(entry)
            stored = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(stored["event"], "source_acquisition")
            self.assertEqual(stored["failure_category"], "timeout")
            self.assertNotIn("content", stored)
            self.assertNotIn("headers", stored)


if __name__ == "__main__":
    unittest.main()
