"""Persistence ports for aggregate roots and immutable provenance objects."""

from __future__ import annotations

from typing import Callable, Protocol

from az_permit_radar.domain.classification import ClassificationResult, TradeTag
from az_permit_radar.domain.customer import CustomerAccount
from az_permit_radar.domain.ingestion import ImportBatch, SourceArtifact, SourceRecord
from az_permit_radar.domain.matching import OpportunityMatch
from az_permit_radar.domain.notification import NotificationAttempt
from az_permit_radar.domain.opportunity import Opportunity
from az_permit_radar.domain.permit import Permit
from az_permit_radar.domain.review import ReviewTask
from az_permit_radar.domain.source_registry import Jurisdiction, Source
from az_permit_radar.domain.value_objects import (
    ClassificationResultId,
    ContentDigest,
    CustomerAccountId,
    ImportBatchId,
    JurisdictionId,
    NotificationAttemptId,
    OpportunityId,
    OpportunityMatchId,
    PermitId,
    ReviewTaskId,
    SourceArtifactId,
    SourceId,
    SourceRecordId,
    TradeTagId,
)


class JurisdictionRepository(Protocol):
    def get(self, jurisdiction_id: JurisdictionId) -> Jurisdiction | None: ...
    def save(self, jurisdiction: Jurisdiction) -> None: ...


class SourceRepository(Protocol):
    def get(self, source_id: SourceId) -> Source | None: ...
    def save(self, source: Source) -> None: ...


class SourceArtifactRepository(Protocol):
    def get(self, artifact_id: SourceArtifactId) -> SourceArtifact | None: ...
    def find_by_digest(self, source_id: SourceId, digest: ContentDigest) -> SourceArtifact | None: ...
    def add(self, artifact: SourceArtifact) -> None: ...


class ImportBatchRepository(Protocol):
    def get(self, import_batch_id: ImportBatchId) -> ImportBatch | None: ...
    def save(self, import_batch: ImportBatch) -> None: ...


class SourceRecordRepository(Protocol):
    def get(self, source_record_id: SourceRecordId) -> SourceRecord | None: ...
    def find_by_external_id(self, source_id: SourceId, external_record_id: str) -> SourceRecord | None: ...
    def save(self, source_record: SourceRecord) -> None: ...


class PermitRepository(Protocol):
    def get(self, permit_id: PermitId) -> Permit | None: ...
    def find_by_number(self, source_id: SourceId, permit_number: str) -> Permit | None: ...
    def save(self, permit: Permit) -> None: ...


class ClassificationResultRepository(Protocol):
    def get(self, classification_result_id: ClassificationResultId) -> ClassificationResult | None: ...
    def find_current_for_permit(self, permit_id: PermitId) -> ClassificationResult | None: ...
    def save(self, classification_result: ClassificationResult) -> None: ...


class TradeTagRepository(Protocol):
    def get(self, trade_tag_id: TradeTagId) -> TradeTag | None: ...
    def save(self, trade_tag: TradeTag) -> None: ...


class OpportunityRepository(Protocol):
    def get(self, opportunity_id: OpportunityId) -> Opportunity | None: ...
    def save(self, opportunity: Opportunity) -> None: ...


class CustomerAccountRepository(Protocol):
    """Normal application port: an account can be reached only through its customer scope."""

    def get_for_customer(self, customer_account_id: CustomerAccountId) -> CustomerAccount | None: ...
    def update_for_customer(
        self,
        customer_account_id: CustomerAccountId,
        operation: Callable[[CustomerAccount], None],
    ) -> CustomerAccount | None: ...


class InternalCustomerAccountRepository(Protocol):
    """Explicit operations-only port; never inject into a normal customer handler."""

    def get_for_internal(self, customer_account_id: CustomerAccountId) -> CustomerAccount | None: ...
    def save_for_internal(self, customer_account: CustomerAccount) -> None: ...
    def list_for_internal(self) -> tuple[CustomerAccount, ...]: ...


class OpportunityMatchRepository(Protocol):
    """Normal application port: every read/write includes the owning customer ID."""

    def get_for_customer(
        self,
        customer_account_id: CustomerAccountId,
        opportunity_match_id: OpportunityMatchId,
    ) -> OpportunityMatch | None: ...
    def list_for_customer(self, customer_account_id: CustomerAccountId) -> tuple[OpportunityMatch, ...]: ...
    def find_for(self, opportunity_id: OpportunityId, customer_account_id: CustomerAccountId) -> OpportunityMatch | None: ...
    def update_for_customer(
        self,
        customer_account_id: CustomerAccountId,
        opportunity_match_id: OpportunityMatchId,
        operation: Callable[[OpportunityMatch], None],
    ) -> OpportunityMatch | None: ...


class InternalOpportunityMatchRepository(Protocol):
    """Explicit internal generation/operations port with intentionally broad visibility."""

    def get_for_internal(self, opportunity_match_id: OpportunityMatchId) -> OpportunityMatch | None: ...
    def list_for_internal(self) -> tuple[OpportunityMatch, ...]: ...
    def save_for_internal(self, opportunity_match: OpportunityMatch) -> None: ...


class NotificationAttemptRepository(Protocol):
    def get(self, notification_attempt_id: NotificationAttemptId) -> NotificationAttempt | None: ...
    def save(self, notification_attempt: NotificationAttempt) -> None: ...


class ReviewTaskRepository(Protocol):
    def get(self, review_task_id: ReviewTaskId) -> ReviewTask | None: ...
    def find_for_classification(self, classification_result_id: ClassificationResultId) -> tuple[ReviewTask, ...]: ...
    def save(self, review_task: ReviewTask) -> None: ...
