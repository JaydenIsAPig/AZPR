"""Framework-neutral source acquisition contracts and orchestration."""

from __future__ import annotations

import hashlib
import math
import time
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Callable, Literal, Protocol, cast

from az_permit_radar.domain.acquisition import (
    AcquisitionJob,
    AcquisitionOutcome,
    AcquisitionRecord,
    AcquisitionTrigger,
)
from az_permit_radar.domain.errors import ConcurrencyConflict, InvariantViolation
from az_permit_radar.domain.ingestion import (
    ArtifactResponseMetadata,
    ImportBatch,
    SourceArtifact,
)
from az_permit_radar.domain.source_registry import (
    AccessReviewStatus,
    AcquisitionMethod,
    SourceProfile,
)
from az_permit_radar.domain.value_objects import (
    AcquisitionJobId,
    ContentDigest,
    IdempotencyKey,
    ImportBatchId,
    SourceArtifactId,
    SourceId,
    UtcTimestamp,
)


@dataclass(frozen=True, slots=True)
class RetryPolicy:
    max_attempts: int = 3
    initial_backoff_seconds: float = 0.25
    backoff_multiplier: float = 2.0
    max_backoff_seconds: float = 5.0

    def __post_init__(self) -> None:
        if (
            isinstance(self.max_attempts, bool)
            or not isinstance(self.max_attempts, int)
            or self.max_attempts < 1
        ):
            raise ValueError("retry max attempts must be at least one")
        numeric_values = (
            self.initial_backoff_seconds,
            self.backoff_multiplier,
            self.max_backoff_seconds,
        )
        if not all(
            isinstance(value, (int, float)) and math.isfinite(value) for value in numeric_values
        ):
            raise ValueError("retry backoff values must be finite numbers")
        if self.initial_backoff_seconds < 0 or self.backoff_multiplier < 1:
            raise ValueError("retry backoff values are invalid")
        if self.max_backoff_seconds < self.initial_backoff_seconds:
            raise ValueError("maximum backoff cannot be less than initial backoff")

    def delay_after(self, attempt: int) -> float:
        return min(
            self.initial_backoff_seconds * (self.backoff_multiplier ** (attempt - 1)),
            self.max_backoff_seconds,
        )


@dataclass(frozen=True, slots=True)
class RequestPolicy:
    user_agent: str
    timeout_seconds: float
    max_requests_per_run: int
    max_response_bytes: int
    retry: RetryPolicy = RetryPolicy()

    def __post_init__(self) -> None:
        if (
            not isinstance(self.user_agent, str)
            or not self.user_agent.strip()
            or "\r" in self.user_agent
            or "\n" in self.user_agent
        ):
            raise ValueError("an explicit acquisition user agent is required")
        if (
            not isinstance(self.timeout_seconds, (int, float))
            or not math.isfinite(self.timeout_seconds)
            or self.timeout_seconds <= 0
        ):
            raise ValueError("acquisition timeout must be positive")
        if (
            isinstance(self.max_requests_per_run, bool)
            or not isinstance(self.max_requests_per_run, int)
            or self.max_requests_per_run < 1
        ):
            raise ValueError("request limit must be at least one")
        if (
            isinstance(self.max_response_bytes, bool)
            or not isinstance(self.max_response_bytes, int)
            or self.max_response_bytes < 1
        ):
            raise ValueError("maximum response bytes must be positive")


@dataclass(frozen=True, slots=True)
class AcquisitionRequest:
    profile: SourceProfile
    import_batch_id: ImportBatchId
    requested_at: UtcTimestamp
    policy: RequestPolicy
    uploaded_file: Path | None = None


@dataclass(frozen=True, slots=True)
class RawAcquisition:
    """Unparsed transport output. Connectors must not emit domain records."""

    content: bytes
    media_type: str
    source_reference: str
    acquired_at: UtcTimestamp
    metadata: tuple[tuple[str, str], ...] = ()
    status_code: int | None = None
    etag: str | None = None
    last_modified: str | None = None

    def __post_init__(self) -> None:
        if not self.content:
            raise ValueError("an acquisition cannot contain an empty artifact")
        if not self.media_type.strip() or not self.source_reference.strip():
            raise ValueError("acquisition media type and source reference are required")
        if self.status_code is not None and not 100 <= self.status_code <= 599:
            raise ValueError("acquisition status code is invalid")
        sensitive_names = {
            "authorization",
            "cookie",
            "proxy-authorization",
            "set-cookie",
            "x-api-key",
        }
        if any(key.lower() in sensitive_names for key, _ in self.metadata):
            raise ValueError("acquisition metadata must not contain sensitive values")


