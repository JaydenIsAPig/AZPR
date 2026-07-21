"""Source acquisition adapters that do not parse permit records."""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
import threading
from copy import deepcopy
from pathlib import Path
from typing import Iterable

from az_permit_radar.application.acquisition import (
    AcquisitionExecution,
    AcquisitionError,
    AcquisitionFailureCategory,
    AcquisitionLogEntry,
    AcquisitionRequest,
    ClaimedAcquisitionAttempt,
    MetricLabels,
    RawAcquisition,
    StoredArtifact,
)
from az_permit_radar.domain.acquisition import (
    AcquisitionJob,
    AcquisitionJobStatus,
    AcquisitionOutcome,
    AcquisitionRecord,
)
from az_permit_radar.domain.errors import ConcurrencyConflict, InvariantViolation
from az_permit_radar.domain.events import DomainEvent
from az_permit_radar.domain.ingestion import (
    ArtifactResponseMetadata,
    ImportBatch,
    ImportBatchStatus,
    SourceArtifact,
)
from az_permit_radar.domain.source_registry import AcquisitionMethod, SourceProfile
from az_permit_radar.domain.value_objects import (
    AcquisitionJobId,
    ContentDigest,
    ImportBatchId,
    SourceArtifactId,
    SourceId,
    UtcTimestamp,
)


class InMemorySourceProfileRegistry:
    def __init__(self, profiles: Iterable[SourceProfile] = ()) -> None:
        self._profiles = {profile.source_id: profile for profile in profiles}

    def get(self, source_id: SourceId) -> SourceProfile | None:
        return self._profiles.get(source_id)

    def list_profiles(self, *, enabled_only: bool = False) -> tuple[SourceProfile, ...]:
        profiles = (
            profile for profile in self._profiles.values() if profile.enabled or not enabled_only
        )
        return tuple(sorted(profiles, key=lambda profile: str(profile.source_id)))

    def save(self, profile: SourceProfile) -> None:
        self._profiles[profile.source_id] = profile


