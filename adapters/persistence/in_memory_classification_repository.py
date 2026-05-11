"""In-memory ClassificationRepository — used during local dev and tests.

Same Protocol as the Postgres-backed repository, so the use case never
knows which is plugged in.
"""

from __future__ import annotations

from typing import Iterable
from uuid import UUID

from domain.classification import Classification


class InMemoryClassificationRepository:
    def __init__(self) -> None:
        self._by_feedback_id: dict[UUID, Classification] = {}

    def add(self, classification: Classification) -> None:
        self._by_feedback_id[classification.feedback_id] = classification

    def get(self, feedback_id: UUID) -> Classification | None:
        return self._by_feedback_id.get(feedback_id)

    def has_classification_for(self, feedback_id: UUID) -> bool:
        return feedback_id in self._by_feedback_id

    def list_by_app(self, app_slug: str | None = None) -> Iterable[Classification]:
        # The in-memory repo doesn't know which feedback belongs to which app —
        # the Postgres repo joins; this in-memory version returns all and
        # leaves filtering to the caller. Phase 1 callers don't need filtering.
        if app_slug is None:
            return list(self._by_feedback_id.values())
        # A future test may exercise this — return [] rather than crash.
        return []

    def __len__(self) -> int:
        return len(self._by_feedback_id)
