import json
import unittest
from decimal import Decimal
from pathlib import Path

from az_permit_radar.application.classification import ClassificationPolicy, ClassificationSignals, PermitClassificationService
from az_permit_radar.application.opportunity_matching import OpportunityGenerator, OpportunityProjectionPolicy
from az_permit_radar.domain.classification import ClassificationOrigin, ClassificationReviewStatus, HumanClassificationDecision
from az_permit_radar.domain.eligibility import PublicationEligibilityError, PublicationEligibilityPolicy
from az_permit_radar.domain.review import ReviewSubjectType, ReviewTaskStatus
from az_permit_radar.domain.value_objects import ClassificationResultId
from az_permit_radar.domain.permit import NormalizedPermitType, Permit, PermitParty, PermitPartyRole
from az_permit_radar.domain.value_objects import JurisdictionId, Money, PermitId, SourceRecordId
from az_permit_radar.infrastructure.opportunity_matching import InMemoryOpportunityMatchStore, InMemoryOpportunityStore
from az_permit_radar.infrastructure.permit_classification import InMemoryClassificationState, RuleEngineConfig, SchemaConstrainedAIClassifier, VersionedPermitRuleEngine, load_classification_policy, precision_by_tag
from tests.support import NOW


def make_permit(description="Commercial tenant improvement and panel upgrade", permit_type="remodel", valuation="120000", parties=()):
    return Permit(PermitId("permit-classify"), JurisdictionId("phoenix"), "BP-1", {SourceRecordId("record-1")}, "parser-1", NOW,
                  valuation=Money(Decimal(valuation)) if valuation else None,
                  permit_type=NormalizedPermitType(permit_type, permit_type.title()), description=description, parties=parties)


