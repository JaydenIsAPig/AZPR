"""Customer Configuration aggregate and preference value objects."""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from enum import Enum

from .errors import ConsentRequired, InvalidStateTransition, InvariantViolation
from .events import ConfigurationChanged, EventRecorder, state_change_event
from .notification import NotificationChannel
from .value_objects import (
    Confidence,
    CustomerAccountId,
    DateRange,
    EmailAddress,
    GeographicCoordinates,
    JurisdictionId,
    Money,
    PhoneNumber,
    TradeTagId,
    UtcTimestamp,
)


@dataclass(frozen=True, slots=True)
class CustomerTradePreference:
    trade_tag_id: TradeTagId
    enabled: bool = True


@dataclass(frozen=True, slots=True)
class ServiceTerritory:
    jurisdiction_ids: frozenset[JurisdictionId] = frozenset()
    postal_codes: frozenset[str] = frozenset()
    radius_center: GeographicCoordinates | None = None
    radius_km: Decimal | None = None

    def __post_init__(self) -> None:
        if not self.jurisdiction_ids and not self.postal_codes and self.radius_center is None:
            raise InvariantViolation("service territory requires at least one geographic scope")
        for postal_code in self.postal_codes:
            if len(postal_code) not in {5, 10} or not postal_code[:5].isdigit():
                raise InvariantViolation(f"invalid service territory postal code: {postal_code!r}")
        if (self.radius_center is None) != (self.radius_km is None):
            raise InvariantViolation("radius center and radius distance must be supplied together")
        if self.radius_km is not None:
            try:
                radius = Decimal(self.radius_km)
            except (InvalidOperation, TypeError) as exc:
                raise InvariantViolation("service radius must be decimal-compatible") from exc
            if not radius.is_finite() or radius <= 0:
                raise InvariantViolation("service radius must be positive")
            object.__setattr__(self, "radius_km", radius)


@dataclass(frozen=True, slots=True)
class CustomerFilter:
    minimum_valuation: Money | None = None
    maximum_valuation: Money | None = None
    minimum_confidence: Confidence | None = None
    issued_during: DateRange | None = None
    excluded_project_classification_codes: frozenset[str] = frozenset()

    def __post_init__(self) -> None:
        if self.minimum_valuation and self.maximum_valuation:
            if self.minimum_valuation.currency != self.maximum_valuation.currency:
                raise InvariantViolation("customer valuation filter currencies must match")
            if self.minimum_valuation.amount > self.maximum_valuation.amount:
                raise InvariantViolation("minimum valuation cannot exceed maximum valuation")
        if any(not code.strip() for code in self.excluded_project_classification_codes):
            raise InvariantViolation("excluded project classification codes cannot be blank")


@dataclass(frozen=True, slots=True)
class NotificationPreference:
    channel: NotificationChannel
    enabled: bool
    destination: EmailAddress | PhoneNumber | None = None
    consent_granted_at: UtcTimestamp | None = None
    consent_reference: str | None = None

    def __post_init__(self) -> None:
        if self.channel is NotificationChannel.EMAIL and self.destination is not None and not isinstance(
            self.destination, EmailAddress
        ):
            raise InvariantViolation("email preference requires an email destination")
        if self.channel is NotificationChannel.SMS and self.destination is not None and not isinstance(
            self.destination, PhoneNumber
        ):
            raise InvariantViolation("SMS preference requires a phone destination")
        if self.enabled and (
            self.destination is None
            or self.consent_granted_at is None
            or self.consent_reference is None
            or not self.consent_reference.strip()
        ):
            raise ConsentRequired("enabled notification preference requires destination and explicit consent")


class CustomerAccountStatus(str, Enum):
    ACTIVE = "active"
    SUSPENDED = "suspended"
    CLOSED = "closed"


_CUSTOMER_TRANSITIONS = {
    CustomerAccountStatus.ACTIVE: frozenset({CustomerAccountStatus.SUSPENDED, CustomerAccountStatus.CLOSED}),
    CustomerAccountStatus.SUSPENDED: frozenset({CustomerAccountStatus.ACTIVE, CustomerAccountStatus.CLOSED}),
    CustomerAccountStatus.CLOSED: frozenset(),
}


@dataclass(slots=True)
class CustomerAccount(EventRecorder):
    customer_account_id: CustomerAccountId
    business_name: str
    created_at: UtcTimestamp
    status: CustomerAccountStatus = CustomerAccountStatus.ACTIVE
    trade_preferences: dict[TradeTagId, CustomerTradePreference] = field(default_factory=dict)
    service_territory: ServiceTerritory | None = None
    customer_filter: CustomerFilter | None = None
    notification_preferences: dict[NotificationChannel, NotificationPreference] = field(default_factory=dict)
    version: int = 0

    def __post_init__(self) -> None:
        self._initialize_events()
        if not self.business_name.strip():
            raise InvariantViolation("customer business name is required")

    def transition_to(self, requested: CustomerAccountStatus, occurred_at: UtcTimestamp) -> None:
        if requested == self.status:
            return
        if requested not in _CUSTOMER_TRANSITIONS[self.status]:
            raise InvalidStateTransition("CustomerAccount", self.status, requested)
        previous = self.status
        self.status = requested
        self.version += 1
        self._record(state_change_event(self, self.customer_account_id, previous, requested, occurred_at))

    def set_trade_preference(self, preference: CustomerTradePreference, occurred_at: UtcTimestamp) -> None:
        self._require_open()
        self.trade_preferences[preference.trade_tag_id] = preference
        self._configuration_changed("trade_preference", str(preference.trade_tag_id), occurred_at)

    def set_service_territory(self, territory: ServiceTerritory, occurred_at: UtcTimestamp) -> None:
        self._require_open()
        self.service_territory = territory
        self._configuration_changed("service_territory", "primary", occurred_at)

    def set_customer_filter(self, customer_filter: CustomerFilter, occurred_at: UtcTimestamp) -> None:
        self._require_open()
        self.customer_filter = customer_filter
        self._configuration_changed("customer_filter", "primary", occurred_at)

    def set_notification_preference(
        self,
        preference: NotificationPreference,
        occurred_at: UtcTimestamp,
    ) -> None:
        self._require_open()
        self.notification_preferences[preference.channel] = preference
        self._configuration_changed("notification_preference", preference.channel.value, occurred_at)

    def _configuration_changed(self, kind: str, key: str, occurred_at: UtcTimestamp) -> None:
        self.version += 1
        self._record(
            ConfigurationChanged(
                aggregate_id=str(self.customer_account_id),
                occurred_at=occurred_at,
                configuration_type=kind,
                configuration_key=key,
            )
        )

    def _require_open(self) -> None:
        if self.status is CustomerAccountStatus.CLOSED:
            raise InvariantViolation("closed customer account cannot be configured")