class InMemoryAcquisitionState:
    """Lock-serialized transactional metadata adapter for deterministic tests/local use."""

    def __init__(self, profiles: Iterable[SourceProfile] = ()) -> None:
        self._lock = threading.RLock()
        self._profiles = {profile.source_id: profile for profile in profiles}
        self._jobs: dict[AcquisitionJobId, AcquisitionJob] = {}
        self._job_by_idempotency: dict[str, AcquisitionJobId] = {}
        self._batches: dict[ImportBatchId, ImportBatch] = {}
        self._artifacts: dict[SourceArtifactId, SourceArtifact] = {}
        self._artifact_by_source_digest: dict[tuple[SourceId, str], SourceArtifactId] = {}
        self._results: dict[AcquisitionJobId, list[AcquisitionRecord]] = {}
        self._outbox: list[DomainEvent] = []
        self._processing_queue: list[ImportBatchId] = []
        self._processing_claims: dict[ImportBatchId, str] = {}

    def get(self, source_id: SourceId) -> SourceProfile | None:
        with self._lock:
            return self._profiles.get(source_id)

    def list_profiles(self, *, enabled_only: bool = False) -> tuple[SourceProfile, ...]:
        with self._lock:
            profiles = (
                profile for profile in self._profiles.values() if profile.enabled or not enabled_only
            )
            return tuple(sorted(profiles, key=lambda profile: str(profile.source_id)))

    def save(self, profile: SourceProfile) -> None:
        with self._lock:
            self._profiles[profile.source_id] = profile

    def create_job(self, job: AcquisitionJob) -> tuple[AcquisitionJob, bool]:
        with self._lock:
            existing_id = self._job_by_idempotency.get(job.idempotency_key.value)
            if existing_id is not None:
                existing = self._jobs[existing_id]
                if (
                    existing.source_id != job.source_id
                    or existing.trigger is not job.trigger
                    or existing.reprocess_artifact_id != job.reprocess_artifact_id
                ):
                    raise InvariantViolation("acquisition idempotency key was reused for another job")
                return deepcopy(existing), False
            self._jobs[job.acquisition_job_id] = deepcopy(job)
            self._job_by_idempotency[job.idempotency_key.value] = job.acquisition_job_id
            return deepcopy(job), True

    def get_job(self, job_id: AcquisitionJobId) -> AcquisitionJob | None:
        with self._lock:
            job = self._jobs.get(job_id)
            return deepcopy(job) if job is not None else None

    def get_result(self, job_id: AcquisitionJobId) -> AcquisitionRecord | None:
        with self._lock:
            results = self._results.get(job_id, ())
            return results[-1] if results else None

    def list_results(self, job_id: AcquisitionJobId) -> tuple[AcquisitionRecord, ...]:
        with self._lock:
            return tuple(self._results.get(job_id, ()))

    def get_artifact(self, artifact_id: SourceArtifactId) -> SourceArtifact | None:
        with self._lock:
            return self._artifacts.get(artifact_id)

    def get_batch(self, batch_id: ImportBatchId) -> ImportBatch | None:
        with self._lock:
            batch = self._batches.get(batch_id)
            return deepcopy(batch) if batch is not None else None

    def find_artifact_by_digest(
        self,
        source_id: SourceId,
        digest: ContentDigest,
    ) -> SourceArtifact | None:
        with self._lock:
            artifact_id = self._artifact_by_source_digest.get((source_id, digest.hexadecimal))
            return self._artifacts.get(artifact_id) if artifact_id is not None else None

    def claim_job(
        self,
        job_id: AcquisitionJobId,
        started_at: UtcTimestamp,
    ) -> ClaimedAcquisitionAttempt:
        """Transaction 1: claim one job attempt and create its started Import Batch."""
        with self._lock:
            job = self._require_job(job_id)
            if job.status is AcquisitionJobStatus.RUNNING or job.is_completed:
                raise ConcurrencyConflict("acquisition job is already running or complete")
            job.start(started_at)
            batch_hash = hashlib.sha256(
                f"{job_id}|attempt:{job.attempt_count}".encode("utf-8")
            ).hexdigest()
            batch = ImportBatch(
                import_batch_id=ImportBatchId(f"batch:{batch_hash}"),
                source_id=job.source_id,
                started_at=started_at,
            )
            self._jobs[job_id] = job
            self._batches[batch.import_batch_id] = batch
            self._outbox.extend(job.pull_domain_events())
            profile = self._profiles[job.source_id]
            return ClaimedAcquisitionAttempt(deepcopy(job), deepcopy(batch), profile)

    def complete_content(
        self,
        *,
        job_id: AcquisitionJobId,
        batch_id: ImportBatchId,
        digest: ContentDigest,
        response_metadata: ArtifactResponseMetadata,
        candidate_artifact: SourceArtifact | None,
        recorded_at: UtcTimestamp,
    ) -> AcquisitionExecution:
        """Transaction 2: enforce source+digest uniqueness and finalize all metadata."""
        with self._lock:
            job, batch = self._require_running_attempt(job_id, batch_id)
            existing_id = self._artifact_by_source_digest.get((job.source_id, digest.hexadecimal))
            processing_enqueued = False
            if existing_id is not None:
                artifact = self._artifacts[existing_id]
                batch.mark_duplicate(artifact.artifact_id, recorded_at)
                job.mark_duplicate(recorded_at)
                outcome = AcquisitionOutcome.DUPLICATE
            else:
                if candidate_artifact is None:
                    raise InvariantViolation("new content finalization requires an artifact candidate")
                if (
                    candidate_artifact.source_id != job.source_id
                    or candidate_artifact.import_batch_id != batch_id
                    or candidate_artifact.content_digest != digest
                ):
                    raise InvariantViolation("artifact candidate does not match acquisition attempt")
                artifact = candidate_artifact
                self._artifacts[artifact.artifact_id] = artifact
                self._artifact_by_source_digest[(job.source_id, digest.hexadecimal)] = artifact.artifact_id
                batch.register_artifact(artifact)
                batch.mark_acquired(recorded_at)
                job.mark_archived(recorded_at)
                self._processing_queue.append(batch_id)
                processing_enqueued = True
                outcome = AcquisitionOutcome.ARCHIVED
            profile = self._profiles[job.source_id].record_attempt(recorded_at, successful=True)
            self._profiles[job.source_id] = profile
            record = AcquisitionRecord(
                acquisition_job_id=job_id,
                source_id=job.source_id,
                import_batch_id=batch_id,
                outcome=outcome,
                recorded_at=recorded_at,
                attempt=job.attempt_count,
                artifact_id=artifact.artifact_id,
                content_digest=digest,
                response_metadata=response_metadata,
            )
            event_count = self._commit_attempt(job, batch, record)
            return AcquisitionExecution(
                record,
                deepcopy(batch),
                artifact,
                processing_enqueued,
                event_count,
            )

    def complete_reprocessing(
        self,
        *,
        job_id: AcquisitionJobId,
        batch_id: ImportBatchId,
        artifact_id: SourceArtifactId,
        recorded_at: UtcTimestamp,
    ) -> AcquisitionExecution:
        with self._lock:
            job, batch = self._require_running_attempt(job_id, batch_id)
            artifact = self._artifacts.get(artifact_id)
            if artifact is None or artifact.source_id != job.source_id:
                raise InvariantViolation("manual reprocessing artifact is unavailable")
            batch.prepare_reprocessing(artifact, recorded_at)
            job.mark_reprocessed(recorded_at)
            self._processing_queue.append(batch_id)
            record = AcquisitionRecord(
                acquisition_job_id=job_id,
                source_id=job.source_id,
                import_batch_id=batch_id,
                outcome=AcquisitionOutcome.REPROCESSED,
                recorded_at=recorded_at,
                attempt=job.attempt_count,
                artifact_id=artifact.artifact_id,
                content_digest=artifact.content_digest,
                response_metadata=artifact.response_metadata,
            )
            event_count = self._commit_attempt(job, batch, record)
            return AcquisitionExecution(record, deepcopy(batch), artifact, True, event_count)

    def complete_disabled(
        self,
        *,
        job_id: AcquisitionJobId,
        batch_id: ImportBatchId,
        recorded_at: UtcTimestamp,
    ) -> AcquisitionExecution:
        with self._lock:
            job, batch = self._require_running_attempt(job_id, batch_id)
            batch.skip("source is disabled", recorded_at)
            job.mark_disabled(recorded_at)
            record = AcquisitionRecord(
                acquisition_job_id=job_id,
                source_id=job.source_id,
                import_batch_id=batch_id,
                outcome=AcquisitionOutcome.DISABLED,
                recorded_at=recorded_at,
                attempt=job.attempt_count,
            )
            event_count = self._commit_attempt(job, batch, record)
            return AcquisitionExecution(record, deepcopy(batch), None, False, event_count)

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
    ) -> AcquisitionExecution:
        with self._lock:
            job, batch = self._require_running_attempt(job_id, batch_id)
            batch.fail(f"{category}: {message}", recorded_at)
            job.fail(category, message, recorded_at)
            profile = self._profiles[job.source_id]
            if profile.enabled:
                self._profiles[job.source_id] = profile.record_attempt(
                    recorded_at,
                    successful=False,
                )
            record = AcquisitionRecord(
                acquisition_job_id=job_id,
                source_id=job.source_id,
                import_batch_id=batch_id,
                outcome=AcquisitionOutcome.FAILED,
                recorded_at=recorded_at,
                attempt=job.attempt_count,
                failure_category=category,
                failure_message=message,
                response_metadata=response_metadata,
                content_digest=content_digest,
            )
            event_count = self._commit_attempt(job, batch, record)
            return AcquisitionExecution(record, deepcopy(batch), None, False, event_count)

    @property
    def outbox_events(self) -> tuple[DomainEvent, ...]:
        with self._lock:
            return tuple(self._outbox)

    @property
    def processing_batch_ids(self) -> tuple[ImportBatchId, ...]:
        with self._lock:
            return tuple(self._processing_queue)

    def claim_processing(
        self,
        batch_id: ImportBatchId,
        correlation_id: str,
    ) -> tuple[ImportBatch, SourceArtifact]:
        """Lease one acquired Batch without detaching its authoritative ownership."""
        if not correlation_id.strip():
            raise InvariantViolation("processing correlation identifier is required")
        with self._lock:
            if batch_id not in self._processing_queue:
                raise InvariantViolation("import batch is not queued for processing")
            existing = self._processing_claims.get(batch_id)
            if existing is not None and existing != correlation_id:
                raise ConcurrencyConflict("import batch is already claimed for processing")
            batch = self._batches[batch_id]
            if batch.status is not ImportBatchStatus.ACQUIRED:
                raise InvariantViolation("only an acquired import batch can be claimed")
            artifact_id = next(iter(batch.artifact_ids), None)
            artifact = self._artifacts.get(artifact_id) if artifact_id is not None else None
            if artifact is None:
                raise InvariantViolation("queued import batch has no authoritative artifact")
            self._processing_claims[batch_id] = correlation_id
            return deepcopy(batch), artifact

    def finish_processing(
        self,
        batch: ImportBatch,
        correlation_id: str,
    ) -> None:
        """Commit the parser-mutated Batch and atomically acknowledge its queue item."""
        with self._lock:
            self._require_processing_claim(batch.import_batch_id, correlation_id)
            if batch.status not in {
                ImportBatchStatus.COMPLETED,
                ImportBatchStatus.PARTIALLY_FAILED,
                ImportBatchStatus.FAILED,
            }:
                raise InvariantViolation("processing completion requires a terminal parsed batch")
            current = self._batches[batch.import_batch_id]
            if current.status is not ImportBatchStatus.ACQUIRED:
                raise ConcurrencyConflict("authoritative import batch changed while processing")
            events = batch.pull_domain_events()
            self._batches[batch.import_batch_id] = deepcopy(batch)
            self._processing_queue.remove(batch.import_batch_id)
            del self._processing_claims[batch.import_batch_id]
            self._outbox.extend(events)

    def fail_processing(
        self,
        batch_id: ImportBatchId,
        correlation_id: str,
        *,
        category: str,
        message: str,
        retryable: bool,
        occurred_at: UtcTimestamp,
    ) -> ImportBatch:
        """Record an unexpected parser/UoW failure and acknowledge the queue item."""
        with self._lock:
            self._require_processing_claim(batch_id, correlation_id)
            batch = deepcopy(self._batches[batch_id])
            batch.fail(message, occurred_at, category=category, retryable=retryable)
            events = batch.pull_domain_events()
            self._batches[batch_id] = deepcopy(batch)
            self._processing_queue.remove(batch_id)
            del self._processing_claims[batch_id]
            self._outbox.extend(events)
            return deepcopy(batch)

    def _require_processing_claim(self, batch_id: ImportBatchId, correlation_id: str) -> None:
        if self._processing_claims.get(batch_id) != correlation_id:
            raise ConcurrencyConflict("import batch processing claim is missing or belongs to another run")

    def _commit_attempt(
        self,
        job: AcquisitionJob,
        batch: ImportBatch,
        record: AcquisitionRecord,
    ) -> int:
        events = (*job.pull_domain_events(), *batch.pull_domain_events())
        self._jobs[job.acquisition_job_id] = job
        self._batches[batch.import_batch_id] = batch
        self._results.setdefault(job.acquisition_job_id, []).append(record)
        self._outbox.extend(events)
        return len(events)

    def _require_job(self, job_id: AcquisitionJobId) -> AcquisitionJob:
        job = self._jobs.get(job_id)
        if job is None:
            raise InvariantViolation("acquisition job is not registered")
        return job

    def _require_running_attempt(
        self,
        job_id: AcquisitionJobId,
        batch_id: ImportBatchId,
    ) -> tuple[AcquisitionJob, ImportBatch]:
        job = self._require_job(job_id)
        batch = self._batches.get(batch_id)
        if batch is None or batch.source_id != job.source_id:
            raise InvariantViolation("import batch does not match acquisition job")
        if job.status is not AcquisitionJobStatus.RUNNING:
            raise ConcurrencyConflict("acquisition job is no longer running")
        return job, batch


