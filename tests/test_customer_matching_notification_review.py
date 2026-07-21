import unittest
from decimal import Decimal

from az_permit_radar.domain.customer import (
    CustomerAccount,
    CustomerAccountStatus,
    CustomerFilter,
    CustomerTradePreference,
    NotificationPreference,
    ServiceTerritory,
)
from az_permit_radar.domain.errors import ConsentRequired, InvalidStateTransition, InvariantViolation
from az_permit_radar.domain.matching import LeadState, MatchExplanation, MatchScoreComponent, OpportunityMatch
from az_permit_radar.domain.notification import (
    NotificationAttempt,
    NotificationAttemptStatus,
    NotificationChannel,
)
from az_permit_radar.domain.review import ReviewSubjectType, ReviewTask, ReviewTaskStatus
from az_permit_radar.domain.value_objects import (
    CalendarDate,
    ClassificationResultId,
    Confidence,
    CustomerAccountId,
    EmailAddress,
    IdempotencyKey,
    JurisdictionId,
    Money,
    NotificationAttemptId,
    OpportunityId,
    OpportunityMatchId,
    PhoneNumber,
    PermitId,
    ReviewTaskId,
)

from tests.support import LATER, NOW, TRADE, explanation


def customer() -> CustomerAccount:
    return CustomerAccount(CustomerAccountId("customer-001"), "Example Electric", NOW)


def opportunity_match() -> OpportunityMatch:
    return OpportunityMatch.create(
        OpportunityMatchId("match-001"),
        OpportunityId("opportunity-001"),
        CustomerAccountId("customer-001"),
        explanation(),
        NOW,
    )


class CustomerConfigurationTests(unittest.TestCase):
    def test_service_territory_requires_scope(self) -> None:
        with self.assertRaises(InvariantViolation):
            ServiceTerritory()

    def test_customer_filter_orders_money_bounds(self) -> None:
        with self.assertRaises(InvariantViolation):
            CustomerFilter(Money(Decimal("1000")), Money(Decimal("100")))

    def test_enabled_email_requires_destination_and_consent(self) -> None:
        with self.assertRaises(ConsentRequired):
            NotificationPreference(NotificationChannel.EMAIL, True, EmailAddress("ops@example.com"))

    def test_notification_destination_matches_channel(self) -> None:
        with self.assertRaises(InvariantViolation):
            NotificationPreference(NotificationChannel.SMS, False, EmailAddress("ops@example.com"))

    def test_customer_owns_configuration_and_emits_events(self) -> None:
        account = customer()
        account.set_trade_preference(CustomerTradePreference(TRADE.trade_tag_id), NOW)
        account.set_service_territory(
            ServiceTerritory(jurisdiction_ids=frozenset({JurisdictionId("jurisdiction-001")})), NOW
        )
        account.set_notification_preference(
            NotificationPreference(
                NotificationChannel.SMS,
                True,
                PhoneNumber("+16025550123"),
                NOW,
                "consent-form-001",
            ),
            NOW,
        )
        self.assertEqual(len(account.pull_domain_events()), 3)

    def test_closed_customer_cannot_be_reconfigured_or_reopened(self) -> None:
        account = customer()
        account.transition_to(CustomerAccountStatus.CLOSED, NOW)
        with self.assertRaises(InvariantViolation):
            account.set_trade_preference(CustomerTradePreference(TRADE.trade_tag_id), LATER)
        with self.assertRaises(InvalidStateTransition):
            account.transition_to(CustomerAccountStatus.ACTIVE, LATER)


class OpportunityMatchTests(unittest.TestCase):
    def test_match_explanation_rejects_duplicate_score_names(self) -> None:
        component = MatchScoreComponent("trade", Decimal("1"), "matched")
        with self.assertRaises(InvariantViolation):
            MatchExplanation(
                frozenset({TRADE.trade_tag_id}),
                "jurisdiction",
                tuple(),
                (component, component),
                tuple(),
                CalendarDate.from_iso("2026-07-17"),
                Confidence(Decimal("1")),
            )

    def test_match_creation_emits_customer_specific_event(self) -> None:
        matched = opportunity_match()
        event = matched.pull_domain_events()[0]
        self.assertEqual(event.customer_account_id, "customer-001")

    def test_lead_state_follows_forward_only_transitions(self) -> None:
        matched = opportunity_match()
        matched.change_lead_state(LeadState.SAVED, NOW)
        matched.change_lead_state(LeadState.CONTACTED, LATER)
        with self.assertRaises(InvalidStateTransition):
            matched.change_lead_state(LeadState.NEW, LATER)

    def test_ended_match_cannot_change_customer_lead_state(self) -> None:
        matched = opportunity_match()
        matched.expire("opportunity expired", NOW)
        with self.assertRaises(InvariantViolation):
            matched.change_lead_state(LeadState.DISMISSED, LATER)


class NotificationAttemptTests(unittest.TestCase):
    def test_attempt_requires_consent_reference(self) -> None:
        with self.assertRaises(InvariantViolation):
            NotificationAttempt(
                NotificationAttemptId("notification-001"),
                OpportunityMatchId("match-001"),
                NotificationChannel.EMAIL,
                IdempotencyKey("notify:match-001:email"),
                NOW,
                "",
            )

    def test_submission_is_not_delivery(self) -> None:
        attempt = NotificationAttempt(
            NotificationAttemptId("notification-001"),
            OpportunityMatchId("match-001"),
            NotificationChannel.EMAIL,
            IdempotencyKey("notify:match-001:email"),
            NOW,
            "consent-001",
        )
        attempt.submit("provider-001", NOW)
        self.assertEqual(attempt.status, NotificationAttemptStatus.SUBMITTED)
        attempt.mark_delivered(LATER)
        self.assertEqual(attempt.status, NotificationAttemptStatus.DELIVERED)

    def test_terminal_attempt_cannot_be_retried_in_place(self) -> None:
        attempt = NotificationAttempt(
            NotificationAttemptId("notification-001"),
            OpportunityMatchId("match-001"),
            NotificationChannel.EMAIL,
            IdempotencyKey("notify:match-001:email"),
            NOW,
            "consent-001",
        )
        attempt.fail("provider unavailable", LATER)
        with self.assertRaises(InvalidStateTransition):
            attempt.submit("provider-001", LATER)


class ReviewTaskTests(unittest.TestCase):
    def test_review_task_requires_reason(self) -> None:
        with self.assertRaises(InvariantViolation):
            ReviewTask(
                ReviewTaskId("review-001"), ReviewSubjectType.PERMIT, "permit-001", "", NOW
            )

    def test_review_task_resolves_and_becomes_terminal(self) -> None:
        task = ReviewTask(
            ReviewTaskId("review-001"),
            ReviewSubjectType.CLASSIFICATION_RESULT,
            "classification-001",
            "low confidence",
            NOW,
            permit_id=PermitId("permit-001"),
            classification_result_id=ClassificationResultId("classification-001"),
        )
        task.start("reviewer-001", NOW)
        task.resolve("accepted after source review", LATER)
        self.assertEqual(task.status, ReviewTaskStatus.RESOLVED)
        with self.assertRaises(InvalidStateTransition):
            task.cancel("late cancellation", LATER)


if __name__ == "__main__":
    unittest.main()
