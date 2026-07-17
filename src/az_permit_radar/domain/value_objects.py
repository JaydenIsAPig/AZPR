"""Validated immutable value objects used across bounded contexts."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import ClassVar

from .errors import InvalidValue


@dataclass(frozen=True, slots=True)
class Identifier:
    value: str
    _pattern: ClassVar[re.Pattern[str]] = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")

    def __post_init__(self) -> None:
        if not isinstance(self.value, str) or not self._pattern.fullmatch(self.value):
            raise InvalidValue(f"invalid {type(self).__name__}: {self.value!r}")

    def __str__(self) -> str:
        return self.value


class JurisdictionId(Identifier):
    pass


class SourceId(Identifier):
    pass


class SourceArtifactId(Identifier):
    pass


class ImportBatchId(Identifier):
    pass


class SourceRecordId(Identifier):
    pass


class PermitId(Identifier):
    pass


class AddressId(Identifier):
    pass


class TradeTagId(Identifier):
    pass


class ClassificationResultId(Identifier):
    pass


class OpportunityId(Identifier):
    pass


class CustomerAccountId(Identifier):
    pass


class OpportunityMatchId(Identifier):
    pass


class NotificationAttemptId(Identifier):
    pass


class ReviewTaskId(Identifier):
    pass


@dataclass(frozen=True, slots=True)
class CalendarDate:
    value: date

    def __post_init__(self) -> None:
        if not isinstance(self.value, date) or isinstance(self.value, datetime):
            raise InvalidValue("CalendarDate requires a date without a time")

    @classmethod
    def from_iso(cls, value: str) -> CalendarDate:
        try:
            return cls(date.fromisoformat(value))
        except (TypeError, ValueError) as exc:
            raise InvalidValue(f"invalid calendar date: {value!r}") from exc


@dataclass(frozen=True, slots=True)
class UtcTimestamp:
    value: datetime

    def __post_init__(self) -> None:
        if not isinstance(self.value, datetime) or self.value.tzinfo is None:
            raise InvalidValue("UtcTimestamp requires a timezone-aware datetime")
        object.__setattr__(self, "value", self.value.astimezone(timezone.utc))

    @classmethod
    def now(cls) -> UtcTimestamp:
        return cls(datetime.now(timezone.utc))


@dataclass(frozen=True, slots=True)
class DateRange:
    starts_on: CalendarDate
    ends_on: CalendarDate

    def __post_init__(self) -> None:
        if self.starts_on.value > self.ends_on.value:
            raise InvalidValue("date range start must not be after end")


@dataclass(frozen=True, slots=True)
class Money:
    amount: Decimal
    currency: str = "USD"

    def __post_init__(self) -> None:
        try:
            amount = Decimal(self.amount)
        except (InvalidOperation, TypeError) as exc:
            raise InvalidValue(f"invalid money amount: {self.amount!r}") from exc
        if not amount.is_finite() or amount < 0:
            raise InvalidValue("money amount must be finite and non-negative")
        if not isinstance(self.currency, str) or not re.fullmatch(r"[A-Z]{3}", self.currency):
            raise InvalidValue("currency must be a three-letter uppercase code")
        object.__setattr__(self, "amount", amount.quantize(Decimal("0.01")))


@dataclass(frozen=True, slots=True)
class Confidence:
    value: Decimal

    def __post_init__(self) -> None:
        try:
            value = Decimal(self.value)
        except (InvalidOperation, TypeError) as exc:
            raise InvalidValue(f"invalid confidence: {self.value!r}") from exc
        if not value.is_finite() or not Decimal("0") <= value <= Decimal("1"):
            raise InvalidValue("confidence must be between 0 and 1 inclusive")
        object.__setattr__(self, "value", value)


@dataclass(frozen=True, slots=True)
class GeographicCoordinates:
    latitude: Decimal
    longitude: Decimal

    def __post_init__(self) -> None:
        try:
            latitude = Decimal(self.latitude)
            longitude = Decimal(self.longitude)
        except (InvalidOperation, TypeError) as exc:
            raise InvalidValue("coordinates must be decimal-compatible") from exc
        if not latitude.is_finite() or not Decimal("-90") <= latitude <= Decimal("90"):
            raise InvalidValue("latitude must be between -90 and 90")
        if not longitude.is_finite() or not Decimal("-180") <= longitude <= Decimal("180"):
            raise InvalidValue("longitude must be between -180 and 180")
        object.__setattr__(self, "latitude", latitude)
        object.__setattr__(self, "longitude", longitude)


@dataclass(frozen=True, slots=True)
class PhoneNumber:
    value: str

    def __post_init__(self) -> None:
        if not isinstance(self.value, str) or not re.fullmatch(r"\+[1-9][0-9]{7,14}", self.value):
            raise InvalidValue("phone number must use E.164 format")


@dataclass(frozen=True, slots=True)
class EmailAddress:
    value: str

    def __post_init__(self) -> None:
        if not isinstance(self.value, str) or not re.fullmatch(
            r"[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Za-z0-9](?:[A-Za-z0-9.-]{0,251}[A-Za-z0-9])?",
            self.value,
        ):
            raise InvalidValue("invalid email address")
        object.__setattr__(self, "value", self.value.lower())


@dataclass(frozen=True, slots=True)
class NormalizedAddress:
    line1: str
    city: str
    region_code: str
    postal_code: str
    line2: str | None = None
    coordinates: GeographicCoordinates | None = None

    def __post_init__(self) -> None:
        for name in ("line1", "city", "region_code", "postal_code"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise InvalidValue(f"normalized address {name} is required")
        if not re.fullmatch(r"[A-Z]{2}", self.region_code):
            raise InvalidValue("region code must be a two-letter uppercase code")
        if not re.fullmatch(r"[0-9]{5}(?:-[0-9]{4})?", self.postal_code):
            raise InvalidValue("postal code must be ZIP or ZIP+4")
        object.__setattr__(self, "line1", " ".join(self.line1.split()))
        object.__setattr__(self, "city", " ".join(self.city.split()))
        if self.line2 is not None:
            normalized_line2 = " ".join(self.line2.split())
            object.__setattr__(self, "line2", normalized_line2 or None)


@dataclass(frozen=True, slots=True)
class ContentDigest:
    algorithm: str
    hexadecimal: str

    def __post_init__(self) -> None:
        algorithm = self.algorithm.lower()
        if algorithm != "sha256":
            raise InvalidValue("only sha256 content digests are supported")
        if not isinstance(self.hexadecimal, str) or not re.fullmatch(r"[0-9a-fA-F]{64}", self.hexadecimal):
            raise InvalidValue("sha256 digest must contain 64 hexadecimal characters")
        object.__setattr__(self, "algorithm", algorithm)
        object.__setattr__(self, "hexadecimal", self.hexadecimal.lower())


@dataclass(frozen=True, slots=True)
class IdempotencyKey:
    value: str

    def __post_init__(self) -> None:
        if not isinstance(self.value, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:-]{7,127}", self.value):
            raise InvalidValue("idempotency key must contain 8-128 safe characters")
