"""Notification preference channel and delivery-attempt lifecycle."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .errors import InvalidStateTransition, InvariantViolation
from .events import EventRecorder, state_change_event
from .value_objects import (
    IdempotencyKey,
    NotificationAttemptId,
    OpportunityMatchId,
    UtcTimestamp,
)


class NotificationChannel(str, Enum):
    EMAIL = "email"
    SMS = "sms"


class NotificationAttemptStatus(str, Enum):
    QUEUED = "queued"
    SUBMITTED = "submitted"
    DELIVERED = "delivered"
    FAILED = "failed"
    SUPPRESSED = "suppressed"


_NOTIFICATION_TRANSITIONS = {
    NotificationAttemptStatus.QUEUED: frozenset(
        {NotificationAttemptStatus.SUBMITTED, NotificationAttemptStatus.FAILED, NotificationAttemptStatus.SUPPRESSED}
    ),
    NotificationAttemptStatus.SUBMITTED: frozenset(
        {NotificationAttemptStatus.DELIVERED, NotificationAttemptStatus.FAILED}
    ),
    NotificationAttemptStatus.DELIVERED: frozenset(),
    NotificationAttemptStatus.FAILED: frozenset(),
    NotificationAttemptStatus.SUPPRESSED: frozenset(),
}


@dataclass(slots=True)
class NotificationAttempt(EventRecorder):
    notification_attempt_id: NotificationAttemptId
    opportunity_match_id: OpportunityMatchId
    channel: NotificationChannel
    idempotency_key: IdempotencyKey
    queued_at: UtcTimestamp
    consent_reference: str
    status: NotificationAttemptStatus = NotificationAttemptStatus.QUEUED
    provider_reference: str | None = None
    outcome_reason: str | None = None
    submitted_at: UtcTimestamp | None = None
    completed_at: UtcTimestamp | None = None
    version: int = 0

    def __post_init__(self) -> None:
        self._initialize_events()
        if not self.consent_reference.strip():
            raise InvariantViolation("notification attempt requires a consent reference")

    def submit(self, provider_reference: str, occurred_at: UtcTimestamp) -> None:
        if not provider_reference.strip():
            raise InvariantViolation("provider reference is required on submission")
        self._transition(NotificationAttemptStatus.SUBMITTED, occurred_at)
        self.provider_reference = provider_reference
        self.submitted_at = occurred_at

    def mark_delivered(self, occurred_at: UtcTimestamp) -> None:
        self._transition(NotificationAttemptStatus.DELIVERED, occurred_at)
        self.completed_at = occurred_at

    def fail(self, reason: str, occurred_at: UtcTimestamp) -> None:
        if not reason.strip():
            raise InvariantViolation("notification failure reason is required")
        self._transition(NotificationAttemptStatus.FAILED, occurred_at)
        self.outcome_reason = reason
        self.completed_at = occurred_at

    def suppress(self, reason: str, occurred_at: UtcTimestamp) -> None:
        if not reason.strip():
            raise InvariantViolation("notification suppression reason is required")
        self._transition(NotificationAttemptStatus.SUPPRESSED, occurred_at)
        self.outcome_reason = reason
        self.completed_at = occurred_at

    def _transition(self, requested: NotificationAttemptStatus, occurred_at: UtcTimestamp) -> None:
        if requested not in _NOTIFICATION_TRANSITIONS[self.status]:
            raise InvalidStateTransition("NotificationAttempt", self.status, requested)
        previous = self.status
        self.status = requested
        self.version += 1
        self._record(
            state_change_event(self, self.notification_attempt_id, previous, requested, occurred_at)
        )
