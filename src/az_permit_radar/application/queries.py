"""Framework-neutral query messages for lightweight CQRS read use cases."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Generic, Protocol, TypeVar

from az_permit_radar.domain.access import AccessContext, AccessPermission
from az_permit_radar.domain.customer import CustomerAccount
from az_permit_radar.domain.errors import ResourceNotFound
from az_permit_radar.domain.matching import LeadState, MatchExplanation, OpportunityMatch, OpportunityMatchStatus
from az_permit_radar.domain.opportunity import Opportunity, OpportunityStatus
from az_permit_radar.domain.permit import Permit
from az_permit_radar.domain.review import ReviewTaskStatus
from az_permit_radar.domain.value_objects import (
    CustomerAccountId,
    JurisdictionId,
    OpportunityId,
    OpportunityMatchId,
    PermitId,
    SourceId,
)


@dataclass(frozen=True, slots=True)
class GetPermit:
    access_context: AccessContext
    customer_account_id: CustomerAccountId
    opportunity_match_id: OpportunityMatchId
    permit_id: PermitId


@dataclass(frozen=True, slots=True)
class FindOpportunities:
    access_context: AccessContext
    status: OpportunityStatus | None = None
    jurisdiction_id: JurisdictionId | None = None


@dataclass(frozen=True, slots=True)
class GetOpportunity:
    access_context: AccessContext
    customer_account_id: CustomerAccountId
    opportunity_match_id: OpportunityMatchId


@dataclass(frozen=True, slots=True)
class GetCustomerOpportunityMatch:
    access_context: AccessContext
    customer_account_id: CustomerAccountId
    opportunity_match_id: OpportunityMatchId


@dataclass(frozen=True, slots=True)
class GetCustomerMatchExplanation:
    access_context: AccessContext
    customer_account_id: CustomerAccountId
    opportunity_match_id: OpportunityMatchId


@dataclass(frozen=True, slots=True)
class GetCustomerConfiguration:
    access_context: AccessContext
    customer_account_id: CustomerAccountId


class CustomerMatchSort(str, Enum):
    MATCHED_AT = "matched_at"
    SCORE = "score"
    STATUS = "status"
    LEAD_STATE = "lead_state"


@dataclass(frozen=True, slots=True)
class FindOpportunityMatchesForCustomer:
    access_context: AccessContext
    customer_account_id: CustomerAccountId
    match_status: OpportunityMatchStatus | None = None
    lead_state: LeadState | None = None
    sort_by: CustomerMatchSort = CustomerMatchSort.MATCHED_AT
    descending: bool = True


@dataclass(frozen=True, slots=True)
class ListCustomerMatchesForInternal:
    access_context: AccessContext
    customer_account_id: CustomerAccountId | None = None


@dataclass(frozen=True, slots=True)
class FindOpenReviewTasks:
    access_context: AccessContext
    status: ReviewTaskStatus = ReviewTaskStatus.OPEN


@dataclass(frozen=True, slots=True)
class GetSourceImportHealth:
    access_context: AccessContext
    source_id: SourceId


QueryT = TypeVar("QueryT")
ResultT = TypeVar("ResultT", covariant=True)


class QueryHandler(Protocol, Generic[QueryT, ResultT]):
    def handle(self, query: QueryT) -> ResultT: ...


@dataclass(frozen=True, slots=True)
class CustomerMatchListView:
    matches: tuple[OpportunityMatch, ...]
    partial_failure: bool = False
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class CustomerOpportunityDetail:
    customer_match: OpportunityMatch
    opportunity: Opportunity
    permits: tuple[Permit, ...]

    @property
    def stale(self) -> bool:
        return self.customer_match.status is OpportunityMatchStatus.STALE


class CustomerMatchQueryStore(Protocol):
    def get_for_customer(
        self,
        customer_account_id: CustomerAccountId,
        opportunity_match_id: OpportunityMatchId,
    ) -> OpportunityMatch | None: ...
    def list_for_customer(self, customer_account_id: CustomerAccountId) -> tuple[OpportunityMatch, ...]: ...


class CustomerAccountQueryStore(Protocol):
    def get_for_customer(self, customer_account_id: CustomerAccountId) -> CustomerAccount | None: ...


class SharedOpportunityQueryStore(Protocol):
    def get(self, opportunity_id: OpportunityId) -> Opportunity | None: ...


class SharedPermitQueryStore(Protocol):
    def get(self, permit_id: PermitId) -> Permit | None: ...


class InternalCustomerMatchQueryStore(Protocol):
    def list_for_internal(self) -> tuple[OpportunityMatch, ...]: ...


class CustomerQueryService:
    """Normal customer reads use only scoped stores and defense-in-depth owner checks."""

    def __init__(
        self,
        *,
        matches: CustomerMatchQueryStore,
        customers: CustomerAccountQueryStore,
        opportunities: SharedOpportunityQueryStore,
        permits: SharedPermitQueryStore,
    ) -> None:
        self._matches = matches
        self._customers = customers
        self._opportunities = opportunities
        self._permits = permits

    def list_matches(self, query: FindOpportunityMatchesForCustomer) -> CustomerMatchListView:
        query.access_context.require_customer(
            query.customer_account_id,
            AccessPermission.CUSTOMER_MATCH_READ,
        )
        matches = tuple(
            match
            for match in self._matches.list_for_customer(query.customer_account_id)
            if match.customer_account_id == query.customer_account_id
            and (query.match_status is None or match.status is query.match_status)
            and (query.lead_state is None or match.lead_state is query.lead_state)
        )
        key = {
            CustomerMatchSort.MATCHED_AT: lambda match: match.matched_at.value,
            CustomerMatchSort.SCORE: lambda match: match.explanation.total_score,
            CustomerMatchSort.STATUS: lambda match: match.status.value,
            CustomerMatchSort.LEAD_STATE: lambda match: match.lead_state.value,
        }[query.sort_by]
        return CustomerMatchListView(tuple(sorted(matches, key=key, reverse=query.descending)))

    def get_match(self, query: GetCustomerOpportunityMatch) -> OpportunityMatch:
        return self._authorized_match(
            query.access_context,
            query.customer_account_id,
            query.opportunity_match_id,
        )

    def get_opportunity(self, query: GetOpportunity) -> CustomerOpportunityDetail:
        match = self._authorized_match(
            query.access_context,
            query.customer_account_id,
            query.opportunity_match_id,
        )
        opportunity = self._opportunities.get(match.opportunity_id)
        if opportunity is None:
            raise ResourceNotFound("customer resource was not found")
        permits = tuple(
            permit
            for permit_id in sorted(opportunity.permit_ids, key=str)
            if (permit := self._permits.get(permit_id)) is not None
        )
        if len(permits) != len(opportunity.permit_ids):
            raise ResourceNotFound("customer resource was not found")
        return CustomerOpportunityDetail(match, opportunity, permits)

    def get_permit(self, query: GetPermit) -> Permit:
        match = self._authorized_match(
            query.access_context,
            query.customer_account_id,
            query.opportunity_match_id,
        )
        opportunity = self._opportunities.get(match.opportunity_id)
        if opportunity is None or query.permit_id not in opportunity.permit_ids:
            raise ResourceNotFound("customer resource was not found")
        permit = self._permits.get(query.permit_id)
        if permit is None:
            raise ResourceNotFound("customer resource was not found")
        return permit

    def get_explanation(self, query: GetCustomerMatchExplanation) -> MatchExplanation:
        return self._authorized_match(
            query.access_context,
            query.customer_account_id,
            query.opportunity_match_id,
        ).explanation

    def get_configuration(self, query: GetCustomerConfiguration) -> CustomerAccount:
        query.access_context.require_customer(
            query.customer_account_id,
            AccessPermission.CUSTOMER_CONFIGURATION_READ,
        )
        account = self._customers.get_for_customer(query.customer_account_id)
        if account is None or account.customer_account_id != query.customer_account_id:
            raise ResourceNotFound("customer resource was not found")
        return account

    def _authorized_match(
        self,
        access_context: AccessContext,
        customer_account_id: CustomerAccountId,
        opportunity_match_id: OpportunityMatchId,
    ) -> OpportunityMatch:
        access_context.require_customer(
            customer_account_id,
            AccessPermission.CUSTOMER_MATCH_READ,
        )
        match = self._matches.get_for_customer(customer_account_id, opportunity_match_id)
        if match is None or match.customer_account_id != customer_account_id:
            raise ResourceNotFound("customer resource was not found")
        return match


class InternalCustomerQueryService:
    """Separate explicit path for authorized operations/support tooling."""

    def __init__(self, matches: InternalCustomerMatchQueryStore) -> None:
        self._matches = matches

    def list_matches(self, query: ListCustomerMatchesForInternal) -> tuple[OpportunityMatch, ...]:
        query.access_context.require_internal(AccessPermission.INTERNAL_CUSTOMER_READ)
        matches = self._matches.list_for_internal()
        if query.customer_account_id is None:
            return matches
        return tuple(
            match for match in matches if match.customer_account_id == query.customer_account_id
        )
