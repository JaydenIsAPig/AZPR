"""Deterministic raw-artifact parsing contracts and orchestration."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from enum import Enum
from typing import Callable, Protocol

from az_permit_radar.domain.errors import InvariantViolation
from az_permit_radar.domain.ingestion import ImportBatch, ImportBatchStatus, SourceArtifact, SourceRecord
from az_permit_radar.domain.parsing import (
    ImportReport,
    IssueSeverity,
    ParseIssue,
    ParsedValue,
    RecordDisposition,
    RowParseResult,
    ValueValidationResult,
)
from az_permit_radar.domain.source_registry import SourceProfile
from az_permit_radar.domain.value_objects import (
    CalendarDate,
    ContentDigest,
    Money,
    SourceId,
    SourceRecordId,
    UtcTimestamp,
)


class ArtifactUnusableCategory(str, Enum):
    CONFIGURATION = "configuration"
    ARTIFACT_READ = "artifact_read"
    CHECKSUM = "checksum"
    DECODING = "decoding"
    FORMAT = "format"


class ArtifactUnusable(Exception):
    """A safe batch-level failure indicating that rows cannot be extracted reliably."""

    def __init__(self, category: ArtifactUnusableCategory, safe_message: str) -> None:
        super().__init__(safe_message)
        self.category = category
        self.safe_message = safe_message


@dataclass(frozen=True, slots=True)
class DecodedArtifact:
    text: str
    encoding: str


@dataclass(frozen=True, slots=True)
class ValidatedFormat:
    decoded: DecodedArtifact
    headers: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class RawEntry:
    row_number: int
    values: tuple[tuple[str, str], ...]
    raw_payload: str


@dataclass(frozen=True, slots=True)
class MalformedEntry:
    row_number: int
    raw_payload: str
    issues: tuple[ParseIssue, ...]


ExtractedEntry = RawEntry | MalformedEntry


@dataclass(frozen=True, slots=True)
class ExtractionResult:
    entries: tuple[ExtractedEntry, ...]


@dataclass(frozen=True, slots=True)
class MappedField:
    canonical_field: str
    source_field: str
    raw_value: str
    value_kind: str
    required: bool
    issues: tuple[ParseIssue, ...] = ()


@dataclass(frozen=True, slots=True)
class MappedEntry:
    row_number: int
    fields: tuple[MappedField, ...]
    raw_payload: str
    issues: tuple[ParseIssue, ...] = ()


class ImmutableArtifactReader(Protocol):
    def read(self, artifact: SourceArtifact) -> bytes: ...


class FileDecoder(Protocol):
    def decode(self, content: bytes, media_type: str) -> DecodedArtifact: ...


class FormatValidator(Protocol):
    def validate(self, decoded: DecodedArtifact, profile: SourceProfile) -> ValidatedFormat: ...


class EntryExtractor(Protocol):
    def extract(self, validated: ValidatedFormat) -> ExtractionResult: ...


class SourceFieldMapper(Protocol):
    def map(self, entry: RawEntry) -> MappedEntry: ...


class ValueNormalizer(Protocol):
    def normalize(self, entry: MappedEntry, parser_version: str) -> tuple[ParsedValue, ...]: ...


class RecordValidator(Protocol):
    def validate(self, values: tuple[ParsedValue, ...]) -> tuple[ParseIssue, ...]: ...


class StableExternalRecordKey(Protocol):
    def create(self, profile: SourceProfile, values: tuple[ParsedValue, ...]) -> str | None: ...


class RejectionReporter(Protocol):
    def report(self, result: RowParseResult) -> None: ...


class SourceRecordStore(Protocol):
    def get(self, source_record_id: SourceRecordId) -> SourceRecord | None: ...

    def find_by_external_id(
        self,
        source_id: SourceId,
        external_record_id: str,
    ) -> SourceRecord | None: ...

    def save(self, source_record: SourceRecord) -> None: ...


@dataclass(frozen=True, slots=True)
class ParsingLogEntry:
    event: str
    source_id: str
    import_batch_id: str
    artifact_id: str
    parser_identifier: str
    parser_version: str
    outcome: str
    total_entries: int = 0
    accepted_count: int = 0
    warned_count: int = 0
    rejected_count: int = 0
    duplicate_count: int = 0
    unchanged_count: int = 0
    failure_category: str | None = None
    message: str | None = None

    def as_dict(self) -> dict[str, object]:
        return {
            "event": self.event,
            "source_id": self.source_id,
            "import_batch_id": self.import_batch_id,
            "artifact_id": self.artifact_id,
            "parser_identifier": self.parser_identifier,
            "parser_version": self.parser_version,
            "outcome": self.outcome,
            "total_entries": self.total_entries,
            "accepted_count": self.accepted_count,
            "warned_count": self.warned_count,
            "rejected_count": self.rejected_count,
            "duplicate_count": self.duplicate_count,
            "unchanged_count": self.unchanged_count,
            "failure_category": self.failure_category,
            "message": self.message,
        }


class ParsingLogger(Protocol):
    def record(self, entry: ParsingLogEntry) -> None: ...


class ParsingMetrics(Protocol):
    def increment(self, name: str, *, labels: tuple[tuple[str, str], ...] = ()) -> None: ...


@dataclass(frozen=True, slots=True)
class ParserDefinition:
    parser_identifier: str
    parser_version: str
    decoder: FileDecoder
    format_validator: FormatValidator
    extractor: EntryExtractor
    mapper: SourceFieldMapper
    normalizer: ValueNormalizer
    validator: RecordValidator
    key_strategy: StableExternalRecordKey

    def __post_init__(self) -> None:
        if not self.parser_identifier.strip() or not self.parser_version.strip():
            raise ValueError("parser identifier and version are required")


class SourceParserPipeline:
    """Runs explicit parser stages and creates provenance-rich Source Records."""

    def __init__(
        self,
        *,
        definition: ParserDefinition,
        artifact_reader: ImmutableArtifactReader,
        source_records: SourceRecordStore,
        rejection_reporter: RejectionReporter,
        logger: ParsingLogger,
        metrics: ParsingMetrics,
        now: Callable[[], UtcTimestamp] = UtcTimestamp.now,
    ) -> None:
        self._definition = definition
        self._artifact_reader = artifact_reader
        self._source_records = source_records
        self._rejection_reporter = rejection_reporter
        self._logger = logger
        self._metrics = metrics
        self._now = now

    def parse(
        self,
        *,
        profile: SourceProfile,
        artifact: SourceArtifact,
        batch: ImportBatch,
    ) -> ImportReport:
        self._validate_context(profile, artifact, batch)
        batch.start_processing(self._now())
        try:
            content = self._read_verified(artifact)
            decoded = self._definition.decoder.decode(content, artifact.media_type)
            validated = self._definition.format_validator.validate(decoded, profile)
            extraction = self._definition.extractor.extract(validated)
        except ArtifactUnusable as error:
            self._fail_batch(profile, artifact, batch, error)
            raise
        except OSError as error:
            unusable = ArtifactUnusable(
                ArtifactUnusableCategory.ARTIFACT_READ,
                "archived artifact could not be read",
            )
            self._fail_batch(profile, artifact, batch, unusable)
            raise unusable from error

        rows: list[RowParseResult] = []
        seen_keys: set[str] = set()
        for entry in extraction.entries:
            if isinstance(entry, MalformedEntry):
                result = self._reject_malformed(profile, artifact, batch, entry)
            else:
                result = self._parse_entry(profile, artifact, batch, entry, seen_keys)
            rows.append(result)
            if (
                result.external_record_key is not None
                and result.disposition is not RecordDisposition.REJECTED
            ):
                seen_keys.add(result.external_record_key)

        counts = {disposition: 0 for disposition in RecordDisposition}
        for row in rows:
            counts[row.disposition] += 1
            self._metrics.increment(
                "parser_rows_total",
                labels=(
                    ("source_id", str(profile.source_id)),
                    ("disposition", row.disposition.value),
                ),
            )
        batch.complete(
            counts[RecordDisposition.ACCEPTED] + counts[RecordDisposition.WARNED],
            counts[RecordDisposition.REJECTED],
            self._now(),
        )
        report = ImportReport(
            import_batch_id=batch.import_batch_id,
            artifact_id=artifact.artifact_id,
            parser_identifier=self._definition.parser_identifier,
            parser_version=self._definition.parser_version,
            total_entries=len(rows),
            accepted_count=counts[RecordDisposition.ACCEPTED],
            warned_count=counts[RecordDisposition.WARNED],
            rejected_count=counts[RecordDisposition.REJECTED],
            duplicate_count=counts[RecordDisposition.DUPLICATE],
            unchanged_count=counts[RecordDisposition.UNCHANGED],
            rows=tuple(rows),
        )
        self._metrics.increment(
            "parser_batches_total",
            labels=(("source_id", str(profile.source_id)), ("outcome", batch.status.value)),
        )
        self._logger.record(
            ParsingLogEntry(
                event="import_batch_parsed",
                source_id=str(profile.source_id),
                import_batch_id=str(batch.import_batch_id),
                artifact_id=str(artifact.artifact_id),
                parser_identifier=self._definition.parser_identifier,
                parser_version=self._definition.parser_version,
                outcome=batch.status.value,
                total_entries=report.total_entries,
                accepted_count=report.accepted_count,
                warned_count=report.warned_count,
                rejected_count=report.rejected_count,
                duplicate_count=report.duplicate_count,
                unchanged_count=report.unchanged_count,
            )
        )
        return report

    def _validate_context(
        self,
        profile: SourceProfile,
        artifact: SourceArtifact,
        batch: ImportBatch,
    ) -> None:
        if batch.status is not ImportBatchStatus.ACQUIRED:
            raise InvariantViolation("parsing requires an acquired import batch")
        if profile.source_id != artifact.source_id or batch.source_id != artifact.source_id:
            raise InvariantViolation("parser source provenance does not match")
        if artifact.artifact_id not in batch.artifact_ids:
            raise InvariantViolation("parser artifact is not registered to the import batch")
        if (
            profile.parser_identifier != self._definition.parser_identifier
            or profile.parser_version != self._definition.parser_version
        ):
            error = ArtifactUnusable(
                ArtifactUnusableCategory.CONFIGURATION,
                "source profile parser identity does not match the selected parser",
            )
            batch.start_processing(self._now())
            self._fail_batch(profile, artifact, batch, error)
            raise error

    def _read_verified(self, artifact: SourceArtifact) -> bytes:
        content = self._artifact_reader.read(artifact)
        actual = hashlib.sha256(content).hexdigest()
        if actual != artifact.content_digest.hexadecimal:
            raise ArtifactUnusable(
                ArtifactUnusableCategory.CHECKSUM,
                "archived artifact checksum verification failed",
            )
        return content

    def _parse_entry(
        self,
        profile: SourceProfile,
        artifact: SourceArtifact,
        batch: ImportBatch,
        entry: RawEntry,
        seen_keys: set[str],
    ) -> RowParseResult:
        mapped = self._definition.mapper.map(entry)
        values = self._definition.normalizer.normalize(mapped, self._definition.parser_version)
        issues = mapped.issues + tuple(issue for value in values for issue in value.issues)
        issues += self._definition.validator.validate(values)
        external_key = self._definition.key_strategy.create(profile, values)
        if external_key is None:
            issues += (
                ParseIssue(
                    "missing_external_identifier",
                    "configured unique identifier values are required",
                    IssueSeverity.ERROR,
                ),
            )
        payload_digest = self._payload_digest(values)

        if any(issue.severity is IssueSeverity.ERROR for issue in issues):
            return self._reject_row(
                profile,
                artifact,
                batch,
                entry.row_number,
                external_key,
                payload_digest,
                values,
                issues,
            )
        if external_key in seen_keys:
            duplicate_issue = ParseIssue(
                "duplicate_external_record_key",
                "the external record key already appeared in this artifact",
                IssueSeverity.WARNING,
            )
            return RowParseResult(
                entry.row_number,
                RecordDisposition.DUPLICATE,
                external_key,
                None,
                values,
                issues + (duplicate_issue,),
            )
        if external_key is None:
            raise AssertionError("error-bearing missing keys are rejected before comparison")

        previous = self._source_records.find_by_external_id(profile.source_id, external_key)
        if (
            previous is not None
            and previous.payload_digest == payload_digest
            and previous.parser_version == self._definition.parser_version
        ):
            return RowParseResult(
                entry.row_number,
                RecordDisposition.UNCHANGED,
                external_key,
                None,
                values,
                issues,
            )

        disposition = (
            RecordDisposition.WARNED
            if any(issue.severity is IssueSeverity.WARNING for issue in issues)
            or any(value.validation_result is ValueValidationResult.WARNING for value in values)
            else RecordDisposition.ACCEPTED
        )
        record = SourceRecord(
            source_record_id=self._record_id(batch, entry.row_number, payload_digest),
            source_id=profile.source_id,
            artifact_id=artifact.artifact_id,
            import_batch_id=batch.import_batch_id,
            external_record_id=external_key,
            payload_digest=payload_digest,
            observed_at=self._now(),
            source_row_number=entry.row_number,
            parsed_values=values,
            parse_issues=issues,
        )
        record.mark_parsed(self._definition.parser_version, self._now())
        batch.register_source_record(record)
        self._source_records.save(record)
        return RowParseResult(
            entry.row_number,
            disposition,
            external_key,
            record.source_record_id,
            values,
            issues,
        )

    def _reject_malformed(
        self,
        profile: SourceProfile,
        artifact: SourceArtifact,
        batch: ImportBatch,
        entry: MalformedEntry,
    ) -> RowParseResult:
        digest = ContentDigest("sha256", hashlib.sha256(entry.raw_payload.encode("utf-8")).hexdigest())
        return self._reject_row(
            profile,
            artifact,
            batch,
            entry.row_number,
            None,
            digest,
            (),
            entry.issues,
        )

    def _reject_row(
        self,
        profile: SourceProfile,
        artifact: SourceArtifact,
        batch: ImportBatch,
        row_number: int,
        external_key: str | None,
        payload_digest: ContentDigest,
        values: tuple[ParsedValue, ...],
        issues: tuple[ParseIssue, ...],
    ) -> RowParseResult:
        record = SourceRecord(
            source_record_id=self._record_id(batch, row_number, payload_digest),
            source_id=profile.source_id,
            artifact_id=artifact.artifact_id,
            import_batch_id=batch.import_batch_id,
            external_record_id=external_key,
            payload_digest=payload_digest,
            observed_at=self._now(),
            source_row_number=row_number,
            parsed_values=values,
            parse_issues=issues,
        )
        reason = "; ".join(issue.code for issue in issues if issue.severity is IssueSeverity.ERROR)
        record.reject(
            reason or "malformed_source_row",
            self._now(),
            parser_version=self._definition.parser_version,
        )
        batch.register_source_record(record)
        self._source_records.save(record)
        result = RowParseResult(
            row_number,
            RecordDisposition.REJECTED,
            external_key,
            record.source_record_id,
            values,
            issues,
        )
        self._rejection_reporter.report(result)
        return result

    def _fail_batch(
        self,
        profile: SourceProfile,
        artifact: SourceArtifact,
        batch: ImportBatch,
        error: ArtifactUnusable,
    ) -> None:
        batch.fail(error.safe_message, self._now())
        self._metrics.increment(
            "parser_failures_total",
            labels=(
                ("source_id", str(profile.source_id)),
                ("category", error.category.value),
            ),
        )
        self._logger.record(
            ParsingLogEntry(
                event="import_batch_parse_failed",
                source_id=str(profile.source_id),
                import_batch_id=str(batch.import_batch_id),
                artifact_id=str(artifact.artifact_id),
                parser_identifier=self._definition.parser_identifier,
                parser_version=self._definition.parser_version,
                outcome="failed",
                failure_category=error.category.value,
                message=error.safe_message,
            )
        )

    @staticmethod
    def _record_id(
        batch: ImportBatch,
        row_number: int,
        payload_digest: ContentDigest,
    ) -> SourceRecordId:
        seed = f"{batch.import_batch_id}|{row_number}|{payload_digest.hexadecimal}".encode()
        return SourceRecordId(f"sr-{hashlib.sha256(seed).hexdigest()}")

    @staticmethod
    def _payload_digest(values: tuple[ParsedValue, ...]) -> ContentDigest:
        serializable: list[tuple[str, object]] = []
        for value in values:
            normalized = value.normalized_value
            if isinstance(normalized, CalendarDate):
                encoded: object = {"date": normalized.value.isoformat()}
            elif isinstance(normalized, Money):
                encoded = {"amount": format(normalized.amount, "f"), "currency": normalized.currency}
            else:
                encoded = normalized
            serializable.append((value.canonical_field, encoded))
        payload = json.dumps(sorted(serializable), separators=(",", ":"), sort_keys=True).encode()
        return ContentDigest("sha256", hashlib.sha256(payload).hexdigest())
