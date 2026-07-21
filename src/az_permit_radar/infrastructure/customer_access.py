"""In-memory customer-account adapter with scoped and explicit internal operations."""

from __future__ import annotations

import threading
from copy import deepcopy
from typing import Callable

from az_permit_radar.domain.customer import CustomerAccount
from az_permit_radar.domain.errors import InvariantViolation
from az_permit_radar.domain.value_objects import CustomerAccountId


class InMemoryCustomerAccountStore:
    def __init__(self, accounts: tuple[CustomerAccount, ...] = ()) -> None:
        self._lock = threading.RLock()
        self._accounts = {
            account.customer_account_id: deepcopy(account)
            for account in accounts
        }

    def get_for_customer(
        self,
        customer_account_id: CustomerAccountId,
    ) -> CustomerAccount | None:
        with self._lock:
            account = self._accounts.get(customer_account_id)
            return deepcopy(account) if account is not None else None

    def update_for_customer(
        self,
        customer_account_id: CustomerAccountId,
        operation: Callable[[CustomerAccount], None],
    ) -> CustomerAccount | None:
        with self._lock:
            stored = self._accounts.get(customer_account_id)
            if stored is None:
                return None
            working = deepcopy(stored)
            operation(working)
            if working.customer_account_id != customer_account_id:
                raise InvariantViolation("customer-scoped update cannot change account ownership")
            self._accounts[customer_account_id] = deepcopy(working)
            return deepcopy(working)

    def get_for_internal(
        self,
        customer_account_id: CustomerAccountId,
    ) -> CustomerAccount | None:
        return self.get_for_customer(customer_account_id)

    def save_for_internal(self, account: CustomerAccount) -> None:
        with self._lock:
            self._accounts[account.customer_account_id] = deepcopy(account)

    def list_for_internal(self) -> tuple[CustomerAccount, ...]:
        with self._lock:
            return tuple(deepcopy(account) for account in self._accounts.values())
