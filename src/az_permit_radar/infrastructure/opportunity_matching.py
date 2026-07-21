"""Local persistence and governed score configuration adapters."""

from __future__ import annotations

import json
import threading
from copy import deepcopy
from decimal import Decimal
from typing import Callable

from az_permit_radar.domain.eligibility import PublicationEligibilityPolicy
from az_permit_radar.application.opportunity_matching import OpportunityProjectionPolicy, ScorePolicy
from az_permit_radar.domain.errors import InvariantViolation
from az_permit_radar.domain.matching import OpportunityMatch
from az_permit_radar.domain.opportunity import Opportunity
from az_permit_radar.domain.value_objects import CustomerAccountId, OpportunityId, OpportunityMatchId, UtcTimestamp


class InMemoryOpportunityStore:
    def __init__(self) -> None:
        self._lock = threading.RLock()
        self.items: dict[OpportunityId, Opportunity] = {}

    def get(self, opportunity_id: OpportunityId) -> Opportunity | None:
        with self._lock:
            item = self.items.get(opportunity_id)
            return deepcopy(item) if item else None

    def save(self, opportunity: Opportunity) -> None:
        with self._lock:
            self.items[opportunity.opportunity_id] = deepcopy(opportunity)

    def run_exclusive(self, operation):
        with self._lock:
            return operation()


class InMemoryOpportunityMatchStore:
    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._items: dict[OpportunityMatchId, OpportunityMatch] = {}

    @property
    def items(self) -> dict[OpportunityMatchId, OpportunityMatch]:
        """Read-only diagnostic snapshot; customer handlers do not receive this surface."""
        with self._lock:
            return deepcopy(self._items)

    def get(self, match_id: OpportunityMatchId) -> OpportunityMatch | None:
        """Internal generation compatibility; normal handlers use get_for_customer."""
        with self._lock:
            item = self._items.get(match_id)
            return deepcopy(item) if item else None

    def get_for_customer(
        self,
        customer_account_id: CustomerAccountId,
        match_id: OpportunityMatchId,
    ) -> OpportunityMatch | None:
        with self._lock:
            item = self._items.get(match_id)
            if item is None or item.customer_account_id != customer_account_id:
                return None
            return deepcopy(item)

    def list_for_customer(
        self,
        customer_account_id: CustomerAccountId,
    ) -> tuple[OpportunityMatch, ...]:
        with self._lock:
            return tuple(
                deepcopy(item)
                for item in self._items.values()
                if item.customer_account_id == customer_account_id
            )

    def find_for(self, opportunity_id: OpportunityId, customer_account_id: CustomerAccountId) -> OpportunityMatch | None:
        with self._lock:
            item = next((match for match in self._items.values() if match.opportunity_id == opportunity_id and match.customer_account_id == customer_account_id), None)
            return deepcopy(item) if item else None

    def save(self, match: OpportunityMatch) -> None:
        with self._lock:
            self._items[match.opportunity_match_id] = deepcopy(match)

    def update_for_customer(
        self,
        customer_account_id: CustomerAccountId,
        match_id: OpportunityMatchId,
        operation: Callable[[OpportunityMatch], None],
    ) -> OpportunityMatch | None:
        with self._lock:
            stored = self._items.get(match_id)
            if stored is None or stored.customer_account_id != customer_account_id:
                return None
            working = deepcopy(stored)
            operation(working)
            if working.customer_account_id != customer_account_id:
                raise InvariantViolation("customer-scoped update cannot change Match ownership")
            self._items[match_id] = deepcopy(working)
            return deepcopy(working)

    def get_for_internal(self, match_id: OpportunityMatchId) -> OpportunityMatch | None:
        return self.get(match_id)

    def list_for_internal(self) -> tuple[OpportunityMatch, ...]:
        with self._lock:
            return tuple(deepcopy(item) for item in self._items.values())

    def save_for_internal(self, match: OpportunityMatch) -> None:
        self.save(match)

    def run_exclusive(self, operation):
        with self._lock:
            return operation()

    def mark_stale_for_opportunity(
        self,
        opportunity_id: OpportunityId,
        reason: str,
        occurred_at: UtcTimestamp,
    ) -> None:
        with self._lock:
            for match_id, stored in tuple(self._items.items()):
                if stored.opportunity_id != opportunity_id:
                    continue
                match = deepcopy(stored)
                match.mark_stale(reason, occurred_at)
                self._items[match_id] = deepcopy(match)


def load_score_policy(path: str) -> ScorePolicy:
    with open(path, encoding="utf-8") as stream:
        values = json.load(stream)["opportunity_matching_policy"]
    return ScorePolicy(
        version=values["score_version"],
        weights={name: Decimal(value) for name, value in values["weights"].items()},
        freshness_full_days=values["freshness_full_days"],
        freshness_partial_days=values["freshness_partial_days"],
        policy_id=values["policy_id"],
        unknown_source_date_factor=Decimal(values["unknown_source_date_factor"]),
        exclusion_reason_codes=tuple(values["exclusion_reason_codes"]),
    )


def load_projection_policy(path: str) -> OpportunityProjectionPolicy:
    with open(path, encoding="utf-8") as stream:
        values = json.load(stream)["opportunity_projection_policy"]
    return OpportunityProjectionPolicy(
        version=values["projection_version"],
        source_date_precedence=tuple(values["source_date_precedence"]),
        completeness_fields=tuple(values["completeness_fields"]),
        acquisition_timestamp_role=values["acquisition_timestamp_role"],
        processing_timestamp_role=values["processing_timestamp_role"],
        unknown_source_date_behavior=values["unknown_source_date_behavior"],
        valuation_in_completeness=values["valuation_in_completeness"],
    )


def load_publication_eligibility_policy(path: str) -> PublicationEligibilityPolicy:
    with open(path, encoding="utf-8") as stream:
        values = json.load(stream)["classification_policy"]
    return PublicationEligibilityPolicy.from_decimal(values["publication_confidence"])