class FileDownloadConnector(Protocol):
    method: Literal[AcquisitionMethod.FILE_DOWNLOAD]

    def download_file(self, request: AcquisitionRequest) -> RawAcquisition: ...


class HttpApiConnector(Protocol):
    method: Literal[AcquisitionMethod.HTTP_API]

    def request_api(self, request: AcquisitionRequest) -> RawAcquisition: ...


class HtmlPageConnector(Protocol):
    method: Literal[AcquisitionMethod.HTML_PAGE]

    def fetch_page(self, request: AcquisitionRequest) -> RawAcquisition: ...


class ManuallyUploadedFileConnector(Protocol):
    method: Literal[AcquisitionMethod.MANUAL_UPLOAD]

    def read_uploaded_file(self, request: AcquisitionRequest) -> RawAcquisition: ...


SourceConnector = (
    FileDownloadConnector | HttpApiConnector | HtmlPageConnector | ManuallyUploadedFileConnector
)


class SourceProfileRegistry(Protocol):
    def get(self, source_id: SourceId) -> SourceProfile | None: ...

    def list_profiles(self, *, enabled_only: bool = False) -> tuple[SourceProfile, ...]: ...

    def save(self, profile: SourceProfile) -> None: ...


@dataclass(frozen=True, slots=True)
class StoredArtifact:
    storage_reference: str
    created: bool


class ImmutableArtifactStore(Protocol):
    def put(
        self,
        *,
        source_id: SourceId,
        content: bytes,
        digest: ContentDigest,
        media_type: str,
    ) -> StoredArtifact: ...


class AcquisitionFailureCategory(str, Enum):
    CONFIGURATION = "configuration"
    ACCESS_REVIEW = "access_review"
    ACCESS_CONTROL = "access_control"
    AUTHENTICATION = "authentication"
    AUTHORIZATION = "authorization"
    RATE_LIMITED = "rate_limited"
    TIMEOUT = "timeout"
    NETWORK = "network"
    REMOTE_UNAVAILABLE = "remote_unavailable"
    INVALID_RESPONSE = "invalid_response"
    INVALID_CONTENT = "invalid_content"
    RESPONSE_TOO_LARGE = "response_too_large"
    REQUEST_LIMIT = "request_limit"
    MANUAL_INPUT = "manual_input"
    ARTIFACT_STORAGE = "artifact_storage"
    UNEXPECTED = "unexpected"


class AcquisitionError(Exception):
    def __init__(
        self,
        category: AcquisitionFailureCategory,
        safe_message: str,
        *,
        retryable: bool = False,
    ) -> None:
        super().__init__(safe_message)
        self.category = category
        self.safe_message = safe_message
        self.retryable = retryable


@dataclass(frozen=True, slots=True)
class AcquisitionLogEntry:
    event: str
    source_id: str
    import_batch_id: str | None
    occurred_at: str
    outcome: str
    attempt: int
    failure_category: str | None = None
    message: str | None = None
    artifact_digest: str | None = None
    artifact_reference: str | None = None
    elapsed_ms: int = 0
    acquisition_job_id: str | None = None
    trigger: str | None = None
    status_code: int | None = None
    content_length: int | None = None
    duplicate: bool = False

    def as_dict(self) -> dict[str, object]:
        return {
            "event": self.event,
            "source_id": self.source_id,
            "import_batch_id": self.import_batch_id,
            "occurred_at": self.occurred_at,
            "outcome": self.outcome,
            "attempt": self.attempt,
            "failure_category": self.failure_category,
            "message": self.message,
            "artifact_digest": self.artifact_digest,
            "artifact_reference": self.artifact_reference,
            "elapsed_ms": self.elapsed_ms,
            "acquisition_job_id": self.acquisition_job_id,
            "trigger": self.trigger,
            "status_code": self.status_code,
            "content_length": self.content_length,
            "duplicate": self.duplicate,
        }


class AcquisitionLogger(Protocol):
    def record(self, entry: AcquisitionLogEntry) -> None: ...


@dataclass(frozen=True, slots=True)
class AcquisitionResult:
    artifact: SourceArtifact
    artifact_created: bool
    attempts: int


