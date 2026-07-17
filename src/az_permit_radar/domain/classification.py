"""Permit Intelligence classifications with deterministic/AI provenance."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .errors import InvalidStateTransition, InvariantViolation
from .events import ClassificationReviewed, EventRecorder
from .value_objects import (
    ClassificationResultId,
    Confidence,
    PermitId,
    TradeTagId,
    UtcTimestamp,
)


@dataclass(frozen=True, slots=True)
class ProjectClassification:
    code: str
    label: str

    def __post_init__(self) -> None:
        if not self.code.strip() or not self.label.strip():
            raise InvariantViolation("project classification code and label are required")


@dataclass(frozen=True, slots=True)
class TradeTag:
    trade_tag_id: TradeTagId
    code: str
    label: str

    def __post_init__(self) -> None:
        if not self.code.strip() or not self.label.strip():
            raise InvariantViolation("trade tag code and label are required")


class ClassificationMethod(str, Enum):
    DETERMINISTIC = "deterministic"
    AI_ASSISTED = "ai_assisted"


class ClassificationReviewStatus(str, Enum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    REJECTED = "rejected"


@dataclass(slots=True)
class ClassificationResult(EventRecorder):
    classification_result_id: ClassificationResultId
    permit_id: PermitId
    project_classification: ProjectClassification
    trade_tags: frozenset[TradeTag]
    method: ClassificationMethod
    classifier_version: str
    confidence: Confidence
    evidence: tuple[str, ...]
    produced_at: UtcTimestamp
    model_provider: str | None = None
    model_version: str | None = None
    prompt_version: str | None = None
    review_status: ClassificationReviewStatus = ClassificationReviewStatus.PENDING
    review_note: str | None = None
    version: int = 0

    def __post_init__(self) -> None:
        self._initialize_events()
        if not self.classifier_version.strip():
            raise InvariantViolation("classifier version is required")
        if not self.trade_tags:
            raise InvariantViolation("classification requires at least one trade tag")
        if not self.evidence or any(not item.strip() for item in self.evidence):
            raise InvariantViolation("classification requires non-blank evidence")
        ai_fields = (self.model_provider, self.model_version, self.prompt_version)
        if self.method is ClassificationMethod.AI_ASSISTED and not all(
            value is not None and value.strip() for value in ai_fields
        ):
            raise InvariantViolation("AI-assisted classification requires provider, model, and prompt versions")
        if self.method is ClassificationMethod.DETERMINISTIC and any(ai_fields):
            raise InvariantViolation("deterministic classification cannot claim AI model provenance")

    def accept(self, note: str, occurred_at: UtcTimestamp) -> None:
        self._review(ClassificationReviewStatus.ACCEPTED, note, occurred_at)

    def reject(self, note: str, occurred_at: UtcTimestamp) -> None:
        self._review(ClassificationReviewStatus.REJECTED, note, occurred_at)

    def _review(
        self,
        requested: ClassificationReviewStatus,
        note: str,
        occurred_at: UtcTimestamp,
    ) -> None:
        if self.review_status is not ClassificationReviewStatus.PENDING:
            raise InvalidStateTransition("ClassificationResult", self.review_status, requested)
        if not note.strip():
            raise InvariantViolation("classification review note is required")
        self.review_status = requested
        self.review_note = note
        self.version += 1
        self._record(
            ClassificationReviewed(
                aggregate_id=str(self.classification_result_id),
                occurred_at=occurred_at,
                permit_id=str(self.permit_id),
                review_status=requested.value,
            )
        )
