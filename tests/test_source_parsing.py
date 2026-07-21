import hashlib
import unittest
from decimal import Decimal
from pathlib import Path

from az_permit_radar.application.parsing import (
    ArtifactUnusable,
    ArtifactUnusableCategory,
    SourceParserPipeline,
)
from az_permit_radar.domain.ingestion import ImportBatch, ImportBatchStatus, SourceArtifact
from az_permit_radar.domain.parsing import RecordDisposition, ValueValidationResult
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
    CalendarDate,
    ContentDigest,
    ImportBatchId,
    JurisdictionId,
    Money,
    SourceArtifactId,
    SourceId,
)
from az_permit_radar.infrastructure.source_parsing import (
    InMemoryArtifactReader,
    InMemoryParsingLogger,
    InMemoryParsingMetrics,
    InMemoryRejectionReporter,
    InMemorySourceRecordRepository,
    tucson_fixture_parser_definition,
)

from tests.support import LATER, NOW


FIXTURES = Path(__file__).parent / "fixtures" / "parser"


def profile(*, parser_version: str = "1.1.0") -> SourceProfile:
    return SourceProfile(
        source_id=SourceId("source-tucson-fixture"),
        jurisdiction_id=JurisdictionId("jurisdiction-tucson"),
        jurisdiction="City of Tucson",
        source_name="Synthetic Tucson parser fixture",
        acquisition_method=AcquisitionMethod.MANUAL_UPLOAD,
        endpoint=EndpointConfiguration(),
        file_type=SourceFileType("text/csv", ".csv"),
        schedule="manual",
        time_zone="America/Phoenix",
        authentication_requirement=AuthenticationRequirement.NONE,
        parser_identifier="synthetic-tucson-permit-csv",
        parser_version=parser_version,
        expected_date_fields=("issued_date",),
        expected_unique_identifiers=("permit_number",),
        historical_availability="synthetic fixture only",
        known_limitations=("physical-line CSV fields only", "not a live municipal contract"),
        enabled=True,
        health_status=SourceHealthStatus.UNKNOWN,
        access_review_status=AccessReviewStatus.APPROVED,
        operational_owner="test-operations",
    )


def artifact_and_batch(
    content: bytes,
    *,
    artifact_id: str,
    batch_id: str,
) -> tuple[SourceArtifact, ImportBatch]:
    source_id = SourceId("source-tucson-fixture")
    batch = ImportBatch(ImportBatchId(batch_id), source_id, NOW)
    artifact = SourceArtifact(
        artifact_id=SourceArtifactId(artifact_id),
        source_id=source_id,
        import_batch_id=batch.import_batch_id,
        content_digest=ContentDigest("sha256", hashlib.sha256(content).hexdigest()),
        acquired_at=NOW,
        media_type="text/csv",
        storage_reference=f"memory://{artifact_id}",
    )
    batch.register_artifact(artifact)
    batch.mark_acquired(NOW)
    return artifact, batch


class ParserHarness:
    def __init__(self, repository: InMemorySourceRecordRepository | None = None) -> None:
        self.reader = InMemoryArtifactReader()
        self.repository = repository or InMemorySourceRecordRepository()
        self.rejections = InMemoryRejectionReporter()
        self.logs = InMemoryParsingLogger()
        self.metrics = InMemoryParsingMetrics()

    def pipeline(self, *, parser_version: str = "1.1.0") -> SourceParserPipeline:
        return SourceParserPipeline(
            definition=tucson_fixture_parser_definition(parser_version=parser_version),
            artifact_reader=self.reader,
            source_records=self.repository,
            rejection_reporter=self.rejections,
            logger=self.logs,
            metrics=self.metrics,
            now=lambda: LATER,
        )


