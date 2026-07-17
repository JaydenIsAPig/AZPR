from datetime import datetime, timezone
from decimal import Decimal

from az_permit_radar.domain.classification import ProjectClassification, TradeTag
from az_permit_radar.domain.matching import MatchExplanation, MatchScoreComponent
from az_permit_radar.domain.value_objects import (
    CalendarDate,
    Confidence,
    TradeTagId,
    UtcTimestamp,
)


NOW = UtcTimestamp(datetime(2026, 7, 17, 12, 0, tzinfo=timezone.utc))
LATER = UtcTimestamp(datetime(2026, 7, 17, 13, 0, tzinfo=timezone.utc))
TRADE = TradeTag(TradeTagId("trade-electric"), "electrical", "Electrical")
PROJECT_CLASSIFICATION = ProjectClassification("tenant-improvement", "Tenant Improvement")


def explanation() -> MatchExplanation:
    return MatchExplanation(
        matching_trade_tag_ids=frozenset({TRADE.trade_tag_id}),
        geographic_rule="customer territory contains permit jurisdiction",
        relevant_filters=("minimum confidence satisfied",),
        score_components=(
            MatchScoreComponent("trade", Decimal("0.6"), "electrical tag matched"),
            MatchScoreComponent("geography", Decimal("0.4"), "jurisdiction matched"),
        ),
        exclusions_considered=("valuation threshold",),
        source_freshness_date=CalendarDate.from_iso("2026-07-17"),
        confidence=Confidence(Decimal("0.91")),
    )
