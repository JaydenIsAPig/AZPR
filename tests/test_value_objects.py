import unittest
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from az_permit_radar.domain.errors import InvalidValue
from az_permit_radar.domain.value_objects import (
    CalendarDate,
    Confidence,
    ContentDigest,
    DateRange,
    EmailAddress,
    GeographicCoordinates,
    IdempotencyKey,
    Money,
    NormalizedAddress,
    PermitId,
    PhoneNumber,
    UtcTimestamp,
)


class ValueObjectTests(unittest.TestCase):
    def test_identifier_rejects_blank_or_unsafe_values(self) -> None:
        for value in ("", " has space", "bad/value"):
            with self.subTest(value=value), self.assertRaises(InvalidValue):
                PermitId(value)

    def test_money_is_non_negative_and_quantized(self) -> None:
        self.assertEqual(Money(Decimal("12.345")).amount, Decimal("12.34"))
        with self.assertRaises(InvalidValue):
            Money(Decimal("-0.01"))
        with self.assertRaises(InvalidValue):
            Money(12.34)  # type: ignore[arg-type]

    def test_confidence_is_bounded(self) -> None:
        self.assertEqual(Confidence(Decimal("1")).value, Decimal("1"))
        for value in (Decimal("-0.1"), Decimal("1.1")):
            with self.subTest(value=value), self.assertRaises(InvalidValue):
                Confidence(value)

    def test_coordinates_enforce_world_bounds(self) -> None:
        GeographicCoordinates(Decimal("33.4484"), Decimal("-112.0740"))
        with self.assertRaises(InvalidValue):
            GeographicCoordinates(Decimal("91"), Decimal("0"))

    def test_timestamp_requires_timezone_and_normalizes_to_utc(self) -> None:
        with self.assertRaises(InvalidValue):
            UtcTimestamp(datetime(2026, 7, 17, 12, 0))
        timestamp = UtcTimestamp(datetime(2026, 7, 17, 5, 0, tzinfo=timezone(timedelta(hours=-7))))
        self.assertEqual(timestamp.value.hour, 12)
        self.assertEqual(timestamp.value.tzinfo, timezone.utc)

    def test_date_range_cannot_be_reversed(self) -> None:
        with self.assertRaises(InvalidValue):
            DateRange(CalendarDate(date(2026, 7, 18)), CalendarDate(date(2026, 7, 17)))

    def test_phone_uses_e164(self) -> None:
        self.assertEqual(PhoneNumber("+16025550123").value, "+16025550123")
        with self.assertRaises(InvalidValue):
            PhoneNumber("602-555-0123")

    def test_email_is_normalized(self) -> None:
        self.assertEqual(EmailAddress("Ops@Example.COM").value, "ops@example.com")

    def test_normalized_address_validates_region_and_postal_code(self) -> None:
        address = NormalizedAddress(" 100  W Main St ", " Phoenix ", "AZ", "85001")
        self.assertEqual(address.line1, "100 W Main St")
        with self.assertRaises(InvalidValue):
            NormalizedAddress("100 W Main St", "Phoenix", "Arizona", "85001")

    def test_content_digest_is_sha256_only(self) -> None:
        digest = ContentDigest("SHA256", "A" * 64)
        self.assertEqual(digest.hexadecimal, "a" * 64)
        with self.assertRaises(InvalidValue):
            ContentDigest("md5", "a" * 32)

    def test_idempotency_key_has_minimum_entropy_length(self) -> None:
        IdempotencyKey("notify:match-001:email")
        with self.assertRaises(InvalidValue):
            IdempotencyKey("short")


if __name__ == "__main__":
    unittest.main()
