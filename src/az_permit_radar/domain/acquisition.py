"""Acquisition job lifecycle and immutable operational results."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .errors import InvalidStateTransition, InvariantViolation
from .events import EventRecorder, state_change_event
from .ingestion import ArtifactResponseMetadata
from .value_objects import (
    AcquisitionJobId,
    ContentDigest,
    IdempotencyKey,
    ImportBatchId,
    SourceArtifactId,
    SourceId,
    UtcTimestamp,
)


class AcquisitionTrigger(str, Enum):
    SCHEDULED = "scheduled"
    MANUAL = "manual"
    MANUAL_REPROCESS = "manual_reprocess"


class AcquisitionJobStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    ARCHIVED = "archived"
    DUPLICATE = "duplicate"
    REPROCESSED = "reprocessed"
    FAILED = "failed"
    DISABLED = "disabled"


_COMPLETED_JOB_STATUSES = frozenset(
    {
        AcquisitionJobStatus.ARCHIVED,
        AcquisitionJobStatus.DUPLICATE,
        AcquisitionJobStatus.REPROCESSED,
        AcquisitionJobStatus.DISABLED,
    }
)


@dataclass(slots=True)
class AcquisitionJob(EventRecorder):
    acquisition_job_id: AcquisitionJobId
    source_id: SourceId
    idempotency_key: IdempotencyKey
    trigger: AcquisitionTrigger
    scheduled_for: UtcTimestamp
    schedule_expression: str
    reprocess_artifact_id: SourceArtifactId | None = None
    status: AcquisitionJobStatus = AcquisitionJobStatus.PENDING
    attempt_count: int = 0
    started_at: UtcTimestamp | None = None
    completed_at: UtcTimestamp | None = None
    failure_category: str | None = None
    failure_message: str | None = None
    version: int = 0

    def __post_init__(self) -> None:
        self._initialize_events()
        if not self.schedule_expression.strip():
            raise InvariantViolation("acquisition job schedule expression is required")
        if (
            self.trigger is AcquisitionTrigger.MANUAL_REPROCESS
            and self.reprocess_artifact_id is None
        ):
            raise InvariantViolation("manual reprocessing requires an archived artifact")
        if (
            self.trigger is not AcquisitionTrigger.MANUAL_REPROCESS
            and self.reprocess_artifact_id is not None
        ):
            raise InvariantViolation("only manual reprocessing may reference an archived artifact")

    @property
    def is_completed(self) -> bool:
        return self.status in _COMPLETED_JOB_STATUSES

    def start(self, occurred_at: UtcTimestamp) -> None:
        if self.status not in {AcquisitionJobStatus.PENDING, AcquisitionJobStatus.FAILED}:
            raise InvalidStateTransition("AcquisitionJob", self.status, AcquisitionJobStatus.RUNNING)
        previous = self.status
        self.status = AcquisitionJobStatus.RUNNING
        self.attempt_count += 1
        self.started_at = occurred_at
        self.completed_at = None
        self.failure_category = None
        self.failure_message = None
        self.version += 1
        self._record(
            state_change_event(
                self,
                self.acquisition_job_id,
                previous,
                AcquisitionJobStatus.RUNNING,
                occurred_at,
            )
        )

    def mark_archived(self, occurred_at: UtcTimestamp) -> None:
        self._finish(AcquisitionJobStatus.ARCHIVED, occurred_at)

    def mark_duplicate(self, occurred_at: UtcTimestamp) -> None:
        self._finish(AcquisitionJobStatus.DUPLICATE, occurred_at)

    def mark_reprocessed(self, occurred_at: UtcTimestamp) -> None:
        self._finish(AcquisitionJobStatus.REPROCESSED, occurred_at)

    def mark_disabled(self, occurred_at: UtcTimestamp) -> None:
        self._finish(AcquisitionJobStatus.DISABLED, occurred_at)

    def fail(self, category: str, message: str, occurred_at: UtcTimestamp) -> None:
        if self.status is not AcquisitionJobStatus.RUNNING:
            raise InvalidStateTransition("AcquisitionJob", self.status, AcquisitionJobStatus.FAILED)
        if not category.strip() or not message.strip():
            raise InvariantViolation("acquisition job failure category and message are required")
        previous = self.status
        self.status = AcquisitionJobStatus.FAILED
        self.failure_category = category
        self.failure_message = message
        self.completed_at = occurred_at
        self.version += 1
        self._record(
            state_change_event(
                self,
                self.acquisition_job_id,
                previous,
                AcquisitionJobStatus.FAILED,
                occurred_at,
            )
        )

    def _finish(self, requested: AcquisitionJobStatus, occurred_at: UtcTimestamp) -> None:
        if self.status is not AcquisitionJobStatus.RUNNING:
            raise InvalidStateTransition("AcquisitionJob", self.status, requested)
        previous = self.status
        self.status = requested
        self.completed_at = occurred_at
        self.version += 1
        self._record(
            state_change_event(
                self,
                self.acquisition_job_id,
                previous,
                requested,
                occurred_at,
            )
        )


class AcquisitionOutcome(str, Enum):
    ARCHIVED = "archived"
    DUPLICATE = "duplicate"
    REPROCESSED = "reprocessed"
    FAILED = "failed"
    DISABLED = "disabled"


@dataclass(frozen=True, slots=True)
class AcquisitionRecord:
    acquisition_job_id: AcquisitionJobId
    source_id: SourceId
    import_batch_id: ImportBatchId
    outcome: AcquisitionOutcome
    recorded_at: UtcTimestamp
    attempt: int
    artifact_id: SourceArtifactId | None = None
    content_digest: ContentDigest | None = None
    failure_category: str | None = None
    failure_message: str | None = None
    response_metadata: ArtifactResponseMetadata | None = None

    def __post_init__(self) -> None:
        if self.attempt < 1:
            raise InvariantViolation("acquisition record attempt must be positive")
        if self.outcome is AcquisitionOutcome.FAILED:
            if not self.failure_category or not self.failure_message:
                raise InvariantViolation("failed acquisition record requires failure details")
        elif self.failure_category is not None or self.failure_message is not None:
            raise InvariantViolation("successful acquisition record cannot contain failure details")
        if self.outcome in {
            AcquisitionOutcome.ARCHIVED,
            AcquisitionOutcome.DUPLICATE,
            AcquisitionOutcome.REPROCESSED,
        } and self.artifact_id is None:
            raise InvariantViolation("successful acquisition record requires an artifact")
