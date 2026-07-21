"""Deterministic Opportunity projection and explainable customer matching."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Callable, Protocol, TypeVar

from az_permit_radar.domain.eligibility import (
    EligibilityDecision,
    EligibilityReason,
    PublicationEligibilityError,
    PublicationEligibilityPolicy,
)
from az_permit_radar.domain.classification import ClassificationResult
from az_permit_radar.domain.customer import CustomerAccount, CustomerAccountStatus
from az_permit_radar.domain.errors import InvariantViolation
from az_permit_radar.domain.matching import (
    CustomerConfigurationSnapshot,
    FreshnessEvaluationSnapshot,
    LeadState,
    MatchExplanation,
    MatchScoreComponent,
    OpportunityMatch,
    OpportunityMatchStatus,
    ScorePolicySnapshot,
    TerritoryEvaluationSnapshot,
)
from az_permit_radar.domain.opportunity import Opportunity, OpportunityStatus, SourceFreshnessBasis
from az_permit_radar.domain.permit import Permit
from az_permit_radar.domain.value_objects import CalendarDate, Confidence, CustomerAccountId, OpportunityId, OpportunityMatchId, PermitId, UtcTimestamp


ExclusiveResultT = TypeVar("ExclusiveResultT")


class OpportunityStore(Protocol):
    def get(self, opportunity_id: OpportunityId) -> Opportunity | None: ...
    def save(self, opportunity: Opportunity) -> None: ...
    def run_exclusive(self, operation: Callable[[], ExclusiveResultT]) -> ExclusiveResultT: ...


class OpportunityMatchStore(Protocol):
    def find_for(self, opportunity_id: OpportunityId, customer_account_id: CustomerAccountId) -> OpportunityMatch | None: ...
    def save(self, match: OpportunityMatch) -> None: ...
    def mark_stale_for_opportunity(self, opportunity_id: OpportunityId, reason: str, occurred_at: UtcTimestamp) -> None: ...
    def run_exclusive(self, operation: Callable[[], ExclusiveResultT]) -> ExclusiveResultT: ...


class CurrentClassificationState(Protocol):
    def find_current_for_permit(self, permit_id: PermitId) -> ClassificationResult | None: ...


class TerritoryEvaluationView(Protocol):
    inside_territory: bool
    matched_rule: str | None
    location_verified: bool
    distance_from_origin: Decimal | None
    distance_unit: object | None
    exclusion_reason: str | None


class OpportunityTerritoryEvaluator(Protocol):
    def evaluate_opportunity(self, *, requesting_customer_id: CustomerAccountId, customer: CustomerAccount, opportunity: Opportunity, permits: tuple[Permit, ...]) -> TerritoryEvaluationView: ...


_GOVERNED_EXCLUSION_CODES = tuple(reason.value for reason in EligibilityReason) + (
    "opportunity_projection_not_current",
    "account_not_active", "trade_mismatch", "outside_service_territory",
    "minimum_value", "maximum_value", "value_band", "permit_filter",
    "project_filter", "confidence_filter", "date_filter",
)


@dataclass(frozen=True, slots=True)
class ScorePolicy:
    version: str
    weights: dict[str, Decimal]
    freshness_full_days: int
    freshness_partial_days: int
    policy_id: str = "opportunity-match-score"
    unknown_source_date_factor: Decimal = Decimal("0")
    exclusion_reason_codes: tuple[str, ...] = _GOVERNED_EXCLUSION_CODES

    def __post_init__(self) -> None:
        required = {"trade", "geography", "value", "completeness", "freshness", "notification_readiness"}
        try:
            normalized = {name: Decimal(value) for name, value in self.weights.items()}
        except (InvalidOperation, TypeError) as exc:
            raise InvariantViolation("score weights must be decimal-compatible") from exc
        if set(normalized) != required or sum(normalized.values(), Decimal("0")) != Decimal("100"):
            raise InvariantViolation("versioned score weights must define the six components and total 100")
        if any(value < 0 for value in normalized.values()) or not self.version.strip() or not self.policy_id.strip():
            raise InvariantViolation("score weights must be non-negative and policy/version identified")
        if not 0 <= self.freshness_full_days <= self.freshness_partial_days:
            raise InvariantViolation("freshness day boundaries are invalid")
        unknown_factor = Decimal(self.unknown_source_date_factor)
        if not Decimal("0") <= unknown_factor <= Decimal("1"):
            raise InvariantViolation("unknown source-date factor must be between zero and one")
        if tuple(dict.fromkeys(self.exclusion_reason_codes)) != self.exclusion_reason_codes:
            raise InvariantViolation("score-policy exclusion reason codes must be unique")
        if set(self.exclusion_reason_codes) != set(_GOVERNED_EXCLUSION_CODES):
            raise InvariantViolation("score policy must govern every stable matching exclusion reason")
        object.__setattr__(self, "weights", normalized)
        object.__setattr__(self, "unknown_source_date_factor", unknown_factor)


@dataclass(frozen=True, slots=True)
class OpportunityProjectionPolicy:
    version: str
    source_date_precedence: tuple[str, ...]
    completeness_fields: tuple[str, ...]
    acquisition_timestamp_role: str
    processing_timestamp_role: str
    unknown_source_date_behavior: str = "zero_source_freshness_credit"
    valuation_in_completeness: bool = False

    def __post_init__(self) -> None:
        allowed_dates = {"issued_on", "applied_on"}
        allowed_completeness = {"permit_type", "description", "address", "permit_date"}
        if not self.version.strip() or set(self.source_date_precedence) != allowed_dates:
            raise InvariantViolation("projection policy requires issued/applied source-date precedence")
        if set(self.completeness_fields) != allowed_completeness or "valuation" in self.completeness_fields:
            raise InvariantViolation("projection completeness must use the four governed non-valuation fields")
        if self.acquisition_timestamp_role != "context_only" or self.processing_timestamp_role != "provenance_only":
            raise InvariantViolation("projection timestamp roles must preserve source/acquisition/processing distinctions")
        if self.unknown_source_date_behavior != "zero_source_freshness_credit":
            raise InvariantViolation("unknown source dates must receive zero freshness credit")
        if self.valuation_in_completeness:
            raise InvariantViolation("valuation cannot contribute to both value and completeness")


@dataclass(frozen=True, slots=True)
class MatchGenerationResult:
    match: OpportunityMatch | None
    exclusion_rules: tuple[str, ...]
    human_readable: str


class OpportunityGenerator:
    def __init__(
        self,
        opportunities: OpportunityStore,
        eligibility: PublicationEligibilityPolicy,
        classifications: CurrentClassificationState,
        matches: OpportunityMatchStore,
        projection_policy: OpportunityProjectionPolicy,
    ) -> None:
        self._opportunities = opportunities
        self._eligibility = eligibility
        self._classifications = classifications
        self._matches = matches
        self._projection_policy = projection_policy

    def generate(self, permit: Permit, occurred_at: UtcTimestamp) -> Opportunity:
        return self._opportunities.run_exclusive(lambda: self._generate(permit, occurred_at))

    def _generate(self, permit: Permit, occurred_at: UtcTimestamp) -> Opportunity:
        current = self._classifications.find_current_for_permit(permit.permit_id)
        applicable = (current,) if current is not None else ()
        digest = hashlib.sha256(str(permit.permit_id).encode()).hexdigest()
        opportunity_id = OpportunityId(f"opportunity-{digest}")
        existing = self._opportunities.get(opportunity_id)
        decision = self._eligibility.evaluate_generation(
            permit=permit,
            classifications=applicable,
        )
        if not decision.eligible:
            if existing is not None and existing.status in {
                OpportunityStatus.CANDIDATE,
                OpportunityStatus.PUBLISHED,
            }:
                existing.transition_to(
                    OpportunityStatus.SUPPRESSED,
                    f"publication eligibility blocked: {', '.join(decision.reasons)}",
                    occurred_at,
                )
                self._opportunities.save(existing)
            raise PublicationEligibilityError(decision)
        projected = self._project(
            permit,
            current,
            opportunity_id,
            occurred_at,
            projection_revision=(existing.projection_revision + 1 if existing is not None else 1),
        )
        if existing is not None:
            if existing.projection_fingerprint != projected.projection_fingerprint:
                existing.regenerate_from(projected, occurred_at)
                self._opportunities.save(existing)
                self._matches.mark_stale_for_opportunity(
                    existing.opportunity_id,
                    f"Opportunity projection advanced to revision {existing.projection_revision}",
                    occurred_at,
                )
                return existing
            if existing.status is OpportunityStatus.CANDIDATE:
                existing.transition_to(
                    OpportunityStatus.PUBLISHED,
                    "central publication eligibility satisfied",
                    occurred_at,
                )
                self._opportunities.save(existing)
            elif existing.status is not OpportunityStatus.PUBLISHED:
                raise PublicationEligibilityError(
                    EligibilityDecision((EligibilityReason.OPPORTUNITY_NOT_PUBLISHABLE.value,))
                )
            return existing
        projected.transition_to(
            OpportunityStatus.PUBLISHED,
            "central publication eligibility satisfied",
            occurred_at,
        )
        self._opportunities.save(projected)
        return projected

    def _project(
        self,
        permit: Permit,
        current: ClassificationResult | None,
        opportunity_id: OpportunityId,
        occurred_at: UtcTimestamp,
        *,
        projection_revision: int,
    ) -> Opportunity:
        applicable = (current,) if current is not None else ()
        categories = frozenset(item.project_classification.code for item in applicable)
        trades = frozenset(tag.trade_tag_id for item in applicable for tag in item.trade_tags)
        confidence = min((item.confidence.value for item in applicable), default=Decimal("0"))
        permit_date, freshness_basis = self._source_freshness(permit)
        source_acquired_at = max(
            (evidence.acquired_at for evidence in permit.source_evidence if evidence.acquired_at is not None),
            key=lambda value: value.value,
            default=None,
        )
        processing_recorded_at = max(
            (permit.recorded_at, *(entry.occurred_at for entry in permit.history)),
            key=lambda value: value.value,
        )
        location = None
        if permit.address and permit.address.normalized:
            normalized = permit.address.normalized
            location = f"{normalized.city}, {normalized.region_code} {normalized.postal_code[:5]}"
        type_label = permit.permit_type.label if permit.permit_type else "Permit"
        description = self._safe_description(permit.description)
        completeness = self._completeness(permit)
        value_band = self._value_band(permit)
        projection_fingerprint = self._projection_fingerprint(
            permit=permit,
            classification=current,
            headline_type=type_label,
            safe_description=description,
            location=location,
            categories=categories,
            trades=trades,
            value_band=value_band,
            completeness=completeness,
            source_freshness_basis=freshness_basis,
            source_acquired_at=source_acquired_at,
            processing_recorded_at=processing_recorded_at,
        )
        return Opportunity(
            opportunity_id, frozenset({permit.permit_id}),
            frozenset(item.classification_result_id for item in applicable), trades, occurred_at,
            headline=f"{type_label} opportunity in {location or str(permit.jurisdiction_id)}",
            concise_description=f"The source permit record describes {description}." if description else "The source permit record does not provide a work description.",
            location=location, jurisdiction_id=permit.jurisdiction_id, permit_date=permit_date,
            project_category_codes=categories, value_signal=permit.valuation,
            value_band=value_band, completeness_indicator=completeness,
            confidence=Confidence(confidence), source_freshness_date=permit_date,
            projection_fingerprint=projection_fingerprint,
            projection_revision=projection_revision,
            permit_version=permit.version,
            parser_version=permit.parser_version,
            classification_versions=tuple(sorted(item.classification_version for item in applicable)),
            rule_set_versions=tuple(sorted(item.rule_set_version for item in applicable)),
            source_freshness_basis=freshness_basis,
            source_acquired_at=source_acquired_at,
            processing_recorded_at=processing_recorded_at,
        )

    def _projection_fingerprint(
        self,
        *,
        permit: Permit,
        classification: ClassificationResult | None,
        headline_type: str,
        safe_description: str | None,
        location: str | None,
        categories: frozenset[str],
        trades: frozenset,
        value_band: str,
        completeness: str,
        source_freshness_basis: SourceFreshnessBasis,
        source_acquired_at: UtcTimestamp | None,
        processing_recorded_at: UtcTimestamp,
    ) -> str:
        payload = {
            "permit_id": str(permit.permit_id),
            "permit_version": permit.version,
            "permit_status": permit.status.value,
            "canonical_status": permit.canonical_status.value,
            "duplicate_candidate_id": str(permit.duplicate_candidate_id) if permit.duplicate_candidate_id else None,
            "parser_version": permit.parser_version,
            "projection_policy_version": self._projection_policy.version,
            "permit_number": permit.permit_number,
            "authority_status": permit.authority_status.value,
            "permit_type": permit.permit_type.code if permit.permit_type else None,
            "headline_type": headline_type,
            "safe_description": safe_description,
            "location": location,
            "address_key": permit.address.canonical_key() if permit.address else None,
            "parcel": permit.parcel_reference.value if permit.parcel_reference else None,
            "issued_on": permit.issued_on.value.isoformat() if permit.issued_on else None,
            "applied_on": permit.applied_on.value.isoformat() if permit.applied_on else None,
            "valuation": str(permit.valuation.amount) if permit.valuation else None,
            "value_band": value_band,
            "completeness": completeness,
            "categories": sorted(categories),
            "trades": sorted(str(value) for value in trades),
            "classification": (
                {
                    "id": str(classification.classification_result_id),
                    "classification_version": classification.classification_version,
                    "rule_set_version": classification.rule_set_version,
                    "revision": classification.revision,
                    "aggregate_version": classification.version,
                    "confidence": str(classification.confidence.value),
                }
                if classification is not None
                else None
            ),
            "freshness_basis": source_freshness_basis.value,
            "source_acquired_at": source_acquired_at.value.isoformat() if source_acquired_at else None,
            "processing_recorded_at": processing_recorded_at.value.isoformat(),
            "source_evidence": [
                {
                    "record_id": str(item.source_record_id),
                    "fingerprint": item.record_fingerprint,
                    "parser_version": item.parser_version,
                    "observed_at": item.observed_at.value.isoformat(),
                    "acquired_at": item.acquired_at.value.isoformat() if item.acquired_at else None,
                }
                for item in sorted(permit.source_evidence, key=lambda value: str(value.source_record_id))
            ],
        }
        return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()

    @staticmethod
    def _safe_description(value: str | None) -> str | None:
        if value is None:
            return None
        safe = re.sub(r"[\w.+-]+@[\w.-]+", "[contact removed]", value)
        safe = re.sub(r"\b(?:\+?1[-. ]?)?\(?\d{3}\)?[-. ]?\d{3}[-. ]?\d{4}\b", "[contact removed]", safe)
        return " ".join(safe.split())[:240] or None

    @staticmethod
    def _value_band(permit: Permit) -> str:
        if permit.valuation is None:
            return "unknown"
        amount = permit.valuation.amount
        return "under_25k" if amount < 25000 else "25k_to_100k" if amount < 100000 else "100k_to_500k" if amount < 500000 else "500k_plus"

    def _source_freshness(self, permit: Permit) -> tuple[CalendarDate | None, SourceFreshnessBasis]:
        for field_name in self._projection_policy.source_date_precedence:
            value = getattr(permit, field_name)
            if value is not None:
                return value, SourceFreshnessBasis(field_name)
        return None, SourceFreshnessBasis.UNKNOWN

    def _completeness(self, permit: Permit) -> str:
        values = {
            "permit_type": permit.permit_type,
            "description": permit.description,
            "address": permit.address,
            "permit_date": permit.issued_on or permit.applied_on,
        }
        present = sum(values[name] is not None and values[name] != "" for name in self._projection_policy.completeness_fields)
        total = len(self._projection_policy.completeness_fields)
        return "complete" if present == total else "partial" if present * 2 >= total else "sparse"


class ExplainableMatchGenerator:
    _EXCLUSIONS = _GOVERNED_EXCLUSION_CODES
    _EXCLUSION_MESSAGES = {
        "permit_missing": "a referenced Permit is unavailable",
        "permit_voided": "the Permit is voided",
        "permit_superseded": "the Permit is superseded",
        "probable_duplicate_unresolved": "the Permit has an unresolved probable duplicate",
        "noncanonical_permit": "the Permit is not canonical",
        "classification_missing": "the current Classification Result is missing or differs from the Opportunity revision",
        "classification_pending_review": "classification review is pending",
        "classification_rejected": "classification was rejected",
        "classification_confidence_below_publication_threshold": "classification confidence is below the publication threshold",
        "geography_unverified": "the Opportunity location could not be verified",
        "opportunity_not_publishable": "the Opportunity is not published",
        "opportunity_projection_not_current": "the supplied Opportunity projection is not the current persisted revision",
        "account_not_active": "the Customer Account is not active",
        "trade_mismatch": "no enabled customer trade matches",
        "outside_service_territory": "the Opportunity is outside the customer service territory",
        "minimum_value": "the source valuation is below the customer minimum",
        "maximum_value": "the source valuation is above the customer maximum",
        "value_band": "the value band is not allowed",
        "permit_filter": "the Permit type is excluded",
        "project_filter": "the project category is excluded",
        "confidence_filter": "confidence is below the customer threshold",
        "date_filter": "the Permit date is outside the customer date range",
    }

    def __init__(self, matches: OpportunityMatchStore, geography: OpportunityTerritoryEvaluator, policy: ScorePolicy, eligibility: PublicationEligibilityPolicy, classifications: CurrentClassificationState, opportunities: OpportunityStore) -> None:
        self._matches, self._geography, self.policy, self._eligibility, self._classifications, self._opportunities = matches, geography, policy, eligibility, classifications, opportunities

    def generate(self, *, opportunity: Opportunity, permits: tuple[Permit, ...], customer: CustomerAccount, evaluated_on: CalendarDate, occurred_at: UtcTimestamp) -> MatchGenerationResult:
        return self._matches.run_exclusive(
            lambda: self._generate(
                opportunity=opportunity,
                permits=permits,
                customer=customer,
                evaluated_on=evaluated_on,
                occurred_at=occurred_at,
            )
        )

    def _generate(self, *, opportunity: Opportunity, permits: tuple[Permit, ...], customer: CustomerAccount, evaluated_on: CalendarDate, occurred_at: UtcTimestamp) -> MatchGenerationResult:
        existing = self._matches.find_for(opportunity.opportunity_id, customer.customer_account_id)
        current = self._opportunities.get(opportunity.opportunity_id)
        if current is None or (
            current.projection_fingerprint != opportunity.projection_fingerprint
            or current.projection_revision != opportunity.projection_revision
            or current.status is not opportunity.status
        ):
            reasons = ("opportunity_projection_not_current",)
            return MatchGenerationResult(existing, reasons, self._exclusion_text(reasons))
        classifications = tuple(
            result
            for permit in permits
            if (result := self._classifications.find_current_for_permit(permit.permit_id)) is not None
        )
        preflight = self._eligibility.evaluate_matching(
            opportunity=opportunity,
            permits=permits,
            classifications=classifications,
            geography_verified=True,
        )
        if not preflight.eligible:
            readable = self._exclusion_text(preflight.reasons)
            if existing and (existing.lead_state is LeadState.DISMISSED or existing.status not in {OpportunityMatchStatus.ACTIVE, OpportunityMatchStatus.STALE}):
                return MatchGenerationResult(existing, preflight.reasons, readable)
            if existing:
                existing.exclude(readable, occurred_at)
                self._matches.save(existing)
                return MatchGenerationResult(existing, preflight.reasons, readable)
            return MatchGenerationResult(None, preflight.reasons, readable)
        geography = self._geography.evaluate_opportunity(requesting_customer_id=customer.customer_account_id, customer=customer, opportunity=opportunity, permits=permits)
        exclusions = self._exclusions(
            opportunity,
            permits,
            classifications,
            customer,
            evaluated_on,
            geography,
        )
        if existing and (existing.lead_state is LeadState.DISMISSED or existing.status not in {OpportunityMatchStatus.ACTIVE, OpportunityMatchStatus.STALE}):
            readable = (
                f"Existing dismissed or ended customer match retained. {self._exclusion_text(exclusions)}"
                if exclusions
                else "Existing dismissed or ended customer match retained."
            )
            return MatchGenerationResult(existing, exclusions, readable)
        if exclusions:
            readable = self._exclusion_text(exclusions)
            if existing:
                existing.exclude(readable, occurred_at)
                self._matches.save(existing)
                return MatchGenerationResult(existing, exclusions, readable)
            return MatchGenerationResult(None, exclusions, readable)
        matching_trades = frozenset(tag for tag in opportunity.trade_tag_ids if customer.trade_preferences.get(tag) and customer.trade_preferences[tag].enabled)
        explanation = self._explanation(
            opportunity,
            customer,
            matching_trades,
            geography,
            evaluated_on,
            occurred_at,
        )
        if existing and existing.status is OpportunityMatchStatus.ACTIVE and existing.explanation.replay_key() == explanation.replay_key():
            return MatchGenerationResult(existing, (), "Idempotent replay returned the existing customer match.")
        if existing:
            existing.recalculate(explanation, occurred_at)
            self._matches.save(existing)
            return MatchGenerationResult(existing, (), explanation.human_readable)
        seed = f"{opportunity.opportunity_id}:{customer.customer_account_id}".encode()
        match = OpportunityMatch.create(OpportunityMatchId(f"match-{hashlib.sha256(seed).hexdigest()}"), opportunity.opportunity_id, customer.customer_account_id, explanation, occurred_at)
        self._matches.save(match)
        return MatchGenerationResult(match, (), explanation.human_readable)

    def _exclusion_text(self, reasons: tuple[str, ...]) -> str:
        details = "; ".join(self._EXCLUSION_MESSAGES[reason] for reason in reasons)
        return f"Excluded: {details}."

    def _exclusions(self, opportunity: Opportunity, permits: tuple[Permit, ...], classifications: tuple[ClassificationResult, ...], customer: CustomerAccount, evaluated_on: CalendarDate, geography: TerritoryEvaluationView) -> tuple[str, ...]:
        decision = self._eligibility.evaluate_matching(
            opportunity=opportunity,
            permits=permits,
            classifications=classifications,
            geography_verified=geography.inside_territory and bool(getattr(geography, "location_verified", False)),
        )
        reasons: list[str] = list(decision.reasons)
        if customer.status is not CustomerAccountStatus.ACTIVE:
            reasons.append("account_not_active")
        enabled = {tag for tag, preference in customer.trade_preferences.items() if preference.enabled}
        if not opportunity.trade_tag_ids & enabled:
            reasons.append("trade_mismatch")
        if not geography.inside_territory:
            reasons.append("outside_service_territory")
        filters = customer.customer_filter
        if filters:
            if filters.minimum_valuation and (opportunity.value_signal is None or opportunity.value_signal.amount < filters.minimum_valuation.amount):
                reasons.append("minimum_value")
            if filters.maximum_valuation and opportunity.value_signal and opportunity.value_signal.amount > filters.maximum_valuation.amount:
                reasons.append("maximum_value")
            if filters.allowed_value_bands and opportunity.value_band not in filters.allowed_value_bands:
                reasons.append("value_band")
            permit_types = {permit.permit_type.code for permit in permits if permit.permit_type}
            if permit_types & filters.excluded_permit_type_codes:
                reasons.append("permit_filter")
            if opportunity.project_category_codes & filters.excluded_project_classification_codes:
                reasons.append("project_filter")
            if filters.minimum_confidence and opportunity.confidence.value < filters.minimum_confidence.value:
                reasons.append("confidence_filter")
            if filters.issued_during and (opportunity.permit_date is None or not filters.issued_during.starts_on.value <= opportunity.permit_date.value <= filters.issued_during.ends_on.value):
                reasons.append("date_filter")
        return tuple(dict.fromkeys(reasons))

    def _explanation(
        self,
        opportunity: Opportunity,
        customer: CustomerAccount,
        trades: frozenset,
        geography: TerritoryEvaluationView,
        evaluated_on: CalendarDate,
        calculated_at: UtcTimestamp,
    ) -> MatchExplanation:
        weights = self.policy.weights
        value_points = weights["value"] if opportunity.value_signal is not None else Decimal("0")
        completeness_factor = {"complete": Decimal("1"), "partial": Decimal("0.5")}.get(opportunity.completeness_indicator, Decimal("0"))
        source_age = (
            max(0, (evaluated_on.value - opportunity.source_freshness_date.value).days)
            if opportunity.source_freshness_date
            else None
        )
        acquisition_age = (
            max(0, (evaluated_on.value - opportunity.source_acquired_at.value.date()).days)
            if opportunity.source_acquired_at
            else None
        )
        freshness_factor = (
            Decimal("1")
            if source_age is not None and source_age <= self.policy.freshness_full_days
            else Decimal("0.5")
            if source_age is not None and source_age <= self.policy.freshness_partial_days
            else Decimal("0")
            if source_age is not None
            else self.policy.unknown_source_date_factor
        )
        freshness_rationale = (
            f"{opportunity.source_freshness_basis.value} source date is {source_age} days old"
            if source_age is not None
            else "source issue/application date is unavailable; acquisition age is retained separately and earns no source-freshness credit"
        )
        notification_ready = any(preference.enabled for preference in customer.notification_preferences.values())
        components = (
            MatchScoreComponent("trade", weights["trade"], "at least one enabled customer trade matched"),
            MatchScoreComponent("geography", weights["geography"], f"territory rule matched: {geography.matched_rule or 'uncertain'}"),
            MatchScoreComponent("value", value_points, "source valuation is present" if value_points else "source valuation is absent"),
            MatchScoreComponent("completeness", weights["completeness"] * completeness_factor, f"opportunity completeness is {opportunity.completeness_indicator}; valuation is excluded from completeness"),
            MatchScoreComponent("freshness", weights["freshness"] * freshness_factor, freshness_rationale),
            MatchScoreComponent("notification_readiness", weights["notification_readiness"] if notification_ready else Decimal("0"), "an enabled consented notification channel exists" if notification_ready else "no enabled notification channel"),
        )
        total = sum((component.value for component in components), Decimal("0"))
        geographic_rule = geography.matched_rule or "uncertain"
        matched_rules = ("active_account", "trade_overlap", f"territory:{geographic_rule}")
        readable = (
            f"Score {total}/100 under {self.policy.version} for Opportunity revision "
            f"{opportunity.projection_revision}: trade and {geographic_rule} territory matched; "
            f"value, non-valuation completeness, {freshness_rationale}, and notification readiness "
            "were evaluated deterministically."
        )
        distance_unit = getattr(geography.distance_unit, "value", None)
        if distance_unit is None and geography.distance_unit is not None:
            distance_unit = str(geography.distance_unit)
        score_policy_snapshot = ScorePolicySnapshot(
            self.policy.policy_id,
            self.policy.version,
            tuple(sorted(self.policy.weights.items())),
            self.policy.freshness_full_days,
            self.policy.freshness_partial_days,
            self.policy.unknown_source_date_factor,
            self.policy.exclusion_reason_codes,
        )
        customer_snapshot = CustomerConfigurationSnapshot(
            customer.version,
            tuple(sorted(customer.trade_preferences.values(), key=lambda item: str(item.trade_tag_id))),
            customer.service_territory,
            customer.customer_filter,
            tuple(
                sorted(
                    preference.channel.value
                    for preference in customer.notification_preferences.values()
                    if preference.enabled
                )
            ),
        )
        territory_snapshot = TerritoryEvaluationSnapshot(
            geographic_rule,
            geography.inside_territory,
            geography.location_verified,
            geography.distance_from_origin,
            distance_unit,
            geography.exclusion_reason,
        )
        freshness_snapshot = FreshnessEvaluationSnapshot(
            opportunity.source_freshness_date,
            opportunity.source_freshness_basis.value,
            opportunity.source_acquired_at,
            opportunity.processing_recorded_at or opportunity.created_at,
            evaluated_on,
            source_age,
            acquisition_age,
        )
        return MatchExplanation(
            matching_trade_tag_ids=trades,
            geographic_rule=geographic_rule,
            relevant_filters=self._relevant_filters(customer),
            score_components=components,
            exclusions_considered=self.policy.exclusion_reason_codes,
            source_freshness_date=opportunity.source_freshness_date,
            confidence=opportunity.confidence,
            score_version=self.policy.version,
            total_score=total,
            matched_rules=matched_rules,
            exclusion_rules=self._EXCLUSIONS,
            human_readable=readable,
            customer_configuration_version=customer.version,
            score_policy_snapshot=score_policy_snapshot,
            customer_configuration_snapshot=customer_snapshot,
            territory_evaluation_snapshot=territory_snapshot,
            freshness_evaluation_snapshot=freshness_snapshot,
            calculated_at=calculated_at,
            opportunity_revision=opportunity.projection_revision,
            publication_confidence_threshold=self._eligibility.publication_confidence,
        )

    @staticmethod
    def _relevant_filters(customer: CustomerAccount) -> tuple[str, ...]:
        filters = customer.customer_filter
        if filters is None:
            return ("no optional customer filters configured",)
        values: list[str] = []
        if filters.minimum_valuation:
            values.append(f"minimum valuation {filters.minimum_valuation.amount} {filters.minimum_valuation.currency}")
        if filters.maximum_valuation:
            values.append(f"maximum valuation {filters.maximum_valuation.amount} {filters.maximum_valuation.currency}")
        if filters.minimum_confidence:
            values.append(f"minimum confidence {filters.minimum_confidence.value}")
        if filters.allowed_value_bands:
            values.append(f"allowed value bands {','.join(sorted(filters.allowed_value_bands))}")
        if filters.excluded_permit_type_codes:
            values.append(f"excluded Permit types {','.join(sorted(filters.excluded_permit_type_codes))}")
        if filters.excluded_project_classification_codes:
            values.append(f"excluded project categories {','.join(sorted(filters.excluded_project_classification_codes))}")
        if filters.issued_during:
            values.append(
                f"Permit date range {filters.issued_during.starts_on.value.isoformat()} to {filters.issued_during.ends_on.value.isoformat()}"
            )
        return tuple(values) or ("configured customer filters contain no active restrictions",)
