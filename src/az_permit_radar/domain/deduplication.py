"""Permit duplicate evidence, review candidates, and retained manual decisions."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from .errors import InvalidStateTransition, InvariantViolation
from .events import EventRecorder, state_change_event
from .value_objects import DuplicateCandidateId, PermitId, UtcTimestamp


class DuplicateEvidenceLayer(str, Enum):
    SOURCE_EXTERNAL_IDENTIFIER = "source_external_identifier"
    SOURCE_RECORD_FINGERPRINT = "source_record_fingerprint"
    JURISDICTION_ADDRESS_TYPE_DATE = "jurisdiction_address_type_date"
    MANUAL_DECISION = "manual_decision"


@dataclass(frozen=True, slots=True)
class DuplicateEvidence:
    layer: DuplicateEvidenceLayer
    explanation: str
    score: int

    def __post_init__(self) -> None:
        if not self.explanation.strip() or not 0 <= self.score <= 100:
            raise InvariantViolation("duplicate evidence requires an explanation and score 0-100")


class DuplicateCandidateStatus(str, Enum):
    PENDING_REVIEW = "pending_review"
    MERGED = "merged"
    DISTINCT = "distinct"


class ManualDuplicateDecision(str, Enum):
    MERGE = "merge"
    KEEP_DISTINCT = "keep_distinct"


@dataclass(frozen=True, slots=True)
class DuplicateDecisionRecord:
    decision: ManualDuplicateDecision
    actor_id: str
    rationale: str
    decided_at: UtcTimestamp

    def __post_init__(self) -> None:
        if not self.actor_id.strip() or not self.rationale.strip():
            raise InvariantViolation("manual duplicate decision requires actor and rationale")


@dataclass(slots=True)
class PermitDuplicateCandidate(EventRecorder):
    candidate_id: DuplicateCandidateId
    permit_id: PermitId
    possible_duplicate_of_id: PermitId
    evidence: tuple[DuplicateEvidence, ...]
    created_at: UtcTimestamp
    status: DuplicateCandidateStatus = DuplicateCandidateStatus.PENDING_REVIEW
    decisions: list[DuplicateDecisionRecord] = field(default_factory=list)
    version: int = 0

    def __post_init__(self) -> None:
        self._initialize_events()
        if self.permit_id == self.possible_duplicate_of_id:
            raise InvariantViolation("duplicate candidate must compare distinct permits")
        if not self.evidence:
            raise InvariantViolation("duplicate candidate requires layered evidence")

    def decide(
        self,
        decision: ManualDuplicateDecision,
        *,
        actor_id: str,
        rationale: str,
        occurred_at: UtcTimestamp,
    ) -> DuplicateDecisionRecord:
        if self.status is not DuplicateCandidateStatus.PENDING_REVIEW:
            raise InvalidStateTransition("PermitDuplicateCandidate", self.status, decision)
        record = DuplicateDecisionRecord(decision, actor_id, rationale, occurred_at)
        previous = self.status
        self.status = (
            DuplicateCandidateStatus.MERGED
            if decision is ManualDuplicateDecision.MERGE
            else DuplicateCandidateStatus.DISTINCT
        )
        self.decisions.append(record)
        self.version += 1
        self._record(state_change_event(self, self.candidate_id, previous, self.status, occurred_at))
        return record

