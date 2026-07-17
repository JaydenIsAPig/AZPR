"""Source Registry domain entities."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .errors import InvalidStateTransition, InvariantViolation
from .events import EventRecorder, state_change_event
from .value_objects import JurisdictionId, SourceId, UtcTimestamp


class JurisdictionStatus(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"


@dataclass(slots=True)
class Jurisdiction(EventRecorder):
    jurisdiction_id: JurisdictionId
    name: str
    region_code: str
    status: JurisdictionStatus = JurisdictionStatus.ACTIVE
    version: int = 0

    def __post_init__(self) -> None:
        self._initialize_events()
        if not self.name.strip():
            raise InvariantViolation("jurisdiction name is required")
        if self.region_code != "AZ":
            raise InvariantViolation("pilot jurisdictions must use Arizona region code AZ")

    def activate(self, occurred_at: UtcTimestamp) -> None:
        self._transition(JurisdictionStatus.ACTIVE, occurred_at)

    def deactivate(self, occurred_at: UtcTimestamp) -> None:
        self._transition(JurisdictionStatus.INACTIVE, occurred_at)

    def _transition(self, requested: JurisdictionStatus, occurred_at: UtcTimestamp) -> None:
        if requested == self.status:
            return
        previous = self.status
        self.status = requested
        self.version += 1
        self._record(state_change_event(self, self.jurisdiction_id, previous, requested, occurred_at))


class SourceStatus(str, Enum):
    DRAFT = "draft"
    ACTIVE = "active"
    PAUSED = "paused"
    RETIRED = "retired"


_SOURCE_TRANSITIONS = {
    SourceStatus.DRAFT: frozenset({SourceStatus.ACTIVE, SourceStatus.RETIRED}),
    SourceStatus.ACTIVE: frozenset({SourceStatus.PAUSED, SourceStatus.RETIRED}),
    SourceStatus.PAUSED: frozenset({SourceStatus.ACTIVE, SourceStatus.RETIRED}),
    SourceStatus.RETIRED: frozenset(),
}


@dataclass(slots=True)
class Source(EventRecorder):
    source_id: SourceId
    jurisdiction_id: JurisdictionId
    name: str
    source_family: str
    status: SourceStatus = SourceStatus.DRAFT
    version: int = 0

    def __post_init__(self) -> None:
        self._initialize_events()
        if not self.name.strip():
            raise InvariantViolation("source name is required")
        if not self.source_family.strip():
            raise InvariantViolation("source family is required")

    def transition_to(self, requested: SourceStatus, occurred_at: UtcTimestamp) -> None:
        if requested == self.status:
            return
        if requested not in _SOURCE_TRANSITIONS[self.status]:
            raise InvalidStateTransition("Source", self.status, requested)
        previous = self.status
        self.status = requested
        self.version += 1
        self._record(state_change_event(self, self.source_id, previous, requested, occurred_at))
