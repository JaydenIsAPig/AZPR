"""Versioned rules and fail-closed schema adapter for Permit Intelligence."""

from __future__ import annotations

import json
import re
import threading
from copy import deepcopy
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Callable

from az_permit_radar.application.classification import ClassificationPolicy, ClassificationSignals
from az_permit_radar.domain.classification import (
    ClassificationAssertion,
    ClassificationOrigin,
    ClassificationResult,
)
from az_permit_radar.domain.errors import InvariantViolation
from az_permit_radar.domain.permit import PermitPartyRole
from az_permit_radar.domain.review import ReviewTask
from az_permit_radar.domain.value_objects import (
    ClassificationResultId,
    Confidence,
    PermitId,
    ReviewTaskId,
)


_TAGS = frozenset({
    "market_segment", "new_construction", "remodel", "addition", "demolition",
    "tenant_improvement", "mechanical", "electrical", "plumbing", "roofing", "solar",
    "fire_suppression", "low_voltage", "concrete_structural", "landscaping_indicator",
    "equipment_rental_indicator", "value_band", "owner_builder", "data_completeness",
})

_KEYWORDS = {
    "new_construction": ("new construction", "new building", "ground up"),
    "remodel": ("remodel", "renovation", "alteration"),
    "addition": ("addition", "add room", "expand building"),
    "demolition": ("demolition", "demolish", "demo building"),
    "tenant_improvement": ("tenant improvement", "tenant buildout", "tenant build-out"),
    "mechanical": ("mechanical", "hvac", "air conditioning", "heat pump"),
    "electrical": ("electrical", "panel upgrade", "service upgrade", "wiring"),
    "plumbing": ("plumbing", "sewer", "water heater", "repipe"),
    "roofing": ("roofing", "reroof", "re-roof", "roof replacement"),
    "solar": ("solar", "photovoltaic", "pv system"),
    "fire_suppression": ("fire suppression", "fire sprinkler", "sprinkler system"),
    "low_voltage": ("low voltage", "data cabling", "security system"),
    "concrete_structural": ("concrete", "foundation", "structural steel", "retaining wall"),
    "landscaping_indicator": ("landscaping", "landscape", "irrigation"),
    "equipment_rental_indicator": ("crane", "scissor lift", "boom lift", "excavator"),
}


def load_classification_policy(path: str) -> ClassificationPolicy:
    with open(path, encoding="utf-8") as stream:
        values = json.load(stream)["classification_policy"]
    return ClassificationPolicy(
        Decimal(values["ai_acceptance_confidence"]),
        Decimal(values["review_confidence"]),
        Decimal(values["publication_confidence"]),
        values["rule_set_version"],
    )


