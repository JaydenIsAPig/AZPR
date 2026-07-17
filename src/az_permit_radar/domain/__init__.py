"""Framework-independent domain model for the AZ Permit Radar pilot."""

from .acquisition import (
    AcquisitionJob,
    AcquisitionJobStatus,
    AcquisitionOutcome,
    AcquisitionRecord,
    AcquisitionTrigger,
)
from .customer import (
    CustomerAccount,
    CustomerAccountStatus,
    CustomerFilter,
    CustomerTradePreference,
    NotificationPreference,
    ServiceTerritory,
)
from .deduplication import (
    DuplicateCandidateStatus,
    DuplicateDecisionRecord,
    DuplicateEvidence,
    DuplicateEvidenceLayer,
    ManualDuplicateDecision,
    PermitDuplicateCandidate,
)
from .errors import (
    ConsentRequired,
    DomainError,
    DuplicateConfiguration,
    InvariantViolation,
    InvalidStateTransition,
    InvalidValue,
)
from .ingestion import (
    ArtifactResponseMetadata,
    ImportBatch,
    ImportBatchStatus,
    SourceArtifact,
    SourceRecord,
    SourceRecordStatus,
)
from .matching import (
    LeadState,
    MatchExplanation,
    MatchScoreComponent,
    OpportunityMatch,
    OpportunityMatchStatus,
)
from .parsing import (
    ImportReport,
    IssueSeverity,
    ParseIssue,
    ParsedValue,
    RecordDisposition,
    RowParseResult,
    ValueValidationResult,
)
from .notification import (
    NotificationAttempt,
    NotificationAttemptStatus,
    NotificationChannel,
)
from .opportunity import Opportunity, OpportunityStatus
from .permit import (
    Address,
    AddressResolutionStatus,
    CoordinateSource,
    GeocodeQuality,
    GeocodeResult,
    NormalizedPermitType,
    ParcelReference,
    Permit,
    PermitAuthorityStatus,
    PermitHistoryAction,
    PermitHistoryEntry,
    PermitParty,
    PermitPartyRole,
    PermitSnapshot,
    PermitSourceEvidence,
    PermitStatus,
)
from .review import ReviewSubjectType, ReviewTask, ReviewTaskStatus
from .source_registry import (
    AccessReviewStatus,
    AcquisitionMethod,
    AuthenticationRequirement,
    EndpointConfiguration,
    Jurisdiction,
    JurisdictionStatus,
    Source,
    SourceFileType,
    SourceHealthStatus,
    SourceProfile,
    SourceStatus,
)
from .classification import (
    ClassificationMethod,
    ClassificationResult,
    ClassificationReviewStatus,
    ProjectClassification,
    TradeTag,
)
from .value_objects import *  # noqa: F403

__all__ = [name for name in globals() if not name.startswith("_")]
