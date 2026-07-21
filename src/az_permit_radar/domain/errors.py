"""Domain-level failures independent of transport and persistence concerns."""


class DomainError(Exception):
    """Base class for expected domain failures."""


class InvalidValue(DomainError, ValueError):
    """A value object could not be constructed from the supplied value."""


class InvariantViolation(DomainError):
    """An operation would violate an aggregate or entity invariant."""


class InvalidStateTransition(DomainError):
    """A requested lifecycle transition is not allowed from the current state."""

    def __init__(self, entity: str, current: object, requested: object) -> None:
        super().__init__(f"{entity} cannot transition from {current!s} to {requested!s}")
        self.entity = entity
        self.current = current
        self.requested = requested


class DuplicateConfiguration(InvariantViolation):
    """A customer aggregate already contains the identified configuration."""


class ConsentRequired(InvariantViolation):
    """A notification preference cannot be enabled without explicit consent."""


class ConcurrencyConflict(DomainError):
    """A repository rejected a stale aggregate version."""


class AuthenticationRequired(DomainError):
    """The operation requires a verified actor context."""


class ForbiddenAccess(DomainError):
    """An authenticated actor lacks a required permission."""


class ResourceNotFound(DomainError):
    """A resource is missing or deliberately hidden by anti-enumeration policy."""
