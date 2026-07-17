"""Immutable deterministic parsing results and rejection vocabulary."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .errors import InvariantViolation
from .value_objects import (
    CalendarDate,
    ImportBatchId,
    Money,
    SourceArtifactId,
    SourceRecordId,
)


class IssueSeverity(str, Enum):
    WARNING = "warning"
    ERROR = "error"


class ValueValidationResult(str, Enum):
    VALID = "valid"
    EMPTY = "empty"
    WARNING = "warning"
    ERROR = "error"


class RecordDisposition(str, Enum):
    ACCEPTED = "accepted"
    WARNED = "warned"
    REJECTED = "rejected"
    DUPLICATE = "duplicate"
    UNCHANGED = "unchanged"


NormalizedValue = str | CalendarDate | Money | None


@dataclass(frozen=True, slots=True)
class ParseIssue:
    code: str
    message: str
    severity: IssueSeverity
    source_field: str | None = None

    def __post_init__(self) -> None:
        if not self.code.strip() or not self.message.strip():
            raise InvariantViolation("parse issue code and message are required")
        if self.source_field is not None and not self.source_field.strip():
            raise InvariantViolation("parse issue source field cannot be blank")


@dataclass(frozen=True, slots=True)
class ParsedValue:
    canonical_field: str
    source_field: str
    raw_value: str | None
    normalized_value: NormalizedValue
    parser_version: str
    validation_result: ValueValidationResult
    issues: tuple[ParseIssue, ...] = ()

    def __post_init__(self) -> None:
        if not self.canonical_field.strip() or not self.source_field.strip():
            raise InvariantViolation("parsed value field names are required")
        if not self.parser_version.strip():
            raise InvariantViolation("parsed value parser version is required")
        has_error = any(issue.severity is IssueSeverity.ERROR for issue in self.issues)
        has_warning = any(issue.severity is IssueSeverity.WARNING for issue in self.issues)
        if self.validation_result is ValueValidationResult.ERROR and not has_error:
            raise InvariantViolation("an invalid parsed value requires an error")
        if self.validation_result is ValueValidationResult.WARNING and not has_warning:
            raise InvariantViolation("a warned parsed value requires a warning")
        if has_error and self.validation_result is not ValueValidationResult.ERROR:
            raise InvariantViolation("parsed value errors require an error result")


@dataclass(frozen=True, slots=True)
class RowParseResult:
    row_number: int
    disposition: RecordDisposition
    external_record_key: str | None
    source_record_id: SourceRecordId | None
    values: tuple[ParsedValue, ...]
    issues: tuple[ParseIssue, ...] = ()

    def __post_init__(self) -> None:
        if self.row_number < 2:
            raise InvariantViolation("source row numbers must follow the header row")
        if self.external_record_key is not None and not self.external_record_key.strip():
            raise InvariantViolation("external record key cannot be blank")
        creates_record = self.disposition in {
            RecordDisposition.ACCEPTED,
            RecordDisposition.WARNED,
            RecordDisposition.REJECTED,
        }
        if creates_record != (self.source_record_id is not None):
            raise InvariantViolation("row disposition and source record identity disagree")


@dataclass(frozen=True, slots=True)
class ImportReport:
    import_batch_id: ImportBatchId
    artifact_id: SourceArtifactId
    parser_identifier: str
    parser_version: str
    total_entries: int
    accepted_count: int
    warned_count: int
    rejected_count: int
    duplicate_count: int
    unchanged_count: int
    rows: tuple[RowParseResult, ...]

    def __post_init__(self) -> None:
        if not self.parser_identifier.strip() or not self.parser_version.strip():
            raise InvariantViolation("import report parser identity is required")
        counts = (
            self.accepted_count,
            self.warned_count,
            self.rejected_count,
            self.duplicate_count,
            self.unchanged_count,
        )
        if self.total_entries < 0 or any(count < 0 for count in counts):
            raise InvariantViolation("import report counts cannot be negative")
        if sum(counts) != self.total_entries or len(self.rows) != self.total_entries:
            raise InvariantViolation("import report counts must partition all extracted entries")

