import unittest
from decimal import Decimal

from az_permit_radar.domain.classification import (
    ClassificationMethod,
    ClassificationResult,
    ClassificationReviewStatus,
)
from az_permit_radar.domain.errors import InvalidStateTransition, InvariantViolation
from az_permit_radar.domain.opportunity import Opportunity, OpportunityStatus
from az_permit_radar.domain.permit import Address, ParcelReference, Permit, PermitStatus
from az_permit_radar.domain.value_objects import (
    AddressId,
    CalendarDate,
    ClassificationResultId,
    Confidence,
    JurisdictionId,
    NormalizedAddress,
    OpportunityId,
    PermitId,
    SourceRecordId,
)

from tests.support import LATER, NOW, PROJECT_CLASSIFICATION, TRADE


def permit() -> Permit:
    jurisdiction_id = JurisdictionId("jurisdiction-001")
    return Permit(
        permit_id=PermitId("permit-001"),
        jurisdiction_id=jurisdiction_id,
        permit_number="BP-2026-001",
        source_record_ids={SourceRecordId("source-record-001")},
        parser_version="parser-1",
        recorded_at=NOW,
        issued_on=CalendarDate.from_iso("2026-07-16"),
        address=Address(
            AddressId("address-001"),
            "100 W Main St, Phoenix, AZ 85001",
            NormalizedAddress("100 W Main St", "Phoenix", "AZ", "85001"),
        ),
        parcel_reference=ParcelReference(jurisdiction_id, "parcel-001"),
    )


def classification(method: ClassificationMethod = ClassificationMethod.DETERMINISTIC) -> ClassificationResult:
    ai = method is ClassificationMethod.AI_ASSISTED
    return ClassificationResult(
        classification_result_id=ClassificationResultId("classification-001"),
        permit_id=PermitId("permit-001"),
        project_classification=PROJECT_CLASSIFICATION,
        trade_tags=frozenset({TRADE}),
        method=method,
        classifier_version="classifier-1",
        confidence=Confidence(Decimal("0.90")),
        evidence=("description contains panel upgrade",),
        produced_at=NOW,
        model_provider="provider" if ai else None,
        model_version="model-1" if ai else None,
        prompt_version="prompt-1" if ai else None,
    )


def opportunity() -> Opportunity:
    return Opportunity(
        OpportunityId("opportunity-001"),
        frozenset({PermitId("permit-001")}),
        frozenset({ClassificationResultId("classification-001")}),
        frozenset({TRADE.trade_tag_id}),
        NOW,
    )


class PermitTests(unittest.TestCase):
    def test_permit_requires_source_provenance(self) -> None:
        with self.assertRaises(InvariantViolation):
            Permit(
                PermitId("permit-001"),
                JurisdictionId("jurisdiction-001"),
                "BP-1",
                set(),
                "parser-1",
                NOW,
            )

    def test_parcel_jurisdiction_must_match_permit(self) -> None:
        with self.assertRaises(InvariantViolation):
            Permit(
                PermitId("permit-001"),
                JurisdictionId("jurisdiction-001"),
                "BP-1",
                {SourceRecordId("source-record-001")},
                "parser-1",
                NOW,
                parcel_reference=ParcelReference(JurisdictionId("jurisdiction-002"), "parcel-1"),
            )

    def test_correction_preserves_old_source_record_and_adds_new_provenance(self) -> None:
        observed = permit()
        observed.record_correction(SourceRecordId("source-record-002"), "parser-2", LATER)
        self.assertEqual(observed.status, PermitStatus.CORRECTED)
        self.assertEqual(len(observed.source_record_ids), 2)
        self.assertEqual(observed.parser_version, "parser-2")

    def test_voided_permit_cannot_be_corrected(self) -> None:
        observed = permit()
        observed.void(NOW)
        with self.assertRaises(InvalidStateTransition):
            observed.record_correction(SourceRecordId("source-record-002"), "parser-2", LATER)


class ClassificationTests(unittest.TestCase):
    def test_deterministic_classification_rejects_ai_provenance(self) -> None:
        with self.assertRaises(InvariantViolation):
            ClassificationResult(
                ClassificationResultId("classification-001"),
                PermitId("permit-001"),
                PROJECT_CLASSIFICATION,
                frozenset({TRADE}),
                ClassificationMethod.DETERMINISTIC,
                "classifier-1",
                Confidence(Decimal("0.9")),
                ("evidence",),
                NOW,
                model_provider="provider",
            )

    def test_ai_classification_requires_complete_provenance(self) -> None:
        with self.assertRaises(InvariantViolation):
            ClassificationResult(
                ClassificationResultId("classification-001"),
                PermitId("permit-001"),
                PROJECT_CLASSIFICATION,
                frozenset({TRADE}),
                ClassificationMethod.AI_ASSISTED,
                "classifier-1",
                Confidence(Decimal("0.9")),
                ("evidence",),
                NOW,
                model_provider="provider",
            )

    def test_classification_can_be_reviewed_only_once(self) -> None:
        result = classification()
        result.accept("verified against description", NOW)
        self.assertEqual(result.review_status, ClassificationReviewStatus.ACCEPTED)
        with self.assertRaises(InvalidStateTransition):
            result.reject("changed mind", LATER)


class OpportunityTests(unittest.TestCase):
    def test_opportunity_requires_permit_classification_and_trade(self) -> None:
        with self.assertRaises(InvariantViolation):
            Opportunity(
                OpportunityId("opportunity-001"),
                frozenset(),
                frozenset({ClassificationResultId("classification-001")}),
                frozenset({TRADE.trade_tag_id}),
                NOW,
            )

    def test_opportunity_lifecycle_is_explicit_and_terminal(self) -> None:
        candidate = opportunity()
        candidate.transition_to(OpportunityStatus.PUBLISHED, "review passed", NOW)
        candidate.transition_to(OpportunityStatus.EXPIRED, "freshness window ended", LATER)
        with self.assertRaises(InvalidStateTransition):
            candidate.transition_to(OpportunityStatus.PUBLISHED, "republish", LATER)


if __name__ == "__main__":
    unittest.main()
