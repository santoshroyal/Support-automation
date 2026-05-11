"""Port for persisting drafts and their lifecycle changes."""

from __future__ import annotations

from typing import Iterable, Protocol
from uuid import UUID

from domain.draft_reply import DraftReply, DraftStatus


class DraftReplyRepositoryPort(Protocol):
    def add(self, draft: DraftReply) -> None: ...

    def get(self, draft_id: UUID) -> DraftReply | None: ...

    def list_by_status(self, status: DraftStatus, limit: int = 100) -> Iterable[DraftReply]: ...

    def has_draft_for(self, feedback_id: UUID) -> bool: ...

    def update_status(self, draft_id: UUID, status: DraftStatus, edited_body: str | None = None) -> None: ...
