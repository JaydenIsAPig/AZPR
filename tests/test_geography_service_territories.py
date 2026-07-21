import unittest
from decimal import Decimal

from az_permit_radar.application.geography import DistanceUnit, GeographyPolicy, GeographyQueryService, ServiceTerritoryManager, _haversine_km
from az_permit_radar.domain.customer import CustomerAccount, ServiceTerritory
from az_permit_radar.domain.errors import InvariantViolation
from az_permit_radar.domain.permit import Address, Permit
from az_permit_radar.domain.opportunity import Opportunity
from az_permit_radar.domain.value_objects import AddressId, ClassificationResultId, CustomerAccountId, GeographicCoordinates, JurisdictionId, NormalizedAddress, OpportunityId, PermitId, SourceRecordId, TradeTagId
from az_permit_radar.infrastructure.geography import load_geography_policy
from tests.support import NOW


def customer(value="customer-geo"):
    return CustomerAccount(CustomerAccountId(value), "Geo Contractor", NOW)


def permit(*, jurisdiction="phoenix", city="Phoenix", postal="85001", coordinates=GeographicCoordinates(Decimal("33.4484"), Decimal("-112.0740"))):
    normalized = NormalizedAddress("1 W Washington St", city, "AZ", postal, coordinates=coordinates)
    return Permit(PermitId("permit-geo"), JurisdictionId(jurisdiction), "BP-GEO", {SourceRecordId("record-geo")}, "parser-1", NOW,
                  address=Address(AddressId("address-geo"), "1 W Washington St", normalized))


POLICY = GeographyPolicy(Decimal("100"), 3, 2, 2)


