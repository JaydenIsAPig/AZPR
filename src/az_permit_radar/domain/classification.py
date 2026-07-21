"""Permit Intelligence classifications with deterministic/AI provenance."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .errors import InvalidStateTransition, InvariantViolation
from .events import ClassificationReviewed, EventRecorder
from .value_objects import (
    ClassificationResultId,
    Confidence,
    PermitId,
    TradeTagId,
    UtcTimestamp,
)


@dataclass(frozen=True, slots=True)
class ProjectClassification:
    code: str
    label: str

    def __post_init__(self) -> None:
        if not self.code.strip() or not self.label.strip():
            raise InvariantViolation("project classification code and label are required")


@dataclass(frozen=True, slots=True)
class TradeTag:
    trade_tag_id: TradeTagId
    code: str
    label: str

    def __post_init__(self) -> None:
        if not self.code.strip() or not self.label.strip():
            raise InvariantViolation("trade tag code and label are required")


class ClassificationMethod(str, Enum):
    DETERMINISTIC = "deterministic"
    AI_ASSISTED = "ai_assisted"


class ClassificationOrigin(str, Enum):
    SOURCE = "source"
    DETERMINISTIC_RULE = "deterministic_rule"
    AI = "ai"
    HUMAN = "human"


@dataclass(frozen=True, slots=True)
class ClassificationAssertion:
    """One independently-provenanced classification tag."""

    tag: str
    value: str | bool
    origin: ClassificationOrigin
    confidence: Confidence
    evidence: tuple[str, ...]
    rule_id: str | None = None
    rule_version: str | None = None
    model_provider: str | None = None
    model_version: str | None = None
    classifier_version: str | None = None

    def __post_init__(self) -> None:
        if not self.tag.strip() or not self.evidence or any(not item.strip() for item in self.evidence):
            raise InvariantViolation("classification assertion requires tag and evidence")
        if self.origin is ClassificationOrigin.DETERMINISTIC_RULE:
            if not self.rule_id or not self.rule_id.strip() or not self.rule_version or not self.rule_version.strip():
                raise InvariantViolation("deterministic assertion requires rule identifier and version")
        elif self.rule_id is not None or self.rule_version is not None:
            raise InvariantViolation("only deterministic assertions may claim rule provenance")
        if self.origin is ClassificationOrigin.AI:
            if not all(value and value.strip() for value in (self.model_provider, self.model_version, self.classifier_version)):
                raise InvariantViolation("AI assertion requires provider, model, and classifier versions")
        elif any((self.model_provider, self.model_version)):
            raise InvariantViolation("only AI assertions may claim model provenance")


@dataclass(frozen=True, slots=True)
class HumanClassificationDecision:
    permit_id: PermitId
    tag: str
    value: str | bool
    actor_id: str
    rationale: str
    decided_at: UtcTimestamp
    source_assertion_origin: ClassificationOrigin | None = None
    classification_result_id: ClassificationResultId | None = None
    prior_value: str | bool | None = None
    classification_version: str = "legacy"

    def __post_init__(self) -> None:
        if any(not value.strip() for value in (self.tag, self.actor_id, self.rationale, self.classification_version)):
            raise InvariantViolation("human classification decision fields are required")

    @property
    def new_value(self) -> str | bool:
        return self.value

    def as_labeled_example(self) -> dict[str, str | bool]:
        return {"permit_id": str(self.permit_id), "tag": self.tag, "value": self.value}


class ClassificationReviewStatus(str, Enum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    REJECTED = "rejected"


@dataclass(slots=True)
class ClassificationResult(EventRecorder):
    classification_result_id: ClassificationResultId
    permit_id: PermitId
    project_classification: ProjectClassification
    trade_tags: frozenset[TradeTag]
    method: ClassificationMethod
    classifier_version: str
    confidence: Confidence
    evidence: tuple[str, ...]
    produced_at: UtcTimestamp
    assertions: tuple[ClassificationAssertion, ...] = ()
    rule_set_version: str = "legacy"
    supersedes_classification_result_id: ClassificationResultId | None = None
    revision: int = 1
    human_decisions: tuple[HumanClassificationDecision, ...] = ()
    model_provider: str | None = None
    model_version: str | None = None
    prompt_version: str | None = None
    review_status: ClassificationReviewStatus = ClassificationReviewStatus.PENDING
    review_note: str | None = None
    version: int = 0

    def __post_init__(self) -> None:
        self._initialize_events()
        if not self.classifier_version.strip():
            raise InvariantViolation("classifier version is required")
        if not self.rule_set_version.strip() or self.revision < 1:
            raise InvariantViolation("classification rule-set version and positive revision are required")
        if not self.trade_tags:
            raise InvariantViolation("classification requires at least one trade tag")
        if not self.evidence or any(not item.strip() for item in self.evidence):
            raise InvariantViolation("classification requires non-blank evidence")
        ai_fields = (self.model_provider, self.model_version, self.prompt_version)
        if self.method is ClassificationMethod.AI_ASSISTED and not all(
            value is not None and value.strip() for value in ai_fields
        ):
            raise InvariantViolation("AI-assisted classification requires provider, model, and prompt versions")
        if self.method is ClassificationMethod.DETERMINISTIC and any(ai_fields):
            raise InvariantViolation("deterministic classification cannot claim AI model provenance")
        if self.supersedes_classification_result_id == self.classification_result_id:
            raise InvariantViolation("classification result cannot supersede itself")
        if self.assertions:
            if any(not assertion.tag.strip() for assertion in self.assertions):
                raise InvariantViolation("classification assertions require tags")
            calculated = min(assertion.confidence.value for assertion in self.effective_assertions)
            if calculated != self.confidence.value:
                raise InvariantViolation("classification confidence must equal the least-confident effective assertion")
        for decision in self.human_decisions:
            self._validate_human_decision(decision)

    @property
    def classification_version(self) -> str:
        return self.classifier_version

    @property
    def effective_assertions(self) -> tuple[ClassificationAssertion, ...]:
        by_tag: dict[str, ClassificationAssertion] = {}
        for assertion in self.assertions:
            by_tag[assertion.tag] = assertion
        return tuple(sorted(by_tag.values(), key=lambda item: item.tag))

    def record_human_decision(self, decision: HumanClassificationDecision) -> None:
        self._validate_human_decision(decision)
        if decision in self.human_decisions:
            return
        current = next((item for item in self.effective_assertions if item.tag == decision.tag), None)
        current_value = current.value if current is not None else None
        if decision.prior_value != current_value:
            raise InvariantViolation("human decision prior value must match the effective assertion")
        assertion = ClassificationAssertion(
            tag=decision.tag,
            value=decision.new_value,
            origin=ClassificationOrigin.HUMAN,
            confidence=Confidence(1),
            evidence=(decision.rationale,),
            classifier_version=decision.classification_version,
        )
        self.human_decisions = (*self.human_decisions, decision)
        self.assertions = (*self.assertions, assertion)
        self.confidence = Confidence(min(item.confidence.value for item in self.effective_assertions))
        self.version += 1

    def _validate_human_decision(self, decision: HumanClassificationDecision) -> None:
        if decision.permit_id != self.permit_id:
            raise InvariantViolation("human decision Permit does not match classification result")
        if decision.classification_result_id not in {None, self.classification_result_id}:
            raise InvariantViolation("human decision classification identifier does not match")
        if decision.classification_version != self.classification_version:
            raise InvariantViolation("human decision classification version does not match")

    def accept(self, note: str, occurred_at: UtcTimestamp) -> None:
        self._review(ClassificationReviewStatus.ACCEPTED, note, occurred_at)

    def reject(self, note: str, occurred_at: UtcTimestamp) -> None:
        self._review(ClassificationReviewStatus.REJECTED, note, occurred_at)

    def _review(
        self,
        requested: ClassificationReviewStatus,
        note: str,
        occurred_at: UtcTimestamp,
    ) -> None:
        if self.review_status is requested and self.review_note == note:
            return
        if self.review_status is not ClassificationReviewStatus.PENDING:
            raise InvalidStateTransition("ClassificationResult", self.review_status, requested)
        if not note.strip():
            raise InvariantViolation("classification review note is required")
        self.review_status = requested
        self.review_note = note
        self.version += 1
        self._record(
            ClassificationReviewed(
                aggregate_id=str(self.classification_result_id),
                occurred_at=occurred_at,
                permit_id=str(self.permit_id),
                review_status=requested.value,
            )
        )
