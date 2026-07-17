"""Standard-library infrastructure adapters for AZ Permit Radar."""

from .source_acquisition import (
    FakeConnector,
    FileSystemImmutableArtifactStore,
    InMemoryAcquisitionMetrics,
    InMemoryAcquisitionState,
    InMemoryAcquisitionLogger,
    InMemorySourceProfileRegistry,
    JsonLinesAcquisitionLogger,
    ManualFixtureConnector,
)

__all__ = [
    "FakeConnector",
    "FileSystemImmutableArtifactStore",
    "InMemoryAcquisitionMetrics",
    "InMemoryAcquisitionState",
    "InMemoryAcquisitionLogger",
    "InMemorySourceProfileRegistry",
    "JsonLinesAcquisitionLogger",
    "ManualFixtureConnector",
]
