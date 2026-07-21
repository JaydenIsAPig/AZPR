"""Framework-neutral command messages for lightweight CQRS write use cases."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Generic, Protocol, TypeVar

from az_permit_radar.domain.access import AccessContext, AccessPermission
from az_permit_radar.domain.classification import ClassificationMethod, ProjectClassification, TradeTag
from az_permit_radar.domain.customer import (
    CustomerAccount,
    CustomerFilter,
    CustomerTradePreference,
    NotificationPreference,
    ServiceTerritory,
)
from az_permit_radar.domain.errors import DomainError, ResourceNotFound
from az_permit_radar.domain.matching import LeadState, MatchExplanation, OpportunityMatch
from az_permit_radar.domain.notification import NotificationChannel
from az_permit_radar.domain.opportunity import Opportunity
from az_permit_radar.domain.permit import Address, ParcelReference, Permit
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
    access_context: AccessContext
    customer_account_id: CustomerAccountId
    preference: CustomerTradePreference
    occurred_at: UtcTimestamp


@dataclass(frozen=True, slots=True)
class ConfigureServiceTerritory:
    access_context: AccessContext
    customer_account_id: CustomerAccountId
    service_territory: ServiceTerritory
    occurred_at: UtcTimestamp


@dataclass(frozen=True, slots=True)
class ConfigureCustomerFilter:
    access_context: AccessContext
    customer_account_id: CustomerAccountId
    customer_filter: CustomerFilter
    occurred_at: UtcTimestamp


@dataclass(frozen=True, slots=True)
class ConfigureNotificationPreference:
    access_context: AccessContext
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
    access_context: AccessContext
    customer_account_id: CustomerAccountId
    opportunity_match_id: OpportunityMatchId
    requested_state: LeadState
    occurred_at: UtcTimestamp


@dataclass(frozen=True, slots=True)
class SaveCustomerMatch:
    access_context: AccessContext
    customer_account_id: CustomerAccountId
    opportunity_match_id: OpportunityMatchId
    occurred_at: UtcTimestamp


@dataclass(frozen=True, slots=True)
class DismissCustomerMatch:
    access_context: AccessContext
    customer_account_id: CustomerAccountId
    opportunity_match_id: OpportunityMatchId
    occurred_at: UtcTimestamp


@dataclass(frozen=True, slots=True)
class MarkCustomerMatchContacted:
    access_context: AccessContext
    customer_account_id: CustomerAccountId
    opportunity_match_id: OpportunityMatchId
    occurred_at: UtcTimestamp


@dataclass(frozen=True, slots=True)
class RecalculateCustomerMatches:
    access_context: AccessContext
    customer_account_id: CustomerAccountId
    evaluated_on: CalendarDate
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


class CustomerAccountCommandStore(Protocol):
    def get_for_customer(self, customer_account_id: CustomerAccountId) -> CustomerAccount | None: ...
    def update_for_customer(
        self,
        customer_account_id: CustomerAccountId,
        operation: Callable[[CustomerAccount], None],
    ) -> CustomerAccount | None: ...


class CustomerMatchCommandStore(Protocol):
    def get_for_customer(
        self,
        customer_account_id: CustomerAccountId,
        opportunity_match_id: OpportunityMatchId,
    ) -> OpportunityMatch | None: ...
    def list_for_customer(self, customer_account_id: CustomerAccountId) -> tuple[OpportunityMatch, ...]: ...
    def update_for_customer(
        self,
        customer_account_id: CustomerAccountId,
        opportunity_match_id: OpportunityMatchId,
        operation: Callable[[OpportunityMatch], None],
    ) -> OpportunityMatch | None: ...


class SharedOpportunityCommandStore(Protocol):
    def get(self, opportunity_id: OpportunityId) -> Opportunity | None: ...


class SharedPermitCommandStore(Protocol):
    def get(self, permit_id: PermitId) -> Permit | None: ...


class MatchGenerationView(Protocol):
    match: OpportunityMatch | None


class CustomerMatchRecalculator(Protocol):
    def generate(
        self,
        *,
        opportunity: Opportunity,
        permits: tuple[Permit, ...],
        customer: CustomerAccount,
        evaluated_on: CalendarDate,
        occurred_at: UtcTimestamp,
    ) -> MatchGenerationView: ...


@dataclass(frozen=True, slots=True)
class CustomerMatchRecalculationResult:
    updated_matches: tuple[OpportunityMatch, ...]
    failed_match_ids: tuple[OpportunityMatchId, ...]

    @property
    def partial_failure(self) -> bool:
        return bool(self.failed_match_ids)


class CustomerCommandService:
    """Customer-only writes; every entry point authorizes before repository access."""

    def __init__(
        self,
        *,
        customers: CustomerAccountCommandStore,
        matches: CustomerMatchCommandStore,
        opportunities: SharedOpportunityCommandStore,
        permits: SharedPermitCommandStore,
        recalculator: CustomerMatchRecalculator,
    ) -> None:
        self._customers = customers
        self._matches = matches
        self._opportunities = opportunities
        self._permits = permits
        self._recalculator = recalculator

    def change_lead_state(self, command: ChangeLeadState) -> OpportunityMatch:
        return self._change_lead_state(
            command.access_context,
            command.customer_account_id,
            command.opportunity_match_id,
            command.requested_state,
            command.occurred_at,
        )

    def save(self, command: SaveCustomerMatch) -> OpportunityMatch:
        return self._change_lead_state(
            command.access_context,
            command.customer_account_id,
            command.opportunity_match_id,
            LeadState.SAVED,
            command.occurred_at,
        )

    def dismiss(self, command: DismissCustomerMatch) -> OpportunityMatch:
        return self._change_lead_state(
            command.access_context,
            command.customer_account_id,
            command.opportunity_match_id,
            LeadState.DISMISSED,
            command.occurred_at,
        )

    def mark_contacted(self, command: MarkCustomerMatchContacted) -> OpportunityMatch:
        return self._change_lead_state(
            command.access_context,
            command.customer_account_id,
            command.opportunity_match_id,
            LeadState.CONTACTED,
            command.occurred_at,
        )

    def configure_trade(self, command: ConfigureCustomerTradePreference) -> CustomerAccount:
        return self._configure(
            command.access_context,
            command.customer_account_id,
            lambda account: account.set_trade_preference(command.preference, command.occurred_at),
        )

    def configure_territory(self, command: ConfigureServiceTerritory) -> CustomerAccount:
        return self._configure(
            command.access_context,
            command.customer_account_id,
            lambda account: account.set_service_territory(command.service_territory, command.occurred_at),
        )

    def configure_filter(self, command: ConfigureCustomerFilter) -> CustomerAccount:
        return self._configure(
            command.access_context,
            command.customer_account_id,
            lambda account: account.set_customer_filter(command.customer_filter, command.occurred_at),
        )

    def configure_notification(self, command: ConfigureNotificationPreference) -> CustomerAccount:
        return self._configure(
            command.access_context,
            command.customer_account_id,
            lambda account: account.set_notification_preference(
                command.notification_preference,
                command.occurred_at,
            ),
        )

    def recalculate(self, command: RecalculateCustomerMatches) -> CustomerMatchRecalculationResult:
        command.access_context.require_customer(
            command.customer_account_id,
            AccessPermission.CUSTOMER_MATCH_RECALCULATE,
        )
        customer = self._customers.get_for_customer(command.customer_account_id)
        if customer is None:
            raise ResourceNotFound("customer resource was not found")
        updated: list[OpportunityMatch] = []
        failed: list[OpportunityMatchId] = []
        for existing in self._matches.list_for_customer(command.customer_account_id):
            opportunity = self._opportunities.get(existing.opportunity_id)
            permits = (
                tuple(
                    permit
                    for permit_id in sorted(opportunity.permit_ids, key=str)
                    if (permit := self._permits.get(permit_id)) is not None
                )
                if opportunity is not None
                else ()
            )
            if opportunity is None or len(permits) != len(opportunity.permit_ids):
                failed.append(existing.opportunity_match_id)
                continue
            try:
                generated = self._recalculator.generate(
                    opportunity=opportunity,
                    permits=permits,
                    customer=customer,
                    evaluated_on=command.evaluated_on,
                    occurred_at=command.occurred_at,
                )
            except DomainError:
                failed.append(existing.opportunity_match_id)
                continue
            if generated.match is not None:
                if generated.match.customer_account_id != command.customer_account_id:
                    raise ResourceNotFound("customer resource was not found")
                updated.append(generated.match)
        return CustomerMatchRecalculationResult(tuple(updated), tuple(failed))

    def _change_lead_state(
        self,
        access_context: AccessContext,
        customer_account_id: CustomerAccountId,
        opportunity_match_id: OpportunityMatchId,
        requested_state: LeadState,
        occurred_at: UtcTimestamp,
    ) -> OpportunityMatch:
        access_context.require_customer(
            customer_account_id,
            AccessPermission.CUSTOMER_LEAD_WRITE,
        )
        match = self._matches.update_for_customer(
            customer_account_id,
            opportunity_match_id,
            lambda item: item.change_lead_state(requested_state, occurred_at),
        )
        if match is None:
            raise ResourceNotFound("customer resource was not found")
        return match

    def _configure(
        self,
        access_context: AccessContext,
        customer_account_id: CustomerAccountId,
        operation: Callable[[CustomerAccount], None],
    ) -> CustomerAccount:
        access_context.require_customer(
            customer_account_id,
            AccessPermission.CUSTOMER_CONFIGURATION_WRITE,
        )
        customer = self._customers.update_for_customer(customer_account_id, operation)
        if customer is None:
            raise ResourceNotFound("customer resource was not found")
        return customer
