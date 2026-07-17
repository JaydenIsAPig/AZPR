"""Framework-neutral query messages for lightweight CQRS read use cases."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Generic, Protocol, TypeVar

from az_permit_radar.domain.matching import LeadState, OpportunityMatchStatus
from az_permit_radar.domain.opportunity import OpportunityStatus
from az_permit_radar.domain.review import ReviewTaskStatus
from az_permit_radar.domain.value_objects import (
    CustomerAccountId,
    JurisdictionId,
    OpportunityId,
    PermitId,
    SourceId,
)


@dataclass(frozen=True, slots=True)
class GetPermit:
    permit_id: PermitId


@dataclass(frozen=True, slots=True)
class FindOpportunities:
    status: OpportunityStatus | None = None
    jurisdiction_id: JurisdictionId | None = None


@dataclass(frozen=True, slots=True)
class GetOpportunity:
    opportunity_id: OpportunityId


@dataclass(frozen=True, slots=True)
class FindOpportunityMatchesForCustomer:
    customer_account_id: CustomerAccountId
    match_status: OpportunityMatchStatus | None = None
    lead_state: LeadState | None = None


@dataclass(frozen=True, slots=True)
class FindOpenReviewTasks:
    status: ReviewTaskStatus = ReviewTaskStatus.OPEN


@dataclass(frozen=True, slots=True)
class GetSourceImportHealth:
    source_id: SourceId


QueryT = TypeVar("QueryT")
ResultT = TypeVar("ResultT", covariant=True)


class QueryHandler(Protocol, Generic[QueryT, ResultT]):
    def handle(self, query: QueryT) -> ResultT: ...
