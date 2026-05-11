"""Port for delivering a draft to its review surface (Gmail thread, filesystem, etc.)."""

from __future__ import annotations

from typing import Protocol

from domain.draft_reply import DraftReply
from domain.feedback import Feedback


class ReplyDeliveryPort(Protocol):
    def deliver(self, feedback: Feedback, draft: DraftReply) -> None: ...
