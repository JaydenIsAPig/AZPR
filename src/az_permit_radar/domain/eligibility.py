"""Central fail-closed publication eligibility for Opportunities and Customer Matches."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import Enum

from .classification import ClassificationResult, ClassificationReviewStatus
from .errors import InvariantViolation
from .opportunity import Opportunity, OpportunityStatus
from .permit import Permit, PermitAuthorityStatus, PermitCanonicalStatus, PermitStatus
from .value_objects import Confidence


class EligibilityReason(str, Enum):
    PERMIT_MISSING = "permit_missing"
    PERMIT_VOIDED = "permit_voided"
    PERMIT_SUPERSEDED = "permit_superseded"
    PROBABLE_DUPLICATE_UNRESOLVED = "probable_duplicate_unresolved"
    NONCANONICAL_PERMIT = "noncanonical_permit"
    CLASSIFICATION_MISSING = "classification_missing"
    CLASSIFICATION_PENDING_REVIEW = "classification_pending_review"
    CLASSIFICATION_REJECTED = "classification_rejected"
    CLASSIFICATION_CONFIDENCE_BELOW_PUBLICATION_THRESHOLD = (
        "classification_confidence_below_publication_threshold"
    )
    GEOGRAPHY_UNVERIFIED = "geography_unverified"
    OPPORTUNITY_NOT_PUBLISHABLE = "opportunity_not_publishable"


@dataclass(frozen=True, slots=True)
class EligibilityDecision:
    reasons: tuple[str, ...] = ()

    @property
    def eligible(self) -> bool:
        return not self.reasons


class PublicationEligibilityError(InvariantViolation):
    def __init__(self, decision: EligibilityDecision) -> None:
        self.decision = decision
        super().__init__(f"publication eligibility blocked: {', '.join(decision.reasons)}")


@dataclass(frozen=True, slots=True)
class PublicationEligibilityPolicy:
    publication_confidence: Confidence

    @classmethod
    def from_decimal(cls, value: Decimal | str) -> PublicationEligibilityPolicy:
        return cls(Confidence(Decimal(value)))

    def evaluate_generation(
        self,
        *,
        permit: Permit,
        classifications: tuple[ClassificationResult, ...],
    ) -> EligibilityDecision:
        reasons = self._permit_and_classification_reasons(permit, classifications)
        return EligibilityDecision(self._unique(reasons))

    def evaluate_matching(
        self,
        *,
        opportunity: Opportunity,
        permits: tuple[Permit, ...],
        classifications: tuple[ClassificationResult, ...],
        geography_verified: bool,
    ) -> EligibilityDecision:
        reasons: list[str] = []
        if opportunity.status is not OpportunityStatus.PUBLISHED:
            reasons.append(EligibilityReason.OPPORTUNITY_NOT_PUBLISHABLE.value)
        supplied_permits = {permit.permit_id: permit for permit in permits}
        for permit_id in opportunity.permit_ids:
            permit = supplied_permits.get(permit_id)
            if permit is None:
                reasons.append(EligibilityReason.PERMIT_MISSING.value)
                continue
            reasons.extend(self._permit_and_classification_reasons(permit, classifications))
        supplied_classification_ids = {
            result.classification_result_id
            for result in classifications
            if isinstance(result, ClassificationResult)
        }
        if not opportunity.classification_result_ids <= supplied_classification_ids:
            reasons.append(EligibilityReason.CLASSIFICATION_MISSING.value)
        if not geography_verified:
            reasons.append(EligibilityReason.GEOGRAPHY_UNVERIFIED.value)
        return EligibilityDecision(self._unique(reasons))

    def _permit_and_classification_reasons(
        self,
        permit: Permit,
        classifications: tuple[ClassificationResult, ...],
    ) -> list[str]:
        reasons: list[str] = []
        if permit.status is PermitStatus.VOIDED or permit.authority_status is PermitAuthorityStatus.VOIDED:
            reasons.append(EligibilityReason.PERMIT_VOIDED.value)
        if permit.status is PermitStatus.SUPERSEDED:
            reasons.append(EligibilityReason.PERMIT_SUPERSEDED.value)
        if permit.canonical_status is PermitCanonicalStatus.PROBABLE_DUPLICATE:
            reasons.append(EligibilityReason.PROBABLE_DUPLICATE_UNRESOLVED.value)
        elif permit.canonical_status is PermitCanonicalStatus.NONCANONICAL:
            reasons.append(EligibilityReason.NONCANONICAL_PERMIT.value)

        applicable = tuple(
            result
            for result in classifications
            if isinstance(result, ClassificationResult) and result.permit_id == permit.permit_id
        )
        if not applicable:
            reasons.append(EligibilityReason.CLASSIFICATION_MISSING.value)
            return reasons
        for result in applicable:
            if result.review_status is ClassificationReviewStatus.PENDING:
                reasons.append(EligibilityReason.CLASSIFICATION_PENDING_REVIEW.value)
            elif result.review_status is ClassificationReviewStatus.REJECTED:
                reasons.append(EligibilityReason.CLASSIFICATION_REJECTED.value)
            if result.confidence.value < self.publication_confidence.value:
                reasons.append(
                    EligibilityReason.CLASSIFICATION_CONFIDENCE_BELOW_PUBLICATION_THRESHOLD.value
                )
        return reasons

    @staticmethod
    def _unique(reasons: list[str]) -> tuple[str, ...]:
        return tuple(dict.fromkeys(reasons))
