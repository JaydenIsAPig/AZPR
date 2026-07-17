import unittest
from dataclasses import FrozenInstanceError

from az_permit_radar.domain.errors import InvalidStateTransition, InvariantViolation
from az_permit_radar.domain.ingestion import ImportBatch, ImportBatchStatus, SourceArtifact, SourceRecord
from az_permit_radar.domain.source_registry import Jurisdiction, Source, SourceStatus
from az_permit_radar.domain.value_objects import (
    ContentDigest,
    ImportBatchId,
    JurisdictionId,
    SourceArtifactId,
    SourceId,
    SourceRecordId,
)

from tests.support import LATER, NOW


DIGEST = ContentDigest("sha256", "a" * 64)


def artifact(batch_id: ImportBatchId = ImportBatchId("batch-001")) -> SourceArtifact:
    return SourceArtifact(
        SourceArtifactId("artifact-001"),
        SourceId("source-001"),
        batch_id,
        DIGEST,
        NOW,
        "application/json",
        "artifact://source-001/a",
    )


def source_record() -> SourceRecord:
    return SourceRecord(
        SourceRecordId("source-record-001"),
        SourceId("source-001"),
        SourceArtifactId("artifact-001"),
        ImportBatchId("batch-001"),
        "external-001",
        DIGEST,
        NOW,
    )


class SourceRegistryTests(unittest.TestCase):
    def test_pilot_jurisdiction_must_be_in_arizona(self) -> None:
        with self.assertRaises(InvariantViolation):
            Jurisdiction(JurisdictionId("jurisdiction-001"), "Other", "NM")

    def test_retired_source_is_terminal(self) -> None:
        source = Source(SourceId("source-001"), JurisdictionId("jurisdiction-001"), "Portal", "portal")
        source.transition_to(SourceStatus.RETIRED, NOW)
        with self.assertRaises(InvalidStateTransition):
            source.transition_to(SourceStatus.ACTIVE, LATER)


class IngestionTests(unittest.TestCase):
    def test_source_artifact_is_immutable(self) -> None:
        archived = artifact()
        with self.assertRaises(FrozenInstanceError):
            archived.storage_reference = "changed"  # type: ignore[misc]

    def test_batch_requires_artifact_before_acquired(self) -> None:
        batch = ImportBatch(ImportBatchId("batch-001"), SourceId("source-001"), NOW)
        with self.assertRaises(InvariantViolation):
            batch.mark_acquired(LATER)

    def test_batch_rejects_artifact_from_another_batch(self) -> None:
        batch = ImportBatch(ImportBatchId("batch-001"), SourceId("source-001"), NOW)
        with self.assertRaises(InvariantViolation):
            batch.register_artifact(artifact(ImportBatchId("batch-other")))

    def test_batch_completes_with_registered_record_counts(self) -> None:
        batch = ImportBatch(ImportBatchId("batch-001"), SourceId("source-001"), NOW)
        batch.register_artifact(artifact())
        batch.mark_acquired(NOW)
        record = source_record()
        batch.register_source_record(record)
        batch.start_processing(NOW)
        record.mark_parsed("parser-1", NOW)
        batch.complete(1, 0, LATER)
        self.assertEqual(batch.status, ImportBatchStatus.COMPLETED)
        self.assertGreaterEqual(len(batch.pull_domain_events()), 3)

    def test_registering_same_source_record_is_idempotent_inside_batch(self) -> None:
        batch = ImportBatch(ImportBatchId("batch-001"), SourceId("source-001"), NOW)
        batch.register_artifact(artifact())
        batch.mark_acquired(NOW)
        record = source_record()
        batch.register_source_record(record)
        version = batch.version
        batch.register_source_record(record)
        self.assertEqual(batch.version, version)
        self.assertEqual(len(batch.source_record_ids), 1)

    def test_batch_detects_inconsistent_completion_counts(self) -> None:
        batch = ImportBatch(ImportBatchId("batch-001"), SourceId("source-001"), NOW)
        batch.register_artifact(artifact())
        batch.mark_acquired(NOW)
        batch.start_processing(NOW)
        with self.assertRaises(InvariantViolation):
            batch.complete(1, 0, LATER)

    def test_source_record_cannot_be_parsed_after_rejection(self) -> None:
        record = source_record()
        record.reject("malformed payload", NOW)
        with self.assertRaises(InvalidStateTransition):
            record.mark_parsed("parser-1", LATER)


if __name__ == "__main__":
    unittest.main()
