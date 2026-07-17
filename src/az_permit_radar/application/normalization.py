"""Deterministic Source Record to Permit normalization and duplicate orchestration."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from enum import Enum
from typing import Callable, Protocol

from az_permit_radar.domain.deduplication import (
    DuplicateEvidence,
    DuplicateEvidenceLayer,
    ManualDuplicateDecision,
    PermitDuplicateCandidate,
)
from az_permit_radar.domain.errors import InvariantViolation
from az_permit_radar.domain.ingestion import SourceRecord, SourceRecordStatus
from az_permit_radar.domain.permit import (
    Address,
    NormalizedPermitType,
    ParcelReference,
    Permit,
    PermitAuthorityStatus,
    PermitParty,
    PermitSourceEvidence,
    PermitStatus,
)
from az_permit_radar.domain.review import ReviewSubjectType, ReviewTask
from az_permit_radar.domain.source_registry import Jurisdiction
from az_permit_radar.domain.value_objects import (
    CalendarDate,
    Confidence,
    DuplicateCandidateId,
    GeographicCoordinates,
    JurisdictionId,
    Money,
    NormalizedAddress,
    PermitId,
    ReviewTaskId,
    SourceId,
    UtcTimestamp,
)


@dataclass(frozen=True, slots=True)
class GeocodingResponse:
    provider: str
    normalized_address: NormalizedAddress
    coordinates: GeographicCoordinates
    quality: str
    confidence: Confidence

    def __post_init__(self) -> None:
        if not self.provider.strip() or not self.quality.strip():
            raise ValueError("geocoding response provider and quality are required")
        if self.normalized_address.coordinates not in {None, self.coordinates}:
            raise ValueError("geocoding response coordinates disagree with normalized address")


class GeocodingAdapter(Protocol):
    def geocode(
        self,
        *,
        raw_address: str,
        normalized_hint: NormalizedAddress | None,
        jurisdiction: Jurisdiction,
    ) -> GeocodingResponse | None: ...


class JurisdictionResolver(Protocol):
    def resolve(self, *, source_id: SourceId, raw_value: str | None) -> Jurisdiction | None: ...


@dataclass(frozen=True, slots=True)
class NormalizedPermitCandidate:
    permit_number: str
    authority_status: PermitAuthorityStatus
    permit_type: NormalizedPermitType | None
    description: str | None
    applied_on: CalendarDate | None
    issued_on: CalendarDate | None
    valuation: Money | None
    parties: tuple[PermitParty, ...]
    address: Address | None
    parcel_reference: ParcelReference | None
    warnings: tuple[str, ...] = ()


class PermitRecordNormalizer(Protocol):
    def normalize(
        self,
        *,
        source_record: SourceRecord,
        jurisdiction: Jurisdiction,
        geocoder: GeocodingAdapter,
        occurred_at: UtcTimestamp,
    ) -> NormalizedPermitCandidate: ...


class PermitNormalizationStore(Protocol):
    def get(self, permit_id: PermitId) -> Permit | None: ...

    def find_by_source_external(
        self,
        source_id: SourceId,
        external_record_id: str,
    ) -> Permit | None: ...

    def find_by_source_fingerprint(self, source_id: SourceId, fingerprint: str) -> Permit | None: ...

    def list_by_jurisdiction(self, jurisdiction_id: JurisdictionId) -> tuple[Permit, ...]: ...

    def save(self, permit: Permit) -> None: ...


class DuplicateCandidateStore(Protocol):
    def get(self, candidate_id: DuplicateCandidateId) -> PermitDuplicateCandidate | None: ...

    def save(self, candidate: PermitDuplicateCandidate) -> None: ...


class NormalizationReviewStore(Protocol):
    def save(self, review_task: ReviewTask) -> None: ...


@dataclass(frozen=True, slots=True)
class NormalizationLogEntry:
    event: str
    source_id: str
    source_record_id: str
    permit_id: str | None
    outcome: str
    parser_version: str
    duplicate_layer: str | None = None
    review_count: int = 0

    def as_dict(self) -> dict[str, object]:
        return {
            "event": self.event,
            "source_id": self.source_id,
            "source_record_id": self.source_record_id,
            "permit_id": self.permit_id,
            "outcome": self.outcome,
            "parser_version": self.parser_version,
            "duplicate_layer": self.duplicate_layer,
            "review_count": self.review_count,
        }


class NormalizationLogger(Protocol):
    def record(self, entry: NormalizationLogEntry) -> None: ...


class NormalizationMetrics(Protocol):
    def increment(self, name: str, *, labels: tuple[tuple[str, str], ...] = ()) -> None: ...


class PermitNormalizationOutcome(str, Enum):
    CREATED = "created"
    CORRECTED = "corrected"
    EXACT_DUPLICATE = "exact_duplicate"
    PROBABLE_DUPLICATE = "probable_duplicate"


@dataclass(frozen=True, slots=True)
class PermitNormalizationResult:
    outcome: PermitNormalizationOutcome
    permit: Permit
    evidence: tuple[DuplicateEvidence, ...]
    duplicate_candidate: PermitDuplicateCandidate | None = None
    review_tasks: tuple[ReviewTask, ...] = ()
    warnings: tuple[str, ...] = ()


class PermitNormalizationWorkflow:
    def __init__(
        self,
        *,
        normalizer: PermitRecordNormalizer,
        jurisdictions: JurisdictionResolver,
        geocoder: GeocodingAdapter,
        permits: PermitNormalizationStore,
        duplicate_candidates: DuplicateCandidateStore,
        reviews: NormalizationReviewStore,
        logger: NormalizationLogger,
        metrics: NormalizationMetrics,
        now: Callable[[], UtcTimestamp] = UtcTimestamp.now,
    ) -> None:
        self._normalizer = normalizer
        self._jurisdictions = jurisdictions
        self._geocoder = geocoder
        self._permits = permits
        self._duplicate_candidates = duplicate_candidates
        self._reviews = reviews
        self._logger = logger
        self._metrics = metrics
        self._now = now

    def normalize(self, source_record: SourceRecord) -> PermitNormalizationResult:
        if source_record.status is not SourceRecordStatus.PARSED or source_record.parser_version is None:
            raise InvariantViolation("permit normalization requires a successfully parsed Source Record")
        raw_jurisdiction = self._text_value(source_record, "jurisdiction")
        jurisdiction = self._jurisdictions.resolve(
            source_id=source_record.source_id,
            raw_value=raw_jurisdiction,
        )
        if jurisdiction is None:
            raise InvariantViolation("Source Record jurisdiction cannot be resolved")
        occurred_at = self._now()
        candidate = self._normalizer.normalize(
            source_record=source_record,
            jurisdiction=jurisdiction,
            geocoder=self._geocoder,
            occurred_at=occurred_at,
        )
        evidence = PermitSourceEvidence(
            source_id=source_record.source_id,
            source_record_id=source_record.source_record_id,
            external_record_id=source_record.external_record_id,
            record_fingerprint=source_record.payload_digest.hexadecimal,
            parser_version=source_record.parser_version,
            observed_at=source_record.observed_at,
        )

        exact, exact_layer = self._find_exact(source_record)
        if exact is not None:
            if self._has_fingerprint(exact, evidence):
                exact.attach_exact_evidence(evidence, occurred_at)
                self._permits.save(exact)
                duplicate_evidence = (
                    DuplicateEvidence(exact_layer, "exact normalized evidence matched", 100),
                )
                return self._finish(
                    source_record,
                    PermitNormalizationOutcome.EXACT_DUPLICATE,
                    exact,
                    duplicate_evidence,
                    candidate.warnings,
                )
            exact.apply_normalized_correction(
                evidence=evidence,
                permit_number=candidate.permit_number,
                authority_status=candidate.authority_status,
                permit_type=candidate.permit_type,
                description=candidate.description,
                applied_on=candidate.applied_on,
                issued_on=candidate.issued_on,
                address=candidate.address,
                parcel_reference=candidate.parcel_reference,
                valuation=candidate.valuation,
                parties=candidate.parties,
                occurred_at=occurred_at,
            )
            self._permits.save(exact)
            review_tasks = self._address_reviews(exact, occurred_at)
            return self._finish(
                source_record,
                PermitNormalizationOutcome.CORRECTED,
                exact,
                (
                    DuplicateEvidence(
                        DuplicateEvidenceLayer.SOURCE_EXTERNAL_IDENTIFIER,
                        "source external identifier matched with a changed fingerprint",
                        100,
                    ),
                ),
                candidate.warnings,
                review_tasks=review_tasks,
            )

        permit = Permit(
            permit_id=self._permit_id(source_record),
            jurisdiction_id=jurisdiction.jurisdiction_id,
            permit_number=candidate.permit_number,
            source_record_ids={source_record.source_record_id},
            parser_version=source_record.parser_version,
            recorded_at=occurred_at,
            issued_on=candidate.issued_on,
            address=candidate.address,
            parcel_reference=candidate.parcel_reference,
            valuation=candidate.valuation,
            authority_status=candidate.authority_status,
            permit_type=candidate.permit_type,
            description=candidate.description,
            applied_on=candidate.applied_on,
            parties=candidate.parties,
            source_evidence=[evidence],
        )
        probable_permit, probable_evidence = self._find_probable(permit)
        self._permits.save(permit)
        review_tasks = list(self._address_reviews(permit, occurred_at))
        if probable_permit is None:
            return self._finish(
                source_record,
                PermitNormalizationOutcome.CREATED,
                permit,
                (),
                candidate.warnings,
                review_tasks=tuple(review_tasks),
            )

        duplicate_candidate = self._candidate(permit, probable_permit, probable_evidence, occurred_at)
        self._duplicate_candidates.save(duplicate_candidate)
        duplicate_review = self._review_task(
            ReviewSubjectType.PERMIT_DUPLICATE,
            str(duplicate_candidate.candidate_id),
            "probable permit duplicate requires an explicit merge or distinct decision",
            occurred_at,
        )
        self._reviews.save(duplicate_review)
        review_tasks.append(duplicate_review)
        return self._finish(
            source_record,
            PermitNormalizationOutcome.PROBABLE_DUPLICATE,
            permit,
            probable_evidence,
            candidate.warnings,
            duplicate_candidate=duplicate_candidate,
            review_tasks=tuple(review_tasks),
        )

    def decide_duplicate(
        self,
        candidate_id: DuplicateCandidateId,
        *,
        decision: ManualDuplicateDecision,
        actor_id: str,
        rationale: str,
    ) -> PermitDuplicateCandidate:
        candidate = self._duplicate_candidates.get(candidate_id)
        if candidate is None:
            raise InvariantViolation("permit duplicate candidate does not exist")
        occurred_at = self._now()
        incoming = self._permits.get(candidate.permit_id)
        canonical = self._permits.get(candidate.possible_duplicate_of_id)
        if incoming is None or canonical is None:
            raise InvariantViolation("permit duplicate candidate references unavailable permits")
        candidate.decide(
            decision,
            actor_id=actor_id,
            rationale=rationale,
            occurred_at=occurred_at,
        )
        if decision is ManualDuplicateDecision.MERGE:
            canonical.absorb_manual_merge(incoming, rationale=rationale, occurred_at=occurred_at)
            incoming.supersede(canonical.permit_id, rationale=rationale, occurred_at=occurred_at)
            self._permits.save(canonical)
            self._permits.save(incoming)
        self._duplicate_candidates.save(candidate)
        self._metrics.increment(
            "permit_duplicate_decisions_total",
            labels=(("decision", decision.value),),
        )
        return candidate

    def _find_exact(
        self,
        source_record: SourceRecord,
    ) -> tuple[Permit | None, DuplicateEvidenceLayer]:
        if source_record.external_record_id is not None:
            permit = self._permits.find_by_source_external(
                source_record.source_id,
                source_record.external_record_id,
            )
            if permit is not None:
                return permit, DuplicateEvidenceLayer.SOURCE_EXTERNAL_IDENTIFIER
        permit = self._permits.find_by_source_fingerprint(
            source_record.source_id,
            source_record.payload_digest.hexadecimal,
        )
        return permit, DuplicateEvidenceLayer.SOURCE_RECORD_FINGERPRINT

    @staticmethod
    def _has_fingerprint(permit: Permit, evidence: PermitSourceEvidence) -> bool:
        return any(
            item.source_id == evidence.source_id
            and item.record_fingerprint == evidence.record_fingerprint
            for item in permit.source_evidence
        )

    def _find_probable(
        self,
        incoming: Permit,
    ) -> tuple[Permit | None, tuple[DuplicateEvidence, ...]]:
        best: Permit | None = None
        best_evidence: tuple[DuplicateEvidence, ...] = ()
        best_score = 0
        for existing in self._permits.list_by_jurisdiction(incoming.jurisdiction_id):
            if existing.status in {PermitStatus.VOIDED, PermitStatus.SUPERSEDED}:
                continue
            evidence = self._similarity_evidence(incoming, existing)
            score = sum(item.score for item in evidence)
            if score >= 75 and score > best_score:
                best = existing
                best_evidence = evidence
                best_score = score
        return best, best_evidence

    @staticmethod
    def _similarity_evidence(
        incoming: Permit,
        existing: Permit,
    ) -> tuple[DuplicateEvidence, ...]:
        score = 0
        reasons: list[str] = ["jurisdiction matched"]
        incoming_address = incoming.address.canonical_key() if incoming.address else None
        existing_address = existing.address.canonical_key() if existing.address else None
        if incoming_address is not None and incoming_address == existing_address:
            score += 45
            reasons.append("normalized address matched")
        incoming_type = incoming.permit_type.code if incoming.permit_type else None
        existing_type = existing.permit_type.code if existing.permit_type else None
        if incoming_type is not None and incoming_type == existing_type:
            score += 25
            reasons.append("normalized permit type matched")
        incoming_date = incoming.issued_on or incoming.applied_on
        existing_date = existing.issued_on or existing.applied_on
        if incoming_date is not None and existing_date is not None:
            difference = abs((incoming_date.value - existing_date.value).days)
            if difference == 0:
                score += 30
                reasons.append("permit date matched")
            elif difference <= 7:
                score += 20
                reasons.append("permit dates are within seven days")
        if score == 0:
            return ()
        return (
            DuplicateEvidence(
                DuplicateEvidenceLayer.JURISDICTION_ADDRESS_TYPE_DATE,
                "; ".join(reasons),
                score,
            ),
        )

    def _candidate(
        self,
        permit: Permit,
        existing: Permit,
        evidence: tuple[DuplicateEvidence, ...],
        occurred_at: UtcTimestamp,
    ) -> PermitDuplicateCandidate:
        seed = "|".join(sorted((str(permit.permit_id), str(existing.permit_id))))
        candidate_id = DuplicateCandidateId(
            f"duplicate-{hashlib.sha256(seed.encode()).hexdigest()}"
        )
        prior = self._duplicate_candidates.get(candidate_id)
        if prior is not None:
            return prior
        return PermitDuplicateCandidate(
            candidate_id,
            permit.permit_id,
            existing.permit_id,
            evidence,
            occurred_at,
        )

    def _address_reviews(self, permit: Permit, occurred_at: UtcTimestamp) -> tuple[ReviewTask, ...]:
        address = permit.address
        if address is None or address.review_reason is None:
            return ()
        review = self._review_task(
            ReviewSubjectType.ADDRESS,
            str(address.address_id),
            address.review_reason,
            occurred_at,
        )
        self._reviews.save(review)
        return (review,)

    @staticmethod
    def _review_task(
        subject_type: ReviewSubjectType,
        subject_id: str,
        reason: str,
        occurred_at: UtcTimestamp,
    ) -> ReviewTask:
        seed = f"{subject_type.value}|{subject_id}|{reason}".encode()
        return ReviewTask(
            ReviewTaskId(f"review-{hashlib.sha256(seed).hexdigest()}"),
            subject_type,
            subject_id,
            reason,
            occurred_at,
        )

    @staticmethod
    def _permit_id(source_record: SourceRecord) -> PermitId:
        identity = source_record.external_record_id or source_record.payload_digest.hexadecimal
        seed = f"{source_record.source_id}|{identity}".encode()
        return PermitId(f"permit-{hashlib.sha256(seed).hexdigest()}")

    @staticmethod
    def _text_value(source_record: SourceRecord, canonical_field: str) -> str | None:
        value = next(
            (item.normalized_value for item in source_record.parsed_values if item.canonical_field == canonical_field),
            None,
        )
        return value if isinstance(value, str) and value.strip() else None

    def _finish(
        self,
        source_record: SourceRecord,
        outcome: PermitNormalizationOutcome,
        permit: Permit,
        evidence: tuple[DuplicateEvidence, ...],
        warnings: tuple[str, ...],
        *,
        duplicate_candidate: PermitDuplicateCandidate | None = None,
        review_tasks: tuple[ReviewTask, ...] = (),
    ) -> PermitNormalizationResult:
        duplicate_layer = evidence[0].layer.value if evidence else None
        self._metrics.increment(
            "permit_normalizations_total",
            labels=(("outcome", outcome.value),),
        )
        self._logger.record(
            NormalizationLogEntry(
                event="source_record_normalized",
                source_id=str(source_record.source_id),
                source_record_id=str(source_record.source_record_id),
                permit_id=str(permit.permit_id),
                outcome=outcome.value,
                parser_version=source_record.parser_version or "unknown",
                duplicate_layer=duplicate_layer,
                review_count=len(review_tasks),
            )
        )
        return PermitNormalizationResult(
            outcome,
            permit,
            evidence,
            duplicate_candidate,
            review_tasks,
            warnings,
        )
