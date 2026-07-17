"""Permit domain aggregate and location concepts."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .errors import InvalidStateTransition, InvariantViolation
from .events import EventRecorder, state_change_event
from .value_objects import (
    AddressId,
    CalendarDate,
    JurisdictionId,
    Money,
    NormalizedAddress,
    PermitId,
    SourceRecordId,
    UtcTimestamp,
)


@dataclass(frozen=True, slots=True)
class Address:
    address_id: AddressId
    raw_text: str
    normalized: NormalizedAddress | None = None

    def __post_init__(self) -> None:
        if not self.raw_text.strip() and self.normalized is None:
            raise InvariantViolation("address requires raw text or a normalized value")


@dataclass(frozen=True, slots=True)
class ParcelReference:
    jurisdiction_id: JurisdictionId
    value: str

    def __post_init__(self) -> None:
        if not self.value.strip():
            raise InvariantViolation("parcel reference value is required")


class PermitStatus(str, Enum):
    ACTIVE = "active"
    CORRECTED = "corrected"
    VOIDED = "voided"


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

    def record_correction(
        self,
        source_record_id: SourceRecordId,
        parser_version: str,
        occurred_at: UtcTimestamp,
    ) -> None:
        if self.status is PermitStatus.VOIDED:
            raise InvalidStateTransition("Permit", self.status, PermitStatus.CORRECTED)
        if source_record_id in self.source_record_ids:
            raise InvariantViolation("permit correction requires a new source record")
        if not parser_version.strip():
            raise InvariantViolation("permit correction parser version is required")
        previous = self.status
        self.source_record_ids.add(source_record_id)
        self.parser_version = parser_version
        self.status = PermitStatus.CORRECTED
        self.version += 1
        self._record(state_change_event(self, self.permit_id, previous, self.status, occurred_at))

    def void(self, occurred_at: UtcTimestamp) -> None:
        if self.status is PermitStatus.VOIDED:
            return
        previous = self.status
        self.status = PermitStatus.VOIDED
        self.version += 1
        self._record(state_change_event(self, self.permit_id, previous, self.status, occurred_at))
