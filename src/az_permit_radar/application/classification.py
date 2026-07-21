"""Persisted deterministic-first Permit classification orchestration."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from decimal import Decimal
from typing import Protocol

from az_permit_radar.domain.classification import (
    ClassificationAssertion,
    ClassificationMethod,
    ClassificationOrigin,
    ClassificationResult,
    ClassificationReviewStatus,
    HumanClassificationDecision,
    ProjectClassification,
    TradeTag,
)
from az_permit_radar.domain.errors import InvariantViolation
from az_permit_radar.domain.permit import Permit
from az_permit_radar.domain.review import ReviewSubjectType, ReviewTask
from az_permit_radar.domain.value_objects import (
    ClassificationResultId,
    Confidence,
    PermitId,
    ReviewTaskId,
    TradeTagId,
    UtcTimestamp,
)


_PROJECT_TAGS = (
    "new_construction",
    "remodel",
    "addition",
    "demolition",
    "tenant_improvement",
)
_TRADE_TAGS = frozenset(
    {
        "mechanical",
        "electrical",
        "plumbing",
        "roofing",
        "solar",
        "fire_suppression",
        "low_voltage",
        "concrete_structural",
        "landscaping_indicator",
        "equipment_rental_indicator",
    }
)


@dataclass(frozen=True, slots=True)
class ClassificationPolicy:
    ai_acceptance_confidence: Decimal
    review_confidence: Decimal
    publication_confidence: Decimal | None = None
    rule_set_version: str = "1.0.0"

    def __post_init__(self) -> None:
        publication = (
            self.review_confidence
            if self.publication_confidence is None
            else Decimal(self.publication_confidence)
        )
        values = (
            Decimal(self.ai_acceptance_confidence),
            Decimal(self.review_confidence),
            publication,
        )
        if any(not Decimal("0") <= value <= Decimal("1") for value in values):
            raise InvariantViolation("classification confidence thresholds must be between zero and one")
        if not self.rule_set_version.strip():
            raise InvariantViolation("classification rule-set version is required")
        object.__setattr__(self, "ai_acceptance_confidence", values[0])
        object.__setattr__(self, "review_confidence", values[1])
        object.__setattr__(self, "publication_confidence", publication)


@dataclass(frozen=True, slots=True)
class ClassificationOutcome:
    classification_result: ClassificationResult
    review_tasks: tuple[ReviewTask, ...]
    ai_status: str

    @property
    def assertions(self) -> tuple[ClassificationAssertion, ...]:
        """Compatibility view; assertions are evidence owned by the Result."""
        return self.classification_result.effective_assertions


@dataclass(frozen=True, slots=True)
class ClassificationSignals:
    permit: Permit
    occupancy: str | None = None
    project: str | None = None
    source_categories: tuple[str, ...] = ()


class DeterministicClassifier(Protocol):
    def classify(self, signals: ClassificationSignals) -> tuple[ClassificationAssertion, ...]: ...


class AmbiguousDescriptionClassifier(Protocol):
    def classify_description(self, permit: Permit) -> tuple[ClassificationAssertion, ...]: ...


class ClassificationState(Protocol):
    def get_result(self, result_id: ClassificationResultId) -> ClassificationResult | None: ...

    def find_current_for_permit(self, permit_id: PermitId) -> ClassificationResult | None: ...

    def find_review_tasks(self, result_id: ClassificationResultId) -> tuple[ReviewTask, ...]: ...

    def save_outcome(
        self,
        result: ClassificationResult,
        review_tasks: tuple[ReviewTask, ...],
    ) -> None: ...

    def save_review_resolution(
        self,
        result: ClassificationResult,
        review_tasks: tuple[ReviewTask, ...],
    ) -> None: ...


class PermitClassificationService:
    """Creates the sole authoritative ClassificationResult consumed downstream."""

    def __init__(
        self,
        rules: DeterministicClassifier,
        ai: AmbiguousDescriptionClassifier | None,
        policy: ClassificationPolicy,
        state: ClassificationState,
        *,
        classification_version: str = "permit-classification-1.0.0",
    ) -> None:
        if not classification_version.strip():
            raise InvariantViolation("classification version is required")
        self._rules, self._ai, self._policy, self._state = rules, ai, policy, state
        self.classification_version = classification_version

    def classify(self, signals: ClassificationSignals, occurred_at: UtcTimestamp) -> ClassificationOutcome:
        permit = signals.permit
        deterministic = self._rules.classify(signals)
        by_tag = {item.tag: item for item in deterministic}
        ai_status = "not_needed"
        if permit.description and self._ai is not None:
            try:
                proposals = self._ai.classify_description(permit)
                ai_status = "completed"
            except Exception:
                proposals, ai_status = (), "failed_closed"
            for proposal in proposals:
                if proposal.origin is not ClassificationOrigin.AI:
                    continue
                if proposal.tag in by_tag:  # AI never overwrites deterministic facts.
                    continue
                if proposal.confidence.value >= self._policy.ai_acceptance_confidence:
                    by_tag[proposal.tag] = proposal

        assertions = tuple(sorted(by_tag.values(), key=lambda item: item.tag))
        if not assertions:
            raise InvariantViolation("classification requires at least one derived assertion")
        identity = self._identity(permit.permit_id, assertions)
        result_id = ClassificationResultId(f"classification-{identity}")
        existing = self._state.get_result(result_id)
        if existing is not None:
            return ClassificationOutcome(
                existing,
                self._state.find_review_tasks(result_id),
                ai_status,
            )

        previous = self._state.find_current_for_permit(permit.permit_id)
        confidence = Confidence(min(assertion.confidence.value for assertion in assertions))
        auto_accept_threshold = max(
            self._policy.review_confidence,
            self._policy.publication_confidence,
        )
        review_status = (
            ClassificationReviewStatus.ACCEPTED
            if confidence.value >= auto_accept_threshold
            else ClassificationReviewStatus.PENDING
        )
        ai_assertions = tuple(
            assertion for assertion in assertions if assertion.origin is ClassificationOrigin.AI
        )
        result = ClassificationResult(
            classification_result_id=result_id,
            permit_id=permit.permit_id,
            project_classification=self._project_classification(assertions),
            trade_tags=self._trade_tags(assertions),
            method=(ClassificationMethod.AI_ASSISTED if ai_assertions else ClassificationMethod.DETERMINISTIC),
            classifier_version=self.classification_version,
            confidence=confidence,
            evidence=tuple(evidence for assertion in assertions for evidence in assertion.evidence),
            produced_at=occurred_at,
            assertions=assertions,
            rule_set_version=self._policy.rule_set_version,
            supersedes_classification_result_id=(
                previous.classification_result_id if previous is not None else None
            ),
            revision=(previous.revision + 1 if previous is not None else 1),
            model_provider=(ai_assertions[0].model_provider if ai_assertions else None),
            model_version=(ai_assertions[0].model_version if ai_assertions else None),
            prompt_version=(ai_assertions[0].classifier_version if ai_assertions else None),
            review_status=review_status,
            review_note=("automatically accepted above governed thresholds" if review_status is ClassificationReviewStatus.ACCEPTED else None),
        )
        review_tasks = self._review_tasks(result, occurred_at)
        self._state.save_outcome(result, review_tasks)
        return ClassificationOutcome(result, review_tasks, ai_status)

    def resolve_review(
        self,
        classification_result_id: ClassificationResultId,
        *,
        approved: bool,
        actor_id: str,
        reason: str,
        occurred_at: UtcTimestamp,
    ) -> ClassificationResult:
        if not actor_id.strip() or not reason.strip():
            raise InvariantViolation("classification review actor and reason are required")
        result = self._state.get_result(classification_result_id)
        if result is None:
            raise InvariantViolation("classification result does not exist")
        tasks = self._state.find_review_tasks(classification_result_id)
        resolution = f"{'approved' if approved else 'rejected'}: {reason}"
        if approved:
            for assertion in result.effective_assertions:
                if assertion.confidence.value >= self._policy.publication_confidence:
                    continue
                result.record_human_decision(
                    HumanClassificationDecision(
                        permit_id=result.permit_id,
                        tag=assertion.tag,
                        value=assertion.value,
                        actor_id=actor_id,
                        rationale=reason,
                        decided_at=occurred_at,
                        source_assertion_origin=assertion.origin,
                        classification_result_id=result.classification_result_id,
                        prior_value=assertion.value,
                        classification_version=result.classification_version,
                    )
                )
            result.accept(reason, occurred_at)
        else:
            result.reject(reason, occurred_at)
        for task in tasks:
            task.resolve(resolution, occurred_at)
        self._state.save_review_resolution(result, tasks)
        return result

    def _identity(
        self,
        permit_id: PermitId,
        assertions: tuple[ClassificationAssertion, ...],
    ) -> str:
        payload = {
            "permit_id": str(permit_id),
            "classification_version": self.classification_version,
            "rule_set_version": self._policy.rule_set_version,
            "assertions": [
                {
                    "tag": item.tag,
                    "value": item.value,
                    "origin": item.origin.value,
                    "confidence": str(item.confidence.value),
                    "rule_id": item.rule_id,
                    "rule_version": item.rule_version,
                    "model_provider": item.model_provider,
                    "model_version": item.model_version,
                    "classifier_version": item.classifier_version,
                }
                for item in assertions
            ],
        }
        return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()

    @staticmethod
    def _project_classification(
        assertions: tuple[ClassificationAssertion, ...],
    ) -> ProjectClassification:
        by_tag = {item.tag: item for item in assertions}
        selected = next(
            (tag for tag in _PROJECT_TAGS if tag in by_tag and by_tag[tag].value is True),
            None,
        )
        if selected is None and "market_segment" in by_tag:
            selected = str(by_tag["market_segment"].value)
        selected = selected or "unclassified"
        return ProjectClassification(selected.replace("_", "-"), selected.replace("_", " ").title())

    @staticmethod
    def _trade_tags(assertions: tuple[ClassificationAssertion, ...]) -> frozenset[TradeTag]:
        tags = frozenset(
            TradeTag(
                TradeTagId(f"trade-{assertion.tag.replace('_', '-')}"),
                assertion.tag,
                assertion.tag.replace("_", " ").title(),
            )
            for assertion in assertions
            if assertion.tag in _TRADE_TAGS and assertion.value is True
        )
        if not tags:
            raise InvariantViolation("classification requires at least one actionable trade assertion")
        return tags

    @staticmethod
    def _review_tasks(
        result: ClassificationResult,
        occurred_at: UtcTimestamp,
    ) -> tuple[ReviewTask, ...]:
        if result.review_status is not ClassificationReviewStatus.PENDING:
            return ()
        seed = f"{result.classification_result_id}:governed-confidence-review".encode()
        return (
            ReviewTask(
                ReviewTaskId(f"review-{hashlib.sha256(seed).hexdigest()}"),
                ReviewSubjectType.CLASSIFICATION_RESULT,
                str(result.classification_result_id),
                "classification confidence below governed publication threshold",
                occurred_at,
                permit_id=result.permit_id,
                classification_result_id=result.classification_result_id,
            ),
        )
