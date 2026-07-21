import threading
import unittest
from decimal import Decimal

from az_permit_radar.domain.eligibility import PublicationEligibilityError, PublicationEligibilityPolicy
from az_permit_radar.application.geography import GeographyQueryService
from az_permit_radar.application.opportunity_matching import ExplainableMatchGenerator, OpportunityGenerator, OpportunityProjectionPolicy, ScorePolicy
from az_permit_radar.domain.classification import ClassificationMethod, ClassificationResult, ClassificationReviewStatus
from az_permit_radar.domain.customer import CustomerAccount, CustomerAccountStatus, CustomerFilter, CustomerTradePreference, NotificationPreference, ServiceTerritory
from az_permit_radar.domain.errors import InvariantViolation
from az_permit_radar.domain.matching import LeadState, OpportunityMatchStatus
from az_permit_radar.domain.notification import NotificationChannel
from az_permit_radar.domain.opportunity import OpportunityProjectionStatus, OpportunityStatus, SourceFreshnessBasis
from az_permit_radar.domain.permit import Address, NormalizedPermitType, Permit, PermitAuthorityStatus, PermitCanonicalStatus, PermitSourceEvidence
from az_permit_radar.domain.value_objects import AddressId, CalendarDate, ClassificationResultId, Confidence, CustomerAccountId, DuplicateCandidateId, EmailAddress, JurisdictionId, Money, NormalizedAddress, PermitId, SourceId, SourceRecordId
from az_permit_radar.infrastructure.opportunity_matching import InMemoryOpportunityMatchStore, InMemoryOpportunityStore, load_projection_policy, load_publication_eligibility_policy, load_score_policy
from az_permit_radar.infrastructure.permit_classification import InMemoryClassificationState
from tests.support import LATER, NOW, TRADE, PROJECT_CLASSIFICATION


EVALUATED = CalendarDate.from_iso("2026-07-20")


def observed_permit(jurisdiction="phoenix", value="150000"):
    return Permit(PermitId("permit-match"), JurisdictionId(jurisdiction), "BP-2026-10", {SourceRecordId("record-match")}, "parser-1", NOW,
                  issued_on=CalendarDate.from_iso("2026-07-19"),
                  address=Address(AddressId("address-match"), "1 W Main", NormalizedAddress("1 W Main", "Phoenix", "AZ", "85001")),
                  valuation=Money(Decimal(value)) if value else None,
                  permit_type=NormalizedPermitType("tenant-improvement", "Tenant Improvement"),
                  description="Tenant improvement; contact 602-555-0100 for private details")


def classification(*, permit_id="permit-match", result_id="classification-match", confidence="0.9", review_status=ClassificationReviewStatus.ACCEPTED, supersedes=None, revision=1, classifier_version="rules-1", rule_set_version="legacy"):
    return ClassificationResult(
        ClassificationResultId(result_id),
        PermitId(permit_id),
        PROJECT_CLASSIFICATION,
        frozenset({TRADE}),
        ClassificationMethod.DETERMINISTIC,
        classifier_version,
        Confidence(Decimal(confidence)),
        ("deterministic tags",),
        NOW,
        supersedes_classification_result_id=(ClassificationResultId(supersedes) if supersedes else None),
        revision=revision,
        rule_set_version=rule_set_version,
        review_status=review_status,
    )


def account(value="customer-a", jurisdiction="phoenix", trade=True, notifications=True):
    customer = CustomerAccount(CustomerAccountId(value), f"Business {value}", NOW)
    if trade:
        customer.set_trade_preference(CustomerTradePreference(TRADE.trade_tag_id), NOW)
    customer.set_service_territory(ServiceTerritory(jurisdiction_ids=frozenset({JurisdictionId(jurisdiction)})), NOW)
    if notifications:
        customer.set_notification_preference(NotificationPreference(NotificationChannel.EMAIL, True, EmailAddress("ops@example.com"), NOW, "consent-1"), NOW)
    return customer


