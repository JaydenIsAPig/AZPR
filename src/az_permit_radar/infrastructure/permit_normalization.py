"""Deterministic Arizona permit/address normalization and local adapters."""

from __future__ import annotations

import hashlib
import re
import threading
from copy import deepcopy
from dataclasses import replace
from decimal import Decimal, InvalidOperation

from az_permit_radar.application.normalization import (
    GeocodingAdapter,
    GeocodingResponse,
    NormalizationLogEntry,
    NormalizedPermitCandidate,
)
from az_permit_radar.domain.deduplication import PermitDuplicateCandidate
from az_permit_radar.domain.errors import InvalidValue
from az_permit_radar.domain.ingestion import SourceRecord
from az_permit_radar.domain.permit import (
    Address,
    AddressResolutionStatus,
    CoordinateSource,
    GeocodeQuality,
    GeocodeResult,
    NormalizedPermitType,
    ParcelReference,
    Permit,
    PermitAuthorityStatus,
    PermitParty,
    PermitPartyRole,
    PermitStatus,
)
from az_permit_radar.domain.review import ReviewTask
from az_permit_radar.domain.source_registry import Jurisdiction
from az_permit_radar.domain.value_objects import (
    AddressId,
    CalendarDate,
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


_STATUS_MAP = {
    "applied": PermitAuthorityStatus.APPLIED,
    "application received": PermitAuthorityStatus.APPLIED,
    "pending": PermitAuthorityStatus.APPLIED,
    "issued": PermitAuthorityStatus.ISSUED,
    "permit issued": PermitAuthorityStatus.ISSUED,
    "active": PermitAuthorityStatus.ACTIVE,
    "open": PermitAuthorityStatus.ACTIVE,
    "complete": PermitAuthorityStatus.COMPLETED,
    "completed": PermitAuthorityStatus.COMPLETED,
    "final": PermitAuthorityStatus.COMPLETED,
    "finaled": PermitAuthorityStatus.COMPLETED,
    "expired": PermitAuthorityStatus.EXPIRED,
    "cancelled": PermitAuthorityStatus.CANCELLED,
    "canceled": PermitAuthorityStatus.CANCELLED,
    "void": PermitAuthorityStatus.VOIDED,
    "voided": PermitAuthorityStatus.VOIDED,
}

_TYPE_MAP = {
    "residential remodel": ("remodel", "Remodel"),
    "commercial remodel": ("remodel", "Remodel"),
    "remodel": ("remodel", "Remodel"),
    "alteration": ("remodel", "Remodel"),
    "new commercial": ("new_construction", "New Construction"),
    "new residential": ("new_construction", "New Construction"),
    "new construction": ("new_construction", "New Construction"),
    "solar": ("solar", "Solar"),
    "photovoltaic": ("solar", "Solar"),
    "electrical": ("electrical", "Electrical"),
    "plumbing": ("plumbing", "Plumbing"),
    "mechanical": ("mechanical", "Mechanical"),
    "demolition": ("demolition", "Demolition"),
}

_STREET_REPLACEMENTS = (
    (r"\bNORTH\b", "N"),
    (r"\bSOUTH\b", "S"),
    (r"\bEAST\b", "E"),
    (r"\bWEST\b", "W"),
    (r"\bSTREET\b", "ST"),
    (r"\bAVENUE\b", "AVE"),
    (r"\bBOULEVARD\b", "BLVD"),
    (r"\bROAD\b", "RD"),
    (r"\bDRIVE\b", "DR"),
    (r"\bLANE\b", "LN"),
    (r"\bCOURT\b", "CT"),
    (r"\bPLACE\b", "PL"),
    (r"\bPARKWAY\b", "PKWY"),
    (r"\bHIGHWAY\b", "HWY"),
)


class ArizonaPermitRecordNormalizer:
    """Fixture-oriented deterministic normalization; no inference or AI."""

    def normalize(
        self,
        *,
        source_record: SourceRecord,
        jurisdiction: Jurisdiction,
        geocoder: GeocodingAdapter,
        occurred_at: UtcTimestamp,
    ) -> NormalizedPermitCandidate:
        warnings: list[str] = []
        permit_number_raw = self._text(source_record, "permit_number", "permit_identifier")
        if permit_number_raw is None:
            permit_number = f"UNIDENTIFIED-{source_record.payload_digest.hexadecimal[:12].upper()}"
            warnings.append("permit identifier missing; stable fingerprint fallback used")
        else:
            permit_number = self._permit_number(permit_number_raw)

        authority_status = self._authority_status(
            self._text(source_record, "permit_status", "status")
        )
        permit_type = self._permit_type(self._text(source_record, "permit_type", "type"))
        description = self._clean_text(
            self._text(source_record, "description", "work_description")
        )
        applied_on = self._date(source_record, "application_date", "applied_date")
        issued_on = self._date(source_record, "issued_date", "issue_date")
        if applied_on and issued_on and applied_on.value > issued_on.value:
            warnings.append("application date followed issue date; application date omitted")
            applied_on = None
        valuation = self._money(source_record, "valuation", "declared_valuation")
        parties = self._parties(source_record)
        address, address_warnings = self._address(
            source_record,
            jurisdiction,
            geocoder,
            occurred_at,
        )
        warnings.extend(address_warnings)
        parcel_reference = self._parcel(source_record, jurisdiction.jurisdiction_id)
        return NormalizedPermitCandidate(
            permit_number=permit_number,
            authority_status=authority_status,
            permit_type=permit_type,
            description=description,
            applied_on=applied_on,
            issued_on=issued_on,
            valuation=valuation,
            parties=parties,
            address=address,
            parcel_reference=parcel_reference,
            warnings=tuple(warnings),
        )

    @staticmethod
    def _value(source_record: SourceRecord, *names: str) -> object | None:
        by_name = {value.canonical_field: value.normalized_value for value in source_record.parsed_values}
        return next((by_name[name] for name in names if by_name.get(name) is not None), None)

    @classmethod
    def _text(cls, source_record: SourceRecord, *names: str) -> str | None:
        value = cls._value(source_record, *names)
        return value if isinstance(value, str) and value.strip() else None

    @classmethod
    def _date(cls, source_record: SourceRecord, *names: str) -> CalendarDate | None:
        value = cls._value(source_record, *names)
        return value if isinstance(value, CalendarDate) else None

    @classmethod
    def _money(cls, source_record: SourceRecord, *names: str) -> Money | None:
        value = cls._value(source_record, *names)
        return value if isinstance(value, Money) else None

    @staticmethod
    def _clean_text(value: str | None) -> str | None:
        return " ".join(value.split()) if value else None

    @staticmethod
    def _permit_number(value: str) -> str:
        normalized = re.sub(r"[^A-Z0-9]+", "-", value.upper()).strip("-")
        return normalized or "UNIDENTIFIED"

    @staticmethod
    def _authority_status(value: str | None) -> PermitAuthorityStatus:
        if value is None:
            return PermitAuthorityStatus.UNKNOWN
        return _STATUS_MAP.get(" ".join(value.lower().split()), PermitAuthorityStatus.UNKNOWN)

    @staticmethod
    def _permit_type(value: str | None) -> NormalizedPermitType | None:
        if value is None:
            return None
        cleaned = " ".join(value.lower().split())
        mapped = _TYPE_MAP.get(cleaned)
        if mapped is not None:
            return NormalizedPermitType(*mapped)
        code = re.sub(r"[^a-z0-9]+", "_", cleaned).strip("_")
        return NormalizedPermitType(code or "unknown", cleaned.title())

    @classmethod
    def _parties(cls, source_record: SourceRecord) -> tuple[PermitParty, ...]:
        parties: list[PermitParty] = []
        contractor = cls._text(source_record, "contractor_name", "contractor")
        contractor_license = cls._text(
            source_record,
            "contractor_license",
            "contractor_license_number",
        )
        applicant = cls._text(source_record, "applicant_name", "applicant")
        if contractor:
            parties.append(
                PermitParty(
                    PermitPartyRole.CONTRACTOR,
                    cls._party_name(contractor),
                    cls._license(contractor_license),
                )
            )
        if applicant:
            parties.append(PermitParty(PermitPartyRole.APPLICANT, cls._party_name(applicant)))
        return tuple(parties)

    @staticmethod
    def _party_name(value: str) -> str:
        return " ".join(value.upper().split())

    @staticmethod
    def _license(value: str | None) -> str | None:
        if value is None:
            return None
        normalized = re.sub(r"[^A-Z0-9]+", "", value.upper())
        return normalized or None

    @classmethod
    def _parcel(
        cls,
        source_record: SourceRecord,
        jurisdiction_id: JurisdictionId,
    ) -> ParcelReference | None:
        raw = cls._text(source_record, "parcel_id", "parcel_identifier", "apn")
        if raw is None:
            return None
        normalized = re.sub(r"[^A-Z0-9]+", "", raw.upper())
        return ParcelReference(jurisdiction_id, normalized, raw)

    def _address(
        self,
        source_record: SourceRecord,
        jurisdiction: Jurisdiction,
        geocoder: GeocodingAdapter,
        occurred_at: UtcTimestamp,
    ) -> tuple[Address | None, tuple[str, ...]]:
        raw = self._text(source_record, "address", "project_address")
        line1 = self._text(source_record, "address_line1", "street_address")
        line2 = self._text(source_record, "address_line2", "unit")
        city = self._text(source_record, "city")
        region = self._text(source_record, "state", "region_code")
        postal = self._text(source_record, "postal_code", "zip_code", "zip")
        fallback_city = re.sub(r"^City of\s+", "", jurisdiction.name, flags=re.IGNORECASE)
        if raw and line1 is None:
            line1, parsed_line2, parsed_city, parsed_region, parsed_postal = self._parse_address(
                raw,
                fallback_city,
            )
            line2 = line2 or parsed_line2
            city = city or parsed_city
            region = region or parsed_region
            postal = postal or parsed_postal
        if raw is None:
            raw = ", ".join(part for part in (line1, line2, city, region, postal) if part)
        if not raw:
            return None, ()
        normalized = self._normalized_address(line1, line2, city or fallback_city, region, postal)
        source_coordinates = self._coordinates(source_record)
        if source_coordinates is not None and normalized is not None:
            normalized = replace(normalized, coordinates=source_coordinates)
            return (
                Address(
                    self._address_id(raw, normalized),
                    raw,
                    normalized,
                    AddressResolutionStatus.NORMALIZED,
                    CoordinateSource.SOURCE,
                ),
                (),
            )

        response = geocoder.geocode(
            raw_address=raw,
            normalized_hint=normalized,
            jurisdiction=jurisdiction,
        )
        if response is not None:
            geocoded_address = replace(response.normalized_address, coordinates=response.coordinates)
            try:
                quality = GeocodeQuality(response.quality.lower())
            except ValueError:
                quality = GeocodeQuality.UNKNOWN
            provenance = GeocodeResult(
                response.provider,
                occurred_at,
                quality,
                response.confidence,
                response.coordinates,
            )
            return (
                Address(
                    self._address_id(raw, geocoded_address),
                    raw,
                    geocoded_address,
                    AddressResolutionStatus.GEOCODED,
                    CoordinateSource.GEOCODER,
                    provenance,
                ),
                (),
            )

        reason = "address could not be resolved by the configured geocoder"
        return (
            Address(
                self._address_id(raw, normalized),
                raw,
                normalized,
                AddressResolutionStatus.REVIEW_REQUIRED,
                CoordinateSource.NONE,
                review_reason=reason,
            ),
            (reason,),
        )

    @staticmethod
    def _parse_address(
        raw: str,
        fallback_city: str,
    ) -> tuple[str | None, str | None, str | None, str | None, str | None]:
        parts = [part.strip() for part in raw.split(",") if part.strip()]
        line = parts[0] if parts else raw.strip()
        city: str | None = None
        region: str | None = None
        postal: str | None = None
        if len(parts) >= 3:
            city = parts[-2]
            state_zip = parts[-1]
        elif len(parts) == 2:
            state_zip = parts[-1]
            match = re.fullmatch(r"(.+?)\s+(AZ)\s+([0-9]{5}(?:-[0-9]{4})?)", state_zip, re.I)
            if match:
                city, region, postal = match.groups()
            else:
                city = fallback_city
        else:
            state_zip = ""
            tail = re.search(
                rf"\b({re.escape(fallback_city)})\s+(AZ)\s+([0-9]{{5}}(?:-[0-9]{{4}})?)$",
                line,
                re.I,
            )
            if tail:
                city, region, postal = tail.groups()
                line = line[: tail.start()].strip(" ,")
        if region is None and state_zip:
            match = re.fullmatch(r"(AZ)\s+([0-9]{5}(?:-[0-9]{4})?)", state_zip, re.I)
            if match:
                region, postal = match.groups()
        line, line2 = ArizonaPermitRecordNormalizer._split_unit(line)
        return line, line2, city or fallback_city, region, postal

    @staticmethod
    def _split_unit(line: str) -> tuple[str, str | None]:
        match = re.search(
            r"\s+(?:(APT|APARTMENT|UNIT)|(#)|(STE|SUITE))\s*([A-Z0-9-]+)$",
            line,
            re.I,
        )
        if match is None:
            return line, None
        unit = match.group(4).upper()
        prefix = "STE" if match.group(3) else "UNIT"
        return line[: match.start()].strip(), f"{prefix} {unit}"

    @staticmethod
    def _street_line(value: str) -> str:
        normalized = " ".join(value.upper().replace(".", "").split())
        for pattern, replacement in _STREET_REPLACEMENTS:
            normalized = re.sub(pattern, replacement, normalized)
        return normalized

    @classmethod
    def _normalized_address(
        cls,
        line1: str | None,
        line2: str | None,
        city: str | None,
        region: str | None,
        postal: str | None,
    ) -> NormalizedAddress | None:
        if not line1 or not city or not region or not postal:
            return None
        region_code = region.upper().strip()
        postal_code = postal.strip()
        if region_code != "AZ" or not re.fullmatch(r"[0-9]{5}(?:-[0-9]{4})?", postal_code):
            return None
        normalized_line1, embedded_line2 = cls._split_unit(line1)
        normalized_line2 = line2 or embedded_line2
        if normalized_line2:
            _unused, normalized_line2 = cls._split_unit(f"X {normalized_line2}")
            normalized_line2 = normalized_line2 or " ".join(line2.upper().split())
        return NormalizedAddress(
            cls._street_line(normalized_line1),
            " ".join(city.upper().split()),
            region_code,
            postal_code,
            normalized_line2,
        )

    @classmethod
    def _coordinates(cls, source_record: SourceRecord) -> GeographicCoordinates | None:
        latitude = cls._text(source_record, "latitude", "lat")
        longitude = cls._text(source_record, "longitude", "lon", "lng")
        if latitude is None or longitude is None:
            return None
        try:
            return GeographicCoordinates(Decimal(latitude), Decimal(longitude))
        except (InvalidOperation, InvalidValue):
            return None

    @staticmethod
    def _address_id(raw: str, normalized: NormalizedAddress | None) -> AddressId:
        identity = (
            "|".join(
                (
                    normalized.line1,
                    normalized.line2 or "",
                    normalized.city,
                    normalized.region_code,
                    normalized.postal_code,
                )
            )
            if normalized is not None
            else " ".join(raw.upper().split())
        )
        return AddressId(f"address-{hashlib.sha256(identity.encode()).hexdigest()}")


class InMemoryJurisdictionResolver:
    def __init__(
        self,
        source_jurisdictions: dict[SourceId, Jurisdiction],
        aliases: dict[JurisdictionId, tuple[str, ...]] | None = None,
    ) -> None:
        self._source_jurisdictions = dict(source_jurisdictions)
        self._aliases = dict(aliases or {})

    def resolve(self, *, source_id: SourceId, raw_value: str | None) -> Jurisdiction | None:
        jurisdiction = self._source_jurisdictions.get(source_id)
        if jurisdiction is None:
            return None
        if raw_value is None:
            return deepcopy(jurisdiction)
        accepted = {
            jurisdiction.name.lower(),
            re.sub(r"^city of\s+", "", jurisdiction.name.lower()),
            *(alias.lower() for alias in self._aliases.get(jurisdiction.jurisdiction_id, ())),
        }
        return deepcopy(jurisdiction) if " ".join(raw_value.lower().split()) in accepted else None


class FakeGeocoder:
    def __init__(self, responses: dict[str, GeocodingResponse | None]) -> None:
        self._responses = dict(responses)
        self.calls: list[str] = []

    def geocode(
        self,
        *,
        raw_address: str,
        normalized_hint: NormalizedAddress | None,
        jurisdiction: Jurisdiction,
    ) -> GeocodingResponse | None:
        del normalized_hint, jurisdiction
        self.calls.append(raw_address)
        return self._responses.get(raw_address)


class NullGeocoder(FakeGeocoder):
    def __init__(self) -> None:
        super().__init__({})


class InMemoryPermitNormalizationStore:
    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._permits: dict[PermitId, Permit] = {}
        self._source_external: dict[tuple[SourceId, str], PermitId] = {}
        self._source_fingerprint: dict[tuple[SourceId, str], PermitId] = {}

    def get(self, permit_id: PermitId) -> Permit | None:
        with self._lock:
            permit = self._permits.get(permit_id)
            return deepcopy(permit) if permit is not None else None

    def find_by_source_external(
        self,
        source_id: SourceId,
        external_record_id: str,
    ) -> Permit | None:
        with self._lock:
            permit_id = self._source_external.get((source_id, external_record_id))
            return self.get(permit_id) if permit_id is not None else None

    def find_by_source_fingerprint(self, source_id: SourceId, fingerprint: str) -> Permit | None:
        with self._lock:
            permit_id = self._source_fingerprint.get((source_id, fingerprint))
            return self.get(permit_id) if permit_id is not None else None

    def list_by_jurisdiction(self, jurisdiction_id: JurisdictionId) -> tuple[Permit, ...]:
        with self._lock:
            return tuple(
                deepcopy(permit)
                for permit in self._permits.values()
                if permit.jurisdiction_id == jurisdiction_id
            )

    def save(self, permit: Permit) -> None:
        with self._lock:
            self._permits[permit.permit_id] = deepcopy(permit)
            self._rebuild_indexes()

    def _rebuild_indexes(self) -> None:
        self._source_external.clear()
        self._source_fingerprint.clear()
        for permit in self._permits.values():
            if permit.status is PermitStatus.SUPERSEDED:
                continue
            for evidence in permit.source_evidence:
                if evidence.external_record_id is not None:
                    self._source_external[(evidence.source_id, evidence.external_record_id)] = (
                        permit.permit_id
                    )
                self._source_fingerprint[(evidence.source_id, evidence.record_fingerprint)] = (
                    permit.permit_id
                )

    @property
    def permits(self) -> tuple[Permit, ...]:
        with self._lock:
            return tuple(deepcopy(permit) for permit in self._permits.values())


class InMemoryDuplicateCandidateStore:
    def __init__(self) -> None:
        self._candidates: dict[DuplicateCandidateId, PermitDuplicateCandidate] = {}

    def get(self, candidate_id: DuplicateCandidateId) -> PermitDuplicateCandidate | None:
        candidate = self._candidates.get(candidate_id)
        return deepcopy(candidate) if candidate is not None else None

    def save(self, candidate: PermitDuplicateCandidate) -> None:
        self._candidates[candidate.candidate_id] = deepcopy(candidate)

    @property
    def candidates(self) -> tuple[PermitDuplicateCandidate, ...]:
        return tuple(deepcopy(candidate) for candidate in self._candidates.values())


class InMemoryNormalizationReviewStore:
    def __init__(self) -> None:
        self.tasks: dict[ReviewTaskId, ReviewTask] = {}

    def save(self, review_task: ReviewTask) -> None:
        self.tasks[review_task.review_task_id] = deepcopy(review_task)


class InMemoryNormalizationLogger:
    def __init__(self) -> None:
        self.entries: list[NormalizationLogEntry] = []

    def record(self, entry: NormalizationLogEntry) -> None:
        self.entries.append(entry)


class InMemoryNormalizationMetrics:
    def __init__(self) -> None:
        self.counters: dict[tuple[str, tuple[tuple[str, str], ...]], int] = {}

    def increment(self, name: str, *, labels: tuple[tuple[str, str], ...] = ()) -> None:
        key = (name, tuple(sorted(labels)))
        self.counters[key] = self.counters.get(key, 0) + 1