class InMemoryClassificationState:
    """Atomic in-memory Result/Review persistence for local workflows and tests."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._results: dict[ClassificationResultId, ClassificationResult] = {}
        self._current_by_permit: dict[PermitId, ClassificationResultId] = {}
        self._reviews: dict[ReviewTaskId, ReviewTask] = {}

    def get_result(self, result_id: ClassificationResultId) -> ClassificationResult | None:
        with self._lock:
            result = self._results.get(result_id)
            return deepcopy(result) if result is not None else None

    def find_current_for_permit(self, permit_id: PermitId) -> ClassificationResult | None:
        with self._lock:
            result_id = self._current_by_permit.get(permit_id)
            result = self._results.get(result_id) if result_id is not None else None
            return deepcopy(result) if result is not None else None

    def find_review_tasks(self, result_id: ClassificationResultId) -> tuple[ReviewTask, ...]:
        with self._lock:
            return tuple(
                deepcopy(task)
                for task in self._reviews.values()
                if task.classification_result_id == result_id
            )

    def save_outcome(
        self,
        result: ClassificationResult,
        review_tasks: tuple[ReviewTask, ...],
    ) -> None:
        with self._lock:
            existing = self._results.get(result.classification_result_id)
            if existing is not None:
                if existing != result:
                    raise InvariantViolation("classification identity collision")
                return
            current_id = self._current_by_permit.get(result.permit_id)
            if current_id != result.supersedes_classification_result_id:
                if current_id is not None or result.supersedes_classification_result_id is not None:
                    raise InvariantViolation("classification revision does not supersede the current result")
            for task in review_tasks:
                if task.classification_result_id != result.classification_result_id:
                    raise InvariantViolation("classification Review Task references another Result")
            self._results[result.classification_result_id] = deepcopy(result)
            self._current_by_permit[result.permit_id] = result.classification_result_id
            for task in review_tasks:
                self._reviews.setdefault(task.review_task_id, deepcopy(task))

    def save_review_resolution(
        self,
        result: ClassificationResult,
        review_tasks: tuple[ReviewTask, ...],
    ) -> None:
        with self._lock:
            current_id = self._current_by_permit.get(result.permit_id)
            if current_id != result.classification_result_id:
                raise InvariantViolation("only the current classification Result can be reviewed")
            self._results[result.classification_result_id] = deepcopy(result)
            for task in review_tasks:
                if task.classification_result_id != result.classification_result_id:
                    raise InvariantViolation("classification Review Task references another Result")
                self._reviews[task.review_task_id] = deepcopy(task)

    @property
    def results(self) -> tuple[ClassificationResult, ...]:
        with self._lock:
            return tuple(deepcopy(result) for result in self._results.values())


@dataclass(frozen=True, slots=True)
class RuleEngineConfig:
    version: str = "1.0.0"
    jurisdiction_mappings: dict[str, dict[str, tuple[str, str | bool]]] | None = None


class VersionedPermitRuleEngine:
    def __init__(self, config: RuleEngineConfig = RuleEngineConfig()) -> None:
        self.config = config

    def classify(self, signals: ClassificationSignals) -> tuple[ClassificationAssertion, ...]:
        permit = signals.permit
        permit_type = permit.permit_type.code if permit.permit_type else ""
        text = " ".join(filter(None, (permit_type, permit.description, signals.occupancy, signals.project, *signals.source_categories))).lower()
        assertions: dict[str, ClassificationAssertion] = {}

        def add(tag: str, value: str | bool, rule: str, evidence: str, confidence: str = "0.95") -> None:
            assertions[tag] = ClassificationAssertion(tag, value, ClassificationOrigin.DETERMINISTIC_RULE, Confidence(Decimal(confidence)), (evidence,), rule, self.config.version)

        residential = self._contains(text, ("residential", "single family", "duplex", "r-3"))
        commercial = self._contains(text, ("commercial", "office", "retail", "warehouse", "tenant improvement"))
        if residential != commercial:
            add("market_segment", "residential" if residential else "commercial", "segment-001", "permit/occupancy/project/category signal")
        for tag, phrases in _KEYWORDS.items():
            if self._contains(text, phrases):
                add(tag, True, f"keyword-{tag}-001", f"normalized text matched {tag}")
        jurisdiction_rules = (self.config.jurisdiction_mappings or {}).get(str(permit.jurisdiction_id), {})
        for source_value, (tag, value) in jurisdiction_rules.items():
            if source_value.lower() in {item.lower() for item in signals.source_categories}:
                add(tag, value, f"jurisdiction-{permit.jurisdiction_id}-{source_value}", "jurisdiction-specific source category mapping")

        if permit.valuation is None:
            add("value_band", "unknown", "valuation-band-001", "valuation absent", "1")
        else:
            amount = permit.valuation.amount
            band = "under_25k" if amount < 25000 else "25k_to_100k" if amount < 100000 else "100k_to_500k" if amount < 500000 else "500k_plus"
            add("value_band", band, "valuation-band-001", "source valuation threshold", "1")
        contractors = [party for party in permit.parties if party.role is PermitPartyRole.CONTRACTOR]
        owner_builder = any(self._contains(party.name.lower(), ("owner builder", "owner-builder")) for party in contractors)
        if contractors:
            add("owner_builder", owner_builder, "contractor-owner-builder-001", "contractor fields evaluated", "1")
        required = (permit.permit_type, permit.description, permit.valuation, permit.address)
        completeness = sum(value is not None and value != "" for value in required) / len(required)
        add("data_completeness", "complete" if completeness == 1 else "partial" if completeness >= .5 else "sparse", "completeness-001", "required normalized fields counted", "1")
        return tuple(assertions.values())

    @staticmethod
    def _contains(text: str, phrases: tuple[str, ...]) -> bool:
        return any(re.search(rf"(?<![a-z0-9]){re.escape(phrase)}(?![a-z0-9])", text) for phrase in phrases)


class SchemaConstrainedAIClassifier:
    """Provider-neutral adapter; accepts JSON only and returns no values on any invalid response."""

    def __init__(self, invoke: Callable[[dict[str, Any]], Any], *, provider: str, model_version: str, classifier_version: str, allowed_tags: frozenset[str] = _TAGS) -> None:
        self._invoke, self.provider, self.model_version, self.classifier_version = invoke, provider, model_version, classifier_version
        self.allowed_tags = allowed_tags

    def classify_description(self, permit: Any) -> tuple[ClassificationAssertion, ...]:
        description = self._sanitize(permit.description or "")
        payload = {"description": description[:1000], "schema": {"assertions": [{"tag": "enum", "value": "string|boolean", "confidence": "0..1", "evidence": "string"}]}}
        try:
            response = self._invoke(payload)
            if isinstance(response, str):
                response = json.loads(response)
            if not isinstance(response, dict) or set(response) != {"assertions"} or not isinstance(response["assertions"], list):
                return ()
            results = []
            for item in response["assertions"]:
                if not isinstance(item, dict) or set(item) != {"tag", "value", "confidence", "evidence"}:
                    return ()
                if item["tag"] not in self.allowed_tags or type(item["value"]) not in (str, bool):
                    return ()
                confidence = Decimal(str(item["confidence"]))
                if not Decimal("0") <= confidence <= Decimal("1") or not isinstance(item["evidence"], str) or not item["evidence"].strip():
                    return ()
                results.append(ClassificationAssertion(item["tag"], item["value"], ClassificationOrigin.AI, Confidence(confidence), (item["evidence"],), model_provider=self.provider, model_version=self.model_version, classifier_version=self.classifier_version))
            return tuple(results)
        except Exception:
            return ()

    @staticmethod
    def _sanitize(value: str) -> str:
        value = re.sub(r"[\w.+-]+@[\w.-]+", "[email]", value)
        value = re.sub(r"\b(?:\+?1[-. ]?)?\(?\d{3}\)?[-. ]?\d{3}[-. ]?\d{4}\b", "[phone]", value)
        return " ".join(value.replace("\x00", " ").split())


def precision_by_tag(expected: list[dict[str, Any]], predicted: list[set[str]]) -> dict[str, Decimal]:
    counts: dict[str, list[int]] = {}
    for fixture, tags in zip(expected, predicted, strict=True):
        truth = set(fixture["expected_tags"])
        for tag in tags:
            counts.setdefault(tag, [0, 0])[1] += 1
            if tag in truth:
                counts[tag][0] += 1
    return {tag: Decimal(correct) / total for tag, (correct, total) in sorted(counts.items())}
