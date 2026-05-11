"""In-memory DraftReplyRepository — used during local dev and tests."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Iterable
from uuid import UUID

from domain.draft_reply import DraftReply, DraftStatus


class InMemoryDraftReplyRepository:
    def __init__(self) -> None:
        self._by_id: dict[UUID, DraftReply] = {}
        # feedback_id → latest draft id (one active draft per feedback;
        # earlier drafts move to status=regenerated when a fresh one lands).
        self._latest_by_feedback: dict[UUID, UUID] = {}

    def add(self, draft: DraftReply) -> None:
        # Demote any earlier active draft for the same feedback so the
        # in-memory store mirrors the "only one active draft per feedback"
        # invariant the dashboard relies on.
        previous_id = self._latest_by_feedback.get(draft.feedback_id)
        if previous_id is not None:
            previous = self._by_id[previous_id]
            if previous.status is DraftStatus.DRAFT:
                previous.status = DraftStatus.REGENERATED
        self._by_id[draft.id] = draft
        self._latest_by_feedback[draft.feedback_id] = draft.id

    def get(self, draft_id: UUID) -> DraftReply | None:
        return self._by_id.get(draft_id)

    def list_by_status(
        self, status: DraftStatus, limit: int = 100
    ) -> Iterable[DraftReply]:
        out: list[DraftReply] = []
        for draft in self._by_id.values():
            if draft.status is status:
                out.append(draft)
                if len(out) >= limit:
                    break
        return out

    def has_draft_for(self, feedback_id: UUID) -> bool:
        draft_id = self._latest_by_feedback.get(feedback_id)
        if draft_id is None:
            return False
        return self._by_id[draft_id].status in {
            DraftStatus.DRAFT,
            DraftStatus.SENT,
            DraftStatus.EDITED,
        }

    def update_status(
        self,
        draft_id: UUID,
        status: DraftStatus,
        edited_body: str | None = None,
    ) -> None:
        draft = self._by_id.get(draft_id)
        if draft is None:
            return
        draft.status = status
        if edited_body is not None:
            draft.edited_body = edited_body
        if status is DraftStatus.SENT:
            draft.sent_at = datetime.now(timezone.utc)

    def __len__(self) -> int:
        return len(self._by_id)