class InMemoryAcquisitionMetrics:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.counters: dict[tuple[str, MetricLabels], int] = {}
        self.observations: dict[tuple[str, MetricLabels], list[float]] = {}

    def increment(self, name: str, *, labels: MetricLabels = ()) -> None:
        key = (name, tuple(sorted(labels)))
        with self._lock:
            self.counters[key] = self.counters.get(key, 0) + 1

    def observe(self, name: str, value: float, *, labels: MetricLabels = ()) -> None:
        key = (name, tuple(sorted(labels)))
        with self._lock:
            self.observations.setdefault(key, []).append(value)


class InMemoryAcquisitionLogger:
    def __init__(self) -> None:
        self.entries: list[AcquisitionLogEntry] = []

    def record(self, entry: AcquisitionLogEntry) -> None:
        self.entries.append(entry)


class JsonLinesAcquisitionLogger:
    """Append-only structured acquisition log with no connector payloads or credentials."""

    def __init__(self, path: Path) -> None:
        self._path = path

    def record(self, entry: AcquisitionLogEntry) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with self._path.open("a", encoding="utf-8") as stream:
            json.dump(entry.as_dict(), stream, sort_keys=True, separators=(",", ":"))
            stream.write("\n")


class FileSystemImmutableArtifactStore:
    """Content-addressed, create-once raw artifact storage for local deployments/tests."""

    def __init__(self, root: Path) -> None:
        self._root = root.resolve()

    def put(
        self,
        *,
        source_id: SourceId,
        content: bytes,
        digest: ContentDigest,
        media_type: str,
    ) -> StoredArtifact:
        del media_type  # bytes are stored raw; media type remains on SourceArtifact metadata
        actual = hashlib.sha256(content).hexdigest()
        if actual != digest.hexadecimal:
            raise AcquisitionError(
                AcquisitionFailureCategory.ARTIFACT_STORAGE,
                "artifact checksum does not match supplied digest",
            )
        target_dir = self._root / str(source_id) / "sha256" / digest.hexadecimal[:2]
        target_dir.mkdir(parents=True, exist_ok=True)
        target = target_dir / f"{digest.hexadecimal}.raw"
        created = False
        file_descriptor, temporary_name = tempfile.mkstemp(prefix=".incoming-", dir=target_dir)
        temporary = Path(temporary_name)
        try:
            with os.fdopen(file_descriptor, "wb") as stream:
                stream.write(content)
                stream.flush()
                os.fsync(stream.fileno())
            temporary.chmod(0o444)
            try:
                os.link(temporary, target)
                created = True
            except FileExistsError:
                pass
        finally:
            temporary.unlink(missing_ok=True)
        existing_digest = hashlib.sha256(target.read_bytes()).hexdigest()
        if existing_digest != digest.hexadecimal:
            raise AcquisitionError(
                AcquisitionFailureCategory.ARTIFACT_STORAGE,
                "immutable artifact path contains different bytes",
            )
        return StoredArtifact(storage_reference=target.as_uri(), created=created)


