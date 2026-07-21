import hashlib
import unittest
from decimal import Decimal

from az_permit_radar.application.normalization import (
    GeocodingResponse,
    PermitNormalizationOutcome,
    PermitNormalizationWorkflow,
)
from az_permit_radar.domain.deduplication import (
    DuplicateCandidateStatus,
    ManualDuplicateDecision,
)
from az_permit_radar.domain.ingestion import SourceRecord
from az_permit_radar.domain.parsing import ParsedValue, ValueValidationResult
from az_permit_radar.domain.permit import (
    AddressResolutionStatus,
    CoordinateSource,
    GeocodeQuality,
    PermitAuthorityStatus,
    PermitCanonicalStatus,
    PermitHistoryAction,
    PermitPartyRole,
    PermitStatus,
)
from az_permit_radar.domain.review import ReviewSubjectType
from az_permit_radar.domain.source_registry import Jurisdiction
from az_permit_radar.domain.value_objects import (
    CalendarDate,
    Confidence,
    ContentDigest,
    GeographicCoordinates,
    ImportBatchId,
    JurisdictionId,
    Money,
    NormalizedAddress,
    SourceArtifactId,
    SourceId,
    SourceRecordId,
)
from az_permit_radar.infrastructure.permit_normalization import (
    ArizonaPermitRecordNormalizer,
    FakeGeocoder,
    InMemoryJurisdictionResolver,
    InMemoryNormalizationLogger,
    InMemoryNormalizationMetrics,
    InMemoryNormalizationUnitOfWork,
    NullGeocoder,
)

from tests.support import LATER, NOW


JURISDICTION = Jurisdiction(JurisdictionId("jurisdiction-tucson"), "City of Tucson", "AZ")
SOURCE_A = SourceId("source-normalize-a")
SOURCE_B = SourceId("source-normalize-b")


def parsed_value(name: str, value: object) -> ParsedValue:
    raw = value.value.isoformat() if isinstance(value, CalendarDate) else str(value)
    if isinstance(value, Money):
        raw = format(value.amount, "f")
    return ParsedValue(
        canonical_field=name,
        source_field=name,
        raw_value=raw,
        normalized_value=value,  # type: ignore[arg-type]
        parser_version="parser-1",
        validation_result=ValueValidationResult.VALID,
    )


def source_record(
    record_id: str,
    *,
    source_id: SourceId = SOURCE_A,
    external_id: str | None = "external-001",
    fingerprint_seed: str = "record-one",
    fields: dict[str, object] | None = None,
) -> SourceRecord:
    digest = ContentDigest("sha256", hashlib.sha256(fingerprint_seed.encode()).hexdigest())
    record = SourceRecord(
        source_record_id=SourceRecordId(record_id),
        source_id=source_id,
        artifact_id=SourceArtifactId(f"artifact-{record_id}"),
        import_batch_id=ImportBatchId(f"batch-{record_id}"),
        external_record_id=external_id,
        payload_digest=digest,
        observed_at=NOW,
        acquired_at=NOW,
        source_row_number=2,
        parsed_values=tuple(
            parsed_value(name, value) for name, value in (fields or {}).items()
        ),
    )
    record.mark_parsed("parser-1", NOW)
    return record


def base_fields(
    *,
    permit_number: str = "BP-2026-001",
    address: str = "100 W Congress St, Tucson, AZ 85701",
) -> dict[str, object]:
    return {
        "permit_number": permit_number,
        "permit_status": "Permit Issued",
        "permit_type": "Residential Remodel",
        "description": "  Electrical   service upgrade  ",
        "application_date": CalendarDate.from_iso("2026-07-10"),
        "issued_date": CalendarDate.from_iso("2026-07-16"),
        "valuation": Money(Decimal("12500.00")),
        "contractor_name": "  Old Pueblo Electric LLC ",
        "contractor_license": "roc-123456",
        "applicant_name": "  Jane Applicant ",
        "address": address,
        "parcel_id": "123-45-678A",
    }


