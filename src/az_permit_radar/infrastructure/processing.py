"""Process-local adapters for correlated end-to-end processing."""

from __future__ import annotations

import json
import threading
from copy import deepcopy
from typing import Callable, TypeVar

from az_permit_radar.application.processing import ProcessingConsistencyPolicy, ProcessingRunResult, ProcessingTraceEntry
from az_permit_radar.domain.errors import InvariantViolation


RunResultT = TypeVar("RunResultT")


class InMemoryProcessingRunStore:
    """Serializes a correlation command and retains its immutable replay result."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._results: dict[str, ProcessingRunResult] = {}

    def run_once(
        self,
        correlation_id: str,
        operation: Callable[[], RunResultT],
    ) -> RunResultT:
        if not correlation_id.strip():
            raise InvariantViolation("processing correlation identifier is required")
        with self._lock:
            existing = self._results.get(correlation_id)
            if existing is not None:
                return deepcopy(existing)  # type: ignore[return-value]
            result = operation()
            if not isinstance(result, ProcessingRunResult):
                raise InvariantViolation("processing command returned an unsupported result")
            self._results[correlation_id] = deepcopy(result)
            return deepcopy(result)  # type: ignore[return-value]

    @property
    def results(self) -> tuple[ProcessingRunResult, ...]:
        with self._lock:
            return tuple(deepcopy(result) for result in self._results.values())


class InMemoryProcessingTraceLogger:
    def __init__(self) -> None:
        self._lock = threading.RLock()
        self.entries: list[ProcessingTraceEntry] = []

    def record(self, entry: ProcessingTraceEntry) -> None:
        with self._lock:
            self.entries.append(entry)


def load_processing_consistency_policy(path: str) -> ProcessingConsistencyPolicy:
    with open(path, encoding="utf-8") as stream:
        values = json.load(stream)["processing_workflow_policy"]
    return ProcessingConsistencyPolicy(
        version=values["version"],
        batch_owner=values["batch_owner"],
        normalization_atomicity=values["normalization_atomicity"],
        retryable_batch_failure_action=values["retryable_batch_failure_action"],
        uniqueness_scopes=tuple(values["uniqueness_scopes"]),
        failure_categories=tuple(values["failure_categories"]),
    )