class FakeConnector:
    """Deterministic raw connector for unit tests; it never performs I/O or parsing."""

    def __init__(
        self,
        *,
        method: AcquisitionMethod,
        outcomes: Iterable[RawAcquisition | AcquisitionError],
    ) -> None:
        self.method = method
        self._outcomes = tuple(outcomes)
        if not self._outcomes:
            raise ValueError("fake connector requires at least one deterministic outcome")
        self.calls: list[AcquisitionRequest] = []

    def acquire(self, request: AcquisitionRequest) -> RawAcquisition:
        self.calls.append(request)
        index = min(len(self.calls) - 1, len(self._outcomes) - 1)
        outcome = self._outcomes[index]
        if isinstance(outcome, AcquisitionError):
            raise outcome
        return outcome

    def download_file(self, request: AcquisitionRequest) -> RawAcquisition:
        return self.acquire(request)

    def request_api(self, request: AcquisitionRequest) -> RawAcquisition:
        return self.acquire(request)

    def fetch_page(self, request: AcquisitionRequest) -> RawAcquisition:
        return self.acquire(request)

    def read_uploaded_file(self, request: AcquisitionRequest) -> RawAcquisition:
        return self.acquire(request)


class ManualFixtureConnector:
    """Reads a caller-selected fixture under one approved directory, without parsing it."""

    method = AcquisitionMethod.MANUAL_UPLOAD

    def __init__(self, fixture_root: Path) -> None:
        self._fixture_root = fixture_root.resolve()

    def acquire(self, request: AcquisitionRequest) -> RawAcquisition:
        return self.read_uploaded_file(request)

    def read_uploaded_file(self, request: AcquisitionRequest) -> RawAcquisition:
        if request.uploaded_file is None:
            raise AcquisitionError(
                AcquisitionFailureCategory.MANUAL_INPUT,
                "manual acquisition requires an uploaded fixture path",
            )
        try:
            path = request.uploaded_file.resolve(strict=True)
        except OSError as exc:
            raise AcquisitionError(
                AcquisitionFailureCategory.MANUAL_INPUT,
                "uploaded fixture does not exist",
            ) from exc
        if not path.is_relative_to(self._fixture_root) or not path.is_file():
            raise AcquisitionError(
                AcquisitionFailureCategory.MANUAL_INPUT,
                "uploaded fixture is outside the approved fixture directory",
            )
        try:
            with path.open("rb") as stream:
                content = stream.read(request.policy.max_response_bytes + 1)
        except OSError as exc:
            raise AcquisitionError(
                AcquisitionFailureCategory.MANUAL_INPUT,
                "uploaded fixture could not be read",
            ) from exc
        if len(content) > request.policy.max_response_bytes:
            raise AcquisitionError(
                AcquisitionFailureCategory.RESPONSE_TOO_LARGE,
                "uploaded fixture exceeds configured byte limit",
            )
        return RawAcquisition(
            content=content,
            media_type=request.profile.file_type.media_type,
            source_reference=f"manual-upload:{path.name}",
            acquired_at=request.requested_at,
            metadata=(("filename", path.name),),
        )
