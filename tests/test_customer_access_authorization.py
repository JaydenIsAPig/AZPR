import unittest
from types import SimpleNamespace

from az_permit_radar.application import queries, repositories
from az_permit_radar.application.commands import (
    ConfigureCustomerTradePreference,
    CustomerCommandService,
    DismissCustomerMatch,
    MarkCustomerMatchContacted,
    RecalculateCustomerMatches,
    SaveCustomerMatch,
)
from az_permit_radar.application.queries import (
    CustomerQueryService,
    FindOpportunityMatchesForCustomer,
    GetCustomerConfiguration,
    GetCustomerMatchExplanation,
    GetCustomerOpportunityMatch,
    GetOpportunity,
    GetPermit,
    InternalCustomerQueryService,
    ListCustomerMatchesForInternal,
)
from az_permit_radar.domain.access import AccessContext, AccessPermission
from az_permit_radar.domain.customer import CustomerAccount, CustomerTradePreference
from az_permit_radar.domain.errors import AuthenticationRequired, ForbiddenAccess, ResourceNotFound
from az_permit_radar.domain.matching import LeadState, OpportunityMatch, OpportunityMatchStatus
from az_permit_radar.domain.opportunity import Opportunity, OpportunityStatus
from az_permit_radar.domain.permit import Permit
from az_permit_radar.domain.value_objects import (
    AccessActorId,
    ClassificationResultId,
    CustomerAccountId,
    JurisdictionId,
    OpportunityId,
    OpportunityMatchId,
    PermitId,
    SourceRecordId,
)
from az_permit_radar.infrastructure.customer_access import InMemoryCustomerAccountStore
from az_permit_radar.infrastructure.opportunity_matching import InMemoryOpportunityMatchStore, InMemoryOpportunityStore
from az_permit_radar.infrastructure.permit_normalization import InMemoryPermitNormalizationStore
from tests.support import LATER, NOW, TRADE, explanation


CUSTOMER_PERMISSIONS = frozenset(
    {
        AccessPermission.CUSTOMER_MATCH_READ,
        AccessPermission.CUSTOMER_LEAD_WRITE,
        AccessPermission.CUSTOMER_CONFIGURATION_READ,
        AccessPermission.CUSTOMER_CONFIGURATION_WRITE,
        AccessPermission.CUSTOMER_MATCH_RECALCULATE,
    }
)


def customer_context(value: str) -> AccessContext:
    customer_id = CustomerAccountId(value)
    return AccessContext.customer(
        AccessActorId(f"actor-{value}"),
        frozenset({customer_id}),
        CUSTOMER_PERMISSIONS,
    )


class RecordingRecalculator:
    def __init__(self, matches: InMemoryOpportunityMatchStore) -> None:
        self.matches = matches
        self.customer_calls: list[CustomerAccountId] = []

    def generate(self, *, opportunity, permits, customer, evaluated_on, occurred_at):
        del permits, evaluated_on, occurred_at
        self.customer_calls.append(customer.customer_account_id)
        return SimpleNamespace(
            match=self.matches.find_for(opportunity.opportunity_id, customer.customer_account_id)
        )


class LeakyMatchStore:
    """Deliberately violates its scoped contract to test handler defense in depth."""

    def __init__(self, matches: tuple[OpportunityMatch, ...]) -> None:
        self.matches = matches

    def get_for_customer(self, customer_account_id, opportunity_match_id):
        del customer_account_id
        return next(
            (match for match in self.matches if match.opportunity_match_id == opportunity_match_id),
            None,
        )

    def list_for_customer(self, customer_account_id):
        del customer_account_id
        return self.matches


class CustomerAccessAuthorizationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.customer_a_id = CustomerAccountId("customer-a")
        self.customer_b_id = CustomerAccountId("customer-b")
        self.customer_a = CustomerAccount(self.customer_a_id, "Customer A", NOW)
        self.customer_b = CustomerAccount(self.customer_b_id, "Customer B", NOW)
        self.customers = InMemoryCustomerAccountStore((self.customer_a, self.customer_b))

        self.permit = Permit(
            PermitId("permit-shared"),
            JurisdictionId("jurisdiction-shared"),
            "SHARED-001",
            {SourceRecordId("record-shared")},
            "parser-1",
            NOW,
        )
        self.opportunity = Opportunity(
            OpportunityId("opportunity-shared"),
            frozenset({self.permit.permit_id}),
            frozenset({ClassificationResultId("classification-shared")}),
            frozenset({TRADE.trade_tag_id}),
            NOW,
            status=OpportunityStatus.PUBLISHED,
        )
        self.match_a = OpportunityMatch.create(
            OpportunityMatchId("match-a"),
            self.opportunity.opportunity_id,
            self.customer_a_id,
            explanation(),
            NOW,
        )
        self.match_b = OpportunityMatch.create(
            OpportunityMatchId("match-b"),
            self.opportunity.opportunity_id,
            self.customer_b_id,
            explanation(),
            LATER,
        )
        self.matches = InMemoryOpportunityMatchStore()
        self.matches.save_for_internal(self.match_a)
        self.matches.save_for_internal(self.match_b)
        self.opportunities = InMemoryOpportunityStore()
        self.opportunities.save(self.opportunity)
        self.permits = InMemoryPermitNormalizationStore()
        self.permits.save(self.permit)
        self.recalculator = RecordingRecalculator(self.matches)
        self.queries = CustomerQueryService(
            matches=self.matches,
            customers=self.customers,
            opportunities=self.opportunities,
            permits=self.permits,
        )
        self.commands = CustomerCommandService(
            customers=self.customers,
            matches=self.matches,
            opportunities=self.opportunities,
            permits=self.permits,
            recalculator=self.recalculator,
        )
        self.access_a = customer_context("customer-a")
        self.access_b = customer_context("customer-b")

    def test_customer_can_read_own_match_opportunity_permit_and_explanation(self):
        match = self.queries.get_match(
            GetCustomerOpportunityMatch(self.access_a, self.customer_a_id, self.match_a.opportunity_match_id)
        )
        detail = self.queries.get_opportunity(
            GetOpportunity(self.access_a, self.customer_a_id, self.match_a.opportunity_match_id)
        )
        score = self.queries.get_explanation(
            GetCustomerMatchExplanation(self.access_a, self.customer_a_id, self.match_a.opportunity_match_id)
        )
        permit = self.queries.get_permit(
            GetPermit(
                self.access_a,
                self.customer_a_id,
                self.match_a.opportunity_match_id,
                self.permit.permit_id,
            )
        )
        self.assertEqual(match.customer_account_id, self.customer_a_id)
        self.assertEqual(detail.opportunity.opportunity_id, self.opportunity.opportunity_id)
        self.assertEqual(detail.permits[0].permit_id, self.permit.permit_id)
        self.assertEqual(permit.permit_id, self.permit.permit_id)
        self.assertEqual(score, self.match_a.explanation)

    def test_cross_customer_match_and_missing_match_share_not_found_policy(self):
        errors = []
        for match_id in (self.match_b.opportunity_match_id, OpportunityMatchId("missing-match")):
            with self.assertRaises(ResourceNotFound) as raised:
                self.queries.get_match(
                    GetCustomerOpportunityMatch(self.access_a, self.customer_a_id, match_id)
                )
            errors.append(str(raised.exception))
        self.assertEqual(errors[0], errors[1])

    def test_customer_cannot_claim_another_customer_scope_or_enumerate_matches(self):
        with self.assertRaises(ResourceNotFound):
            self.queries.list_matches(
                FindOpportunityMatchesForCustomer(self.access_a, self.customer_b_id)
            )
        listed = self.queries.list_matches(
            FindOpportunityMatchesForCustomer(self.access_a, self.customer_a_id)
        )
        self.assertEqual(tuple(match.customer_account_id for match in listed.matches), (self.customer_a_id,))

    def test_customer_cannot_alter_another_customers_lead_state(self):
        with self.assertRaises(ResourceNotFound):
            self.commands.dismiss(
                DismissCustomerMatch(
                    self.access_a,
                    self.customer_a_id,
                    self.match_b.opportunity_match_id,
                    NOW,
                )
            )
        self.assertEqual(
            self.matches.get_for_customer(self.customer_b_id, self.match_b.opportunity_match_id).lead_state,
            LeadState.NEW,
        )

    def test_unapproved_notes_have_no_customer_query_or_command_surface(self):
        self.assertFalse(hasattr(self.queries, "get_note"))
        self.assertFalse(hasattr(self.commands, "update_note"))
        self.assertFalse(hasattr(queries, "GetCustomerMatchNote"))

    def test_customer_cannot_read_or_change_another_customers_configuration(self):
        with self.assertRaises(ResourceNotFound):
            self.queries.get_configuration(GetCustomerConfiguration(self.access_a, self.customer_b_id))
        with self.assertRaises(ResourceNotFound):
            self.commands.configure_trade(
                ConfigureCustomerTradePreference(
                    self.access_a,
                    self.customer_b_id,
                    CustomerTradePreference(TRADE.trade_tag_id),
                    NOW,
                )
            )
        stored_b = self.customers.get_for_customer(self.customer_b_id)
        self.assertEqual(stored_b.trade_preferences, {})

    def test_two_customers_act_independently_on_one_shared_opportunity(self):
        self.commands.save(
            SaveCustomerMatch(self.access_a, self.customer_a_id, self.match_a.opportunity_match_id, NOW)
        )
        self.commands.mark_contacted(
            MarkCustomerMatchContacted(self.access_b, self.customer_b_id, self.match_b.opportunity_match_id, NOW)
        )
        stored_a = self.matches.get_for_customer(self.customer_a_id, self.match_a.opportunity_match_id)
        stored_b = self.matches.get_for_customer(self.customer_b_id, self.match_b.opportunity_match_id)
        self.assertEqual(stored_a.lead_state, LeadState.SAVED)
        self.assertEqual(stored_b.lead_state, LeadState.CONTACTED)
        self.assertEqual(self.opportunities.get(self.opportunity.opportunity_id).status, OpportunityStatus.PUBLISHED)

    def test_customer_dismissal_does_not_suppress_other_match_or_shared_opportunity(self):
        self.commands.dismiss(
            DismissCustomerMatch(self.access_a, self.customer_a_id, self.match_a.opportunity_match_id, NOW)
        )
        stored_b = self.matches.get_for_customer(self.customer_b_id, self.match_b.opportunity_match_id)
        self.assertEqual(stored_b.status, OpportunityMatchStatus.ACTIVE)
        self.assertEqual(stored_b.lead_state, LeadState.NEW)
        self.assertEqual(self.opportunities.get(self.opportunity.opportunity_id).status, OpportunityStatus.PUBLISHED)

    def test_unauthenticated_and_permission_denied_are_distinct(self):
        with self.assertRaises(AuthenticationRequired):
            self.queries.list_matches(
                FindOpportunityMatchesForCustomer(AccessContext.unauthenticated(), self.customer_a_id)
            )
        read_only = AccessContext.customer(
            AccessActorId("actor-read-only"),
            frozenset({self.customer_a_id}),
            frozenset({AccessPermission.CUSTOMER_MATCH_READ}),
        )
        with self.assertRaises(ForbiddenAccess):
            self.commands.save(
                SaveCustomerMatch(read_only, self.customer_a_id, self.match_a.opportunity_match_id, NOW)
            )

    def test_internal_access_uses_separate_explicit_path(self):
        internal = InternalCustomerQueryService(self.matches)
        access = AccessContext.internal(
            AccessActorId("actor-operations"),
            frozenset({AccessPermission.INTERNAL_CUSTOMER_READ}),
        )
        self.assertEqual(len(internal.list_matches(ListCustomerMatchesForInternal(access))), 2)
        with self.assertRaises(ForbiddenAccess):
            internal.list_matches(ListCustomerMatchesForInternal(self.access_a))

    def test_customer_recalculation_touches_only_requested_customer(self):
        result = self.commands.recalculate(
            RecalculateCustomerMatches(
                self.access_a,
                self.customer_a_id,
                self.match_a.explanation.source_freshness_date,
                LATER,
            )
        )
        self.assertFalse(result.partial_failure)
        self.assertEqual(self.recalculator.customer_calls, [self.customer_a_id])
        self.assertEqual(tuple(match.customer_account_id for match in result.updated_matches), (self.customer_a_id,))

    def test_normal_handler_filters_a_repository_that_returns_cross_customer_data(self):
        leaky = CustomerQueryService(
            matches=LeakyMatchStore((self.match_a, self.match_b)),
            customers=self.customers,
            opportunities=self.opportunities,
            permits=self.permits,
        )
        listed = leaky.list_matches(
            FindOpportunityMatchesForCustomer(self.access_a, self.customer_a_id)
        )
        self.assertEqual(listed.matches, (self.match_a,))
        with self.assertRaises(ResourceNotFound):
            leaky.get_match(
                GetCustomerOpportunityMatch(
                    self.access_a,
                    self.customer_a_id,
                    self.match_b.opportunity_match_id,
                )
            )

    def test_normal_repository_contracts_expose_no_unscoped_get_or_save(self):
        self.assertNotIn("get", repositories.OpportunityMatchRepository.__dict__)
        self.assertNotIn("save", repositories.OpportunityMatchRepository.__dict__)
        self.assertNotIn("get", repositories.CustomerAccountRepository.__dict__)
        self.assertNotIn("save", repositories.CustomerAccountRepository.__dict__)


if __name__ == "__main__":
    unittest.main()