class SourceParsingTests(unittest.TestCase):
    def test_parser_v1_1_maps_optional_permit_normalization_fields(self) -> None:
        content = (FIXTURES / "tucson-permits-normalization-v1.1.csv").read_bytes()
        artifact, batch = artifact_and_batch(
            content,
            artifact_id="artifact-normalization-fields",
            batch_id="batch-normalization-fields",
        )
        harness = ParserHarness()
        harness.reader.add(artifact, content)

        report = harness.pipeline().parse(profile=profile(), artifact=artifact, batch=batch)
        record = harness.repository.get(report.rows[0].source_record_id)  # type: ignore[arg-type]
        by_name = {value.canonical_field: value.normalized_value for value in record.parsed_values}  # type: ignore[union-attr]

        self.assertEqual(report.accepted_count, 1)
        self.assertEqual(record.acquired_at, artifact.acquired_at)  # type: ignore[union-attr]
        self.assertEqual(by_name["application_date"], CalendarDate.from_iso("2026-07-10"))
        self.assertEqual(by_name["permit_status"], "Permit Issued")
        self.assertEqual(by_name["permit_type"], "Residential Remodel")
        self.assertEqual(by_name["parcel_id"], "123-45-678A")
        self.assertEqual(by_name["latitude"], "32.2217")
        self.assertFalse(any(name.startswith("source_extra.") for name in by_name))

    def test_fixture_batch_accepts_valid_rows_and_quarantines_only_bad_rows(self) -> None:
        content = (FIXTURES / "tucson-permits-v1.csv").read_bytes()
        artifact, batch = artifact_and_batch(
            content, artifact_id="artifact-parser-v1", batch_id="batch-parser-v1"
        )
        harness = ParserHarness()
        harness.reader.add(artifact, content)

        report = harness.pipeline().parse(profile=profile(), artifact=artifact, batch=batch)

        self.assertEqual(
            (
                report.accepted_count,
                report.warned_count,
                report.rejected_count,
                report.duplicate_count,
                report.unchanged_count,
            ),
            (2, 0, 3, 1, 0),
        )
        self.assertEqual(report.total_entries, 6)
        self.assertEqual(batch.status, ImportBatchStatus.PARTIALLY_FAILED)
        self.assertEqual(len(harness.rejections.rows), 3)
        self.assertEqual(len(harness.repository.records), 5)
        malformed = report.rows[2]
        self.assertEqual(malformed.disposition, RecordDisposition.REJECTED)
        self.assertEqual(malformed.issues[0].code, "csv_column_count_mismatch")
        self.assertEqual(report.rows[-1].disposition, RecordDisposition.DUPLICATE)
        self.assertEqual(report.parser_version, "1.1.0")

    def test_values_preserve_raw_normalized_source_field_version_and_validation(self) -> None:
        content = (FIXTURES / "tucson-permits-v1.csv").read_bytes()
        artifact, batch = artifact_and_batch(
            content, artifact_id="artifact-values", batch_id="batch-values"
        )
        harness = ParserHarness()
        harness.reader.add(artifact, content)

        report = harness.pipeline().parse(profile=profile(), artifact=artifact, batch=batch)
        first = report.rows[0]
        issued = next(value for value in first.values if value.canonical_field == "issued_date")
        valuation = next(value for value in first.values if value.canonical_field == "valuation")
        empty_valuation = next(
            value for value in report.rows[1].values if value.canonical_field == "valuation"
        )

        self.assertEqual(issued.raw_value, "2026-07-16")
        self.assertEqual(issued.source_field, "Issued Date")
        self.assertEqual(issued.normalized_value, CalendarDate.from_iso("2026-07-16"))
        self.assertEqual(issued.parser_version, "1.1.0")
        self.assertEqual(valuation.normalized_value, Money(Decimal("12345.67")))
        self.assertEqual(empty_valuation.validation_result, ValueValidationResult.EMPTY)
        self.assertIsNone(empty_valuation.normalized_value)
        records = [record for record in harness.repository.records if record.parser_version]
        self.assertTrue(all(record.parser_version == "1.1.0" for record in records))

    def test_alias_columns_stable_keys_duplicates_unchanged_and_warned_changes(self) -> None:
        first_content = (FIXTURES / "tucson-permits-v1.csv").read_bytes()
        first_artifact, first_batch = artifact_and_batch(
            first_content, artifact_id="artifact-history-v1", batch_id="batch-history-v1"
        )
        harness = ParserHarness()
        harness.reader.add(first_artifact, first_content)
        first_report = harness.pipeline().parse(
            profile=profile(), artifact=first_artifact, batch=first_batch
        )

        changed = (FIXTURES / "tucson-permits-changed-columns.csv").read_bytes()
        changed_artifact, changed_batch = artifact_and_batch(
            changed, artifact_id="artifact-history-v2", batch_id="batch-history-v2"
        )
        harness.reader.add(changed_artifact, changed)
        changed_report = harness.pipeline().parse(
            profile=profile(), artifact=changed_artifact, batch=changed_batch
        )

        self.assertEqual(
            (
                changed_report.accepted_count,
                changed_report.warned_count,
                changed_report.rejected_count,
                changed_report.duplicate_count,
                changed_report.unchanged_count,
            ),
            (0, 2, 0, 1, 1),
        )
        self.assertEqual(
            first_report.rows[0].external_record_key,
            changed_report.rows[0].external_record_key,
        )
        self.assertEqual(changed_report.rows[0].disposition, RecordDisposition.UNCHANGED)
        warning_codes = {issue.code for issue in changed_report.rows[1].issues}
        self.assertIn("value_normalized", warning_codes)
        self.assertEqual(changed_batch.status, ImportBatchStatus.COMPLETED)

    def test_reprocessing_with_new_parser_version_creates_new_results(self) -> None:
        content = (FIXTURES / "tucson-permits-v1.csv").read_bytes()
        artifact, first_batch = artifact_and_batch(
            content, artifact_id="artifact-reprocess", batch_id="batch-reprocess-v1"
        )
        harness = ParserHarness()
        harness.reader.add(artifact, content)
        harness.pipeline().parse(profile=profile(), artifact=artifact, batch=first_batch)

        reprocess_batch = ImportBatch(
            ImportBatchId("batch-reprocess-v2"), artifact.source_id, LATER
        )
        reprocess_batch.prepare_reprocessing(artifact, LATER)
        report = harness.pipeline(parser_version="2.0.0").parse(
            profile=profile(parser_version="2.0.0"),
            artifact=artifact,
            batch=reprocess_batch,
        )

        self.assertEqual(report.accepted_count, 2)
        self.assertEqual(report.unchanged_count, 0)
        parsed_versions = {
            record.parser_version
            for record in harness.repository.records
            if record.status.value == "parsed"
        }
        self.assertEqual(parsed_versions, {"1.1.0", "2.0.0"})

    def test_unusable_artifact_fails_whole_batch_and_is_observable(self) -> None:
        content = (FIXTURES / "tucson-permits-unusable.csv").read_bytes()
        artifact, batch = artifact_and_batch(
            content, artifact_id="artifact-unusable", batch_id="batch-unusable"
        )
        harness = ParserHarness()
        harness.reader.add(artifact, content)

        with self.assertRaises(ArtifactUnusable) as raised:
            harness.pipeline().parse(profile=profile(), artifact=artifact, batch=batch)

        self.assertEqual(raised.exception.category, ArtifactUnusableCategory.FORMAT)
        self.assertEqual(batch.status, ImportBatchStatus.FAILED)
        self.assertEqual(harness.logs.entries[-1].outcome, "failed")
        self.assertNotIn("T26-0001", str(harness.logs.entries[-1].as_dict()))
        self.assertEqual(len(harness.repository.records), 0)

    def test_checksum_mismatch_fails_before_decoding(self) -> None:
        expected = b"Permit Number,Issued Date\nT26-1,2026-07-17\n"
        artifact, batch = artifact_and_batch(
            expected, artifact_id="artifact-checksum", batch_id="batch-checksum"
        )
        harness = ParserHarness()
        harness.reader.add(artifact, b"changed bytes")

        with self.assertRaises(ArtifactUnusable) as raised:
            harness.pipeline().parse(profile=profile(), artifact=artifact, batch=batch)

        self.assertEqual(raised.exception.category, ArtifactUnusableCategory.CHECKSUM)
        self.assertEqual(batch.status, ImportBatchStatus.FAILED)

    def test_unreadable_archive_fails_with_safe_category(self) -> None:
        content = b"Permit Number,Issued Date\nT26-1,2026-07-17\n"
        artifact, batch = artifact_and_batch(
            content, artifact_id="artifact-unreadable", batch_id="batch-unreadable"
        )
        harness = ParserHarness()

        with self.assertRaises(ArtifactUnusable) as raised:
            harness.pipeline().parse(profile=profile(), artifact=artifact, batch=batch)

        self.assertEqual(raised.exception.category, ArtifactUnusableCategory.ARTIFACT_READ)
        self.assertEqual(batch.status, ImportBatchStatus.FAILED)

    def test_invalid_utf8_fails_at_explicit_decoder_boundary(self) -> None:
        content = b"Permit Number,Issued Date\nT26-1,\xff\n"
        artifact, batch = artifact_and_batch(
            content, artifact_id="artifact-encoding", batch_id="batch-encoding"
        )
        harness = ParserHarness()
        harness.reader.add(artifact, content)

        with self.assertRaises(ArtifactUnusable) as raised:
            harness.pipeline().parse(profile=profile(), artifact=artifact, batch=batch)

        self.assertEqual(raised.exception.category, ArtifactUnusableCategory.DECODING)
        self.assertEqual(batch.status, ImportBatchStatus.FAILED)

    def test_structured_summary_logs_and_metrics_exclude_raw_values(self) -> None:
        content = (FIXTURES / "tucson-permits-v1.csv").read_bytes()
        artifact, batch = artifact_and_batch(
            content, artifact_id="artifact-observe", batch_id="batch-observe"
        )
        harness = ParserHarness()
        harness.reader.add(artifact, content)
        report = harness.pipeline().parse(profile=profile(), artifact=artifact, batch=batch)

        entry = harness.logs.entries[-1]
        self.assertEqual(entry.rejected_count, report.rejected_count)
        self.assertNotIn("Congress", str(entry.as_dict()))
        self.assertEqual(
            harness.metrics.counters[
                (
                    "parser_rows_total",
                    (("disposition", "accepted"), ("source_id", "source-tucson-fixture")),
                )
            ],
            2,
        )


if __name__ == "__main__":
    unittest.main()
