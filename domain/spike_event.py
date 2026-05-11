"""SpikeEvent — a recorded instance of a complaint cluster crossing thresholds.

Created by `DetectComplaintSpike`. Re-detection within a 6-hour window is
suppressed so we don't alert on the same spike repeatedly.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID, uuid4


@dataclass
class SpikeEvent:
    cluster_id: UUID
    window_start: datetime
    window_end: datetime
    count: int
    baseline: float
    ratio: float
    sample_feedback_ids: list[UUID] = field(default_factory=list)
    id: UUID = field(default_factory=uuid4)
    alerted_at: datetime | None = None
