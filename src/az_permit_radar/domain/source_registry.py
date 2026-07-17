"""Source Registry domain entities."""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum
from urllib.parse import urlparse
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from .errors import InvalidStateTransition, InvariantViolation
from .events import EventRecorder, state_change_event
from .value_objects import JurisdictionId, SourceId, UtcTimestamp


class JurisdictionStatus(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"


@dataclass(slots=True)
class Jurisdiction(EventRecorder):
    jurisdiction_id: JurisdictionId
    name: str
    region_code: str
    status: JurisdictionStatus = JurisdictionStatus.ACTIVE
    version: int = 0

    def __post_init__(self) -> None:
        self._initialize_events()
        if not self.name.strip():
            raise InvariantViolation("jurisdiction name is required")
        if self.region_code != "AZ":
            raise InvariantViolation("pilot jurisdictions must use Arizona region code AZ")

    def activate(self, occurred_at: UtcTimestamp) -> None:
        self._transition(JurisdictionStatus.ACTIVE, occurred_at)

    def deactivate(self, occurred_at: UtcTimestamp) -> None:
        self._transition(JurisdictionStatus.INACTIVE, occurred_at)

    def _transition(self, requested: JurisdictionStatus, occurred_at: UtcTimestamp) -> None:
        if requested == self.status:
            return
        previous = self.status
        self.status = requested
        self.version += 1
        self._record(state_change_event(self, self.jurisdiction_id, previous, requested, occurred_at))


class SourceStatus(str, Enum):
    DRAFT = "draft"
    ACTIVE = "active"
    PAUSED = "paused"
    RETIRED = "retired"


class AcquisitionMethod(str, Enum):
    FILE_DOWNLOAD = "file_download"
    HTTP_API = "http_api"
    HTML_PAGE = "html_page"
    MANUAL_UPLOAD = "manual_upload"


class AuthenticationRequirement(str, Enum):
    NONE = "none"
    API_KEY = "api_key"
    BASIC = "basic"
    OAUTH2 = "oauth2"
    SESSION = "session"


class SourceHealthStatus(str, Enum):
    UNKNOWN = "unknown"
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    FAILING = "failing"
    DISABLED = "disabled"


class AccessReviewStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    NOT_REQUIRED = "not_required"
    RESTRICTED = "restricted"


@dataclass(frozen=True, slots=True)
class EndpointConfiguration:
    """Non-secret endpoint configuration for an acquisition adapter."""

    url: str | None = None
    query_parameters: tuple[tuple[str, str], ...] = ()
    headers: tuple[tuple[str, str], ...] = ()

    def __post_init__(self) -> None:
        if self.url is not None:
            parsed = urlparse(self.url)
            if parsed.scheme not in {"http", "https"} or not parsed.netloc:
                raise InvariantViolation("source endpoint URL must be absolute HTTP(S)")
            if parsed.username or parsed.password:
                raise InvariantViolation("source endpoint URL must not contain credentials")
        for name, pairs in (("query parameter", self.query_parameters), ("header", self.headers)):
            if any(
                not key.strip()
                or not value.strip()
                or "\r" in key
                or "\n" in key
                or "\r" in value
                or "\n" in value
                for key, value in pairs
            ):
                raise InvariantViolation(f"source endpoint {name} names and values cannot be blank")
        sensitive_headers = {"authorization", "proxy-authorization", "cookie", "set-cookie"}
        if any(key.lower() in sensitive_headers for key, _ in self.headers):
            raise InvariantViolation("source endpoint configuration must not contain secret-bearing headers")
        sensitive_queries = {"api_key", "apikey", "key", "password", "secret", "signature", "token"}
        if any(key.lower() in sensitive_queries for key, _ in self.query_parameters):
            raise InvariantViolation("source endpoint configuration must not contain query credentials")


@dataclass(frozen=True, slots=True)
class SourceFileType:
    media_type: str
    extension: str

    def __post_init__(self) -> None:
        if not self.media_type.strip() or "/" not in self.media_type:
            raise InvariantViolation("source file media type is required")
        if not self.extension.startswith(".") or len(self.extension) < 2:
            raise InvariantViolation("source file extension must begin with a dot")


@dataclass(frozen=True, slots=True)
class SourceProfile:
    """Operational description of one heterogeneous permit source."""

    source_id: SourceId
    jurisdiction_id: JurisdictionId
    jurisdiction: str
    source_name: str
    acquisition_method: AcquisitionMethod
    endpoint: EndpointConfiguration
    file_type: SourceFileType
    schedule: str
    time_zone: str
    authentication_requirement: AuthenticationRequirement
    parser_identifier: str
    parser_version: str
    expected_date_fields: tuple[str, ...]
    expected_unique_identifiers: tuple[str, ...]
    historical_availability: str
    known_limitations: tuple[str, ...]
    enabled: bool
    health_status: SourceHealthStatus
    access_review_status: AccessReviewStatus
    operational_owner: str
    last_attempted_acquisition: UtcTimestamp | None = None
    last_successful_acquisition: UtcTimestamp | None = None

    def __post_init__(self) -> None:
        required_text = {
            "jurisdiction": self.jurisdiction,
            "source name": self.source_name,
            "schedule": self.schedule,
            "parser identifier": self.parser_identifier,
            "parser version": self.parser_version,
            "historical availability": self.historical_availability,
            "operational owner": self.operational_owner,
        }
        for label, value in required_text.items():
            if not value.strip():
                raise InvariantViolation(f"source profile {label} is required")
        try:
            ZoneInfo(self.time_zone)
        except (ZoneInfoNotFoundError, ValueError) as exc:
            raise InvariantViolation("source profile time zone must be a valid IANA name") from exc
        if self.acquisition_method is not AcquisitionMethod.MANUAL_UPLOAD and self.endpoint.url is None:
            raise InvariantViolation("network source profiles require an endpoint URL")
        if not self.expected_date_fields:
            raise InvariantViolation("source profile requires at least one expected date field")
        if not self.expected_unique_identifiers:
            raise InvariantViolation("source profile requires at least one expected unique identifier")
        for label, values in (
            ("expected date field", self.expected_date_fields),
            ("expected unique identifier", self.expected_unique_identifiers),
            ("known limitation", self.known_limitations),
        ):
            if any(not value.strip() for value in values):
                raise InvariantViolation(f"source profile {label} cannot be blank")
        if len(set(self.expected_date_fields)) != len(self.expected_date_fields):
            raise InvariantViolation("source profile expected date fields must be unique")
        if len(set(self.expected_unique_identifiers)) != len(self.expected_unique_identifiers):
            raise InvariantViolation("source profile expected unique identifiers must be unique")
        if self.last_successful_acquisition is not None and self.last_attempted_acquisition is None:
            raise InvariantViolation("a successful acquisition requires an attempted acquisition time")
        if (
            self.last_successful_acquisition is not None
            and self.last_attempted_acquisition is not None
            and self.last_successful_acquisition.value > self.last_attempted_acquisition.value
        ):
            raise InvariantViolation("last successful acquisition cannot follow last attempted acquisition")
        if not self.enabled and self.health_status is not SourceHealthStatus.DISABLED:
            raise InvariantViolation("a disabled source profile must have disabled health status")

    def record_attempt(self, attempted_at: UtcTimestamp, *, successful: bool) -> SourceProfile:
        if successful:
            return replace(
                self,
                last_attempted_acquisition=attempted_at,
                last_successful_acquisition=attempted_at,
                health_status=SourceHealthStatus.HEALTHY,
            )
        return replace(
            self,
            last_attempted_acquisition=attempted_at,
            health_status=SourceHealthStatus.FAILING,
        )


_SOURCE_TRANSITIONS = {
    SourceStatus.DRAFT: frozenset({SourceStatus.ACTIVE, SourceStatus.RETIRED}),
    SourceStatus.ACTIVE: frozenset({SourceStatus.PAUSED, SourceStatus.RETIRED}),
    SourceStatus.PAUSED: frozenset({SourceStatus.ACTIVE, SourceStatus.RETIRED}),
    SourceStatus.RETIRED: frozenset(),
}


@dataclass(slots=True)
class Source(EventRecorder):
    source_id: SourceId
    jurisdiction_id: JurisdictionId
    name: str
    source_family: str
    status: SourceStatus = SourceStatus.DRAFT
    version: int = 0
    profile: SourceProfile | None = None

    def __post_init__(self) -> None:
        self._initialize_events()
        if not self.name.strip():
            raise InvariantViolation("source name is required")
        if not self.source_family.strip():
            raise InvariantViolation("source family is required")
        if self.profile is not None and (
            self.profile.source_id != self.source_id
            or self.profile.jurisdiction_id != self.jurisdiction_id
        ):
            raise InvariantViolation("source profile identity must match its source")

    def transition_to(self, requested: SourceStatus, occurred_at: UtcTimestamp) -> None:
        if requested == self.status:
            return
        if requested not in _SOURCE_TRANSITIONS[self.status]:
            raise InvalidStateTransition("Source", self.status, requested)
        previous = self.status
        self.status = requested
        self.version += 1
        self._record(state_change_event(self, self.source_id, previous, requested, occurred_at))
