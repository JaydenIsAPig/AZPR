"""Domain events emitted by aggregate state changes."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from uuid import uuid4

from .value_objects import UtcTimestamp


@dataclass(frozen=True, slots=True, kw_only=True)
class DomainEvent:
    aggregate_id: str
    occurred_at: UtcTimestamp
    event_id: str = field(default_factory=lambda: str(uuid4()))


@dataclass(frozen=True, slots=True, kw_only=True)
class StateChanged(DomainEvent):
    aggregate_type: str
    previous_state: str
    current_state: str


@dataclass(frozen=True, slots=True, kw_only=True)
class ArtifactRegistered(DomainEvent):
    source_id: str
    artifact_id: str


@dataclass(frozen=True, slots=True, kw_only=True)
class ClassificationReviewed(DomainEvent):
    permit_id: str
    review_status: str


@dataclass(frozen=True, slots=True, kw_only=True)
class OpportunityMatchCreated(DomainEvent):
    opportunity_id: str
    customer_account_id: str


@dataclass(frozen=True, slots=True, kw_only=True)
class ConfigurationChanged(DomainEvent):
    configuration_type: str
    configuration_key: str


class EventRecorder:
    """Small aggregate helper; persistence publishes pulled events through an outbox."""

    _domain_events: list[DomainEvent]

    def _initialize_events(self) -> None:
        self._domain_events = []

    def _record(self, event: DomainEvent) -> None:
        self._domain_events.append(event)

    def pull_domain_events(self) -> tuple[DomainEvent, ...]:
        events = tuple(self._domain_events)
        self._domain_events.clear()
        return events


def state_change_event(
    aggregate: Any,
    aggregate_id: object,
    previous: object,
    current: object,
    occurred_at: UtcTimestamp,
) -> StateChanged:
    return StateChanged(
        aggregate_id=str(aggregate_id),
        occurred_at=occurred_at,
        aggregate_type=type(aggregate).__name__,
        previous_state=str(getattr(previous, "value", previous)),
        current_state=str(getattr(current, "value", current)),
    )