class AcquisitionCoordinator:
    """Acquires and archives raw bytes without parsing them."""

    def __init__(
        self,
        *,
        registry: SourceProfileRegistry,
        artifact_store: ImmutableArtifactStore,
        logger: AcquisitionLogger,
        now: Callable[[], UtcTimestamp] = UtcTimestamp.now,
        sleep: Callable[[float], None] = time.sleep,
        monotonic: Callable[[], float] = time.monotonic,
    ) -> None:
        self._registry = registry
        self._artifact_store = artifact_store
        self._logger = logger
        self._now = now
        self._sleep = sleep
        self._monotonic = monotonic

    def acquire(
        self,
        *,
        source_id: SourceId,
        import_batch_id: ImportBatchId,
        connector: SourceConnector,
        policy: RequestPolicy,
        uploaded_file: Path | None = None,
    ) -> AcquisitionResult:
        preflight_started = self._monotonic()
        profile = self._registry.get(source_id)
        if profile is None:
            error = AcquisitionError(
                AcquisitionFailureCategory.CONFIGURATION,
                "source profile is not registered",
            )
            self._logger.record(
                self._log_entry(
                    import_batch_id,
                    source_id,
                    0,
                    "failed",
                    preflight_started,
                    failure_category=error.category.value,
                    message=error.safe_message,
                )
            )
            raise error
        try:
            self._check_source_access(profile, connector)
        except AcquisitionError as error:
            failed_at = self._now()
            if profile.enabled:
                self._registry.save(profile.record_attempt(failed_at, successful=False))
            self._logger.record(
                self._log_entry(
                    import_batch_id,
                    source_id,
                    0,
                    "failed",
                    preflight_started,
                    failure_category=error.category.value,
                    message=error.safe_message,
                )
            )
            raise
        request = AcquisitionRequest(profile, import_batch_id, self._now(), policy, uploaded_file)
        allowed_attempts = min(policy.retry.max_attempts, policy.max_requests_per_run)
        last_error: AcquisitionError | None = None

        for attempt in range(1, allowed_attempts + 1):
            started = self._monotonic()
            try:
                raw = self._invoke_connector(connector, request)
                if len(raw.content) > policy.max_response_bytes:
                    raise AcquisitionError(
                        AcquisitionFailureCategory.RESPONSE_TOO_LARGE,
                        "acquired artifact exceeds configured byte limit",
                    )
                digest = ContentDigest("sha256", hashlib.sha256(raw.content).hexdigest())
                try:
                    stored = self._artifact_store.put(
                        source_id=source_id,
                        content=raw.content,
                        digest=digest,
                        media_type=raw.media_type,
                    )
                except AcquisitionError:
                    raise
                except OSError as exc:
                    raise AcquisitionError(
                        AcquisitionFailureCategory.ARTIFACT_STORAGE,
                        "immutable artifact storage failed",
                    ) from exc
                artifact_key = hashlib.sha256(
                    f"{source_id}|{import_batch_id}|{digest.hexadecimal}".encode()
                ).hexdigest()
                artifact = SourceArtifact(
                    artifact_id=SourceArtifactId(f"artifact:{artifact_key}"),
                    source_id=source_id,
                    import_batch_id=import_batch_id,
                    content_digest=digest,
                    acquired_at=raw.acquired_at,
                    media_type=raw.media_type,
                    storage_reference=stored.storage_reference,
                )
                self._registry.save(profile.record_attempt(raw.acquired_at, successful=True))
                self._logger.record(
                    self._log_entry(
                        import_batch_id,
                        source_id,
                        attempt,
                        "succeeded",
                        started,
                        artifact_digest=digest.hexadecimal,
                        artifact_reference=stored.storage_reference,
                    )
                )
                return AcquisitionResult(artifact, stored.created, attempt)
            except AcquisitionError as exc:
                should_retry = exc.retryable and attempt < allowed_attempts
                terminal_error = exc
                if (
                    exc.retryable
                    and not should_retry
                    and policy.max_requests_per_run < policy.retry.max_attempts
                ):
                    terminal_error = AcquisitionError(
                        AcquisitionFailureCategory.REQUEST_LIMIT,
                        f"request limit exhausted after {exc.category.value} failure",
                    )
                last_error = terminal_error
                self._logger.record(
                    self._log_entry(
                        import_batch_id,
                        source_id,
                        attempt,
                        "retrying" if should_retry else "failed",
                        started,
                        failure_category=(exc if should_retry else terminal_error).category.value,
                        message=(exc if should_retry else terminal_error).safe_message,
                    )
                )
                if not should_retry:
                    failed_at = self._now()
                    self._registry.save(profile.record_attempt(failed_at, successful=False))
                    if terminal_error is exc:
                        raise
                    raise terminal_error from exc
                self._sleep(policy.retry.delay_after(attempt))
            except Exception as exc:
                failed_at = self._now()
                self._registry.save(profile.record_attempt(failed_at, successful=False))
                error = AcquisitionError(
                    AcquisitionFailureCategory.UNEXPECTED,
                    "connector failed unexpectedly",
                )
                self._logger.record(
                    self._log_entry(
                        import_batch_id,
                        source_id,
                        attempt,
                        "failed",
                        started,
                        failure_category=error.category.value,
                        message=error.safe_message,
                    )
                )
                raise error from exc

        if last_error is not None:
            raise last_error
        raise AcquisitionError(
            AcquisitionFailureCategory.REQUEST_LIMIT,
            "request limit prevented acquisition",
        )

    @staticmethod
    def _check_source_access(profile: SourceProfile, connector: SourceConnector) -> None:
        if not profile.enabled:
            raise AcquisitionError(AcquisitionFailureCategory.CONFIGURATION, "source is disabled")
        if profile.access_review_status not in {
            AccessReviewStatus.APPROVED,
            AccessReviewStatus.NOT_REQUIRED,
        }:
            raise AcquisitionError(
                AcquisitionFailureCategory.ACCESS_REVIEW,
                "source access review does not permit acquisition",
            )
        if connector.method is not profile.acquisition_method:
            raise AcquisitionError(
                AcquisitionFailureCategory.CONFIGURATION,
                "connector acquisition method does not match source profile",
            )

    @staticmethod
    def _invoke_connector(connector: SourceConnector, request: AcquisitionRequest) -> RawAcquisition:
        if connector.method is AcquisitionMethod.FILE_DOWNLOAD:
            return cast(FileDownloadConnector, connector).download_file(request)
        if connector.method is AcquisitionMethod.HTTP_API:
            return cast(HttpApiConnector, connector).request_api(request)
        if connector.method is AcquisitionMethod.HTML_PAGE:
            return cast(HtmlPageConnector, connector).fetch_page(request)
        if connector.method is AcquisitionMethod.MANUAL_UPLOAD:
            return cast(ManuallyUploadedFileConnector, connector).read_uploaded_file(request)
        raise AcquisitionError(
            AcquisitionFailureCategory.CONFIGURATION,
            "connector has an unsupported acquisition method",
        )

    def _log_entry(
        self,
        import_batch_id: ImportBatchId,
        source_id: SourceId,
        attempt: int,
        outcome: Literal["succeeded", "failed", "retrying"],
        started: float,
        *,
        failure_category: str | None = None,
        message: str | None = None,
        artifact_digest: str | None = None,
        artifact_reference: str | None = None,
    ) -> AcquisitionLogEntry:
        return AcquisitionLogEntry(
            event="source_acquisition",
            source_id=str(source_id),
            import_batch_id=str(import_batch_id),
            occurred_at=self._now().value.isoformat(),
            outcome=outcome,
            attempt=attempt,
            failure_category=failure_category,
            message=message,
            artifact_digest=artifact_digest,
            artifact_reference=artifact_reference,
            elapsed_ms=max(0, int((self._monotonic() - started) * 1000)),
        )


