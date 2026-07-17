"""Deterministic CSV parser stages and local parsing adapters."""

from __future__ import annotations

import csv
import hashlib
import re
import threading
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from urllib.parse import unquote, urlparse

from az_permit_radar.application.parsing import (
    ArtifactUnusable,
    ArtifactUnusableCategory,
    DecodedArtifact,
    ExtractionResult,
    MalformedEntry,
    MappedEntry,
    MappedField,
    ParserDefinition,
    ParsingLogEntry,
    RawEntry,
    ValidatedFormat,
)
from az_permit_radar.domain.errors import InvalidValue
from az_permit_radar.domain.ingestion import SourceArtifact, SourceRecord, SourceRecordStatus
from az_permit_radar.domain.parsing import (
    IssueSeverity,
    ParseIssue,
    ParsedValue,
    RowParseResult,
    ValueValidationResult,
)
from az_permit_radar.domain.source_registry import SourceProfile
from az_permit_radar.domain.value_objects import (
    CalendarDate,
    Money,
    SourceArtifactId,
    SourceId,
    SourceRecordId,
)


def _header_key(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", value.strip().lower()).strip("_")


@dataclass(frozen=True, slots=True)
class CsvFieldDefinition:
    canonical_field: str
    aliases: tuple[str, ...]
    value_kind: str
    required: bool = False
    warn_on_normalization: bool = False

    def __post_init__(self) -> None:
        if not self.canonical_field.strip() or not self.aliases:
            raise ValueError("CSV field definitions require a canonical field and aliases")
        if self.value_kind not in {"text", "date", "currency"}:
            raise ValueError("unsupported CSV field value kind")


class Utf8FileDecoder:
    """Decodes UTF-8/UTF-8-BOM files without encoding guessing."""

    def decode(self, content: bytes, media_type: str) -> DecodedArtifact:
        if media_type.split(";", 1)[0].strip().lower() not in {
            "text/csv",
            "application/csv",
            "text/plain",
        }:
            raise ArtifactUnusable(
                ArtifactUnusableCategory.FORMAT,
                "parser supports only the configured CSV media types",
            )
        try:
            text = content.decode("utf-8-sig")
        except UnicodeDecodeError as error:
            raise ArtifactUnusable(
                ArtifactUnusableCategory.DECODING,
                "artifact is not valid UTF-8",
            ) from error
        if "\x00" in text:
            raise ArtifactUnusable(
                ArtifactUnusableCategory.DECODING,
                "artifact contains unsupported NUL bytes",
            )
        return DecodedArtifact(text=text, encoding="utf-8-sig")


class CsvFormatValidator:
    def __init__(self, fields: tuple[CsvFieldDefinition, ...]) -> None:
        self._fields = fields
        aliases: dict[str, str] = {}
        for field in fields:
            for alias in field.aliases:
                key = _header_key(alias)
                if key in aliases and aliases[key] != field.canonical_field:
                    raise ValueError("CSV aliases cannot map to multiple canonical fields")
                aliases[key] = field.canonical_field
        self._aliases = aliases

    def validate(self, decoded: DecodedArtifact, profile: SourceProfile) -> ValidatedFormat:
        lines = decoded.text.splitlines()
        if not lines:
            raise ArtifactUnusable(ArtifactUnusableCategory.FORMAT, "CSV artifact is empty")
        try:
            headers = tuple(next(csv.reader([lines[0]], strict=True)))
        except (csv.Error, StopIteration) as error:
            raise ArtifactUnusable(
                ArtifactUnusableCategory.FORMAT,
                "CSV header row is malformed",
            ) from error
        normalized = tuple(_header_key(header) for header in headers)
        if not headers or any(not header for header in normalized):
            raise ArtifactUnusable(
                ArtifactUnusableCategory.FORMAT,
                "CSV header names cannot be blank",
            )
        if len(set(normalized)) != len(normalized):
            raise ArtifactUnusable(
                ArtifactUnusableCategory.FORMAT,
                "CSV header names must be unique",
            )
        canonical_headers = [self._aliases.get(header) for header in normalized]
        known = [header for header in canonical_headers if header is not None]
        if len(known) != len(set(known)):
            raise ArtifactUnusable(
                ArtifactUnusableCategory.FORMAT,
                "CSV contains ambiguous aliases for one canonical field",
            )
        missing = [
            field.canonical_field
            for field in self._fields
            if field.required and field.canonical_field not in known
        ]
        configured = set(profile.expected_date_fields + profile.expected_unique_identifiers)
        parser_fields = {field.canonical_field for field in self._fields}
        if not configured <= parser_fields:
            raise ArtifactUnusable(
                ArtifactUnusableCategory.CONFIGURATION,
                "source profile expects fields not defined by the selected parser",
            )
        if missing:
            raise ArtifactUnusable(
                ArtifactUnusableCategory.FORMAT,
                "CSV is missing required source columns: " + ", ".join(sorted(missing)),
            )
        return ValidatedFormat(decoded=decoded, headers=headers)


class CsvEntryExtractor:
    """Extracts one physical CSV row at a time so a malformed row is quarantined."""

    def extract(self, validated: ValidatedFormat) -> ExtractionResult:
        entries: list[RawEntry | MalformedEntry] = []
        lines = validated.decoded.text.splitlines()
        for row_number, raw_line in enumerate(lines[1:], start=2):
            if not raw_line.strip():
                continue
            try:
                values = tuple(next(csv.reader([raw_line], strict=True)))
            except (csv.Error, StopIteration):
                entries.append(
                    MalformedEntry(
                        row_number,
                        raw_line,
                        (
                            ParseIssue(
                                "malformed_csv_row",
                                "CSV row could not be decoded",
                                IssueSeverity.ERROR,
                            ),
                        ),
                    )
                )
                continue
            if len(values) != len(validated.headers):
                entries.append(
                    MalformedEntry(
                        row_number,
                        raw_line,
                        (
                            ParseIssue(
                                "csv_column_count_mismatch",
                                "CSV row has a different column count than the header",
                                IssueSeverity.ERROR,
                            ),
                        ),
                    )
                )
                continue
            entries.append(
                RawEntry(
                    row_number=row_number,
                    values=tuple(zip(validated.headers, values, strict=True)),
                    raw_payload=raw_line,
                )
            )
        return ExtractionResult(tuple(entries))


class AliasFieldMapper:
    def __init__(self, fields: tuple[CsvFieldDefinition, ...]) -> None:
        self._fields = fields

    def map(self, entry: RawEntry) -> MappedEntry:
        source_values = {_header_key(name): (name, value) for name, value in entry.values}
        mapped: list[MappedField] = []
        consumed: set[str] = set()
        for field in self._fields:
            matched = next(
                (
                    (alias, source_values[alias])
                    for alias in (_header_key(item) for item in field.aliases)
                    if alias in source_values
                ),
                None,
            )
            if matched is None:
                mapped.append(
                    MappedField(
                        canonical_field=field.canonical_field,
                        source_field=field.canonical_field,
                        raw_value="",
                        value_kind=field.value_kind,
                        required=field.required,
                    )
                )
                continue
            alias, (source_name, raw_value) = matched
            consumed.add(alias)
            mapped.append(
                MappedField(
                    canonical_field=field.canonical_field,
                    source_field=source_name,
                    raw_value=raw_value,
                    value_kind=field.value_kind,
                    required=field.required,
                )
            )
        for normalized_name, (source_name, raw_value) in source_values.items():
            if normalized_name in consumed:
                continue
            issue = ParseIssue(
                "unmapped_source_column",
                "source column is not mapped by this parser version",
                IssueSeverity.WARNING,
                source_name,
            )
            mapped.append(
                MappedField(
                    canonical_field=f"source_extra.{normalized_name}",
                    source_field=source_name,
                    raw_value=raw_value,
                    value_kind="text",
                    required=False,
                    issues=(issue,),
                )
            )
        return MappedEntry(entry.row_number, tuple(mapped), entry.raw_payload)


class ExplicitValueNormalizer:
    def __init__(
        self,
        fields: tuple[CsvFieldDefinition, ...],
        *,
        date_formats: tuple[str, ...],
    ) -> None:
        self._fields = {field.canonical_field: field for field in fields}
        self._date_formats = date_formats
        if not date_formats:
            raise ValueError("at least one explicit date format is required")

    def normalize(self, entry: MappedEntry, parser_version: str) -> tuple[ParsedValue, ...]:
        return tuple(self._normalize_field(field, parser_version) for field in entry.fields)

    def _normalize_field(self, field: MappedField, parser_version: str) -> ParsedValue:
        raw = field.raw_value
        stripped = raw.strip()
        if not stripped:
            if field.required:
                issue = ParseIssue(
                    "required_value_missing",
                    "required source value is empty",
                    IssueSeverity.ERROR,
                    field.source_field,
                )
                return ParsedValue(
                    field.canonical_field,
                    field.source_field,
                    raw,
                    None,
                    parser_version,
                    ValueValidationResult.ERROR,
                    field.issues + (issue,),
                )
            return ParsedValue(
                field.canonical_field,
                field.source_field,
                raw,
                None,
                parser_version,
                ValueValidationResult.EMPTY,
                field.issues,
            )
        if field.value_kind == "date":
            return self._date_value(field, stripped, parser_version)
        if field.value_kind == "currency":
            return self._currency_value(field, stripped, parser_version)
        normalized = " ".join(stripped.split())
        definition = self._fields.get(field.canonical_field)
        if field.canonical_field == "permit_number":
            normalized = normalized.upper()
        issues = field.issues
        if definition is not None and definition.warn_on_normalization and normalized != raw:
            issues += (
                ParseIssue(
                    "value_normalized",
                    "source value required deterministic normalization",
                    IssueSeverity.WARNING,
                    field.source_field,
                ),
            )
        result = ValueValidationResult.WARNING if issues else ValueValidationResult.VALID
        return ParsedValue(
            field.canonical_field,
            field.source_field,
            raw,
            normalized,
            parser_version,
            result,
            issues,
        )

    def _date_value(
        self,
        field: MappedField,
        stripped: str,
        parser_version: str,
    ) -> ParsedValue:
        for date_format in self._date_formats:
            try:
                value = CalendarDate(datetime.strptime(stripped, date_format).date())
                return ParsedValue(
                    field.canonical_field,
                    field.source_field,
                    field.raw_value,
                    value,
                    parser_version,
                    ValueValidationResult.VALID,
                    field.issues,
                )
            except ValueError:
                continue
        issue = ParseIssue(
            "invalid_date",
            "date does not match an explicitly supported source format",
            IssueSeverity.ERROR,
            field.source_field,
        )
        return ParsedValue(
            field.canonical_field,
            field.source_field,
            field.raw_value,
            None,
            parser_version,
            ValueValidationResult.ERROR,
            field.issues + (issue,),
        )

    @staticmethod
    def _currency_value(
        field: MappedField,
        stripped: str,
        parser_version: str,
    ) -> ParsedValue:
        pattern = r"^\$?(?:[0-9]{1,3}(?:,[0-9]{3})+|[0-9]+)(?:\.[0-9]{1,2})?$"
        try:
            if not re.fullmatch(pattern, stripped):
                raise InvalidOperation
            amount = Decimal(stripped.removeprefix("$").replace(",", ""))
            value = Money(amount, "USD")
        except (InvalidOperation, InvalidValue):
            issue = ParseIssue(
                "invalid_currency",
                "currency must be a non-negative USD amount with at most two decimals",
                IssueSeverity.ERROR,
                field.source_field,
            )
            return ParsedValue(
                field.canonical_field,
                field.source_field,
                field.raw_value,
                None,
                parser_version,
                ValueValidationResult.ERROR,
                field.issues + (issue,),
            )
        return ParsedValue(
            field.canonical_field,
            field.source_field,
            field.raw_value,
            value,
            parser_version,
            ValueValidationResult.VALID,
            field.issues,
        )


class TucsonFixtureRecordValidator:
    """Fixture-only record validation; not an approved municipal contract."""

    def validate(self, values: tuple[ParsedValue, ...]) -> tuple[ParseIssue, ...]:
        permit_number = next(
            (value for value in values if value.canonical_field == "permit_number"),
            None,
        )
        if permit_number is None or permit_number.normalized_value is None:
            return ()
        normalized = permit_number.normalized_value
        if not isinstance(normalized, str) or not re.fullmatch(r"[A-Z0-9][A-Z0-9-]{2,39}", normalized):
            return (
                ParseIssue(
                    "invalid_permit_number",
                    "permit number does not match the fixture source contract",
                    IssueSeverity.ERROR,
                    permit_number.source_field,
                ),
            )
        return ()


class HashedExternalRecordKey:
    """Hashes source identity plus configured normalized unique fields."""

    def create(self, profile: SourceProfile, values: tuple[ParsedValue, ...]) -> str | None:
        by_name = {value.canonical_field: value for value in values}
        components: list[str] = [str(profile.source_id)]
        for field_name in profile.expected_unique_identifiers:
            value = by_name.get(field_name)
            if (
                value is None
                or value.normalized_value is None
                or value.validation_result is ValueValidationResult.ERROR
            ):
                return None
            normalized = value.normalized_value
            if isinstance(normalized, CalendarDate):
                encoded = normalized.value.isoformat()
            elif isinstance(normalized, Money):
                encoded = f"{normalized.currency}:{format(normalized.amount, 'f')}"
            else:
                encoded = str(normalized)
            components.append(f"{field_name}={encoded}")
        digest = hashlib.sha256("|".join(components).encode("utf-8")).hexdigest()
        return f"external-{digest}"


class InMemorySourceRecordRepository:
    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._records: dict[SourceRecordId, SourceRecord] = {}
        self._latest: dict[tuple[SourceId, str], SourceRecordId] = {}

    def get(self, source_record_id: SourceRecordId) -> SourceRecord | None:
        with self._lock:
            record = self._records.get(source_record_id)
            return deepcopy(record) if record is not None else None

    def find_by_external_id(self, source_id: SourceId, external_record_id: str) -> SourceRecord | None:
        with self._lock:
            record_id = self._latest.get((source_id, external_record_id))
            record = self._records.get(record_id) if record_id is not None else None
            return deepcopy(record) if record is not None else None

    def save(self, source_record: SourceRecord) -> None:
        with self._lock:
            self._records[source_record.source_record_id] = deepcopy(source_record)
            if (
                source_record.status is SourceRecordStatus.PARSED
                and source_record.external_record_id is not None
            ):
                self._latest[(source_record.source_id, source_record.external_record_id)] = (
                    source_record.source_record_id
                )

    @property
    def records(self) -> tuple[SourceRecord, ...]:
        with self._lock:
            return tuple(deepcopy(record) for record in self._records.values())


class InMemoryArtifactReader:
    def __init__(self, artifacts: dict[SourceArtifactId, bytes] | None = None) -> None:
        self._artifacts = dict(artifacts or {})

    def add(self, artifact: SourceArtifact, content: bytes) -> None:
        self._artifacts[artifact.artifact_id] = bytes(content)

    def read(self, artifact: SourceArtifact) -> bytes:
        try:
            return bytes(self._artifacts[artifact.artifact_id])
        except KeyError as error:
            raise OSError("artifact bytes are unavailable") from error


class FileSystemArtifactReader:
    """Reads only file-URI artifacts beneath one configured archive root."""

    def __init__(self, root: Path) -> None:
        self._root = root.resolve()

    def read(self, artifact: SourceArtifact) -> bytes:
        parsed = urlparse(artifact.storage_reference)
        if parsed.scheme != "file" or parsed.netloc not in {"", "localhost"}:
            raise OSError("artifact reference is not a local file URI")
        path = Path(unquote(parsed.path)).resolve()
        try:
            path.relative_to(self._root)
        except ValueError as error:
            raise OSError("artifact reference escapes the configured archive root") from error
        return path.read_bytes()


class InMemoryRejectionReporter:
    def __init__(self) -> None:
        self.rows: list[RowParseResult] = []

    def report(self, result: RowParseResult) -> None:
        self.rows.append(result)


class InMemoryParsingLogger:
    def __init__(self) -> None:
        self.entries: list[ParsingLogEntry] = []

    def record(self, entry: ParsingLogEntry) -> None:
        self.entries.append(entry)


class InMemoryParsingMetrics:
    def __init__(self) -> None:
        self.counters: dict[tuple[str, tuple[tuple[str, str], ...]], int] = {}

    def increment(self, name: str, *, labels: tuple[tuple[str, str], ...] = ()) -> None:
        key = (name, tuple(sorted(labels)))
        self.counters[key] = self.counters.get(key, 0) + 1


TUCSON_FIXTURE_FIELDS = (
    CsvFieldDefinition(
        "permit_number",
        ("Permit Number", "Permit #", "permit_number"),
        "text",
        required=True,
        warn_on_normalization=True,
    ),
    CsvFieldDefinition(
        "issued_date",
        ("Issued Date", "Issue Date", "issued_date"),
        "date",
        required=True,
    ),
    CsvFieldDefinition(
        "application_date",
        ("Application Date", "Applied Date", "application_date"),
        "date",
    ),
    CsvFieldDefinition(
        "permit_status",
        ("Permit Status", "Status", "permit_status"),
        "text",
    ),
    CsvFieldDefinition(
        "permit_type",
        ("Permit Type", "Type", "permit_type"),
        "text",
    ),
    CsvFieldDefinition(
        "valuation",
        ("Valuation", "Project Value", "valuation"),
        "currency",
    ),
    CsvFieldDefinition(
        "address",
        ("Address", "Project Address", "address"),
        "text",
    ),
    CsvFieldDefinition(
        "description",
        ("Description", "Work Description", "description"),
        "text",
    ),
    CsvFieldDefinition(
        "contractor_name",
        ("Contractor Name", "Contractor", "contractor_name"),
        "text",
    ),
    CsvFieldDefinition(
        "contractor_license",
        ("Contractor License", "ROC Number", "contractor_license"),
        "text",
    ),
    CsvFieldDefinition(
        "applicant_name",
        ("Applicant Name", "Applicant", "applicant_name"),
        "text",
    ),
    CsvFieldDefinition(
        "parcel_id",
        ("Parcel ID", "APN", "parcel_id"),
        "text",
    ),
    CsvFieldDefinition(
        "jurisdiction",
        ("Jurisdiction", "jurisdiction"),
        "text",
    ),
    CsvFieldDefinition(
        "latitude",
        ("Latitude", "Lat", "latitude"),
        "text",
    ),
    CsvFieldDefinition(
        "longitude",
        ("Longitude", "Lon", "Lng", "longitude"),
        "text",
    ),
)


def tucson_fixture_parser_definition(
    *,
    parser_version: str = "1.1.0",
) -> ParserDefinition:
    """Build the synthetic Tucson fixture parser; this is not a live-source approval."""

    return ParserDefinition(
        parser_identifier="synthetic-tucson-permit-csv",
        parser_version=parser_version,
        decoder=Utf8FileDecoder(),
        format_validator=CsvFormatValidator(TUCSON_FIXTURE_FIELDS),
        extractor=CsvEntryExtractor(),
        mapper=AliasFieldMapper(TUCSON_FIXTURE_FIELDS),
        normalizer=ExplicitValueNormalizer(
            TUCSON_FIXTURE_FIELDS,
            date_formats=("%Y-%m-%d", "%m/%d/%Y"),
        ),
        validator=TucsonFixtureRecordValidator(),
        key_strategy=HashedExternalRecordKey(),
    )
