"""Customer-independent Opportunity aggregate."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .errors import InvalidStateTransition, InvariantViolation
from .events import EventRecorder, state_change_event
from .value_objects import (
    CalendarDate,
    ClassificationResultId,
    Confidence,
    JurisdictionId,
    Money,
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


class OpportunityProjectionStatus(str, Enum):
    CURRENT = "current"
    SUPERSEDED = "superseded"


class SourceFreshnessBasis(str, Enum):
    ISSUED_ON = "issued_on"
    APPLIED_ON = "applied_on"
    UNKNOWN = "unknown"


_OPPORTUNITY_TRANSITIONS = {
    OpportunityStatus.CANDIDATE: frozenset({OpportunityStatus.PUBLISHED, OpportunityStatus.SUPPRESSED}),
    OpportunityStatus.PUBLISHED: frozenset({OpportunityStatus.SUPPRESSED, OpportunityStatus.EXPIRED}),
    OpportunityStatus.SUPPRESSED: frozenset(),
    OpportunityStatus.EXPIRED: frozenset(),
}


@dataclass(frozen=True, slots=True)
class OpportunityProjectionSnapshot:
    projection_fingerprint: str
    projection_revision: int
    projection_status: OpportunityProjectionStatus
    generated_at: UtcTimestamp
    superseded_at: UtcTimestamp
    permit_ids: frozenset[PermitId]
    classification_result_ids: frozenset[ClassificationResultId]
    trade_tag_ids: frozenset[TradeTagId]
    headline: str
    concise_description: str
    location: str | None
    jurisdiction_id: JurisdictionId | None
    permit_date: CalendarDate | None
    project_category_codes: frozenset[str]
    value_signal: Money | None
    value_band: str
    completeness_indicator: str
    confidence: Confidence
    source_freshness_date: CalendarDate | None
    source_freshness_basis: SourceFreshnessBasis
    source_acquired_at: UtcTimestamp | None
    processing_recorded_at: UtcTimestamp
    permit_version: int
    parser_version: str
    classification_versions: tuple[str, ...]
    rule_set_versions: tuple[str, ...]


@dataclass(slots=True)
class Opportunity(EventRecorder):
    opportunity_id: OpportunityId
    permit_ids: frozenset[PermitId]
    classification_result_ids: frozenset[ClassificationResultId]
    trade_tag_ids: frozenset[TradeTagId]
    created_at: UtcTimestamp
    headline: str = "Legacy permit opportunity"
    concise_description: str = "Source-backed permit opportunity."
    location: str | None = None
    jurisdiction_id: JurisdictionId | None = None
    permit_date: CalendarDate | None = None
    project_category_codes: frozenset[str] = frozenset()
    value_signal: Money | None = None
    value_band: str = "unknown"
    completeness_indicator: str = "unknown"
    confidence: Confidence = Confidence(0)
    source_freshness_date: CalendarDate | None = None
    factual_wording_basis: str = "source_observed_and_deterministic"
    projection_fingerprint: str = "legacy"
    projection_revision: int = 1
    permit_version: int = 0
    parser_version: str = "legacy"
    classification_versions: tuple[str, ...] = ()
    rule_set_versions: tuple[str, ...] = ()
    source_freshness_basis: SourceFreshnessBasis = SourceFreshnessBasis.UNKNOWN
    source_acquired_at: UtcTimestamp | None = None
    processing_recorded_at: UtcTimestamp | None = None
    updated_at: UtcTimestamp | None = None
    projection_history: tuple[OpportunityProjectionSnapshot, ...] = ()
    status: OpportunityStatus = OpportunityStatus.CANDIDATE
    status_reason: str | None = None
    version: int = 0

    def __post_init__(self) -> None:
        self._initialize_events()
        if self.processing_recorded_at is None:
            self.processing_recorded_at = self.created_at
        if self.updated_at is None:
            self.updated_at = self.created_at
        if not self.permit_ids:
            raise InvariantViolation("opportunity requires at least one permit")
        if not self.classification_result_ids:
            raise InvariantViolation("opportunity requires at least one classification result")
        if not self.trade_tag_ids:
            raise InvariantViolation("opportunity requires at least one trade tag")
        if any(not value.strip() for value in (self.headline, self.concise_description, self.value_band, self.completeness_indicator, self.factual_wording_basis)):
            raise InvariantViolation("opportunity projection text fields are required")
        if any(not code.strip() for code in self.project_category_codes):
            raise InvariantViolation("opportunity project category codes cannot be blank")
        if not self.projection_fingerprint.strip() or not self.parser_version.strip():
            raise InvariantViolation("opportunity projection fingerprint and parser version are required")
        if self.projection_revision < 1 or self.permit_version < 0:
            raise InvariantViolation("opportunity projection and Permit versions are invalid")
        if any(not value.strip() for value in (*self.classification_versions, *self.rule_set_versions)):
            raise InvariantViolation("opportunity classification and rule-set versions cannot be blank")
        if self.source_freshness_basis is SourceFreshnessBasis.UNKNOWN and self.source_freshness_date is not None:
            raise InvariantViolation("unknown source freshness cannot claim a source date")
        if self.source_freshness_basis is not SourceFreshnessBasis.UNKNOWN and self.source_freshness_date is None:
            raise InvariantViolation("known source freshness requires a source date")

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

    def regenerate_from(self, replacement: Opportunity, occurred_at: UtcTimestamp) -> None:
        if replacement.opportunity_id != self.opportunity_id or replacement.permit_ids != self.permit_ids:
            raise InvariantViolation("Opportunity regeneration must retain logical identity and canonical Permits")
        if replacement.projection_fingerprint == self.projection_fingerprint:
            return
        if self.status not in {OpportunityStatus.CANDIDATE, OpportunityStatus.PUBLISHED}:
            raise InvalidStateTransition("Opportunity", self.status, OpportunityStatus.PUBLISHED)
        if replacement.projection_revision != self.projection_revision + 1:
            raise InvariantViolation("Opportunity regeneration must advance exactly one projection revision")
        self.projection_history = (*self.projection_history, self._superseded_snapshot(occurred_at))
        for name in (
            "classification_result_ids",
            "trade_tag_ids",
            "headline",
            "concise_description",
            "location",
            "jurisdiction_id",
            "permit_date",
            "project_category_codes",
            "value_signal",
            "value_band",
            "completeness_indicator",
            "confidence",
            "source_freshness_date",
            "factual_wording_basis",
            "projection_fingerprint",
            "projection_revision",
            "permit_version",
            "parser_version",
            "classification_versions",
            "rule_set_versions",
            "source_freshness_basis",
            "source_acquired_at",
            "processing_recorded_at",
        ):
            setattr(self, name, getattr(replacement, name))
        self.updated_at = occurred_at
        self.status = OpportunityStatus.PUBLISHED
        self.status_reason = "material projection inputs changed; prior revision superseded"
        self.version += 1

    def _superseded_snapshot(self, occurred_at: UtcTimestamp) -> OpportunityProjectionSnapshot:
        return OpportunityProjectionSnapshot(
            projection_fingerprint=self.projection_fingerprint,
            projection_revision=self.projection_revision,
            projection_status=OpportunityProjectionStatus.SUPERSEDED,
            generated_at=self.updated_at or self.created_at,
            superseded_at=occurred_at,
            permit_ids=self.permit_ids,
            classification_result_ids=self.classification_result_ids,
            trade_tag_ids=self.trade_tag_ids,
            headline=self.headline,
            concise_description=self.concise_description,
            location=self.location,
            jurisdiction_id=self.jurisdiction_id,
            permit_date=self.permit_date,
            project_category_codes=self.project_category_codes,
            value_signal=self.value_signal,
            value_band=self.value_band,
            completeness_indicator=self.completeness_indicator,
            confidence=self.confidence,
            source_freshness_date=self.source_freshness_date,
            source_freshness_basis=self.source_freshness_basis,
            source_acquired_at=self.source_acquired_at,
            processing_recorded_at=self.processing_recorded_at or self.created_at,
            permit_version=self.permit_version,
            parser_version=self.parser_version,
            classification_versions=self.classification_versions,
            rule_set_versions=self.rule_set_versions,
        )