@dataclass(frozen=True, slots=True)
class ClaimedAcquisitionAttempt:
    job: AcquisitionJob
    batch: ImportBatch
    profile: SourceProfile


@dataclass(frozen=True, slots=True)
class AcquisitionExecution:
    record: AcquisitionRecord
    batch: ImportBatch
    artifact: SourceArtifact | None
    processing_enqueued: bool
    outbox_event_count: int


class AcquisitionState(Protocol):
    """Atomic state boundaries for acquisition metadata; blob I/O remains outside."""

    def get(self, source_id: SourceId) -> SourceProfile | None: ...

    def list_profiles(self, *, enabled_only: bool = False) -> tuple[SourceProfile, ...]: ...

    def save(self, profile: SourceProfile) -> None: ...

    def create_job(self, job: AcquisitionJob) -> tuple[AcquisitionJob, bool]: ...

    def get_job(self, job_id: AcquisitionJobId) -> AcquisitionJob | None: ...

    def get_result(self, job_id: AcquisitionJobId) -> AcquisitionRecord | None: ...

    def get_artifact(self, artifact_id: SourceArtifactId) -> SourceArtifact | None: ...

    def get_batch(self, batch_id: ImportBatchId) -> ImportBatch | None: ...

    def find_artifact_by_digest(
        self,
        source_id: SourceId,
        digest: ContentDigest,
    ) -> SourceArtifact | None: ...

    def claim_job(self, job_id: AcquisitionJobId, started_at: UtcTimestamp) -> ClaimedAcquisitionAttempt: ...

    def complete_content(
        self,
        *,
        job_id: AcquisitionJobId,
        batch_id: ImportBatchId,
        digest: ContentDigest,
        response_metadata: ArtifactResponseMetadata,
        candidate_artifact: SourceArtifact | None,
        recorded_at: UtcTimestamp,
    ) -> AcquisitionExecution: ...

    def complete_reprocessing(
        self,
        *,
        job_id: AcquisitionJobId,
        batch_id: ImportBatchId,
        artifact_id: SourceArtifactId,
        recorded_at: UtcTimestamp,
    ) -> AcquisitionExecution: ...

    def complete_disabled(
        self,
        *,
        job_id: AcquisitionJobId,
        batch_id: ImportBatchId,
        recorded_at: UtcTimestamp,
    ) -> AcquisitionExecution: ...

    def fail_attempt(
        self,
        *,
        job_id: AcquisitionJobId,
        batch_id: ImportBatchId,
        category: str,
        message: str,
        recorded_at: UtcTimestamp,
        response_metadata: ArtifactResponseMetadata | None = None,
        content_digest: ContentDigest | None = None,
    ) -> AcquisitionExecution: ...

    def claim_processing(
        self,
        batch_id: ImportBatchId,
        correlation_id: str,
    ) -> tuple[ImportBatch, SourceArtifact]: ...

    def finish_processing(self, batch: ImportBatch, correlation_id: str) -> None: ...

    def fail_processing(
        self,
        batch_id: ImportBatchId,
        correlation_id: str,
        *,
        category: str,
        message: str,
        retryable: bool,
        occurred_at: UtcTimestamp,
    ) -> ImportBatch: ...


