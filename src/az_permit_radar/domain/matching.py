"""Explainable Customer Match and customer-scoped lead workflow."""

from __future__ import annotations

from dataclasses import dataclass, fields
from decimal import Decimal, InvalidOperation
from enum import Enum

from .customer import CustomerFilter, CustomerTradePreference, ServiceTerritory
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
        if not value.is_finite() or not Decimal("0") <= value <= Decimal("100"):
            raise InvariantViolation("match score component must be between zero and 100")
        object.__setattr__(self, "value", value)


@dataclass(frozen=True, slots=True)
class ScorePolicySnapshot:
    policy_id: str
    version: str
    component_weights: tuple[tuple[str, Decimal], ...]
    freshness_full_days: int
    freshness_partial_days: int
    unknown_source_date_factor: Decimal
    exclusion_reason_codes: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.policy_id.strip() or not self.version.strip():
            raise InvariantViolation("score policy snapshot identity is required")
        if len({name for name, _ in self.component_weights}) != len(self.component_weights):
            raise InvariantViolation("score policy snapshot component names must be unique")
        if sum((Decimal(value) for _, value in self.component_weights), Decimal("0")) != Decimal("100"):
            raise InvariantViolation("score policy snapshot weights must total 100")
        if not 0 <= self.freshness_full_days <= self.freshness_partial_days:
            raise InvariantViolation("score policy snapshot freshness boundaries are invalid")
        if not Decimal("0") <= Decimal(self.unknown_source_date_factor) <= Decimal("1"):
            raise InvariantViolation("score policy snapshot unknown-date factor is invalid")
        if not self.exclusion_reason_codes or len(set(self.exclusion_reason_codes)) != len(self.exclusion_reason_codes):
            raise InvariantViolation("score policy snapshot requires unique exclusion reason codes")


@dataclass(frozen=True, slots=True)
class CustomerConfigurationSnapshot:
    version: int
    trade_preferences: tuple[CustomerTradePreference, ...]
    service_territory: ServiceTerritory | None
    customer_filter: CustomerFilter | None
    notification_readiness_channels: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.version < 0 or any(not value.strip() for value in self.notification_readiness_channels):
            raise InvariantViolation("customer configuration snapshot is invalid")


@dataclass(frozen=True, slots=True)
class TerritoryEvaluationSnapshot:
    matched_rule: str
    inside_territory: bool
    location_verified: bool
    distance: Decimal | None = None
    distance_unit: str | None = None
    exclusion_reason: str | None = None

    def __post_init__(self) -> None:
        if not self.matched_rule.strip():
            raise InvariantViolation("territory evaluation snapshot requires a rule")
        if self.distance is not None and (self.distance_unit is None or not self.distance_unit.strip()):
            raise InvariantViolation("territory distance requires explicit units")


@dataclass(frozen=True, slots=True)
class FreshnessEvaluationSnapshot:
    source_date: CalendarDate | None
    source_date_basis: str
    acquisition_timestamp: UtcTimestamp | None
    processing_timestamp: UtcTimestamp
    evaluated_on: CalendarDate
    source_age_days: int | None
    acquisition_age_days: int | None

    def __post_init__(self) -> None:
        if not self.source_date_basis.strip():
            raise InvariantViolation("freshness snapshot source-date basis is required")
        if self.source_date is None and self.source_age_days is not None:
            raise InvariantViolation("unknown source date cannot have source age")
        if self.source_date is not None and self.source_age_days is None:
            raise InvariantViolation("known source date requires source age")
        if self.acquisition_timestamp is None and self.acquisition_age_days is not None:
            raise InvariantViolation("missing acquisition timestamp cannot have acquisition age")


