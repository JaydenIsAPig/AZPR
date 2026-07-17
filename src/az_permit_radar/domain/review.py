"""Internal Review Task aggregate."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .errors import InvalidStateTransition, InvariantViolation
from .events import EventRecorder, state_change_event
from .value_objects import ReviewTaskId, UtcTimestamp


class ReviewSubjectType(str, Enum):
    SOURCE_RECORD = "source_record"
    PERMIT = "permit"
    CLASSIFICATION_RESULT = "classification_result"
    OPPORTUNITY = "opportunity"
    OPPORTUNITY_MATCH = "opportunity_match"
    NOTIFICATION_ATTEMPT = "notification_attempt"


class ReviewTaskStatus(str, Enum):
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    RESOLVED = "resolved"
    CANCELLED = "cancelled"


_REVIEW_TRANSITIONS = {
    ReviewTaskStatus.OPEN: frozenset(
        {ReviewTaskStatus.IN_PROGRESS, ReviewTaskStatus.RESOLVED, ReviewTaskStatus.CANCELLED}
    ),
    ReviewTaskStatus.IN_PROGRESS: frozenset({ReviewTaskStatus.RESOLVED, ReviewTaskStatus.CANCELLED}),
    ReviewTaskStatus.RESOLVED: frozenset(),
    ReviewTaskStatus.CANCELLED: frozenset(),
}


@dataclass(slots=True)
class ReviewTask(EventRecorder):
    review_task_id: ReviewTaskId
    subject_type: ReviewSubjectType
    subject_id: str
    reason: str
    opened_at: UtcTimestamp
    status: ReviewTaskStatus = ReviewTaskStatus.OPEN
    assignee_id: str | None = None
    resolution: str | None = None
    completed_at: UtcTimestamp | None = None
    version: int = 0

    def __post_init__(self) -> None:
        self._initialize_events()
        if not self.subject_id.strip() or not self.reason.strip():
            raise InvariantViolation("review task subject and reason are required")

    def start(self, assignee_id: str, occurred_at: UtcTimestamp) -> None:
        if not assignee_id.strip():
            raise InvariantViolation("review task assignee is required")
        self._transition(ReviewTaskStatus.IN_PROGRESS, occurred_at)
        self.assignee_id = assignee_id

    def resolve(self, resolution: str, occurred_at: UtcTimestamp) -> None:
        if not resolution.strip():
            raise InvariantViolation("review task resolution is required")
        self._transition(ReviewTaskStatus.RESOLVED, occurred_at)
        self.resolution = resolution
        self.completed_at = occurred_at

    def cancel(self, reason: str, occurred_at: UtcTimestamp) -> None:
        if not reason.strip():
            raise InvariantViolation("review task cancellation reason is required")
        self._transition(ReviewTaskStatus.CANCELLED, occurred_at)
        self.resolution = reason
        self.completed_at = occurred_at

    def _transition(self, requested: ReviewTaskStatus, occurred_at: UtcTimestamp) -> None:
        if requested not in _REVIEW_TRANSITIONS[self.status]:
            raise InvalidStateTransition("ReviewTask", self.status, requested)
        previous = self.status
        self.status = requested
        self.version += 1
        self._record(state_change_event(self, self.review_task_id, previous, requested, occurred_at))
