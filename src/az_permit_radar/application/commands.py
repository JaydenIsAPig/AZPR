"""Framework-neutral command messages for lightweight CQRS write use cases."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Generic, Protocol, TypeVar

from az_permit_radar.domain.classification import ClassificationMethod, ProjectClassification, TradeTag
from az_permit_radar.domain.customer import (
    CustomerFilter,
    CustomerTradePreference,
    NotificationPreference,
    ServiceTerritory,
)
from az_permit_radar.domain.matching import LeadState, MatchExplanation
from az_permit_radar.domain.notification import NotificationChannel
from az_permit_radar.domain.permit import Address, ParcelReference
from az_permit_radar.domain.review import ReviewSubjectType
from az_permit_radar.domain.value_objects import (
    CalendarDate,
    ClassificationResultId,
    Confidence,
    ContentDigest,
    CustomerAccountId,
    IdempotencyKey,
    ImportBatchId,
    JurisdictionId,
    Money,
    NotificationAttemptId,
    OpportunityId,
    OpportunityMatchId,
    PermitId,
    ReviewTaskId,
    SourceArtifactId,
    SourceId,
    SourceRecordId,
    TradeTagId,
    UtcTimestamp,
)


@dataclass(frozen=True, slots=True)
class RegisterJurisdiction:
    jurisdiction_id: JurisdictionId
    name: str
    region_code: str


@dataclass(frozen=True, slots=True)
class RegisterSource:
    source_id: SourceId
    jurisdiction_id: JurisdictionId
    name: str
    source_family: str


@dataclass(frozen=True, slots=True)
class StartImportBatch:
    import_batch_id: ImportBatchId
    source_id: SourceId
    started_at: UtcTimestamp


@dataclass(frozen=True, slots=True)
class ArchiveSourceArtifact:
    artifact_id: SourceArtifactId
    source_id: SourceId
    import_batch_id: ImportBatchId
    content_digest: ContentDigest
    acquired_at: UtcTimestamp
    media_type: str
    storage_reference: str


@dataclass(frozen=True, slots=True)
class RegisterSourceRecord:
    source_record_id: SourceRecordId
    source_id: SourceId
    artifact_id: SourceArtifactId
    import_batch_id: ImportBatchId
    external_record_id: str | None
    payload_digest: ContentDigest
    observed_at: UtcTimestamp


@dataclass(frozen=True, slots=True)
class CreatePermit:
    permit_id: PermitId
    jurisdiction_id: JurisdictionId
    permit_number: str
    source_record_ids: frozenset[SourceRecordId]
    parser_version: str
    recorded_at: UtcTimestamp
    issued_on: CalendarDate | None = None
    address: Address | None = None
    parcel_reference: ParcelReference | None = None
    valuation: Money | None = None


@dataclass(frozen=True, slots=True)
class RecordClassificationResult:
    classification_result_id: ClassificationResultId
    permit_id: PermitId
    project_classification: ProjectClassification
    trade_tags: frozenset[TradeTag]
    method: ClassificationMethod
    classifier_version: str
    confidence: Confidence
    evidence: tuple[str, ...]
    produced_at: UtcTimestamp
    model_provider: str | None = None
    model_version: str | None = None
    prompt_version: str | None = None


@dataclass(frozen=True, slots=True)
class CreateOpportunity:
    opportunity_id: OpportunityId
    permit_ids: frozenset[PermitId]
    classification_result_ids: frozenset[ClassificationResultId]
    trade_tag_ids: frozenset[TradeTagId]
    created_at: UtcTimestamp


@dataclass(frozen=True, slots=True)
class CreateCustomerAccount:
    customer_account_id: CustomerAccountId
    business_name: str
    created_at: UtcTimestamp


@dataclass(frozen=True, slots=True)
class ConfigureCustomerTradePreference:
    customer_account_id: CustomerAccountId
    preference: CustomerTradePreference
    occurred_at: UtcTimestamp


@dataclass(frozen=True, slots=True)
class ConfigureServiceTerritory:
    customer_account_id: CustomerAccountId
    service_territory: ServiceTerritory
    occurred_at: UtcTimestamp


@dataclass(frozen=True, slots=True)
class ConfigureCustomerFilter:
    customer_account_id: CustomerAccountId
    customer_filter: CustomerFilter
    occurred_at: UtcTimestamp


@dataclass(frozen=True, slots=True)
class ConfigureNotificationPreference:
    customer_account_id: CustomerAccountId
    notification_preference: NotificationPreference
    occurred_at: UtcTimestamp


@dataclass(frozen=True, slots=True)
class CreateOpportunityMatch:
    opportunity_match_id: OpportunityMatchId
    opportunity_id: OpportunityId
    customer_account_id: CustomerAccountId
    explanation: MatchExplanation
    matched_at: UtcTimestamp


@dataclass(frozen=True, slots=True)
class ChangeLeadState:
    opportunity_match_id: OpportunityMatchId
    requested_state: LeadState
    occurred_at: UtcTimestamp


@dataclass(frozen=True, slots=True)
class QueueNotificationAttempt:
    notification_attempt_id: NotificationAttemptId
    opportunity_match_id: OpportunityMatchId
    channel: NotificationChannel
    idempotency_key: IdempotencyKey
    queued_at: UtcTimestamp
    consent_reference: str


@dataclass(frozen=True, slots=True)
class OpenReviewTask:
    review_task_id: ReviewTaskId
    subject_type: ReviewSubjectType
    subject_id: str
    reason: str
    opened_at: UtcTimestamp


CommandT = TypeVar("CommandT")
ResultT = TypeVar("ResultT", covariant=True)


class CommandHandler(Protocol, Generic[CommandT, ResultT]):
    def handle(self, command: CommandT) -> ResultT: ...