class GeographyTerritoryTests(unittest.TestCase):
    def test_policy_loads_from_governed_business_data(self):
        policy = load_geography_policy("docs/current/business-data-v1.7.json")
        self.assertEqual(policy.maximum_radius_km, Decimal("160.934"))

    def test_city_jurisdiction_and_zip_rules_explain_match(self):
        for territory, rule in (
            (ServiceTerritory(jurisdiction_ids=frozenset({JurisdictionId("phoenix")})), "jurisdiction"),
            (ServiceTerritory(city_names=frozenset({" phoenix "})), "city"),
            (ServiceTerritory(postal_codes=frozenset({"85001-1234"})), "postal_code"),
        ):
            account = customer()
            ServiceTerritoryManager(POLICY).configure(account, territory, NOW)
            result = GeographyQueryService().evaluate(requesting_customer_id=account.customer_account_id, customer=account, permit=permit())
            self.assertTrue(result.inside_territory)
            self.assertEqual(result.matched_rule, rule)

    def test_radius_boundary_is_inclusive_and_units_are_explicit(self):
        origin = GeographicCoordinates(Decimal("33.4484"), Decimal("-112.0740"))
        destination = GeographicCoordinates(Decimal("33.5484"), Decimal("-112.0740"))
        probe = customer()
        probe.set_service_territory(ServiceTerritory(radius_center=origin, radius_km=Decimal("100"), origin_coordinates_validated=True), NOW)
        measured = GeographyQueryService().evaluate(requesting_customer_id=probe.customer_account_id, customer=probe, permit=permit(coordinates=destination)).distance_from_origin
        account = customer("customer-boundary")
        ServiceTerritoryManager(POLICY).configure(account, ServiceTerritory(radius_center=origin, radius_km=measured, origin_coordinates_validated=True), NOW)
        result = GeographyQueryService().evaluate(requesting_customer_id=account.customer_account_id, customer=account, permit=permit(coordinates=destination))
        self.assertTrue(result.inside_territory)
        self.assertEqual(result.distance_unit, DistanceUnit.KILOMETERS)
        self.assertEqual(result.distance_from_origin, measured)

    def test_safe_distance_calculation_is_cached(self):
        _haversine_km.cache_clear()
        args = ("33.4484", "-112.0740", "33.5484", "-112.0740")
        _haversine_km(*args)
        _haversine_km(*args)
        self.assertEqual(_haversine_km.cache_info().hits, 1)

    def test_opportunity_query_evaluates_its_referenced_permits(self):
        account = customer()
        account.set_service_territory(ServiceTerritory(jurisdiction_ids=frozenset({JurisdictionId("phoenix")})), NOW)
        observed = permit()
        opportunity = Opportunity(OpportunityId("opportunity-geo"), frozenset({observed.permit_id}), frozenset({ClassificationResultId("classification-geo")}), frozenset({TradeTagId("trade-geo")}), NOW)
        result = GeographyQueryService().evaluate_opportunity(requesting_customer_id=account.customer_account_id, customer=account, opportunity=opportunity, permits=(observed,))
        self.assertTrue(result.inside_territory)
        with self.assertRaises(InvariantViolation):
            GeographyQueryService().evaluate_opportunity(requesting_customer_id=account.customer_account_id, customer=account, opportunity=opportunity, permits=())

    def test_just_outside_radius_is_excluded_with_reason(self):
        account = customer()
        territory = ServiceTerritory(radius_center=GeographicCoordinates(Decimal("33.4484"), Decimal("-112.0740")), radius_km=Decimal("1"), origin_coordinates_validated=True)
        account.set_service_territory(territory, NOW)
        result = GeographyQueryService().evaluate(requesting_customer_id=account.customer_account_id, customer=account, permit=permit(coordinates=GeographicCoordinates(Decimal("33.4684"), Decimal("-112.0740"))))
        self.assertFalse(result.inside_territory)
        self.assertEqual(result.exclusion_reason, "verified location is outside service territory")

    def test_missing_coordinates_requires_explicit_uncertain_opt_in(self):
        for opt_in, expected in ((False, False), (True, True)):
            account = customer()
            account.set_service_territory(ServiceTerritory(radius_center=GeographicCoordinates(Decimal("33"), Decimal("-112")), radius_km=Decimal("10"), origin_coordinates_validated=True, allow_uncertain_geography=opt_in), NOW)
            result = GeographyQueryService().evaluate(requesting_customer_id=account.customer_account_id, customer=account, permit=permit(coordinates=None))
            self.assertEqual(result.inside_territory, expected)
            self.assertFalse(result.location_verified)
            if opt_in:
                self.assertEqual(result.matched_rule, "uncertain_geography_opt_in")
            else:
                self.assertEqual(result.exclusion_reason, "location cannot be verified")

    def test_validated_origin_and_configurable_maximums_are_enforced(self):
        with self.assertRaises(InvariantViolation):
            ServiceTerritory(radius_center=GeographicCoordinates(Decimal("33"), Decimal("-112")), radius_km=Decimal("10"))
        with self.assertRaises(InvariantViolation):
            ServiceTerritoryManager(POLICY).configure(customer(), ServiceTerritory(radius_center=GeographicCoordinates(Decimal("33"), Decimal("-112")), radius_km=Decimal("101"), origin_coordinates_validated=True), NOW)
        with self.assertRaises(InvariantViolation):
            ServiceTerritoryManager(POLICY).configure(customer(), ServiceTerritory(postal_codes=frozenset({"85001", "85002", "85003", "85004"})), NOW)

    def test_queries_are_customer_isolated(self):
        owner = customer("owner")
        owner.set_service_territory(ServiceTerritory(jurisdiction_ids=frozenset({JurisdictionId("phoenix")})), NOW)
        with self.assertRaises(InvariantViolation):
            GeographyQueryService().evaluate(requesting_customer_id=CustomerAccountId("other"), customer=owner, permit=permit())

    def test_polygon_is_reserved_behind_adapter_and_fails_unverified_without_it(self):
        account = customer()
        account.set_service_territory(ServiceTerritory(polygon_reference="polygon-1"), NOW)
        result = GeographyQueryService().evaluate(requesting_customer_id=account.customer_account_id, customer=account, permit=permit())
        self.assertFalse(result.inside_territory)
        self.assertEqual(result.exclusion_reason, "location cannot be verified")


if __name__ == "__main__": unittest.main()