class ClassificationSubsystemTests(unittest.TestCase):
    def test_rules_use_all_context_and_retain_versions(self):
        permit = make_permit(parties=(PermitParty(PermitPartyRole.CONTRACTOR, "Owner-Builder"),))
        engine = VersionedPermitRuleEngine(RuleEngineConfig("2.1.0", {"phoenix": {"CIVIL": ("concrete_structural", True)}}))
        result = engine.classify(ClassificationSignals(permit, occupancy="B office", project="renovation", source_categories=("CIVIL",)))
        by_tag = {item.tag: item for item in result}
        for tag in ("market_segment", "tenant_improvement", "electrical", "remodel", "concrete_structural", "value_band", "owner_builder", "data_completeness"):
            self.assertIn(tag, by_tag)
        self.assertEqual(by_tag["electrical"].origin, ClassificationOrigin.DETERMINISTIC_RULE)
        self.assertEqual(by_tag["electrical"].rule_version, "2.1.0")

    def test_ai_cannot_overwrite_deterministic_and_low_confidence_creates_review(self):
        ai = SchemaConstrainedAIClassifier(lambda _: {"assertions": [
            {"tag":"electrical", "value":False, "confidence":"0.99", "evidence":"ambiguous"},
            {"tag":"low_voltage", "value":True, "confidence":"0.70", "evidence":"mentions controls"}
        ]}, provider="fake", model_version="model-1", classifier_version="prompt-1")
        permit = make_permit()
        state = InMemoryClassificationState()
        service = PermitClassificationService(VersionedPermitRuleEngine(), ai, ClassificationPolicy(Decimal("0.60"), Decimal("0.80"), Decimal("0.80")), state)
        outcome = service.classify(ClassificationSignals(permit), NOW)
        by_tag = {item.tag: item for item in outcome.assertions}
        self.assertTrue(by_tag["electrical"].value)
        self.assertEqual(by_tag["electrical"].origin, ClassificationOrigin.DETERMINISTIC_RULE)
        self.assertEqual(len(outcome.review_tasks), 1)
        self.assertEqual(len(state.results), 1)
        task = outcome.review_tasks[0]
        self.assertEqual(task.subject_type, ReviewSubjectType.CLASSIFICATION_RESULT)
        self.assertEqual(task.subject_id, str(outcome.classification_result.classification_result_id))
        self.assertEqual(task.permit_id, outcome.classification_result.permit_id)
        self.assertEqual(task.classification_result_id, outcome.classification_result.classification_result_id)

        replay = service.classify(ClassificationSignals(permit), NOW)
        self.assertEqual(replay.classification_result.classification_result_id, outcome.classification_result.classification_result_id)
        self.assertEqual(len(state.results), 1)
        self.assertEqual(len(replay.review_tasks), 1)

        with self.assertRaises(PublicationEligibilityError) as blocked:
            OpportunityGenerator(
                InMemoryOpportunityStore(),
                PublicationEligibilityPolicy.from_decimal("0.80"),
                InMemoryClassificationState(),
                InMemoryOpportunityMatchStore(),
                OpportunityProjectionPolicy(
                    "opportunity-projection-1.0.0",
                    ("issued_on", "applied_on"),
                    ("permit_type", "description", "address", "permit_date"),
                    "context_only",
                    "provenance_only",
                ),
            ).generate(permit, NOW)
        self.assertIn("classification_missing", blocked.exception.decision.reasons)

        reviewed = service.resolve_review(
            outcome.classification_result.classification_result_id,
            approved=True,
            actor_id="reviewer-1",
            reason="source record supports the low-voltage scope",
            occurred_at=NOW,
        )
        self.assertEqual(reviewed.review_status, ClassificationReviewStatus.ACCEPTED)
        self.assertEqual(reviewed.confidence.value, Decimal("0.95"))
        self.assertTrue(reviewed.human_decisions)
        version = reviewed.version
        replayed_review = service.resolve_review(
            outcome.classification_result.classification_result_id,
            approved=True,
            actor_id="reviewer-1",
            reason="source record supports the low-voltage scope",
            occurred_at=NOW,
        )
        self.assertEqual(replayed_review.version, version)
        self.assertEqual(state.find_review_tasks(reviewed.classification_result_id)[0].status, ReviewTaskStatus.RESOLVED)

    def test_ai_adapter_minimizes_sanitizes_and_fails_closed(self):
        captured = {}
        def provider(payload):
            captured.update(payload)
            return {"unexpected": []}
        permit = make_permit("Call 602-555-0100 or a@example.com about unusual controls")
        adapter = SchemaConstrainedAIClassifier(provider, provider="fake", model_version="1", classifier_version="1")
        self.assertEqual(adapter.classify_description(permit), ())
        self.assertEqual(set(captured), {"description", "schema"})
        self.assertNotIn("602-555-0100", captured["description"])
        self.assertNotIn("a@example.com", captured["description"])

    def test_provider_failure_does_not_block_rules(self):
        def failure(_): raise TimeoutError
        ai = SchemaConstrainedAIClassifier(failure, provider="fake", model_version="1", classifier_version="1")
        outcome = PermitClassificationService(VersionedPermitRuleEngine(), ai, ClassificationPolicy(Decimal(".8"), Decimal(".7"), Decimal(".7")), InMemoryClassificationState()).classify(ClassificationSignals(make_permit()), NOW)
        self.assertIn("electrical", {item.tag for item in outcome.assertions})

    def test_governed_policy_loads_publication_threshold_and_new_rules_supersede(self):
        policy = load_classification_policy("docs/current/business-data-v1.7.json")
        self.assertEqual(policy.publication_confidence, Decimal("0.80"))
        state = InMemoryClassificationState()
        permit = make_permit()
        first = PermitClassificationService(
            VersionedPermitRuleEngine(RuleEngineConfig("1.0.0")),
            None,
            policy,
            state,
        ).classify(ClassificationSignals(permit), NOW).classification_result
        second = PermitClassificationService(
            VersionedPermitRuleEngine(RuleEngineConfig("2.0.0")),
            None,
            ClassificationPolicy(
                policy.ai_acceptance_confidence,
                policy.review_confidence,
                policy.publication_confidence,
                "2.0.0",
            ),
            state,
        ).classify(ClassificationSignals(permit), NOW).classification_result
        self.assertNotEqual(first.classification_result_id, second.classification_result_id)
        self.assertEqual(second.supersedes_classification_result_id, first.classification_result_id)
        self.assertEqual(second.revision, 2)
        self.assertEqual(state.find_current_for_permit(permit.permit_id).classification_result_id, second.classification_result_id)

    def test_rejection_is_authoritative_and_idempotent(self):
        ai = SchemaConstrainedAIClassifier(
            lambda _: {"assertions": [{"tag": "low_voltage", "value": True, "confidence": "0.70", "evidence": "ambiguous controls"}]},
            provider="fake",
            model_version="model-1",
            classifier_version="prompt-1",
        )
        state = InMemoryClassificationState()
        service = PermitClassificationService(
            VersionedPermitRuleEngine(),
            ai,
            ClassificationPolicy(Decimal(".6"), Decimal(".8"), Decimal(".8")),
            state,
        )
        outcome = service.classify(ClassificationSignals(make_permit()), NOW)
        rejected = service.resolve_review(
            outcome.classification_result.classification_result_id,
            approved=False,
            actor_id="reviewer-2",
            reason="municipal detail contradicts inferred controls scope",
            occurred_at=NOW,
        )
        self.assertEqual(rejected.review_status, ClassificationReviewStatus.REJECTED)
        version = rejected.version
        replay = service.resolve_review(
            ClassificationResultId(str(rejected.classification_result_id)),
            approved=False,
            actor_id="reviewer-2",
            reason="municipal detail contradicts inferred controls scope",
            occurred_at=NOW,
        )
        self.assertEqual(replay.version, version)

    def test_human_decision_exports_labeled_data_without_retraining(self):
        decision = HumanClassificationDecision(PermitId("permit-1"), "solar", True, "reviewer-1", "verified source", NOW, ClassificationOrigin.AI)
        self.assertEqual(decision.as_labeled_example()["tag"], "solar")

    def test_fixed_fixture_precision_by_tag(self):
        fixtures = json.loads(Path("tests/fixtures/classification/evaluation-v1.json").read_text())
        predicted = []
        engine = VersionedPermitRuleEngine()
        for row in fixtures:
            predicted.append({a.tag for a in engine.classify(ClassificationSignals(make_permit(row["description"], row["permit_type"], row["valuation"])))})
        report = precision_by_tag(fixtures, predicted)
        self.assertTrue(report)
        self.assertTrue(all(value == Decimal("1") for value in report.values()))


if __name__ == "__main__": unittest.main()
