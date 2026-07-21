"""Correlated Artifact-to-Customer-Match orchestration for the modular monolith."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Protocol, TypeVar

from az_permit_radar.domain.acquisition import AcquisitionJob, AcquisitionRecord
from az_permit_radar.domain.classification import ClassificationReviewStatus
from az_permit_radar.domain.customer import CustomerAccount
from az_permit_radar.domain.eligibility import PublicationEligibilityError
from az_permit_radar.domain.errors import ConcurrencyConflict, InvariantViolation
from az_permit_radar.domain.ingestion import ImportBatch, ImportBatchStatus, SourceArtifact, SourceRecord
from az_permit_radar.domain.parsing import ImportReport, RecordDisposition
from az_permit_radar.domain.value_objects import (
    AcquisitionJobId,
    CalendarDate,
    ClassificationResultId,
    CustomerAccountId,
    ImportBatchId,
    OpportunityId,
    OpportunityMatchId,
    PermitId,
    ReviewTaskId,
    SourceArtifactId,
    SourceId,
    SourceRecordId,
    UtcTimestamp,
)


class ProcessingStageError(Exception):
    def __init__(self, stage: "ProcessingStage", category: str, message: str, retryable: bool) -> None:
        super().__init__(message)
        self.stage = stage
        self.category = category
        self.safe_message = message
        self.retryable = retryable


class AcquisitionState(Protocol):
    def get_job(self, job_id: AcquisitionJobId) -> AcquisitionJob | None: ...
    def get_result(self, job_id: AcquisitionJobId) -> AcquisitionRecord | None: ...
    def get(self, source_id: SourceId) -> Any | None: ...
    def get_batch(self, batch_id: ImportBatchId) -> ImportBatch | None: ...
    def claim_processing(self, batch_id: ImportBatchId, correlation_id: str) -> tuple[ImportBatch, SourceArtifact]: ...
    def finish_processing(self, batch: ImportBatch, correlation_id: str) -> None: ...
    def fail_processing(self, batch_id: ImportBatchId, correlation_id: str, *, category: str, message: str, retryable: bool, occurred_at: UtcTimestamp) -> ImportBatch: ...


class AcquisitionWorkflow(Protocol):
    def run_job(self, *, job_id: AcquisitionJobId, policy: object, connector: object | None = None, uploaded_file: Path | None = None) -> Any: ...


class ParserPipeline(Protocol):
    def parse(self, *, profile: Any, artifact: SourceArtifact, batch: ImportBatch) -> ImportReport: ...


class NormalizationWorkflow(Protocol):
    def normalize(self, source_record: SourceRecord) -> Any: ...


class ClassificationWorkflow(Protocol):
    def classify(self, signals: Any, occurred_at: UtcTimestamp) -> Any: ...


class OpportunityWorkflow(Protocol):
    def generate(self, permit: Any, occurred_at: UtcTimestamp) -> Any: ...


class MatchWorkflow(Protocol):
    def generate(self, *, opportunity: Any, permits: tuple[Any, ...], customer: CustomerAccount, evaluated_on: CalendarDate, occurred_at: UtcTimestamp) -> Any: ...


class ProcessingStage(str, Enum):
    ACQUISITION = "acquisition"
    STORAGE = "storage"
    PARSING = "parsing"
    NORMALIZATION = "normalization"
    GEOCODING = "geocoding"
    CLASSIFICATION = "classification"
    REVIEW_REQUIREMENT = "review_requirement"
    OPPORTUNITY_PROJECTION = "opportunity_projection"
    MATCHING = "matching"
    COMPLETE = "complete"


class ProcessingOutcome(str, Enum):
    MATCH_CREATED = "match_created"
    EXCLUDED = "excluded"
    REVIEW_REQUIRED = "review_required"
    FAILED = "failed"


class ProcessingRunStatus(str, Enum):
    COMPLETED = "completed"
    PARTIALLY_FAILED = "partially_failed"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class ProcessingConsistencyPolicy:
    version: str
    batch_owner: str
    normalization_atomicity: str
    retryable_batch_failure_action: str
    uniqueness_scopes: tuple[str, ...]
    failure_categories: tuple[str, ...]

    def __post_init__(self) -> None:
        required_failures = {
            "acquisition", "storage", "parsing", "normalization", "geocoding",
            "classification", "review_requirement", "opportunity_projection", "matching",
        }
        if not self.version.strip() or self.batch_owner != "acquisition_state":
            raise InvariantViolation("processing policy requires versioned acquisition-state Batch ownership")
        if self.normalization_atomicity != "process_local_shared_lock_snapshot_rollback":
            raise InvariantViolation("processing policy requires the implemented in-memory normalization boundary")
        if self.retryable_batch_failure_action != "explicit_reprocessing_new_batch":
            raise InvariantViolation("retryable Batch failures require explicit reprocessing")
        if len(set(self.uniqueness_scopes)) != len(self.uniqueness_scopes) or not self.uniqueness_scopes:
            raise InvariantViolation("processing policy uniqueness scopes must be non-empty and unique")
        if set(self.failure_categories) != required_failures:
            raise InvariantViolation("processing policy must define every end-to-end failure category")


@dataclass(frozen=True, slots=True)
class ProcessingClassificationSignals:
    permit: Any
    occupancy: str | None = None
    project: str | None = None
    source_categories: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ProcessingTraceEntry:
    correlation_id: str
    stage: ProcessingStage
    outcome: str
    source_id: SourceId | None = None
    artifact_id: SourceArtifactId | None = None
    artifact_hash: str | None = None
    import_batch_id: ImportBatchId | None = None
    source_record_id: SourceRecordId | None = None
    permit_id: PermitId | None = None
    classification_result_id: ClassificationResultId | None = None
    opportunity_id: OpportunityId | None = None
    match_id: OpportunityMatchId | None = None
    customer_account_id: CustomerAccountId | None = None
    review_task_id: ReviewTaskId | None = None
    failure_category: str | None = None
    retry_disposition: str | None = None
    message: str | None = None

    def __post_init__(self) -> None:
        if not self.correlation_id.strip() or not self.outcome.strip():
            raise InvariantViolation("processing trace correlation and outcome are required")
        if self.message is not None and not self.message.strip():
            raise InvariantViolation("processing trace messages cannot be blank")


class ProcessingTraceLogger(Protocol):
    def record(self, entry: ProcessingTraceEntry) -> None: ...


@dataclass(frozen=True, slots=True)
class RecordProcessingTrace:
    source_record_id: SourceRecordId | None
    outcome: ProcessingOutcome
    final_stage: ProcessingStage
    reason: str
    permit_id: PermitId | None = None
    classification_result_id: ClassificationResultId | None = None
    opportunity_id: OpportunityId | None = None
    match_ids: tuple[OpportunityMatchId, ...] = ()
    review_task_ids: tuple[ReviewTaskId, ...] = ()
    exclusion_reasons: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ProcessingRunResult:
    correlation_id: str
    status: ProcessingRunStatus
    source_id: SourceId
    import_batch_id: ImportBatchId
    artifact_id: SourceArtifactId | None
    artifact_hash: str | None
    records: tuple[RecordProcessingTrace, ...]
    failure_stage: ProcessingStage | None = None
    failure_category: str | None = None
    retry_disposition: str | None = None


class TransactionalSourceRecordStore(Protocol):
    def get(self, source_record_id: SourceRecordId) -> SourceRecord | None: ...

    def find_by_external_id(
        self,
        source_id: SourceId,
        external_record_id: str,
    ) -> SourceRecord | None: ...

    def snapshot(self) -> object: ...

    def restore(self, snapshot: object) -> None: ...


class AuthoritativeBatchParser:
    """Coordinates parser writes with the authoritative Batch and queue owner."""

    def __init__(
        self,
        state: AcquisitionState,
        source_records: TransactionalSourceRecordStore,
        *,
        now: Callable[[], UtcTimestamp] = UtcTimestamp.now,
    ) -> None:
        self._state = state
        self._source_records = source_records
        self._now = now

    def parse(
        self,
        *,
        batch_id: ImportBatchId,
        correlation_id: str,
        profile,
        pipeline: ParserPipeline,
    ) -> tuple[ImportReport, SourceArtifact]:
        batch, artifact = self._state.claim_processing(batch_id, correlation_id)
        snapshot = self._source_records.snapshot()
        try:
            report = pipeline.parse(profile=profile, artifact=artifact, batch=batch)
            self._state.finish_processing(batch, correlation_id)
            return report, artifact
        except Exception as error:
            self._source_records.restore(snapshot)
            if batch.status is ImportBatchStatus.FAILED:
                self._state.finish_processing(batch, correlation_id)
                category = batch.failure_category or "parsing"
                retryable = batch.retry_disposition is not None and batch.retry_disposition.value == "retryable"
                message = batch.failure_reason or "parser rejected the artifact"
            else:
                category = str(getattr(getattr(error, "category", None), "value", "parsing_unexpected"))
                retryable = bool(getattr(error, "retryable", True))
                message = str(getattr(error, "safe_message", "unexpected parser transaction failure"))
                self._state.fail_processing(
                    batch_id,
                    correlation_id,
                    category=category,
                    message=message,
                    retryable=retryable,
                    occurred_at=self._now(),
                )
            raise ProcessingStageError(
                ProcessingStage.PARSING,
                category,
                message,
                retryable,
            ) from error


RunResultT = TypeVar("RunResultT")


class ProcessingRunStore(Protocol):
    def run_once(
        self,
        correlation_id: str,
        operation: Callable[[], RunResultT],
    ) -> RunResultT: ...


class EndToEndPermitProcessingWorkflow:
    """One synchronous, replay-safe vertical path; production worker behavior is deferred."""

    def __init__(
        self,
        *,
        acquisition: AcquisitionWorkflow,
        acquisition_state: AcquisitionState,
        parser: AuthoritativeBatchParser,
        parser_pipeline: ParserPipeline,
        source_records: TransactionalSourceRecordStore,
        normalization: NormalizationWorkflow,
        classification: ClassificationWorkflow,
        opportunities: OpportunityWorkflow,
        matches: MatchWorkflow,
        policy: ProcessingConsistencyPolicy,
        run_store: ProcessingRunStore,
        logger: ProcessingTraceLogger,
        now: Callable[[], UtcTimestamp] = UtcTimestamp.now,
    ) -> None:
        self._acquisition = acquisition
        self._state = acquisition_state
        self._parser = parser
        self._parser_pipeline = parser_pipeline
        self._source_records = source_records
        self._normalization = normalization
        self._classification = classification
        self._opportunities = opportunities
        self._matches = matches
        self.policy = policy
        self._run_store = run_store
        self._logger = logger
        self._now = now

    def run(
        self,
        *,
        correlation_id: str,
        acquisition_job_id: AcquisitionJobId,
        policy: object,
        customers: tuple[CustomerAccount, ...],
        evaluated_on: CalendarDate,
        connector: object | None = None,
        uploaded_file: Path | None = None,
    ) -> ProcessingRunResult:
        if not correlation_id.strip():
            raise InvariantViolation("end-to-end correlation identifier is required")
        return self._run_store.run_once(
            correlation_id,
            lambda: self._run(
                correlation_id=correlation_id,
                acquisition_job_id=acquisition_job_id,
                policy=policy,
                customers=customers,
                evaluated_on=evaluated_on,
                connector=connector,
                uploaded_file=uploaded_file,
            ),
        )

    def _run(
        self,
        *,
        correlation_id: str,
        acquisition_job_id: AcquisitionJobId,
        policy: object,
        customers: tuple[CustomerAccount, ...],
        evaluated_on: CalendarDate,
        connector: object | None,
        uploaded_file: Path | None,
    ) -> ProcessingRunResult:
        job = self._state.get_job(acquisition_job_id)
        if job is None:
            raise InvariantViolation("end-to-end acquisition job is not registered")
        try:
            acquired = self._acquisition.run_job(
                job_id=acquisition_job_id,
                policy=policy,
                connector=connector,
                uploaded_file=uploaded_file,
            )
        except Exception as error:
            category = str(getattr(getattr(error, "category", None), "value", "acquisition_unexpected"))
            stage = (
                ProcessingStage.STORAGE
                if category == "artifact_storage"
                else ProcessingStage.ACQUISITION
            )
            retry = "retryable" if bool(getattr(error, "retryable", False)) else "terminal"
            acquisition_record = self._state.get_result(acquisition_job_id)
            failed_batch_id = (
                acquisition_record.import_batch_id
                if acquisition_record is not None
                else self._failed_batch_id(acquisition_job_id)
            )
            result = self._failed_run(
                correlation_id,
                job.source_id,
                failed_batch_id,
                stage,
                category,
                retry,
            )
            self._logger.record(
                ProcessingTraceEntry(
                    correlation_id, stage, "failed", source_id=job.source_id,
                    import_batch_id=result.import_batch_id,
                    failure_category=category,
                    retry_disposition=retry,
                    message=str(getattr(error, "safe_message", "acquisition failed explicitly")),
                )
            )
            return result

        artifact = acquired.artifact
        self._logger.record(
            ProcessingTraceEntry(
                correlation_id,
                ProcessingStage.ACQUISITION,
                acquired.record.outcome.value,
                source_id=acquired.record.source_id,
                artifact_id=artifact.artifact_id if artifact else None,
                artifact_hash=artifact.content_digest.hexadecimal if artifact else None,
                import_batch_id=acquired.record.import_batch_id,
            )
        )
        if artifact is None or not acquired.processing_enqueued:
            return ProcessingRunResult(
                correlation_id,
                ProcessingRunStatus.COMPLETED,
                acquired.record.source_id,
                acquired.record.import_batch_id,
                artifact.artifact_id if artifact else None,
                artifact.content_digest.hexadecimal if artifact else None,
                (),
            )

        profile = self._state.get(acquired.record.source_id)
        if profile is None:
            raise InvariantViolation("acquired source profile disappeared before parsing")
        try:
            report, artifact = self._parser.parse(
                batch_id=acquired.record.import_batch_id,
                correlation_id=correlation_id,
                profile=profile,
                pipeline=self._parser_pipeline,
            )
        except ProcessingStageError as error:
            batch = self._state.get_batch(acquired.record.import_batch_id)
            retry = (
                batch.retry_disposition.value
                if batch is not None and batch.retry_disposition is not None
                else "terminal"
            )
            self._logger.record(
                ProcessingTraceEntry(
                    correlation_id,
                    ProcessingStage.PARSING,
                    "failed",
                    source_id=profile.source_id,
                    artifact_id=artifact.artifact_id,
                    artifact_hash=artifact.content_digest.hexadecimal,
                    import_batch_id=acquired.record.import_batch_id,
                    failure_category=error.category,
                    retry_disposition=retry,
                    message=error.safe_message,
                )
            )
            return self._failed_run(
                correlation_id,
                profile.source_id,
                acquired.record.import_batch_id,
                ProcessingStage.PARSING,
                error.category,
                retry,
                artifact,
            )

        self._logger.record(
            ProcessingTraceEntry(
                correlation_id,
                ProcessingStage.PARSING,
                "partially_failed" if report.rejected_count else "completed",
                source_id=profile.source_id,
                artifact_id=artifact.artifact_id,
                artifact_hash=artifact.content_digest.hexadecimal,
                import_batch_id=report.import_batch_id,
                message=f"accepted={report.accepted_count}; warned={report.warned_count}; rejected={report.rejected_count}",
            )
        )

        record_results: list[RecordProcessingTrace] = []
        for row in report.rows:
            if row.disposition is RecordDisposition.REJECTED:
                record_results.append(
                    RecordProcessingTrace(
                        row.source_record_id,
                        ProcessingOutcome.FAILED,
                        ProcessingStage.PARSING,
                        "source row rejected by the governed parser",
                        exclusion_reasons=("malformed_source_row",),
                    )
                )
                continue
            if row.disposition is RecordDisposition.DUPLICATE:
                record_results.append(
                    RecordProcessingTrace(
                        None,
                        ProcessingOutcome.EXCLUDED,
                        ProcessingStage.PARSING,
                        "duplicate source row within the artifact",
                        exclusion_reasons=("duplicate_source_row",),
                    )
                )
                continue
            source_record = (
                self._source_records.get(row.source_record_id)
                if row.source_record_id is not None
                else self._source_records.find_by_external_id(profile.source_id, row.external_record_key)
                if row.external_record_key is not None
                else None
            )
            if source_record is None:
                record_results.append(
                    RecordProcessingTrace(
                        row.source_record_id,
                        ProcessingOutcome.FAILED,
                        ProcessingStage.PARSING,
                        "parsed Source Record is unavailable",
                    )
                )
                continue
            record_results.append(
                self._process_record(
                    correlation_id,
                    artifact,
                    report.import_batch_id,
                    source_record,
                    customers,
                    evaluated_on,
                )
            )

        failed = sum(item.outcome is ProcessingOutcome.FAILED for item in record_results)
        status = (
            ProcessingRunStatus.PARTIALLY_FAILED
            if failed and failed < len(record_results)
            else ProcessingRunStatus.FAILED
            if failed
            else ProcessingRunStatus.COMPLETED
        )
        self._logger.record(
            ProcessingTraceEntry(
                correlation_id,
                ProcessingStage.COMPLETE,
                status.value,
                source_id=profile.source_id,
                artifact_id=artifact.artifact_id,
                artifact_hash=artifact.content_digest.hexadecimal,
                import_batch_id=report.import_batch_id,
            )
        )
        return ProcessingRunResult(
            correlation_id,
            status,
            profile.source_id,
            report.import_batch_id,
            artifact.artifact_id,
            artifact.content_digest.hexadecimal,
            tuple(record_results),
        )

    def _process_record(
        self,
        correlation_id: str,
        artifact: SourceArtifact,
        batch_id: ImportBatchId,
        source_record: SourceRecord,
        customers: tuple[CustomerAccount, ...],
        evaluated_on: CalendarDate,
    ) -> RecordProcessingTrace:
        common = dict(
            source_id=source_record.source_id,
            artifact_id=artifact.artifact_id,
            artifact_hash=artifact.content_digest.hexadecimal,
            import_batch_id=batch_id,
            source_record_id=source_record.source_record_id,
        )
        try:
            normalized = self._normalization.normalize(source_record)
        except Exception:
            self._logger.record(
                ProcessingTraceEntry(
                    correlation_id,
                    ProcessingStage.NORMALIZATION,
                    "failed",
                    failure_category="normalization_persistence",
                    retry_disposition="retryable",
                    message="normalization transaction rolled back",
                    **common,
                )
            )
            return RecordProcessingTrace(
                source_record.source_record_id,
                ProcessingOutcome.FAILED,
                ProcessingStage.NORMALIZATION,
                "normalization transaction failed and rolled back",
            )
        permit = normalized.permit
        self._logger.record(
            ProcessingTraceEntry(
                correlation_id,
                ProcessingStage.NORMALIZATION,
                normalized.outcome.value,
                permit_id=permit.permit_id,
                **common,
            )
        )
        if normalized.review_tasks:
            review_ids = tuple(task.review_task_id for task in normalized.review_tasks)
            stage = (
                ProcessingStage.GEOCODING
                if any(task.subject_type.value == "address" for task in normalized.review_tasks)
                else ProcessingStage.REVIEW_REQUIREMENT
            )
            for task in normalized.review_tasks:
                self._logger.record(
                    ProcessingTraceEntry(
                        correlation_id,
                        stage,
                        "review_required",
                        permit_id=permit.permit_id,
                        review_task_id=task.review_task_id,
                        message=task.reason,
                        **common,
                    )
                )
            return RecordProcessingTrace(
                source_record.source_record_id,
                ProcessingOutcome.REVIEW_REQUIRED,
                stage,
                "normalization requires human review",
                permit_id=permit.permit_id,
                review_task_ids=review_ids,
            )
        try:
            classified = self._classification.classify(ProcessingClassificationSignals(permit), self._now())
        except Exception:
            self._logger.record(
                ProcessingTraceEntry(
                    correlation_id,
                    ProcessingStage.CLASSIFICATION,
                    "failed",
                    permit_id=permit.permit_id,
                    failure_category="classification",
                    retry_disposition="terminal",
                    message="classification failed explicitly",
                    **common,
                )
            )
            return RecordProcessingTrace(
                source_record.source_record_id,
                ProcessingOutcome.FAILED,
                ProcessingStage.CLASSIFICATION,
                "classification failed",
                permit_id=permit.permit_id,
            )
        result = classified.classification_result
        self._logger.record(
            ProcessingTraceEntry(
                correlation_id,
                ProcessingStage.CLASSIFICATION,
                result.review_status.value,
                permit_id=permit.permit_id,
                classification_result_id=result.classification_result_id,
                **common,
            )
        )
        if result.review_status is not ClassificationReviewStatus.ACCEPTED:
            review_ids = tuple(task.review_task_id for task in classified.review_tasks)
            for task in classified.review_tasks:
                self._logger.record(
                    ProcessingTraceEntry(
                        correlation_id,
                        ProcessingStage.REVIEW_REQUIREMENT,
                        "review_required",
                        permit_id=permit.permit_id,
                        classification_result_id=result.classification_result_id,
                        review_task_id=task.review_task_id,
                        message=task.reason,
                        **common,
                    )
                )
            return RecordProcessingTrace(
                source_record.source_record_id,
                ProcessingOutcome.REVIEW_REQUIRED,
                ProcessingStage.REVIEW_REQUIREMENT,
                "classification confidence requires human review",
                permit_id=permit.permit_id,
                classification_result_id=result.classification_result_id,
                review_task_ids=review_ids,
            )
        try:
            opportunity = self._opportunities.generate(permit, self._now())
        except PublicationEligibilityError as error:
            self._logger.record(
                ProcessingTraceEntry(
                    correlation_id,
                    ProcessingStage.OPPORTUNITY_PROJECTION,
                    "excluded",
                    permit_id=permit.permit_id,
                    classification_result_id=result.classification_result_id,
                    failure_category="publication_eligibility",
                    retry_disposition="terminal",
                    message=f"excluded: {', '.join(error.decision.reasons)}",
                    **common,
                )
            )
            return RecordProcessingTrace(
                source_record.source_record_id,
                ProcessingOutcome.EXCLUDED,
                ProcessingStage.OPPORTUNITY_PROJECTION,
                "Opportunity publication eligibility failed",
                permit_id=permit.permit_id,
                classification_result_id=result.classification_result_id,
                exclusion_reasons=error.decision.reasons,
            )
        except Exception:
            self._logger.record(
                ProcessingTraceEntry(
                    correlation_id,
                    ProcessingStage.OPPORTUNITY_PROJECTION,
                    "failed",
                    permit_id=permit.permit_id,
                    classification_result_id=result.classification_result_id,
                    failure_category="opportunity_projection",
                    retry_disposition="retryable",
                    message="Opportunity projection failed",
                    **common,
                )
            )
            return RecordProcessingTrace(
                source_record.source_record_id,
                ProcessingOutcome.FAILED,
                ProcessingStage.OPPORTUNITY_PROJECTION,
                "Opportunity projection failed",
                permit_id=permit.permit_id,
                classification_result_id=result.classification_result_id,
            )
        self._logger.record(
            ProcessingTraceEntry(
                correlation_id,
                ProcessingStage.OPPORTUNITY_PROJECTION,
                "published",
                permit_id=permit.permit_id,
                classification_result_id=result.classification_result_id,
                opportunity_id=opportunity.opportunity_id,
                **common,
            )
        )

        match_ids: list[OpportunityMatchId] = []
        exclusions: list[str] = []
        for customer in customers:
            try:
                generated = self._matches.generate(
                    opportunity=opportunity,
                    permits=(permit,),
                    customer=customer,
                    evaluated_on=evaluated_on,
                    occurred_at=self._now(),
                )
            except Exception:
                self._logger.record(
                    ProcessingTraceEntry(
                        correlation_id,
                        ProcessingStage.MATCHING,
                        "failed",
                        permit_id=permit.permit_id,
                        classification_result_id=result.classification_result_id,
                        opportunity_id=opportunity.opportunity_id,
                        customer_account_id=customer.customer_account_id,
                        failure_category="matching",
                        retry_disposition="retryable",
                        message="customer Match generation failed",
                        **common,
                    )
                )
                return RecordProcessingTrace(
                    source_record.source_record_id,
                    ProcessingOutcome.FAILED,
                    ProcessingStage.MATCHING,
                    "customer Match generation failed",
                    permit_id=permit.permit_id,
                    classification_result_id=result.classification_result_id,
                    opportunity_id=opportunity.opportunity_id,
                )
            if generated.match is not None:
                match_ids.append(generated.match.opportunity_match_id)
            exclusions.extend(generated.exclusion_rules)
            self._logger.record(
                ProcessingTraceEntry(
                    correlation_id,
                    ProcessingStage.MATCHING,
                    "matched" if generated.match is not None else "excluded",
                    permit_id=permit.permit_id,
                    classification_result_id=result.classification_result_id,
                    opportunity_id=opportunity.opportunity_id,
                    match_id=(generated.match.opportunity_match_id if generated.match else None),
                    customer_account_id=customer.customer_account_id,
                    message=generated.human_readable,
                    **common,
                )
            )
        return RecordProcessingTrace(
            source_record.source_record_id,
            ProcessingOutcome.MATCH_CREATED if match_ids else ProcessingOutcome.EXCLUDED,
            ProcessingStage.MATCHING,
            "customer Match evaluation completed",
            permit_id=permit.permit_id,
            classification_result_id=result.classification_result_id,
            opportunity_id=opportunity.opportunity_id,
            match_ids=tuple(match_ids),
            exclusion_reasons=tuple(dict.fromkeys(exclusions)),
        )

    @staticmethod
    def _failed_batch_id(job_id: AcquisitionJobId) -> ImportBatchId:
        return ImportBatchId(f"batch-unavailable:{job_id}")

    @staticmethod
    def _failed_run(
        correlation_id: str,
        source_id: SourceId,
        batch_id: ImportBatchId,
        stage: ProcessingStage,
        category: str,
        retry: str,
        artifact: SourceArtifact | None = None,
    ) -> ProcessingRunResult:
        return ProcessingRunResult(
            correlation_id,
            ProcessingRunStatus.FAILED,
            source_id,
            batch_id,
            artifact.artifact_id if artifact else None,
            artifact.content_digest.hexadecimal if artifact else None,
            (),
            failure_stage=stage,
            failure_category=category,
            retry_disposition=retry,
        )
