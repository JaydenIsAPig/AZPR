"""Permit domain aggregate and location concepts."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from .errors import InvalidStateTransition, InvariantViolation
from .events import EventRecorder, state_change_event
from .value_objects import (
    AddressId,
    CalendarDate,
    Confidence,
    GeographicCoordinates,
    JurisdictionId,
    Money,
    NormalizedAddress,
    PermitId,
    SourceId,
    SourceRecordId,
    UtcTimestamp,
)


class AddressResolutionStatus(str, Enum):
    NOT_PRESENT = "not_present"
    NORMALIZED = "normalized"
    GEOCODED = "geocoded"
    REVIEW_REQUIRED = "review_required"


class CoordinateSource(str, Enum):
    NONE = "none"
    SOURCE = "source"
    GEOCODER = "geocoder"


class GeocodeQuality(str, Enum):
    ROOFTOP = "rooftop"
    PARCEL = "parcel"
    STREET = "street"
    LOCALITY = "locality"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class GeocodeResult:
    provider: str
    resolved_at: UtcTimestamp
    quality: GeocodeQuality
    confidence: Confidence
    coordinates: GeographicCoordinates

    def __post_init__(self) -> None:
        if not self.provider.strip():
            raise InvariantViolation("geocode provider is required")


class PermitAuthorityStatus(str, Enum):
    UNKNOWN = "unknown"
    APPLIED = "applied"
    ISSUED = "issued"
    ACTIVE = "active"
    COMPLETED = "completed"
    EXPIRED = "expired"
    CANCELLED = "cancelled"
    VOIDED = "voided"


@dataclass(frozen=True, slots=True)
class NormalizedPermitType:
    code: str
    label: str

    def __post_init__(self) -> None:
        if not self.code.strip() or not self.label.strip():
            raise InvariantViolation("normalized permit type code and label are required")


class PermitPartyRole(str, Enum):
    CONTRACTOR = "contractor"
    APPLICANT = "applicant"


@dataclass(frozen=True, slots=True)
class PermitParty:
    role: PermitPartyRole
    name: str
    license_number: str | None = None

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise InvariantViolation("permit party name is required")
        if self.license_number is not None and not self.license_number.strip():
            raise InvariantViolation("permit party license number cannot be blank")


@dataclass(frozen=True, slots=True)
class PermitSourceEvidence:
    source_id: SourceId
    source_record_id: SourceRecordId
    external_record_id: str | None
    record_fingerprint: str
    parser_version: str
    observed_at: UtcTimestamp

    def __post_init__(self) -> None:
        if self.external_record_id is not None and not self.external_record_id.strip():
            raise InvariantViolation("permit evidence external identifier cannot be blank")
        if not self.record_fingerprint.strip() or not self.parser_version.strip():
            raise InvariantViolation("permit evidence fingerprint and parser version are required")


@dataclass(frozen=True, slots=True)
class Address:
    address_id: AddressId
    raw_text: str
    normalized: NormalizedAddress | None = None
    resolution_status: AddressResolutionStatus = AddressResolutionStatus.NORMALIZED
    coordinate_source: CoordinateSource = CoordinateSource.NONE
    geocode_result: GeocodeResult | None = None
    review_reason: str | None = None

    def __post_init__(self) -> None:
        if not self.raw_text.strip() and self.normalized is None:
            raise InvariantViolation("address requires raw text or a normalized value")
        if self.resolution_status is AddressResolutionStatus.GEOCODED and self.geocode_result is None:
            raise InvariantViolation("a geocoded address requires geocoder provenance")
        if self.geocode_result is not None:
            if self.coordinate_source is not CoordinateSource.GEOCODER:
                raise InvariantViolation("geocoder provenance requires geocoder coordinate source")
            if self.normalized is None or self.normalized.coordinates != self.geocode_result.coordinates:
                raise InvariantViolation("geocoder coordinates must match the normalized address")
        if self.coordinate_source is CoordinateSource.SOURCE and (
            self.normalized is None or self.normalized.coordinates is None
        ):
            raise InvariantViolation("source coordinates require a normalized address")
        if self.resolution_status is AddressResolutionStatus.REVIEW_REQUIRED:
            if self.review_reason is None or not self.review_reason.strip():
                raise InvariantViolation("review-required address needs a reason")
        elif self.review_reason is not None:
            raise InvariantViolation("address review reason requires review-required status")

    def canonical_key(self) -> str | None:
        if self.normalized is None:
            return None
        value = self.normalized
        return "|".join(
            part.upper()
            for part in (
                value.line1,
                value.line2 or "",
                value.city,
                value.region_code,
                value.postal_code,
            )
        )


@dataclass(frozen=True, slots=True)
class ParcelReference:
    jurisdiction_id: JurisdictionId
    value: str
    raw_value: str | None = None

    def __post_init__(self) -> None:
        if not self.value.strip():
            raise InvariantViolation("parcel reference value is required")
        if self.raw_value is not None and not self.raw_value.strip():
            raise InvariantViolation("raw parcel reference cannot be blank")


class PermitStatus(str, Enum):
    ACTIVE = "active"
    CORRECTED = "corrected"
    VOIDED = "voided"
    SUPERSEDED = "superseded"


class PermitHistoryAction(str, Enum):
    EXACT_EVIDENCE_ATTACHED = "exact_evidence_attached"
    CORRECTED = "corrected"
    MANUAL_MERGE = "manual_merge"
    SUPERSEDED = "superseded"
    VOIDED = "voided"


@dataclass(frozen=True, slots=True)
class PermitSnapshot:
    permit_number: str
    authority_status: PermitAuthorityStatus
    permit_type: NormalizedPermitType | None
    description: str | None
    applied_on: CalendarDate | None
    issued_on: CalendarDate | None
    address: Address | None
    parcel_reference: ParcelReference | None
    valuation: Money | None
    parties: tuple[PermitParty, ...]
    parser_version: str
    source_record_ids: frozenset[SourceRecordId]


@dataclass(frozen=True, slots=True)
class PermitHistoryEntry:
    action: PermitHistoryAction
    occurred_at: UtcTimestamp
    reason: str
    source_record_id: SourceRecordId | None = None
    related_permit_id: PermitId | None = None
    previous: PermitSnapshot | None = None

    def __post_init__(self) -> None:
        if not self.reason.strip():
            raise InvariantViolation("permit history reason is required")


@dataclass(slots=True)
class Permit(EventRecorder):
    permit_id: PermitId
    jurisdiction_id: JurisdictionId
    permit_number: str
    source_record_ids: set[SourceRecordId]
    parser_version: str
    recorded_at: UtcTimestamp
    issued_on: CalendarDate | None = None
    address: Address | None = None
    parcel_reference: ParcelReference | None = None
    valuation: Money | None = None
    authority_status: PermitAuthorityStatus = PermitAuthorityStatus.UNKNOWN
    permit_type: NormalizedPermitType | None = None
    description: str | None = None
    applied_on: CalendarDate | None = None
    parties: tuple[PermitParty, ...] = ()
    source_evidence: list[PermitSourceEvidence] = field(default_factory=list)
    history: list[PermitHistoryEntry] = field(default_factory=list)
    superseded_by: PermitId | None = None
    merged_permit_ids: set[PermitId] = field(default_factory=set)
    status: PermitStatus = PermitStatus.ACTIVE
    version: int = 0

    def __post_init__(self) -> None:
        self._initialize_events()
        if not self.permit_number.strip():
            raise InvariantViolation("permit number is required")
        if not self.source_record_ids:
            raise InvariantViolation("permit requires at least one source record")
        if not self.parser_version.strip():
            raise InvariantViolation("permit parser version is required")
        if self.parcel_reference and self.parcel_reference.jurisdiction_id != self.jurisdiction_id:
            raise InvariantViolation("parcel reference jurisdiction must match permit jurisdiction")
        if self.applied_on and self.issued_on and self.applied_on.value > self.issued_on.value:
            raise InvariantViolation("permit application date cannot follow issue date")
        evidence_ids = {evidence.source_record_id for evidence in self.source_evidence}
        if not evidence_ids <= self.source_record_ids:
            raise InvariantViolation("permit evidence must reference permit source records")
        if self.status is PermitStatus.SUPERSEDED and self.superseded_by is None:
            raise InvariantViolation("superseded permit requires a canonical permit")
        if self.superseded_by == self.permit_id:
            raise InvariantViolation("permit cannot supersede itself")

    def snapshot(self) -> PermitSnapshot:
        return PermitSnapshot(
            permit_number=self.permit_number,
            authority_status=self.authority_status,
            permit_type=self.permit_type,
            description=self.description,
            applied_on=self.applied_on,
            issued_on=self.issued_on,
            address=self.address,
            parcel_reference=self.parcel_reference,
            valuation=self.valuation,
            parties=self.parties,
            parser_version=self.parser_version,
            source_record_ids=frozenset(self.source_record_ids),
        )

    def attach_exact_evidence(
        self,
        evidence: PermitSourceEvidence,
        occurred_at: UtcTimestamp,
    ) -> None:
        if self.status in {PermitStatus.VOIDED, PermitStatus.SUPERSEDED}:
            raise InvalidStateTransition("Permit", self.status, PermitStatus.ACTIVE)
        if evidence.source_record_id in self.source_record_ids:
            return
        self.source_record_ids.add(evidence.source_record_id)
        self.source_evidence.append(evidence)
        self.parser_version = evidence.parser_version
        self.history.append(
            PermitHistoryEntry(
                PermitHistoryAction.EXACT_EVIDENCE_ATTACHED,
                occurred_at,
                "exact duplicate evidence attached without changing normalized facts",
                source_record_id=evidence.source_record_id,
            )
        )
        self.version += 1

    def apply_normalized_correction(
        self,
        *,
        evidence: PermitSourceEvidence,
        permit_number: str,
        authority_status: PermitAuthorityStatus,
        permit_type: NormalizedPermitType | None,
        description: str | None,
        applied_on: CalendarDate | None,
        issued_on: CalendarDate | None,
        address: Address | None,
        parcel_reference: ParcelReference | None,
        valuation: Money | None,
        parties: tuple[PermitParty, ...],
        occurred_at: UtcTimestamp,
    ) -> None:
        if self.status in {PermitStatus.VOIDED, PermitStatus.SUPERSEDED}:
            raise InvalidStateTransition("Permit", self.status, PermitStatus.CORRECTED)
        if evidence.source_record_id in self.source_record_ids:
            raise InvariantViolation("permit correction requires a new source record")
        if applied_on and issued_on and applied_on.value > issued_on.value:
            raise InvariantViolation("permit application date cannot follow issue date")
        if parcel_reference and parcel_reference.jurisdiction_id != self.jurisdiction_id:
            raise InvariantViolation("parcel reference jurisdiction must match permit jurisdiction")
        previous = self.snapshot()
        self.permit_number = permit_number
        self.authority_status = authority_status
        self.permit_type = permit_type
        self.description = description
        self.applied_on = applied_on
        self.issued_on = issued_on
        self.address = address
        self.parcel_reference = parcel_reference
        self.valuation = valuation
        self.parties = parties
        self.source_record_ids.add(evidence.source_record_id)
        self.source_evidence.append(evidence)
        self.parser_version = evidence.parser_version
        self.status = PermitStatus.CORRECTED
        self.history.append(
            PermitHistoryEntry(
                PermitHistoryAction.CORRECTED,
                occurred_at,
                "changed source fingerprint produced a normalized correction",
                source_record_id=evidence.source_record_id,
                previous=previous,
            )
        )
        self.version += 1

    def record_correction(
        self,
        source_record_id: SourceRecordId,
        parser_version: str,
        occurred_at: UtcTimestamp,
    ) -> None:
        if self.status in {PermitStatus.VOIDED, PermitStatus.SUPERSEDED}:
            raise InvalidStateTransition("Permit", self.status, PermitStatus.CORRECTED)
        if source_record_id in self.source_record_ids:
            raise InvariantViolation("permit correction requires a new source record")
        if not parser_version.strip():
            raise InvariantViolation("permit correction parser version is required")
        snapshot = self.snapshot()
        previous = self.status
        self.source_record_ids.add(source_record_id)
        self.parser_version = parser_version
        self.status = PermitStatus.CORRECTED
        self.history.append(
            PermitHistoryEntry(
                PermitHistoryAction.CORRECTED,
                occurred_at,
                "source correction provenance attached",
                source_record_id=source_record_id,
                previous=snapshot,
            )
        )
        self.version += 1
        self._record(state_change_event(self, self.permit_id, previous, self.status, occurred_at))

    def void(self, occurred_at: UtcTimestamp) -> None:
        if self.status is PermitStatus.VOIDED:
            return
        if self.status is PermitStatus.SUPERSEDED:
            raise InvalidStateTransition("Permit", self.status, PermitStatus.VOIDED)
        previous = self.status
        self.status = PermitStatus.VOIDED
        self.history.append(
            PermitHistoryEntry(
                PermitHistoryAction.VOIDED,
                occurred_at,
                "permit was explicitly voided",
                previous=self.snapshot(),
            )
        )
        self.version += 1
        self._record(state_change_event(self, self.permit_id, previous, self.status, occurred_at))

    def absorb_manual_merge(
        self,
        duplicate: Permit,
        *,
        rationale: str,
        occurred_at: UtcTimestamp,
    ) -> None:
        if self.status in {PermitStatus.VOIDED, PermitStatus.SUPERSEDED}:
            raise InvalidStateTransition("Permit", self.status, PermitStatus.ACTIVE)
        if duplicate.permit_id == self.permit_id or duplicate.jurisdiction_id != self.jurisdiction_id:
            raise InvariantViolation("manual permit merge requires distinct permits in one jurisdiction")
        if not rationale.strip():
            raise InvariantViolation("manual merge rationale is required")
        previous_snapshot = self.snapshot()
        known_records = set(self.source_record_ids)
        self.source_record_ids.update(duplicate.source_record_ids)
        self.source_evidence.extend(
            evidence
            for evidence in duplicate.source_evidence
            if evidence.source_record_id not in known_records
        )
        self.merged_permit_ids.add(duplicate.permit_id)
        self.history.append(
            PermitHistoryEntry(
                PermitHistoryAction.MANUAL_MERGE,
                occurred_at,
                rationale,
                related_permit_id=duplicate.permit_id,
                previous=previous_snapshot,
            )
        )
        self.version += 1

    def supersede(
        self,
        canonical_permit_id: PermitId,
        *,
        rationale: str,
        occurred_at: UtcTimestamp,
    ) -> None:
        if self.status is PermitStatus.SUPERSEDED:
            if self.superseded_by == canonical_permit_id:
                return
            raise InvalidStateTransition("Permit", self.status, PermitStatus.SUPERSEDED)
        if canonical_permit_id == self.permit_id or not rationale.strip():
            raise InvariantViolation("permit supersession requires a distinct canonical permit and reason")
        previous = self.status
        snapshot = self.snapshot()
        self.status = PermitStatus.SUPERSEDED
        self.superseded_by = canonical_permit_id
        self.history.append(
            PermitHistoryEntry(
                PermitHistoryAction.SUPERSEDED,
                occurred_at,
                rationale,
                related_permit_id=canonical_permit_id,
                previous=snapshot,
            )
        )
        self.version += 1
        self._record(state_change_event(self, self.permit_id, previous, self.status, occurred_at))
