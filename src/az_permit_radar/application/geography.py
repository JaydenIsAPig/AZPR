"""Explainable, customer-isolated service-territory evaluation."""

from __future__ import annotations

import math
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from enum import Enum
from functools import lru_cache
from typing import Protocol

from az_permit_radar.domain.customer import CustomerAccount, ServiceTerritory
from az_permit_radar.domain.errors import InvariantViolation
from az_permit_radar.domain.permit import Permit
from az_permit_radar.domain.opportunity import Opportunity
from az_permit_radar.domain.value_objects import CustomerAccountId, GeographicCoordinates, UtcTimestamp


class DistanceUnit(str, Enum):
    KILOMETERS = "km"


@dataclass(frozen=True, slots=True)
class GeographyPolicy:
    maximum_radius_km: Decimal
    maximum_postal_codes: int
    maximum_jurisdictions: int
    maximum_cities: int

    def __post_init__(self) -> None:
        try:
            radius = Decimal(self.maximum_radius_km)
        except (InvalidOperation, TypeError) as exc:
            raise InvariantViolation("maximum radius must be decimal-compatible") from exc
        if not radius.is_finite() or radius <= 0 or min(self.maximum_postal_codes, self.maximum_jurisdictions, self.maximum_cities) <= 0:
            raise InvariantViolation("geography limits must be positive")
        object.__setattr__(self, "maximum_radius_km", radius)


@dataclass(frozen=True, slots=True)
class TerritoryEvaluation:
    customer_account_id: CustomerAccountId
    inside_territory: bool
    distance_from_origin: Decimal | None
    distance_unit: DistanceUnit | None
    matched_rule: str | None
    exclusion_reason: str | None
    location_verified: bool


class PolygonContainment(Protocol):
    def contains(self, polygon_reference: str, coordinates: GeographicCoordinates) -> bool: ...


class ServiceTerritoryManager:
    def __init__(self, policy: GeographyPolicy) -> None:
        self.policy = policy

    def configure(self, customer: CustomerAccount, territory: ServiceTerritory, occurred_at: UtcTimestamp) -> None:
        if territory.radius_km is not None and territory.radius_km > self.policy.maximum_radius_km:
            raise InvariantViolation("service radius exceeds configured business maximum")
        if len(territory.postal_codes) > self.policy.maximum_postal_codes:
            raise InvariantViolation("postal-code territory exceeds configured business maximum")
        if len(territory.jurisdiction_ids) > self.policy.maximum_jurisdictions:
            raise InvariantViolation("jurisdiction territory exceeds configured business maximum")
        if len(territory.city_names) > self.policy.maximum_cities:
            raise InvariantViolation("city territory exceeds configured business maximum")
        customer.set_service_territory(territory, occurred_at)


class GeographyQueryService:
    """Uses Haversine great-circle distance on a spherical Earth (mean radius 6,371.0088 km)."""

    def __init__(self, polygon: PolygonContainment | None = None) -> None:
        self._polygon = polygon

    def evaluate(self, *, requesting_customer_id: CustomerAccountId, customer: CustomerAccount, permit: Permit) -> TerritoryEvaluation:
        if customer.customer_account_id != requesting_customer_id:
            raise InvariantViolation("service territory query cannot cross customer boundaries")
        territory = customer.service_territory
        if territory is None:
            return self._result(customer, False, reason="customer has no service territory", verified=False)

        address = permit.address
        normalized = address.normalized if address else None
        coordinates = normalized.coordinates if normalized else None
        distance = self._distance(territory.radius_center, coordinates) if territory.radius_center and coordinates else None

        if permit.jurisdiction_id in territory.jurisdiction_ids:
            return self._result(customer, True, distance, "jurisdiction", verified=True)
        if normalized and " ".join(normalized.city.upper().split()) in territory.city_names:
            return self._result(customer, True, distance, "city", verified=True)
        if normalized and normalized.postal_code[:5] in {code[:5] for code in territory.postal_codes}:
            return self._result(customer, True, distance, "postal_code", verified=True)
        if distance is not None and territory.radius_km is not None and distance <= territory.radius_km:
            return self._result(customer, True, distance, "radius", verified=True)
        if territory.polygon_reference and coordinates and self._polygon is not None and self._polygon.contains(territory.polygon_reference, coordinates):
            return self._result(customer, True, distance, "polygon", verified=True)

        verifiable_for_any_rule = bool(territory.jurisdiction_ids)
        verifiable_for_any_rule = verifiable_for_any_rule or bool(normalized and (territory.city_names or territory.postal_codes))
        verifiable_for_any_rule = verifiable_for_any_rule or bool(coordinates and territory.radius_center)
        verifiable_for_any_rule = verifiable_for_any_rule or bool(coordinates and territory.polygon_reference and self._polygon)
        cannot_verify = not verifiable_for_any_rule
        if cannot_verify and territory.allow_uncertain_geography:
            return self._result(customer, True, distance, "uncertain_geography_opt_in", verified=False)
        reason = "location cannot be verified" if cannot_verify else "verified location is outside service territory"
        return self._result(customer, False, distance, reason=reason, verified=not cannot_verify)

    def evaluate_opportunity(self, *, requesting_customer_id: CustomerAccountId, customer: CustomerAccount, opportunity: Opportunity, permits: tuple[Permit, ...]) -> TerritoryEvaluation:
        supplied = {permit.permit_id for permit in permits}
        if not permits or not opportunity.permit_ids <= supplied:
            raise InvariantViolation("opportunity geography query requires every referenced Permit")
        evaluations = tuple(self.evaluate(requesting_customer_id=requesting_customer_id, customer=customer, permit=permit) for permit in permits if permit.permit_id in opportunity.permit_ids)
        return next((result for result in evaluations if result.inside_territory), evaluations[0])

    @staticmethod
    def _result(customer: CustomerAccount, inside: bool, distance: Decimal | None = None, rule: str | None = None, *, reason: str | None = None, verified: bool) -> TerritoryEvaluation:
        return TerritoryEvaluation(customer.customer_account_id, inside, distance, DistanceUnit.KILOMETERS if distance is not None else None, rule, reason, verified)

    @staticmethod
    def _distance(origin: GeographicCoordinates, destination: GeographicCoordinates) -> Decimal:
        return _haversine_km(str(origin.latitude), str(origin.longitude), str(destination.latitude), str(destination.longitude))


@lru_cache(maxsize=4096)
def _haversine_km(lat1: str, lon1: str, lat2: str, lon2: str) -> Decimal:
    phi1, phi2 = math.radians(float(lat1)), math.radians(float(lat2))
    d_phi = math.radians(float(lat2) - float(lat1))
    d_lambda = math.radians(float(lon2) - float(lon1))
    a = math.sin(d_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    kilometers = 6371.0088 * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return Decimal(str(kilometers)).quantize(Decimal("0.001"))
