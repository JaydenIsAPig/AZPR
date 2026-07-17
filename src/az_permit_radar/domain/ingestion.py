"""Permit Ingestion domain entities and immutable provenance objects."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from .errors import InvalidStateTransition, InvariantViolation
from .events import ArtifactRegistered, EventRecorder, state_change_event
from .value_objects import (
    ContentDigest,
    ImportBatchId,
    SourceArtifactId,
    SourceId,
    SourceRecordId,
    UtcTimestamp,
)


@dataclass(frozen=True, slots=True)
class SourceArtifact:
    artifact_id: SourceArtifactId
    source_id: SourceId
    import_batch_id: ImportBatchId
    content_digest: ContentDigest
    acquired_at: UtcTimestamp
    media_type: str
    storage_reference: str

    def __post_init__(self) -> None:
        if not self.media_type.strip():
            raise InvariantViolation("source artifact media type is required")
        if not self.storage_reference.strip():
            raise InvariantViolation("source artifact storage reference is required")


class SourceRecordStatus(str, Enum):
    RECEIVED = "received"
    PARSED = "parsed"
    REJECTED = "rejected"


@dataclass(slots=True)
class SourceRecord(EventRecorder):
    source_record_id: SourceRecordId
    source_id: SourceId
    artifact_id: SourceArtifactId
    import_batch_id: ImportBatchId
    external_record_id: str | None
    payload_digest: ContentDigest
    observed_at: UtcTimestamp
    status: SourceRecordStatus = SourceRecordStatus.RECEIVED
    parser_version: str | None = None
    rejection_reason: str | None = None
    version: int = 0

    def __post_init__(self) -> None:
        self._initialize_events()
        if self.external_record_id is not None and not self.external_record_id.strip():
            raise InvariantViolation("external record identifier cannot be blank")

    def mark_parsed(self, parser_version: str, occurred_at: UtcTimestamp) -> None:
        if self.status is not SourceRecordStatus.RECEIVED:
            raise InvalidStateTransition("SourceRecord", self.status, SourceRecordStatus.PARSED)
        if not parser_version.strip():
            raise InvariantViolation("parser version is required")
        previous = self.status
        self.status = SourceRecordStatus.PARSED
        self.parser_version = parser_version
        self.version += 1
        self._record(state_change_event(self, self.source_record_id, previous, self.status, occurred_at))

    def reject(self, reason: str, occurred_at: UtcTimestamp) -> None:
        if self.status is not SourceRecordStatus.RECEIVED:
            raise InvalidStateTransition("SourceRecord", self.status, SourceRecordStatus.REJECTED)
        if not reason.strip():
            raise InvariantViolation("source record rejection reason is required")
        previous = self.status
        self.status = SourceRecordStatus.REJECTED
        self.rejection_reason = reason
        self.version += 1
        self._record(state_change_event(self, self.source_record_id, previous, self.status, occurred_at))


class ImportBatchStatus(str, Enum):
    STARTED = "started"
    ACQUIRED = "acquired"
    PROCESSING = "processing"
    COMPLETED = "completed"
    PARTIALLY_FAILED = "partially_failed"
    FAILED = "failed"


_TERMINAL_BATCH_STATES = frozenset(
    {ImportBatchStatus.COMPLETED, ImportBatchStatus.PARTIALLY_FAILED, ImportBatchStatus.FAILED}
)


@dataclass(slots=True)
class ImportBatch(EventRecorder):
    import_batch_id: ImportBatchId
    source_id: SourceId
    started_at: UtcTimestamp
    status: ImportBatchStatus = ImportBatchStatus.STARTED
    artifact_ids: set[SourceArtifactId] = field(default_factory=set)
    source_record_ids: set[SourceRecordId] = field(default_factory=set)
    processed_count: int = 0
    rejected_count: int = 0
    failure_reason: str | None = None
    version: int = 0

    def __post_init__(self) -> None:
        self._initialize_events()
        if self.processed_count < 0 or self.rejected_count < 0:
            raise InvariantViolation("batch counts cannot be negative")

    def register_artifact(self, artifact: SourceArtifact) -> None:
        if self.status is not ImportBatchStatus.STARTED:
            raise InvariantViolation("artifacts can be registered only while a batch is started")
        if artifact.import_batch_id != self.import_batch_id or artifact.source_id != self.source_id:
            raise InvariantViolation("artifact provenance does not match import batch")
        if artifact.artifact_id in self.artifact_ids:
            return
        self.artifact_ids.add(artifact.artifact_id)
        self.version += 1
        self._record(
            ArtifactRegistered(
                aggregate_id=str(self.import_batch_id),
                occurred_at=artifact.acquired_at,
                source_id=str(self.source_id),
                artifact_id=str(artifact.artifact_id),
            )
        )

    def mark_acquired(self, occurred_at: UtcTimestamp) -> None:
        if self.status is not ImportBatchStatus.STARTED:
            raise InvalidStateTransition("ImportBatch", self.status, ImportBatchStatus.ACQUIRED)
        if not self.artifact_ids:
            raise InvariantViolation("an acquired import batch requires at least one artifact")
        self._transition(ImportBatchStatus.ACQUIRED, occurred_at)

    def register_source_record(self, source_record: SourceRecord) -> None:
        if self.status not in {ImportBatchStatus.ACQUIRED, ImportBatchStatus.PROCESSING}:
            raise InvariantViolation("source records require an acquired or processing batch")
        if (
            source_record.import_batch_id != self.import_batch_id
            or source_record.source_id != self.source_id
            or source_record.artifact_id not in self.artifact_ids
        ):
            raise InvariantViolation("source record provenance does not match import batch")
        if source_record.source_record_id in self.source_record_ids:
            return
        self.source_record_ids.add(source_record.source_record_id)
        self.version += 1

    def start_processing(self, occurred_at: UtcTimestamp) -> None:
        if self.status is not ImportBatchStatus.ACQUIRED:
            raise InvalidStateTransition("ImportBatch", self.status, ImportBatchStatus.PROCESSING)
        self._transition(ImportBatchStatus.PROCESSING, occurred_at)

    def complete(self, processed_count: int, rejected_count: int, occurred_at: UtcTimestamp) -> None:
        if self.status is not ImportBatchStatus.PROCESSING:
            raise InvalidStateTransition("ImportBatch", self.status, ImportBatchStatus.COMPLETED)
        if processed_count < 0 or rejected_count < 0:
            raise InvariantViolation("batch counts cannot be negative")
        if processed_count + rejected_count != len(self.source_record_ids):
            raise InvariantViolation("batch completion counts must equal registered source records")
        self.processed_count = processed_count
        self.rejected_count = rejected_count
        requested = ImportBatchStatus.PARTIALLY_FAILED if rejected_count else ImportBatchStatus.COMPLETED
        self._transition(requested, occurred_at)

    def fail(self, reason: str, occurred_at: UtcTimestamp) -> None:
        if self.status in _TERMINAL_BATCH_STATES:
            raise InvalidStateTransition("ImportBatch", self.status, ImportBatchStatus.FAILED)
        if not reason.strip():
            raise InvariantViolation("batch failure reason is required")
        self.failure_reason = reason
        self._transition(ImportBatchStatus.FAILED, occurred_at)

    def _transition(self, requested: ImportBatchStatus, occurred_at: UtcTimestamp) -> None:
        previous = self.status
        self.status = requested
        self.version += 1
        self._record(state_change_event(self, self.import_batch_id, previous, requested, occurred_at))
