"""Port for inbound feedback channels (Gmail, Play, Apple).

One adapter instance per (app, channel) combination. The composition root
iterates the configured apps and constructs the right adapters per channel.
"""

from __future__ import annotations

from datetime import datetime
from typing import Iterable, Protocol

from domain.feedback import FeedbackChannel, RawFeedback


class FeedbackSourcePort(Protocol):
    @property
    def channel(self) -> FeedbackChannel: ...

    @property
    def app_slug(self) -> str:
        """Slug of the Times Internet app this source instance is reading for."""
        ...

    def fetch_new(self, since: datetime | None) -> Iterable[RawFeedback]:
        """Yield feedback received after `since`. Adapter handles cursor reading."""
        ...