MetricLabels = tuple[tuple[str, str], ...]


class AcquisitionMetrics(Protocol):
    def increment(self, name: str, *, labels: MetricLabels = ()) -> None: ...

    def observe(self, name: str, value: float, *, labels: MetricLabels = ()) -> None: ...


class NullAcquisitionMetrics:
    def increment(self, name: str, *, labels: MetricLabels = ()) -> None:
        del name, labels

    def observe(self, name: str, value: float, *, labels: MetricLabels = ()) -> None:
        del name, value, labels


class ScheduledAcquisitionWorkflow:
    """Runs scheduled/manual jobs through immutable raw archival and batch finalization."""

    def __init__(
        self,
        *,
        state: AcquisitionState,
        artifact_store: ImmutableArtifactStore,
        logger: AcquisitionLogger,
        metrics: AcquisitionMetrics | None = None,
        now: Callable[[], UtcTimestamp] = UtcTimestamp.now,
        sleep: Callable[[float], None] = time.sleep,
        monotonic: Callable[[], float] = time.monotonic,
    ) -> None:
        self._state = state
        self._artifact_store = artifact_store
        self._logger = logger
        self._metrics = metrics or NullAcquisitionMetrics()
        self._now = now
        self._sleep = sleep
        self._monotonic = monotonic

    def create_scheduled_job(
        self,
        *,
        source_id: SourceId,
        scheduled_for: UtcTimestamp,
    ) -> AcquisitionJob:
        profile = self._require_profile(source_id)
        material = f"scheduled|{source_id}|{scheduled_for.value.isoformat()}"
        return self._create_job(
            source_id=source_id,
            scheduled_for=scheduled_for,
            schedule_expression=profile.schedule,
            trigger=AcquisitionTrigger.SCHEDULED,
            idempotency_key=self._stable_idempotency_key(material),
        )

    def create_manual_job(
        self,
        *,
        source_id: SourceId,
        requested_at: UtcTimestamp,
        idempotency_key: IdempotencyKey,
    ) -> AcquisitionJob:
        profile = self._require_profile(source_id)
        return self._create_job(
            source_id=source_id,
            scheduled_for=requested_at,
            schedule_expression=profile.schedule,
            trigger=AcquisitionTrigger.MANUAL,
            idempotency_key=idempotency_key,
        )

    def create_manual_reprocessing_job(
        self,
        *,
        artifact_id: SourceArtifactId,
        requested_at: UtcTimestamp,
        idempotency_key: IdempotencyKey,
    ) -> AcquisitionJob:
        artifact = self._state.get_artifact(artifact_id)
        if artifact is None:
            raise AcquisitionError(
                AcquisitionFailureCategory.CONFIGURATION,
                "manual reprocessing artifact is not archived",
            )
        profile = self._require_profile(artifact.source_id)
        return self._create_job(
            source_id=artifact.source_id,
            scheduled_for=requested_at,
            schedule_expression=profile.schedule,
            trigger=AcquisitionTrigger.MANUAL_REPROCESS,
            idempotency_key=idempotency_key,
            reprocess_artifact_id=artifact_id,
        )

    def run_job(
        self,
        *,
        job_id: AcquisitionJobId,
        policy: RequestPolicy,
        connector: SourceConnector | None = None,
        uploaded_file: Path | None = None,
    ) -> AcquisitionExecution:
        workflow_started = self._monotonic()
        existing_job = self._state.get_job(job_id)
        if existing_job is None:
            raise AcquisitionError(
                AcquisitionFailureCategory.CONFIGURATION,
                "acquisition job is not registered",
            )
        if existing_job.is_completed:
            record = self._state.get_result(job_id)
            if record is None:
                raise AcquisitionError(
                    AcquisitionFailureCategory.UNEXPECTED,
                    "completed acquisition job has no result",
                )
            self._metrics.increment("acquisition_job_replays_total")
            execution = self._execution_for_existing(record)
            self._record_workflow_log(
                job=existing_job,
                batch_id=record.import_batch_id,
                outcome="already_completed",
                attempt=record.attempt,
                started=workflow_started,
                artifact_digest=(
                    record.content_digest.hexadecimal
                    if record.content_digest is not None
                    else None
                ),
                artifact_reference=(
                    execution.artifact.storage_reference
                    if execution.artifact is not None
                    else None
                ),
                response_metadata=record.response_metadata,
                duplicate=record.outcome is AcquisitionOutcome.DUPLICATE,
            )
            self._observe_duration(existing_job.source_id, workflow_started)
            return execution

        try:
            claimed = self._state.claim_job(job_id, self._now())
        except ConcurrencyConflict:
            self._metrics.increment("acquisition_concurrency_conflicts_total")
            self._record_workflow_log(
                job=existing_job,
                batch_id=None,
                outcome="concurrent",
                attempt=existing_job.attempt_count,
                started=workflow_started,
                failure_category="concurrency_conflict",
                message="acquisition job is already running",
            )
            self._observe_duration(existing_job.source_id, workflow_started)
            raise

        if not claimed.profile.enabled:
            execution = self._state.complete_disabled(
                job_id=job_id,
                batch_id=claimed.batch.import_batch_id,
                recorded_at=self._now(),
            )
            self._metrics.increment("acquisition_jobs_disabled_total")
            self._record_execution(execution, claimed.job, workflow_started)
            self._observe_duration(claimed.profile.source_id, workflow_started)
            return execution

        if claimed.job.trigger is AcquisitionTrigger.MANUAL_REPROCESS:
            artifact_id = claimed.job.reprocess_artifact_id
            if artifact_id is None:
                raise AcquisitionError(
                    AcquisitionFailureCategory.CONFIGURATION,
                    "manual reprocessing job has no artifact",
                )
            execution = self._state.complete_reprocessing(
                job_id=job_id,
                batch_id=claimed.batch.import_batch_id,
                artifact_id=artifact_id,
                recorded_at=self._now(),
            )
            self._metrics.increment("acquisition_reprocessing_total")
            self._record_execution(execution, claimed.job, workflow_started)
            self._observe_duration(claimed.profile.source_id, workflow_started)
            return execution

        response_metadata: ArtifactResponseMetadata | None = None
        content_digest: ContentDigest | None = None
        try:
            if claimed.profile.access_review_status not in {
                AccessReviewStatus.APPROVED,
                AccessReviewStatus.NOT_REQUIRED,
            }:
                raise AcquisitionError(
                    AcquisitionFailureCategory.ACCESS_REVIEW,
                    "source access review does not permit acquisition",
                )
            if connector is None:
                raise AcquisitionError(
                    AcquisitionFailureCategory.CONFIGURATION,
                    "acquisition job requires a connector",
                )
            if connector.method is not claimed.profile.acquisition_method:
                raise AcquisitionError(
                    AcquisitionFailureCategory.CONFIGURATION,
                    "connector acquisition method does not match source profile",
                )
            raw, connector_attempts = self._fetch_with_retries(
                claimed,
                connector,
                policy,
                uploaded_file,
            )
            response_metadata = self._capture_response_metadata(raw)
            content_digest = ContentDigest("sha256", hashlib.sha256(raw.content).hexdigest())
            self._validate_content(claimed.profile, raw)
            existing_artifact = self._state.find_artifact_by_digest(
                claimed.profile.source_id,
                content_digest,
            )
            candidate: SourceArtifact | None = None
            if existing_artifact is None:
                stored = self._store(raw, claimed.profile.source_id, content_digest)
                artifact_key = hashlib.sha256(
                    f"{claimed.profile.source_id}|{content_digest.hexadecimal}".encode("utf-8")
                ).hexdigest()
                candidate = SourceArtifact(
                    artifact_id=SourceArtifactId(f"artifact:{artifact_key}"),
                    source_id=claimed.profile.source_id,
                    import_batch_id=claimed.batch.import_batch_id,
                    content_digest=content_digest,
                    acquired_at=raw.acquired_at,
                    media_type=raw.media_type,
                    storage_reference=stored.storage_reference,
                    response_metadata=response_metadata,
                )
            execution = self._state.complete_content(
                job_id=job_id,
                batch_id=claimed.batch.import_batch_id,
                digest=content_digest,
                response_metadata=response_metadata,
                candidate_artifact=candidate,
                recorded_at=self._now(),
            )
            self._metrics.increment(
                "acquisition_jobs_completed_total",
                labels=(("outcome", execution.record.outcome.value),),
            )
            self._metrics.observe(
                "acquisition_connector_attempts",
                float(connector_attempts),
                labels=(("source_id", str(claimed.profile.source_id)),),
            )
            self._record_execution(
                execution,
                claimed.job,
                workflow_started,
                response_metadata=response_metadata,
            )
            return execution
        except AcquisitionError as error:
            execution = self._state.fail_attempt(
                job_id=job_id,
                batch_id=claimed.batch.import_batch_id,
                category=error.category.value,
                message=error.safe_message,
                recorded_at=self._now(),
                response_metadata=response_metadata,
                content_digest=content_digest,
            )
            self._metrics.increment(
                "acquisition_failures_total",
                labels=(("category", error.category.value),),
            )
            self._record_execution(execution, claimed.job, workflow_started)
            raise
        finally:
            self._observe_duration(claimed.profile.source_id, workflow_started)

    def _create_job(
        self,
        *,
        source_id: SourceId,
        scheduled_for: UtcTimestamp,
        schedule_expression: str,
        trigger: AcquisitionTrigger,
        idempotency_key: IdempotencyKey,
        reprocess_artifact_id: SourceArtifactId | None = None,
    ) -> AcquisitionJob:
        job_hash = hashlib.sha256(idempotency_key.value.encode("utf-8")).hexdigest()
        requested = AcquisitionJob(
            acquisition_job_id=AcquisitionJobId(f"job:{job_hash}"),
            source_id=source_id,
            idempotency_key=idempotency_key,
            trigger=trigger,
            scheduled_for=scheduled_for,
            schedule_expression=schedule_expression,
            reprocess_artifact_id=reprocess_artifact_id,
        )
        job, created = self._state.create_job(requested)
        if created:
            self._metrics.increment(
                "acquisition_jobs_created_total",
                labels=(("trigger", trigger.value),),
            )
            self._record_workflow_log(
                job=job,
                batch_id=None,
                outcome="created",
                attempt=0,
                started=self._monotonic(),
            )
        else:
            self._metrics.increment("acquisition_job_creation_duplicates_total")
        return job

    def _fetch_with_retries(
        self,
        claimed: ClaimedAcquisitionAttempt,
        connector: SourceConnector,
        policy: RequestPolicy,
        uploaded_file: Path | None,
    ) -> tuple[RawAcquisition, int]:
        allowed_attempts = min(policy.retry.max_attempts, policy.max_requests_per_run)
        request = AcquisitionRequest(
            claimed.profile,
            claimed.batch.import_batch_id,
            self._now(),
            policy,
            uploaded_file,
        )
        for attempt in range(1, allowed_attempts + 1):
            attempt_started = self._monotonic()
            self._metrics.increment(
                "acquisition_fetch_attempts_total",
                labels=(("source_id", str(claimed.profile.source_id)),),
            )
            try:
                raw = AcquisitionCoordinator._invoke_connector(connector, request)
                if len(raw.content) > policy.max_response_bytes:
                    raise AcquisitionError(
                        AcquisitionFailureCategory.RESPONSE_TOO_LARGE,
                        "acquired artifact exceeds configured byte limit",
                    )
                return raw, attempt
            except AcquisitionError as error:
                should_retry = error.retryable and attempt < allowed_attempts
                self._record_workflow_log(
                    job=claimed.job,
                    batch_id=claimed.batch.import_batch_id,
                    outcome="retrying" if should_retry else "failed",
                    attempt=attempt,
                    started=attempt_started,
                    failure_category=error.category.value,
                    message=error.safe_message,
                )
                if not should_retry:
                    if error.retryable and policy.max_requests_per_run < policy.retry.max_attempts:
                        raise AcquisitionError(
                            AcquisitionFailureCategory.REQUEST_LIMIT,
                            f"request limit exhausted after {error.category.value} failure",
                        ) from error
                    raise
                self._sleep(policy.retry.delay_after(attempt))
            except Exception as error:
                raise AcquisitionError(
                    AcquisitionFailureCategory.UNEXPECTED,
                    "connector failed unexpectedly",
                ) from error
        raise AcquisitionError(
            AcquisitionFailureCategory.REQUEST_LIMIT,
            "request limit prevented acquisition",
        )

    def _store(
        self,
        raw: RawAcquisition,
        source_id: SourceId,
        digest: ContentDigest,
    ) -> StoredArtifact:
        try:
            return self._artifact_store.put(
                source_id=source_id,
                content=raw.content,
                digest=digest,
                media_type=raw.media_type,
            )
        except AcquisitionError:
            raise
        except OSError as error:
            raise AcquisitionError(
                AcquisitionFailureCategory.ARTIFACT_STORAGE,
                "immutable artifact storage failed",
            ) from error

    @staticmethod
    def _capture_response_metadata(raw: RawAcquisition) -> ArtifactResponseMetadata:
        try:
            return ArtifactResponseMetadata(
                source_reference=raw.source_reference,
                captured_at=raw.acquired_at,
                content_type=raw.media_type,
                content_length=len(raw.content),
                status_code=raw.status_code,
                etag=raw.etag,
                last_modified=raw.last_modified,
                attributes=raw.metadata,
            )
        except InvariantViolation as error:
            raise AcquisitionError(
                AcquisitionFailureCategory.INVALID_CONTENT,
                "source response metadata is invalid",
            ) from error

    @staticmethod
    def _validate_content(profile: SourceProfile, raw: RawAcquisition) -> None:
        expected_type = profile.file_type.media_type.partition(";")[0].strip().lower()
        actual_type = raw.media_type.partition(";")[0].strip().lower()
        if expected_type != actual_type:
            raise AcquisitionError(
                AcquisitionFailureCategory.INVALID_CONTENT,
                "source response content type does not match source profile",
            )
        if raw.status_code is not None and raw.status_code >= 400:
            raise AcquisitionError(
                AcquisitionFailureCategory.INVALID_RESPONSE,
                "source returned an unsuccessful response status",
            )

    def _require_profile(self, source_id: SourceId) -> SourceProfile:
        profile = self._state.get(source_id)
        if profile is None:
            raise AcquisitionError(
                AcquisitionFailureCategory.CONFIGURATION,
                "source profile is not registered",
            )
        return profile

    @staticmethod
    def _stable_idempotency_key(material: str) -> IdempotencyKey:
        digest = hashlib.sha256(material.encode("utf-8")).hexdigest()
        return IdempotencyKey(f"acq:{digest}")

    def _record_execution(
        self,
        execution: AcquisitionExecution,
        job: AcquisitionJob,
        started: float,
        *,
        response_metadata: ArtifactResponseMetadata | None = None,
    ) -> None:
        record = execution.record
        self._record_workflow_log(
            job=job,
            batch_id=record.import_batch_id,
            outcome=record.outcome.value,
            attempt=record.attempt,
            started=started,
            failure_category=record.failure_category,
            message=record.failure_message,
            artifact_digest=(
                record.content_digest.hexadecimal if record.content_digest is not None else None
            ),
            artifact_reference=(
                execution.artifact.storage_reference if execution.artifact is not None else None
            ),
            response_metadata=response_metadata or record.response_metadata,
            duplicate=record.outcome is AcquisitionOutcome.DUPLICATE,
        )

    def _record_workflow_log(
        self,
        *,
        job: AcquisitionJob,
        batch_id: ImportBatchId | None,
        outcome: str,
        attempt: int,
        started: float,
        failure_category: str | None = None,
        message: str | None = None,
        artifact_digest: str | None = None,
        artifact_reference: str | None = None,
        response_metadata: ArtifactResponseMetadata | None = None,
        duplicate: bool = False,
    ) -> None:
        self._logger.record(
            AcquisitionLogEntry(
                event="source_acquisition_workflow",
                source_id=str(job.source_id),
                import_batch_id=str(batch_id) if batch_id is not None else None,
                occurred_at=self._now().value.isoformat(),
                outcome=outcome,
                attempt=attempt,
                failure_category=failure_category,
                message=message,
                artifact_digest=artifact_digest,
                artifact_reference=artifact_reference,
                elapsed_ms=max(0, int((self._monotonic() - started) * 1000)),
                acquisition_job_id=str(job.acquisition_job_id),
                trigger=job.trigger.value,
                status_code=(response_metadata.status_code if response_metadata else None),
                content_length=(response_metadata.content_length if response_metadata else None),
                duplicate=duplicate,
            )
        )

    def _observe_duration(self, source_id: SourceId, started: float) -> None:
        self._metrics.observe(
            "acquisition_job_duration_ms",
            max(0.0, (self._monotonic() - started) * 1000),
            labels=(("source_id", str(source_id)),),
        )

    def _execution_for_existing(self, record: AcquisitionRecord) -> AcquisitionExecution:
        artifact = (
            self._state.get_artifact(record.artifact_id)
            if record.artifact_id is not None
            else None
        )
        batch = self._state.get_batch(record.import_batch_id)
        if batch is None:
            raise AcquisitionError(
                AcquisitionFailureCategory.UNEXPECTED,
                "completed acquisition job has no import batch",
            )
        return AcquisitionExecution(record, batch, artifact, False, 0)