class NormalizationHarness:
    def __init__(self, geocoder: FakeGeocoder | None = None) -> None:
        self.geocoder = geocoder or NullGeocoder()
        self.unit_of_work = InMemoryNormalizationUnitOfWork()
        self.permits = self.unit_of_work.permits
        self.candidates = self.unit_of_work.duplicate_candidates
        self.reviews = self.unit_of_work.reviews
        self.logs = InMemoryNormalizationLogger()
        self.metrics = InMemoryNormalizationMetrics()
        self.workflow = PermitNormalizationWorkflow(
            normalizer=ArizonaPermitRecordNormalizer(),
            jurisdictions=InMemoryJurisdictionResolver(
                {SOURCE_A: JURISDICTION, SOURCE_B: JURISDICTION},
                {JURISDICTION.jurisdiction_id: ("Tucson",)},
            ),
            geocoder=self.geocoder,
            permits=self.permits,
            duplicate_candidates=self.candidates,
            reviews=self.reviews,
            unit_of_work=self.unit_of_work,
            logger=self.logs,
            metrics=self.metrics,
            now=lambda: LATER,
        )


class PermitNormalizationTests(unittest.TestCase):
    def test_normalizes_all_supported_fields_units_parcel_and_source_coordinates(self) -> None:
        fields = base_fields(
            permit_number=" bp 2026 / 001 ",
            address="100 West Congress Street Apartment 5, Tucson, AZ 85701",
        )
        fields.update({"latitude": "32.2217", "longitude": "-110.9265"})
        fields["jurisdiction"] = "Tucson"
        harness = NormalizationHarness()

        result = harness.workflow.normalize(source_record("record-full", fields=fields))
        permit = result.permit

        self.assertEqual(result.outcome, PermitNormalizationOutcome.CREATED)
        self.assertEqual(permit.source_evidence[0].acquired_at, NOW)
        self.assertEqual(permit.permit_number, "BP-2026-001")
        self.assertEqual(permit.authority_status, PermitAuthorityStatus.ISSUED)
        self.assertEqual(permit.permit_type.code, "remodel")  # type: ignore[union-attr]
        self.assertEqual(permit.description, "Electrical service upgrade")
        self.assertEqual(permit.applied_on, CalendarDate.from_iso("2026-07-10"))
        self.assertEqual(permit.issued_on, CalendarDate.from_iso("2026-07-16"))
        self.assertEqual(permit.valuation, Money(Decimal("12500.00")))
        self.assertEqual(permit.address.normalized.line1, "100 W CONGRESS ST")  # type: ignore[union-attr]
        self.assertEqual(permit.address.normalized.line2, "UNIT 5")  # type: ignore[union-attr]
        self.assertEqual(permit.address.coordinate_source, CoordinateSource.SOURCE)  # type: ignore[union-attr]
        self.assertEqual(
            permit.address.normalized.coordinates,  # type: ignore[union-attr]
            GeographicCoordinates(Decimal("32.2217"), Decimal("-110.9265")),
        )
        self.assertEqual(permit.parcel_reference.value, "12345678A")  # type: ignore[union-attr]
        self.assertEqual(permit.parcel_reference.raw_value, "123-45-678A")  # type: ignore[union-attr]
        self.assertEqual(
            {party.role for party in permit.parties},
            {PermitPartyRole.CONTRACTOR, PermitPartyRole.APPLICANT},
        )
        self.assertEqual(permit.parties[0].license_number, "ROC123456")
        self.assertEqual(len(harness.geocoder.calls), 0)

    def test_geocoder_result_retains_provider_timestamp_quality_and_confidence(self) -> None:
        raw_address = "500 E 22nd St, Tucson, AZ 85713"
        coordinates = GeographicCoordinates(Decimal("32.2050"), Decimal("-110.9600"))
        response = GeocodingResponse(
            provider="fixture-geocoder",
            normalized_address=NormalizedAddress("500 E 22ND ST", "TUCSON", "AZ", "85713"),
            coordinates=coordinates,
            quality="rooftop",
            confidence=Confidence(Decimal("0.98")),
        )
        harness = NormalizationHarness(FakeGeocoder({raw_address: response}))

        result = harness.workflow.normalize(
            source_record("record-geocode", fields=base_fields(address=raw_address))
        )
        address = result.permit.address

        self.assertEqual(address.resolution_status, AddressResolutionStatus.GEOCODED)  # type: ignore[union-attr]
        self.assertEqual(address.coordinate_source, CoordinateSource.GEOCODER)  # type: ignore[union-attr]
        self.assertEqual(address.geocode_result.provider, "fixture-geocoder")  # type: ignore[union-attr]
        self.assertEqual(address.geocode_result.resolved_at, LATER)  # type: ignore[union-attr]
        self.assertEqual(address.geocode_result.quality, GeocodeQuality.ROOFTOP)  # type: ignore[union-attr]
        self.assertEqual(address.geocode_result.confidence, Confidence(Decimal("0.98")))  # type: ignore[union-attr]

    def test_address_resolution_failure_creates_reviewable_state_without_logging_address(self) -> None:
        raw_address = "Unresolved site near parcel 123"
        harness = NormalizationHarness()

        result = harness.workflow.normalize(
            source_record("record-review", fields=base_fields(address=raw_address))
        )

        self.assertEqual(
            result.permit.address.resolution_status,  # type: ignore[union-attr]
            AddressResolutionStatus.REVIEW_REQUIRED,
        )
        self.assertEqual(len(result.review_tasks), 1)
        self.assertEqual(result.review_tasks[0].subject_type, ReviewSubjectType.ADDRESS)
        self.assertNotIn(raw_address, str(harness.logs.entries[0].as_dict()))

    def test_exact_duplicate_by_source_external_identifier_is_automatically_resolved(self) -> None:
        harness = NormalizationHarness()
        first = source_record("record-exact-one", fields=base_fields())
        second = source_record("record-exact-two", fields=base_fields())

        created = harness.workflow.normalize(first)
        duplicate = harness.workflow.normalize(second)

        self.assertEqual(created.outcome, PermitNormalizationOutcome.CREATED)
        self.assertEqual(duplicate.outcome, PermitNormalizationOutcome.EXACT_DUPLICATE)
        self.assertEqual(len(harness.permits.permits), 1)
        self.assertEqual(len(duplicate.permit.source_record_ids), 2)
        self.assertEqual(
            duplicate.permit.history[-1].action,
            PermitHistoryAction.EXACT_EVIDENCE_ATTACHED,
        )

    def test_missing_identifiers_use_stable_fingerprint_and_resolve_exact_duplicates(self) -> None:
        fields = base_fields()
        fields.pop("permit_number")
        harness = NormalizationHarness()
        first = source_record(
            "record-missing-one",
            external_id=None,
            fingerprint_seed="missing-shared",
            fields=fields,
        )
        second = source_record(
            "record-missing-two",
            external_id=None,
            fingerprint_seed="missing-shared",
            fields=fields,
        )

        created = harness.workflow.normalize(first)
        duplicate = harness.workflow.normalize(second)

        self.assertTrue(created.permit.permit_number.startswith("UNIDENTIFIED-"))
        self.assertIn("stable fingerprint fallback", created.warnings[0])
        self.assertEqual(duplicate.outcome, PermitNormalizationOutcome.EXACT_DUPLICATE)
        self.assertEqual(len(harness.permits.permits), 1)

    def test_changed_fingerprint_for_same_external_id_records_correction_snapshot(self) -> None:
        harness = NormalizationHarness()
        original_fields = base_fields()
        corrected_fields = base_fields()
        corrected_fields["valuation"] = Money(Decimal("25000.00"))
        corrected_fields["description"] = "Corrected scope"
        original = source_record(
            "record-correction-one",
            fingerprint_seed="before",
            fields=original_fields,
        )
        corrected = source_record(
            "record-correction-two",
            fingerprint_seed="after",
            fields=corrected_fields,
        )

        harness.workflow.normalize(original)
        result = harness.workflow.normalize(corrected)

        self.assertEqual(result.outcome, PermitNormalizationOutcome.CORRECTED)
        self.assertEqual(result.permit.status, PermitStatus.CORRECTED)
        self.assertEqual(result.permit.valuation, Money(Decimal("25000.00")))
        self.assertEqual(result.permit.history[-1].previous.valuation, Money(Decimal("12500.00")))  # type: ignore[union-attr]
        self.assertEqual(result.permit.source_record_ids, {original.source_record_id, corrected.source_record_id})
        self.assertNotEqual(original.artifact_id, corrected.artifact_id)
        self.assertEqual(original.payload_digest.hexadecimal, hashlib.sha256(b"before").hexdigest())

    def test_address_variants_create_probable_duplicate_review_not_silent_merge(self) -> None:
        harness = NormalizationHarness()
        first_fields = base_fields(address="100 West Congress Street Apt 5, Tucson, AZ 85701")
        second_fields = base_fields(address="100 W Congress St #5, Tucson, AZ 85701")
        first = source_record(
            "record-probable-one",
            source_id=SOURCE_A,
            external_id="external-a",
            fingerprint_seed="probable-a",
            fields=first_fields,
        )
        second = source_record(
            "record-probable-two",
            source_id=SOURCE_B,
            external_id="external-b",
            fingerprint_seed="probable-b",
            fields=second_fields,
        )

        first_result = harness.workflow.normalize(first)
        second_result = harness.workflow.normalize(second)

        self.assertEqual(first_result.outcome, PermitNormalizationOutcome.CREATED)
        self.assertEqual(second_result.outcome, PermitNormalizationOutcome.PROBABLE_DUPLICATE)
        self.assertEqual(len(harness.permits.permits), 2)
        self.assertIsNotNone(second_result.duplicate_candidate)
        self.assertEqual(second_result.permit.canonical_status, PermitCanonicalStatus.PROBABLE_DUPLICATE)
        self.assertEqual(second_result.permit.duplicate_candidate_id, second_result.duplicate_candidate.candidate_id)
        self.assertEqual(
            second_result.duplicate_candidate.status,  # type: ignore[union-attr]
            DuplicateCandidateStatus.PENDING_REVIEW,
        )
        self.assertTrue(
            any(task.subject_type is ReviewSubjectType.PERMIT_DUPLICATE for task in second_result.review_tasks)
        )

    def test_manual_merge_retains_decision_and_supersession_history(self) -> None:
        harness = NormalizationHarness()
        harness.workflow.normalize(
            source_record(
                "record-merge-one",
                source_id=SOURCE_A,
                external_id="merge-a",
                fingerprint_seed="merge-one",
                fields=base_fields(address="100 West Congress Street, Tucson, AZ 85701"),
            )
        )
        probable = harness.workflow.normalize(
            source_record(
                "record-merge-two",
                source_id=SOURCE_B,
                external_id="merge-b",
                fingerprint_seed="merge-two",
                fields=base_fields(address="100 W Congress St, Tucson, AZ 85701"),
            )
        )
        candidate = probable.duplicate_candidate

        decided = harness.workflow.decide_duplicate(
            candidate.candidate_id,  # type: ignore[union-attr]
            decision=ManualDuplicateDecision.MERGE,
            actor_id="reviewer-001",
            rationale="same permit confirmed against municipal detail",
        )

        self.assertEqual(decided.status, DuplicateCandidateStatus.MERGED)
        self.assertEqual(decided.decisions[0].actor_id, "reviewer-001")
        incoming = harness.permits.get(decided.permit_id)
        canonical = harness.permits.get(decided.possible_duplicate_of_id)
        self.assertEqual(incoming.status, PermitStatus.SUPERSEDED)  # type: ignore[union-attr]
        self.assertEqual(incoming.canonical_status, PermitCanonicalStatus.NONCANONICAL)  # type: ignore[union-attr]
        self.assertEqual(incoming.superseded_by, canonical.permit_id)  # type: ignore[union-attr]
        self.assertIn(incoming.permit_id, canonical.merged_permit_ids)  # type: ignore[union-attr]
        self.assertEqual(len(canonical.source_record_ids), 2)  # type: ignore[union-attr]
        self.assertEqual(canonical.history[-1].action, PermitHistoryAction.MANUAL_MERGE)  # type: ignore[union-attr]
        self.assertEqual(incoming.history[-1].action, PermitHistoryAction.SUPERSEDED)  # type: ignore[union-attr]

    def test_manual_keep_distinct_decision_is_retained_without_supersession(self) -> None:
        harness = NormalizationHarness()
        harness.workflow.normalize(
            source_record(
                "record-distinct-one",
                source_id=SOURCE_A,
                external_id="distinct-a",
                fingerprint_seed="distinct-one",
                fields=base_fields(),
            )
        )
        probable = harness.workflow.normalize(
            source_record(
                "record-distinct-two",
                source_id=SOURCE_B,
                external_id="distinct-b",
                fingerprint_seed="distinct-two",
                fields=base_fields(),
            )
        )

        decided = harness.workflow.decide_duplicate(
            probable.duplicate_candidate.candidate_id,  # type: ignore[union-attr]
            decision=ManualDuplicateDecision.KEEP_DISTINCT,
            actor_id="reviewer-002",
            rationale="separate permit applications confirmed",
        )

        self.assertEqual(decided.status, DuplicateCandidateStatus.DISTINCT)
        self.assertEqual(decided.decisions[0].rationale, "separate permit applications confirmed")
        self.assertEqual(
            harness.permits.get(decided.permit_id).status,  # type: ignore[union-attr]
            PermitStatus.ACTIVE,
        )
        self.assertEqual(
            harness.permits.get(decided.permit_id).canonical_status,  # type: ignore[union-attr]
            PermitCanonicalStatus.CANONICAL,
        )
        self.assertIsNone(harness.permits.get(decided.permit_id).duplicate_candidate_id)  # type: ignore[union-attr]


if __name__ == "__main__":
    unittest.main()
