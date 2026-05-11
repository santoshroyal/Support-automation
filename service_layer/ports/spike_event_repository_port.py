"""Port for persisting spike events.

A spike event is a recorded instance of a complaint cluster crossing
its alert thresholds inside a time window. The DetectComplaintSpike use
case writes one each time a spike is detected (with a suppression window
to avoid re-alerting the same cluster repeatedly within a short period).
The digest builder reads recent events to assemble its email.
"""

from __future__ import annotations

from datetime import datetime
from typing import Iterable, Protocol
from uuid import UUID

from domain.spike_event import SpikeEvent


class SpikeEventRepositoryPort(Protocol):
    def add(self, event: SpikeEvent) -> None: ...

    def has_recent_event_for(
        self, cluster_id: UUID, within_seconds: int
    ) -> bool:
        """True if this cluster already has a spike event newer than `within_seconds` ago.

        Used to suppress re-alerting on the same cluster too often.
        """
        ...

    def list_recent(self, since: datetime) -> Iterable[SpikeEvent]:
        """Spike events created since `since`. Powers the digest's "what fired" section."""
        ...
