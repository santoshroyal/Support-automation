"""Port for persisting Classification records and finding what's not classified."""

from __future__ import annotations

from typing import Iterable, Protocol
from uuid import UUID

from domain.classification import Classification


class ClassificationRepositoryPort(Protocol):
    def add(self, classification: Classification) -> None: ...

    def get(self, feedback_id: UUID) -> Classification | None: ...

    def has_classification_for(self, feedback_id: UUID) -> bool: ...

    def list_by_app(self, app_slug: str | None = None) -> Iterable[Classification]: ...