@dataclass(frozen=True, slots=True)
class MatchExplanation:
    matching_trade_tag_ids: frozenset[TradeTagId]
    geographic_rule: str
    relevant_filters: tuple[str, ...]
    score_components: tuple[MatchScoreComponent, ...]
    exclusions_considered: tuple[str, ...]
    source_freshness_date: CalendarDate | None
    confidence: Confidence
    score_version: str = "legacy-1"
    total_score: Decimal | None = None
    matched_rules: tuple[str, ...] = ()
    exclusion_rules: tuple[str, ...] = ()
    human_readable: str = "Legacy explainable customer match."
    customer_configuration_version: int = 0
    score_policy_snapshot: ScorePolicySnapshot | None = None
    customer_configuration_snapshot: CustomerConfigurationSnapshot | None = None
    territory_evaluation_snapshot: TerritoryEvaluationSnapshot | None = None
    freshness_evaluation_snapshot: FreshnessEvaluationSnapshot | None = None
    calculated_at: UtcTimestamp | None = None
    opportunity_revision: int = 1
    publication_confidence_threshold: Confidence | None = None

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
        if not self.score_version.strip() or not self.human_readable.strip():
            raise InvariantViolation("match score version and human-readable explanation are required")
        if self.customer_configuration_version < 0:
            raise InvariantViolation("customer configuration version cannot be negative")
        if self.opportunity_revision < 1:
            raise InvariantViolation("match explanation Opportunity revision must be positive")
        calculated = sum((component.value for component in self.score_components), Decimal("0"))
        total = calculated if self.total_score is None else Decimal(self.total_score)
        if not Decimal("0") <= total <= Decimal("100") or total != calculated:
            raise InvariantViolation("match total must equal component values and stay within 100 points")
        object.__setattr__(self, "total_score", total)
        for collection in (self.matched_rules, self.exclusion_rules):
            if any(not value.strip() for value in collection):
                raise InvariantViolation("match rule identifiers cannot be blank")
        if self.score_version.startswith("opportunity-score-") and any(
            value is None
            for value in (
                self.score_policy_snapshot,
                self.customer_configuration_snapshot,
                self.territory_evaluation_snapshot,
                self.freshness_evaluation_snapshot,
                self.calculated_at,
                self.publication_confidence_threshold,
            )
        ):
            raise InvariantViolation("governed match explanation requires immutable evaluation snapshots")

    def replay_key(self) -> tuple[tuple[str, object], ...]:
        """Effective score inputs/output excluding the time this replay was attempted."""
        return tuple(
            (field.name, getattr(self, field.name))
            for field in fields(self)
            if field.name != "calculated_at"
        )


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
    STALE = "stale"
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
    score_history: tuple[MatchExplanation, ...] = ()

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

    def recalculate(self, explanation: MatchExplanation, occurred_at: UtcTimestamp) -> None:
        if self.status not in {OpportunityMatchStatus.ACTIVE, OpportunityMatchStatus.STALE} or self.lead_state is LeadState.DISMISSED:
            raise InvariantViolation("ended or dismissed match cannot be recalculated")
        if self.explanation.replay_key() == explanation.replay_key():
            if self.status is OpportunityMatchStatus.STALE:
                self.status = OpportunityMatchStatus.ACTIVE
                self.status_reason = None
            return
        self.score_history = (*self.score_history, self.explanation)
        self.explanation = explanation
        self.matched_at = occurred_at
        self.status = OpportunityMatchStatus.ACTIVE
        self.status_reason = None
        self.version += 1

    def mark_stale(self, reason: str, occurred_at: UtcTimestamp) -> None:
        if not reason.strip():
            raise InvariantViolation("stale Match reason is required")
        if self.status is OpportunityMatchStatus.STALE:
            return
        if self.status is not OpportunityMatchStatus.ACTIVE:
            return
        previous = self.status
        self.status = OpportunityMatchStatus.STALE
        self.status_reason = reason
        self.version += 1
        self._record(state_change_event(self, self.opportunity_match_id, previous, self.status, occurred_at))

    def exclude(self, reason: str, occurred_at: UtcTimestamp) -> None:
        self._end(OpportunityMatchStatus.EXCLUDED, reason, occurred_at)

    def expire(self, reason: str, occurred_at: UtcTimestamp) -> None:
        self._end(OpportunityMatchStatus.EXPIRED, reason, occurred_at)

    def _end(self, requested: OpportunityMatchStatus, reason: str, occurred_at: UtcTimestamp) -> None:
        if self.status not in {OpportunityMatchStatus.ACTIVE, OpportunityMatchStatus.STALE}:
            raise InvalidStateTransition("OpportunityMatch", self.status, requested)
        if not reason.strip():
            raise InvariantViolation("opportunity match status reason is required")
        previous = self.status
        self.status = requested
        self.status_reason = reason
        self.version += 1
        self._record(state_change_event(self, self.opportunity_match_id, previous, requested, occurred_at))
