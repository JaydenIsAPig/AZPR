"""Framework-neutral identity and object-authorization contract."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .errors import AuthenticationRequired, ForbiddenAccess, InvariantViolation, ResourceNotFound
from .value_objects import AccessActorId, CustomerAccountId


class AccessRole(str, Enum):
    CUSTOMER = "customer"
    INTERNAL = "internal"


class AccessPermission(str, Enum):
    CUSTOMER_MATCH_READ = "customer_match_read"
    CUSTOMER_LEAD_WRITE = "customer_lead_write"
    CUSTOMER_CONFIGURATION_READ = "customer_configuration_read"
    CUSTOMER_CONFIGURATION_WRITE = "customer_configuration_write"
    CUSTOMER_MATCH_RECALCULATE = "customer_match_recalculate"
    INTERNAL_CUSTOMER_READ = "internal_customer_read"


@dataclass(frozen=True, slots=True)
class AccessContext:
    """Verified actor claims supplied by the future Prompt 11 authentication adapter."""

    actor_id: AccessActorId | None
    role: AccessRole | None
    customer_account_ids: frozenset[CustomerAccountId] = frozenset()
    permissions: frozenset[AccessPermission] = frozenset()

    def __post_init__(self) -> None:
        if (self.actor_id is None) != (self.role is None):
            raise InvariantViolation("access actor and role must both be present or absent")
        if self.actor_id is None and (self.customer_account_ids or self.permissions):
            raise InvariantViolation("unauthenticated access cannot carry relationships or permissions")
        if self.role is AccessRole.CUSTOMER and not self.customer_account_ids:
            raise InvariantViolation("customer access requires an account relationship")
        if self.role is AccessRole.INTERNAL and self.customer_account_ids:
            raise InvariantViolation("internal access uses permissions, not implicit customer ownership")
        customer_permissions = {
            AccessPermission.CUSTOMER_MATCH_READ,
            AccessPermission.CUSTOMER_LEAD_WRITE,
            AccessPermission.CUSTOMER_CONFIGURATION_READ,
            AccessPermission.CUSTOMER_CONFIGURATION_WRITE,
            AccessPermission.CUSTOMER_MATCH_RECALCULATE,
        }
        if self.role is AccessRole.CUSTOMER and not self.permissions <= customer_permissions:
            raise InvariantViolation("customer access cannot carry internal permissions")
        if self.role is AccessRole.INTERNAL and any(
            permission in customer_permissions for permission in self.permissions
        ):
            raise InvariantViolation("internal access must use the separate internal permission path")

    @classmethod
    def unauthenticated(cls) -> AccessContext:
        return cls(None, None)

    @classmethod
    def customer(
        cls,
        actor_id: AccessActorId,
        customer_account_ids: frozenset[CustomerAccountId],
        permissions: frozenset[AccessPermission],
    ) -> AccessContext:
        return cls(actor_id, AccessRole.CUSTOMER, customer_account_ids, permissions)

    @classmethod
    def internal(
        cls,
        actor_id: AccessActorId,
        permissions: frozenset[AccessPermission],
    ) -> AccessContext:
        return cls(actor_id, AccessRole.INTERNAL, frozenset(), permissions)

    def require_customer(
        self,
        customer_account_id: CustomerAccountId,
        permission: AccessPermission,
    ) -> None:
        self._require_authenticated()
        if self.role is not AccessRole.CUSTOMER or customer_account_id not in self.customer_account_ids:
            raise ResourceNotFound("customer resource was not found")
        if permission not in self.permissions:
            raise ForbiddenAccess("actor lacks the required customer permission")

    def require_internal(self, permission: AccessPermission) -> None:
        self._require_authenticated()
        if self.role is not AccessRole.INTERNAL or permission not in self.permissions:
            raise ForbiddenAccess("actor lacks the required internal permission")

    def _require_authenticated(self) -> None:
        if self.actor_id is None or self.role is None:
            raise AuthenticationRequired("authenticated access context is required")
