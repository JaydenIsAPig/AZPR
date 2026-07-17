"""Explainable Customer Match and customer-scoped lead workflow."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from enum import Enum

from .errors import InvalidStateTransition, InvariantViolation
from .events import EventRecorder, OpportunityMatchCreated, state_change_event
from .value_objects import (
    CalendarDate,
    Confidence,
    CustomerAccountId,
    OpportunityId,
    OpportunityMatchId,
    TradeTagId,
    UtcTimestamp,
)


@dataclass(frozen=True, slots=True)
class MatchScoreComponent:
    name: str
    value: Decimal
    rationale: str

    def __post_init__(self) -> None:
        if not self.name.strip() or not self.rationale.strip():
            raise InvariantViolation("match score component name and rationale are required")
        try:
            value = Decimal(self.value)
        except (InvalidOperation, TypeError) as exc:
            raise InvariantViolation("match score component must be decimal-compatible") from exc
        if not value.is_finite():
            raise InvariantViolation("match score component must be finite")
        object.__setattr__(self, "value", value)


@dataclass(frozen=True, slots=True)
class MatchExplanation:
    matching_trade_tag_ids: frozenset[TradeTagId]
    geographic_rule: str
    relevant_filters: tuple[str, ...]
    score_components: tuple[MatchScoreComponent, ...]
    exclusions_considered: tuple[str, ...]
    source_freshness_date: CalendarDate
    confidence: Confidence

    def __post_init__(self) -> None:
        if not self.matching_trade_tag_ids:
            raise InvariantViolation("match explanation requires at least one matching trade tag")
        if not self.geographic_rule.strip():
            raise InvariantViolation("match explanation requires a geographic rule")
        if not self.score_components:
            raise InvariantViolation("match explanation requires score components")
        names = [component.name for component in self.score_components]
        if len(names) != len(set(names)):
            raise InvariantViolation("match score component names must be unique")
        for collection in (self.relevant_filters, self.exclusions_considered):
            if any(not value.strip() for value in collection):
                raise InvariantViolation("match explanation entries cannot be blank")


class LeadState(str, Enum):
    NEW = "new"
    SAVED = "saved"
    CONTACTED = "contacted"
    DISMISSED = "dismissed"


_LEAD_TRANSITIONS = {
    LeadState.NEW: frozenset({LeadState.SAVED, LeadState.CONTACTED, LeadState.DISMISSED}),
    LeadState.SAVED: frozenset({LeadState.CONTACTED, LeadState.DISMISSED}),
    LeadState.CONTACTED: frozenset({LeadState.DISMISSED}),
    LeadState.DISMISSED: frozenset(),
}


class OpportunityMatchStatus(str, Enum):
    ACTIVE = "active"
    EXCLUDED = "excluded"
    EXPIRED = "expired"


@dataclass(slots=True)
class OpportunityMatch(EventRecorder):
    opportunity_match_id: OpportunityMatchId
    opportunity_id: OpportunityId
    customer_account_id: CustomerAccountId
    explanation: MatchExplanation
    matched_at: UtcTimestamp
    status: OpportunityMatchStatus = OpportunityMatchStatus.ACTIVE
    lead_state: LeadState = LeadState.NEW
    status_reason: str | None = None
    version: int = 0

    def __post_init__(self) -> None:
        self._initialize_events()

    @classmethod
    def create(
        cls,
        opportunity_match_id: OpportunityMatchId,
        opportunity_id: OpportunityId,
        customer_account_id: CustomerAccountId,
        explanation: MatchExplanation,
        matched_at: UtcTimestamp,
    ) -> OpportunityMatch:
        match = cls(
            opportunity_match_id=opportunity_match_id,
            opportunity_id=opportunity_id,
            customer_account_id=customer_account_id,
            explanation=explanation,
            matched_at=matched_at,
        )
        match._record(
            OpportunityMatchCreated(
                aggregate_id=str(opportunity_match_id),
                occurred_at=matched_at,
                opportunity_id=str(opportunity_id),
                customer_account_id=str(customer_account_id),
            )
        )
        return match

    def change_lead_state(self, requested: LeadState, occurred_at: UtcTimestamp) -> None:
        if self.status is not OpportunityMatchStatus.ACTIVE:
            raise InvariantViolation("lead state can change only on an active opportunity match")
        if requested == self.lead_state:
            return
        if requested not in _LEAD_TRANSITIONS[self.lead_state]:
            raise InvalidStateTransition("LeadState", self.lead_state, requested)
        previous = self.lead_state
        self.lead_state = requested
        self.version += 1
        self._record(state_change_event(self, self.opportunity_match_id, previous, requested, occurred_at))

    def exclude(self, reason: str, occurred_at: UtcTimestamp) -> None:
        self._end(OpportunityMatchStatus.EXCLUDED, reason, occurred_at)

    def expire(self, reason: str, occurred_at: UtcTimestamp) -> None:
        self._end(OpportunityMatchStatus.EXPIRED, reason, occurred_at)

    def _end(self, requested: OpportunityMatchStatus, reason: str, occurred_at: UtcTimestamp) -> None:
        if self.status is not OpportunityMatchStatus.ACTIVE:
            raise InvalidStateTransition("OpportunityMatch", self.status, requested)
        if not reason.strip():
            raise InvariantViolation("opportunity match status reason is required")
        previous = self.status
        self.status = requested
        self.status_reason = reason
        self.version += 1
        self._record(state_change_event(self, self.opportunity_match_id, previous, requested, occurred_at))
