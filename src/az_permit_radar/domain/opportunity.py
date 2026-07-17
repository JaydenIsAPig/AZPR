"""Customer-independent Opportunity aggregate."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .errors import InvalidStateTransition, InvariantViolation
from .events import EventRecorder, state_change_event
from .value_objects import (
    ClassificationResultId,
    OpportunityId,
    PermitId,
    TradeTagId,
    UtcTimestamp,
)


class OpportunityStatus(str, Enum):
    CANDIDATE = "candidate"
    PUBLISHED = "published"
    SUPPRESSED = "suppressed"
    EXPIRED = "expired"


_OPPORTUNITY_TRANSITIONS = {
    OpportunityStatus.CANDIDATE: frozenset({OpportunityStatus.PUBLISHED, OpportunityStatus.SUPPRESSED}),
    OpportunityStatus.PUBLISHED: frozenset({OpportunityStatus.SUPPRESSED, OpportunityStatus.EXPIRED}),
    OpportunityStatus.SUPPRESSED: frozenset(),
    OpportunityStatus.EXPIRED: frozenset(),
}


@dataclass(slots=True)
class Opportunity(EventRecorder):
    opportunity_id: OpportunityId
    permit_ids: frozenset[PermitId]
    classification_result_ids: frozenset[ClassificationResultId]
    trade_tag_ids: frozenset[TradeTagId]
    created_at: UtcTimestamp
    status: OpportunityStatus = OpportunityStatus.CANDIDATE
    status_reason: str | None = None
    version: int = 0

    def __post_init__(self) -> None:
        self._initialize_events()
        if not self.permit_ids:
            raise InvariantViolation("opportunity requires at least one permit")
        if not self.classification_result_ids:
            raise InvariantViolation("opportunity requires at least one classification result")
        if not self.trade_tag_ids:
            raise InvariantViolation("opportunity requires at least one trade tag")

    def transition_to(self, requested: OpportunityStatus, reason: str, occurred_at: UtcTimestamp) -> None:
        if requested == self.status:
            return
        if requested not in _OPPORTUNITY_TRANSITIONS[self.status]:
            raise InvalidStateTransition("Opportunity", self.status, requested)
        if not reason.strip():
            raise InvariantViolation("opportunity state change reason is required")
        previous = self.status
        self.status = requested
        self.status_reason = reason
        self.version += 1
        self._record(state_change_event(self, self.opportunity_id, previous, requested, occurred_at))