class OpportunityGenerationMatchingTests(unittest.TestCase):
    def setUp(self):
        self.opportunities = InMemoryOpportunityStore()
        self.matches = InMemoryOpportunityMatchStore()
        self.permit = observed_permit()
        self.classification = classification()
        self.classifications = self.classification_state(self.classification)
        self.eligibility = load_publication_eligibility_policy("docs/current/business-data-v1.7.json")
        self.projection_policy = load_projection_policy("docs/current/business-data-v1.7.json")
        self.opportunity = OpportunityGenerator(self.opportunities, self.eligibility, self.classifications, self.matches, self.projection_policy).generate(self.permit, NOW)
        self.policy = load_score_policy("docs/current/business-data-v1.7.json")

    @staticmethod
    def classification_state(result):
        state = InMemoryClassificationState()
        state.save_outcome(result, ())
        return state

    def generator(self, policy=None, classifications=None, opportunities=None):
        state = self.classifications if classifications is None else classifications
        store = self.opportunities if opportunities is None else opportunities
        return ExplainableMatchGenerator(self.matches, GeographyQueryService(), policy or self.policy, self.eligibility, state, store)

    def match(self, customer, *, opportunity=None, permit=None, classification_result=None, generator=None, opportunity_store=None):
        state = (
            self.classification_state(classification_result)
            if classification_result is not None
            else self.classifications
        )
        selected = generator or self.generator(classifications=state, opportunities=opportunity_store)
        return selected.generate(
            opportunity=opportunity or self.opportunity,
            permits=(permit or self.permit,),
            customer=customer,
            evaluated_on=EVALUATED,
            occurred_at=NOW,
        )

    def test_opportunity_contains_safe_source_backed_projection_and_replays(self):
        replay = OpportunityGenerator(self.opportunities, self.eligibility, self.classifications, self.matches, self.projection_policy).generate(self.permit, NOW)
        self.assertEqual(replay.opportunity_id, self.opportunity.opportunity_id)
        self.assertEqual(len(self.opportunities.items), 1)
        self.assertNotIn("602-555-0100", self.opportunity.concise_description)
        self.assertIn("source permit record", self.opportunity.concise_description.lower())
        self.assertEqual(self.opportunity.location, "Phoenix, AZ 85001")
        self.assertEqual(self.opportunity.value_band, "100k_to_500k")
        self.assertEqual(self.opportunity.completeness_indicator, "complete")
        self.assertEqual(self.opportunity.status, OpportunityStatus.PUBLISHED)
        self.assertEqual(self.opportunity.projection_revision, 1)
        self.assertEqual(self.opportunity.projection_history, ())

    def test_unchanged_replay_at_later_time_does_not_create_projection_or_score_history(self):
        customer = account("unchanged-replay")
        first = self.match(customer).match
        replayed_opportunity = OpportunityGenerator(
            self.opportunities, self.eligibility, self.classifications, self.matches, self.projection_policy
        ).generate(self.permit, LATER)
        second = self.generator().generate(
            opportunity=replayed_opportunity,
            permits=(self.permit,),
            customer=customer,
            evaluated_on=EVALUATED,
            occurred_at=LATER,
        ).match
        self.assertEqual(replayed_opportunity.projection_revision, 1)
        self.assertEqual(replayed_opportunity.projection_history, ())
        self.assertEqual(second.version, first.version)
        self.assertEqual(second.score_history, ())

    def test_concurrent_opportunity_and_match_generation_are_unique(self):
        opportunity_results = []
        failures = []
        barrier = threading.Barrier(2)

        def generate_opportunity():
            try:
                barrier.wait(timeout=5)
                opportunity_results.append(OpportunityGenerator(
                    self.opportunities, self.eligibility, self.classifications,
                    self.matches, self.projection_policy,
                ).generate(self.permit, NOW))
            except BaseException as error:
                failures.append(error)

        threads = [threading.Thread(target=generate_opportunity) for _ in range(2)]
        for thread in threads: thread.start()
        for thread in threads: thread.join(timeout=5)
        self.assertEqual(failures, [])
        self.assertEqual({item.opportunity_id for item in opportunity_results}, {self.opportunity.opportunity_id})
        self.assertEqual(len(self.opportunities.items), 1)

        customer = account("concurrent-match")
        match_results = []
        barrier = threading.Barrier(2)

        def generate_match():
            try:
                barrier.wait(timeout=5)
                match_results.append(self.match(customer).match)
            except BaseException as error:
                failures.append(error)

        threads = [threading.Thread(target=generate_match) for _ in range(2)]
        for thread in threads: thread.start()
        for thread in threads: thread.join(timeout=5)
        self.assertEqual(failures, [])
        self.assertEqual(len({item.opportunity_match_id for item in match_results}), 1)
        self.assertEqual(len(self.matches.items), 1)

    def test_classification_rule_revision_regenerates_projection_and_recalculates_stale_match(self):
        customer = account("projection-revision")
        original_match = self.match(customer).match
        replacement = classification(
            result_id="classification-rule-revision",
            supersedes=str(self.classification.classification_result_id),
            revision=2,
            rule_set_version="2.0.0",
        )
        self.classifications.save_outcome(replacement, ())

        regenerated = OpportunityGenerator(
            self.opportunities, self.eligibility, self.classifications, self.matches, self.projection_policy
        ).generate(self.permit, LATER)
        stale = self.matches.find_for(regenerated.opportunity_id, customer.customer_account_id)

        self.assertEqual(regenerated.opportunity_id, self.opportunity.opportunity_id)
        self.assertEqual(regenerated.projection_revision, 2)
        self.assertEqual(regenerated.rule_set_versions, ("2.0.0",))
        self.assertEqual(len(regenerated.projection_history), 1)
        self.assertEqual(regenerated.projection_history[0].projection_status, OpportunityProjectionStatus.SUPERSEDED)
        self.assertEqual(regenerated.projection_history[0].projection_revision, 1)
        self.assertEqual(stale.status, OpportunityMatchStatus.STALE)
        blocked_old_revision = self.match(
            account("superseded-projection"), opportunity=self.opportunity
        )
        self.assertIsNone(blocked_old_revision.match)
        self.assertEqual(blocked_old_revision.exclusion_rules, ("opportunity_projection_not_current",))

        recalculated = self.match(customer, opportunity=regenerated).match
        self.assertEqual(recalculated.status, OpportunityMatchStatus.ACTIVE)
        self.assertEqual(recalculated.explanation.opportunity_revision, 2)
        self.assertEqual(len(recalculated.score_history), 1)
        self.assertEqual(recalculated.score_history[0].opportunity_revision, 1)
        self.assertEqual(recalculated.score_history[0], original_match.explanation)

    def test_changed_classification_version_alone_regenerates_projection(self):
        replacement = classification(
            result_id="classification-version-revision",
            supersedes=str(self.classification.classification_result_id),
            revision=2,
            classifier_version="rules-2",
        )
        self.classifications.save_outcome(replacement, ())
        regenerated = OpportunityGenerator(
            self.opportunities, self.eligibility, self.classifications, self.matches, self.projection_policy
        ).generate(self.permit, LATER)
        self.assertEqual(regenerated.projection_revision, 2)
        self.assertEqual(regenerated.classification_versions, ("rules-2",))
        self.assertNotEqual(regenerated.projection_fingerprint, self.opportunity.projection_fingerprint)

    def test_corrected_normalized_facts_regenerate_same_logical_opportunity(self):
        evidence = PermitSourceEvidence(
            SourceId("source-correction"), SourceRecordId("record-correction"), "external-correction",
            "f" * 64, "parser-2", LATER, acquired_at=LATER,
        )
        self.permit.apply_normalized_correction(
            evidence=evidence,
            permit_number=self.permit.permit_number,
            authority_status=PermitAuthorityStatus.ISSUED,
            permit_type=self.permit.permit_type,
            description="Corrected electrical tenant improvement",
            applied_on=self.permit.applied_on,
            issued_on=self.permit.issued_on,
            address=self.permit.address,
            parcel_reference=self.permit.parcel_reference,
            valuation=Money(Decimal("550000")),
            parties=self.permit.parties,
            occurred_at=LATER,
        )
        regenerated = OpportunityGenerator(
            self.opportunities, self.eligibility, self.classifications, self.matches, self.projection_policy
        ).generate(self.permit, LATER)
        self.assertEqual(regenerated.opportunity_id, self.opportunity.opportunity_id)
        self.assertEqual(regenerated.projection_revision, 2)
        self.assertEqual(regenerated.parser_version, "parser-2")
        self.assertEqual(regenerated.value_band, "500k_plus")
        self.assertIn("Corrected electrical", regenerated.concise_description)
        self.assertEqual(regenerated.projection_history[0].value_band, "100k_to_500k")

    def test_positive_match_scores_100_and_has_full_explanation(self):
        customer = account()
        customer.set_customer_filter(CustomerFilter(minimum_valuation=Money(Decimal("100000")), allowed_value_bands=frozenset({"100k_to_500k"})), NOW)
        result = self.match(customer)
        self.assertIsNotNone(result.match)
        explanation = result.match.explanation
        self.assertEqual(explanation.total_score, Decimal("100"))
        self.assertEqual(explanation.score_version, "opportunity-score-1.1.0")
        self.assertEqual(sum(component.value for component in explanation.score_components), Decimal("100"))
        self.assertTrue(explanation.matched_rules)
        self.assertTrue(explanation.exclusion_rules)
        self.assertIn("Score 100/100", explanation.human_readable)
        self.assertEqual(explanation.score_policy_snapshot.policy_id, "opportunity-match-score")
        self.assertEqual(explanation.customer_configuration_snapshot.version, customer.version)
        self.assertEqual(explanation.freshness_evaluation_snapshot.source_date_basis, "issued_on")

    def test_exclusions_cover_account_trade_geography_value_filters_and_suppression(self):
        inactive = account("inactive")
        inactive.transition_to(CustomerAccountStatus.SUSPENDED, NOW)
        self.assertIn("account_not_active", self.match(inactive).exclusion_rules)
        self.assertEqual(self.match(inactive).human_readable, "Excluded: the Customer Account is not active.")
        self.assertIn("trade_mismatch", self.match(account("no-trade", trade=False)).exclusion_rules)
        self.assertIn("outside_service_territory", self.match(account("outside", "tucson")).exclusion_rules)
        filtered = account("filtered")
        filtered.set_customer_filter(CustomerFilter(minimum_valuation=Money(Decimal("200000")), excluded_project_classification_codes=frozenset({PROJECT_CLASSIFICATION.code})), NOW)
        excluded = self.match(filtered).exclusion_rules
        self.assertIn("minimum_value", excluded)
        self.assertIn("project_filter", excluded)
        self.opportunity.transition_to(OpportunityStatus.SUPPRESSED, "internal review", NOW)
        self.opportunities.save(self.opportunity)
        self.assertIn("opportunity_not_publishable", self.match(account("suppressed")).exclusion_rules)

    def test_replay_is_idempotent_and_two_customers_remain_isolated(self):
        first_customer, second_customer = account("customer-one"), account("customer-two")
        first = self.match(first_customer).match
        replay = self.match(first_customer).match
        second = self.match(second_customer).match
        self.assertEqual(first.opportunity_match_id, replay.opportunity_match_id)
        self.assertEqual(first.version, replay.version)
        self.assertNotEqual(first.opportunity_match_id, second.opportunity_match_id)
        self.assertEqual(len(self.matches.items), 2)
        self.assertNotIn(first_customer.business_name, second.explanation.human_readable)
        self.assertNotIn(str(first_customer.customer_account_id), repr(second.explanation.customer_configuration_snapshot))
        self.assertNotIn(str(second_customer.customer_account_id), repr(first.explanation.customer_configuration_snapshot))

    def test_configuration_and_score_rule_changes_recalculate_with_history(self):
        customer = account("recalculate")
        initial = self.match(customer).match
        customer.set_notification_preference(NotificationPreference(NotificationChannel.EMAIL, False), NOW)
        changed = self.match(customer).match
        self.assertEqual(changed.total_score if hasattr(changed, "total_score") else changed.explanation.total_score, Decimal("95"))
        self.assertEqual(len(changed.score_history), 1)
        self.assertEqual(changed.score_history[0].customer_configuration_snapshot.notification_readiness_channels, ("email",))
        self.assertEqual(changed.explanation.customer_configuration_snapshot.notification_readiness_channels, ())
        new_policy = ScorePolicy("opportunity-score-2.0.0", {"trade":30, "geography":30, "value":20, "completeness":10, "freshness":10, "notification_readiness":0}, 30, 90)
        rescored = self.match(customer, generator=self.generator(new_policy)).match
        self.assertEqual(rescored.explanation.score_version, "opportunity-score-2.0.0")
        self.assertEqual(len(rescored.score_history), 2)
        self.assertEqual(rescored.score_history[0].score_version, "opportunity-score-1.1.0")

    def test_customer_configuration_change_recalculates_only_that_customers_match(self):
        changed_customer = account("changed-config")
        untouched_customer = account("untouched-config")
        changed_initial = self.match(changed_customer).match
        untouched_initial = self.match(untouched_customer).match

        changed_customer.set_notification_preference(NotificationPreference(NotificationChannel.EMAIL, False), LATER)
        changed = self.generator().generate(
            opportunity=self.opportunity, permits=(self.permit,), customer=changed_customer,
            evaluated_on=EVALUATED, occurred_at=LATER,
        ).match
        untouched = self.generator().generate(
            opportunity=self.opportunity, permits=(self.permit,), customer=untouched_customer,
            evaluated_on=EVALUATED, occurred_at=LATER,
        ).match

        self.assertEqual(len(changed.score_history), 1)
        self.assertEqual(changed.score_history[0], changed_initial.explanation)
        self.assertEqual(untouched.score_history, ())
        self.assertEqual(untouched.version, untouched_initial.version)

    def test_dismissed_match_is_not_reactivated_or_recalculated(self):
        customer = account("dismissed")
        match = self.match(customer).match
        match.change_lead_state(LeadState.DISMISSED, NOW)
        self.matches.save(match)
        customer.set_notification_preference(NotificationPreference(NotificationChannel.EMAIL, False), NOW)
        replay = self.match(customer).match
        self.assertEqual(replay.lead_state, LeadState.DISMISSED)
        self.assertEqual(replay.version, match.version)

    def test_existing_match_is_terminally_excluded_when_opportunity_is_suppressed(self):
        customer = account("later-suppressed")
        original = self.match(customer).match
        self.opportunity.transition_to(OpportunityStatus.SUPPRESSED, "internal review", NOW)
        self.opportunities.save(self.opportunity)
        result = self.match(customer)
        self.assertEqual(result.match.opportunity_match_id, original.opportunity_match_id)
        self.assertEqual(result.match.status.value, "excluded")
        self.assertIn("opportunity_not_publishable", result.exclusion_rules)

    def test_low_confidence_pending_and_rejected_classifications_fail_closed(self):
        cases = (
            (classification(result_id="low", confidence="0.79"), "classification_confidence_below_publication_threshold"),
            (classification(result_id="pending", confidence="0.90", review_status=ClassificationReviewStatus.PENDING), "classification_pending_review"),
            (classification(result_id="rejected", confidence="0.90", review_status=ClassificationReviewStatus.REJECTED), "classification_rejected"),
        )
        for result, expected_reason in cases:
            with self.subTest(expected_reason=expected_reason):
                state = self.classification_state(result)
                generator = OpportunityGenerator(InMemoryOpportunityStore(), self.eligibility, state, self.matches, self.projection_policy)
                with self.assertRaises(PublicationEligibilityError) as raised:
                    generator.generate(self.permit, NOW)
                self.assertIn(expected_reason, raised.exception.decision.reasons)
                match_result = self.match(
                    account(f"blocked-{result.classification_result_id}"),
                    classification_result=result,
                )
                self.assertIsNone(match_result.match)
                self.assertIn(expected_reason, match_result.exclusion_rules)

    def test_human_approval_allows_one_opportunity_and_match(self):
        pending = classification(
            result_id="classification-human-review",
            confidence="0.90",
            review_status=ClassificationReviewStatus.PENDING,
        )
        with self.assertRaises(PublicationEligibilityError):
            OpportunityGenerator(InMemoryOpportunityStore(), self.eligibility, self.classification_state(pending), self.matches, self.projection_policy).generate(self.permit, NOW)
        pending.accept("reviewer verified municipal source", NOW)
        store = InMemoryOpportunityStore()
        pending_state = self.classification_state(pending)
        generator = OpportunityGenerator(store, self.eligibility, pending_state, self.matches, self.projection_policy)
        approved = generator.generate(self.permit, NOW)
        replay = generator.generate(self.permit, NOW)
        self.assertEqual(approved.opportunity_id, replay.opportunity_id)
        self.assertEqual(len(store.items), 1)
        first_match = self.match(
            account("human-approved"),
            opportunity=approved,
            classification_result=pending,
            opportunity_store=store,
        ).match
        replayed_match = self.match(
            account("human-approved"),
            opportunity=approved,
            classification_result=pending,
            opportunity_store=store,
        ).match
        self.assertEqual(first_match.opportunity_match_id, replayed_match.opportunity_match_id)

    def test_candidate_opportunity_and_threshold_change_cannot_match(self):
        self.opportunity.status = OpportunityStatus.CANDIDATE
        self.opportunities.save(self.opportunity)
        candidate_result = self.match(account("candidate"))
        self.assertIsNone(candidate_result.match)
        self.assertIn("opportunity_not_publishable", candidate_result.exclusion_rules)

        self.opportunity.status = OpportunityStatus.PUBLISHED
        self.opportunities.save(self.opportunity)
        customer = account("threshold-change")
        original = self.match(customer).match
        stricter = ExplainableMatchGenerator(
            self.matches,
            GeographyQueryService(),
            self.policy,
            PublicationEligibilityPolicy.from_decimal("0.95"),
            self.classifications,
            self.opportunities,
        )
        reevaluated = self.match(customer, generator=stricter)
        self.assertEqual(reevaluated.match.opportunity_match_id, original.opportunity_match_id)
        self.assertEqual(reevaluated.match.status.value, "excluded")
        self.assertIn("classification_confidence_below_publication_threshold", reevaluated.exclusion_rules)

    def test_superseded_classification_cannot_be_selected_by_caller(self):
        replacement = classification(
            result_id="classification-replacement",
            supersedes=str(self.classification.classification_result_id),
            revision=2,
        )
        self.classifications.save_outcome(replacement, ())
        result = self.match(account("current-classification-only"))
        self.assertIsNone(result.match)
        self.assertIn("classification_missing", result.exclusion_rules)
        self.assertEqual(
            self.classifications.find_current_for_permit(self.permit.permit_id).classification_result_id,
            replacement.classification_result_id,
        )

    def test_missing_match_inputs_fail_closed_with_structured_reasons(self):
        missing_permit = self.generator().generate(
            opportunity=self.opportunity,
            permits=(),
            customer=account("missing-permit"),
            evaluated_on=EVALUATED,
            occurred_at=NOW,
        )
        self.assertIsNone(missing_permit.match)
        self.assertIn("permit_missing", missing_permit.exclusion_rules)
        missing_classification = self.generator(classifications=InMemoryClassificationState()).generate(
            opportunity=self.opportunity,
            permits=(self.permit,),
            customer=account("missing-classification"),
            evaluated_on=EVALUATED,
            occurred_at=NOW,
        )
        self.assertIsNone(missing_classification.match)
        self.assertIn("classification_missing", missing_classification.exclusion_rules)

    def test_probable_duplicate_is_blocked_until_confirmed_distinct(self):
        candidate_id = DuplicateCandidateId("duplicate-candidate-match")
        self.permit.mark_probable_duplicate(candidate_id, NOW)
        match_result = self.match(account("probable-duplicate"))
        self.assertIsNone(match_result.match)
        self.assertIn("probable_duplicate_unresolved", match_result.exclusion_rules)
        with self.assertRaises(PublicationEligibilityError) as raised:
            OpportunityGenerator(InMemoryOpportunityStore(), self.eligibility, self.classifications, self.matches, self.projection_policy).generate(self.permit, NOW)
        self.assertIn("probable_duplicate_unresolved", raised.exception.decision.reasons)
        self.permit.confirm_distinct(candidate_id, NOW)
        generated_store = InMemoryOpportunityStore()
        generated = OpportunityGenerator(generated_store, self.eligibility, self.classifications, self.matches, self.projection_policy).generate(self.permit, NOW)
        self.assertEqual(generated.status, OpportunityStatus.PUBLISHED)
        self.assertEqual(self.permit.canonical_status, PermitCanonicalStatus.CANONICAL)
        self.assertIsNotNone(
            self.match(
                account("resolved-duplicate"),
                opportunity=generated,
                opportunity_store=generated_store,
            ).match
        )

    def test_voided_or_superseded_permit_suppresses_generation_and_matching(self):
        customer = account("lifecycle")
        original = self.match(customer).match
        self.permit.void(NOW)
        result = self.match(customer)
        self.assertEqual(result.match.opportunity_match_id, original.opportunity_match_id)
        self.assertEqual(result.match.status.value, "excluded")
        self.assertIn("permit_voided", result.exclusion_rules)

        other = observed_permit()
        other.permit_id = PermitId("permit-superseded")
        other_classification = classification(permit_id="permit-superseded", result_id="classification-superseded")
        other_state = self.classification_state(other_classification)
        other_store = InMemoryOpportunityStore()
        other_opportunity = OpportunityGenerator(other_store, self.eligibility, other_state, self.matches, self.projection_policy).generate(other, NOW)
        other.supersede(PermitId("permit-canonical"), rationale="duplicate confirmed", occurred_at=NOW)
        with self.assertRaises(PublicationEligibilityError) as raised:
            OpportunityGenerator(InMemoryOpportunityStore(), self.eligibility, other_state, self.matches, self.projection_policy).generate(other, NOW)
        self.assertIn("permit_superseded", raised.exception.decision.reasons)
        self.assertIn("noncanonical_permit", raised.exception.decision.reasons)
        blocked_match = self.match(
            account("superseded-match"),
            opportunity=other_opportunity,
            permit=other,
            classification_result=other_classification,
            opportunity_store=other_store,
        )
        self.assertIsNone(blocked_match.match)
        self.assertIn("permit_superseded", blocked_match.exclusion_rules)

    def test_canonical_and_superseded_duplicate_cannot_both_match_customer(self):
        customer = account("deduplicated-customer")
        canonical_match = self.match(customer).match
        duplicate = observed_permit()
        duplicate.permit_id = PermitId("permit-duplicate")
        duplicate_classification = classification(permit_id="permit-duplicate", result_id="classification-duplicate")
        duplicate.supersede(self.permit.permit_id, rationale="same municipal permit", occurred_at=NOW)
        with self.assertRaises(PublicationEligibilityError):
            OpportunityGenerator(InMemoryOpportunityStore(), self.eligibility, self.classification_state(duplicate_classification), self.matches, self.projection_policy).generate(duplicate, NOW)
        self.assertIsNotNone(canonical_match)
        self.assertEqual(len(self.matches.items), 1)

    def test_score_policy_boundaries_are_enforced(self):
        with self.assertRaises(InvariantViolation):
            ScorePolicy("bad", {"trade":100, "geography":1, "value":0, "completeness":0, "freshness":0, "notification_readiness":0}, 30, 90)

    def test_missing_valuation_affects_only_value_component_not_completeness(self):
        no_value = observed_permit(value="")
        no_value.permit_id = PermitId("permit-no-value")
        no_value_classification = classification(permit_id="permit-no-value", result_id="classification-no-value")
        state = self.classification_state(no_value_classification)
        no_value_store = InMemoryOpportunityStore()
        opportunity = OpportunityGenerator(
            no_value_store, self.eligibility, state, self.matches, self.projection_policy
        ).generate(no_value, NOW)
        result = self.match(
            account("no-value"), opportunity=opportunity, permit=no_value,
            classification_result=no_value_classification,
            opportunity_store=no_value_store,
        ).match
        full = self.match(account("with-value")).match
        components = {item.name: item.value for item in result.explanation.score_components}
        full_components = {item.name: item.value for item in full.explanation.score_components}
        self.assertEqual(opportunity.completeness_indicator, self.opportunity.completeness_indicator)
        self.assertEqual(components["completeness"], full_components["completeness"])
        self.assertEqual(components["value"], Decimal("0"))
        self.assertEqual(full.explanation.total_score - result.explanation.total_score, Decimal("15"))

    def test_missing_source_date_never_uses_acquisition_or_processing_as_freshness(self):
        permit = observed_permit()
        permit.permit_id = PermitId("permit-unknown-source-date")
        permit.issued_on = None
        permit.applied_on = None
        permit.source_evidence.append(PermitSourceEvidence(
            SourceId("source-unknown-date"), SourceRecordId("record-match"), "external-unknown-date",
            "a" * 64, "parser-1", NOW, acquired_at=NOW,
        ))
        result_state = self.classification_state(classification(
            permit_id="permit-unknown-source-date", result_id="classification-unknown-source-date"
        ))
        unknown_date_store = InMemoryOpportunityStore()
        opportunity = OpportunityGenerator(
            unknown_date_store, self.eligibility, result_state, self.matches, self.projection_policy
        ).generate(permit, NOW)
        match = ExplainableMatchGenerator(
            self.matches, GeographyQueryService(), self.policy, self.eligibility, result_state, unknown_date_store
        ).generate(
            opportunity=opportunity, permits=(permit,), customer=account("unknown-source-date"),
            evaluated_on=EVALUATED, occurred_at=NOW,
        ).match
        components = {item.name: item for item in match.explanation.score_components}
        freshness = match.explanation.freshness_evaluation_snapshot
        self.assertIsNone(opportunity.source_freshness_date)
        self.assertEqual(opportunity.source_freshness_basis, SourceFreshnessBasis.UNKNOWN)
        self.assertEqual(components["freshness"].value, Decimal("0"))
        self.assertIn("earns no source-freshness credit", components["freshness"].rationale)
        self.assertIsNone(freshness.source_age_days)
        self.assertEqual(freshness.acquisition_age_days, 3)
        self.assertEqual(freshness.acquisition_timestamp, NOW)
        self.assertEqual(freshness.processing_timestamp, NOW)


if __name__ == "__main__": unittest.main()
