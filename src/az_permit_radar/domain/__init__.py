"""Framework-independent domain model for the AZ Permit Radar pilot."""

from .customer import (
    CustomerAccount,
    CustomerAccountStatus,
    CustomerFilter,
    CustomerTradePreference,
    NotificationPreference,
    ServiceTerritory,
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
from .notification import (
    NotificationAttempt,
    NotificationAttemptStatus,
    NotificationChannel,
)
from .opportunity import Opportunity, OpportunityStatus
from .permit import Address, ParcelReference, Permit, PermitStatus
from .review import ReviewSubjectType, ReviewTask, ReviewTaskStatus
from .source_registry import Jurisdiction, JurisdictionStatus, Source, SourceStatus
from .classification import (
    ClassificationMethod,
    ClassificationResult,
    ClassificationReviewStatus,
    ProjectClassification,
    TradeTag,
)
from .value_objects import *  # noqa: F403

__all__ = [name for name in globals() if not name.startswith("_")]
