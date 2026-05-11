"""DetectComplaintSpike — find clusters whose recent volume jumped well above baseline.

Algorithm (matches the plan's section 6.5):
  1. Ask the cluster repository for per-cluster volumes:
       last_window_count = members received in the last `recent_window_hours`
       daily_baseline    = average daily count over the prior `baseline_window_days`
  2. A cluster spikes when last_window_count >= min_count
       AND last_window_count >= ratio * GREATEST(daily_baseline, 1.0)
  3. Suppress repeats: skip the cluster if a spike event for it was recorded
     within `suppression_window_seconds`.
  4. Otherwise create a SpikeEvent and persist it; the digest job picks it
     up and turns it into stakeholder email rows.

Defaults are deliberately conservative for phase 1 fixture volumes (the
operator can tune them via config_files/thresholds.yaml later):
    min_count=2, ratio=2.0, recent_window_hours=24, baseline_window_days=7,
    suppression_window_hours=6.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from domain.spike_event import SpikeEvent
from service_layer.ports.feedback_cluster_repository_port import (
    FeedbackClusterRepositoryPort,
)
from service_layer.ports.spike_event_repository_port import SpikeEventRepositoryPort


@dataclass(frozen=True)
class SpikeDetectionResult:
    clusters_examined: int
    spikes_recorded: int
    suppressed_recent: int


class DetectComplaintSpike:
    def __init__(
        self,
        cluster_repository: FeedbackClusterRepositoryPort,
        spike_event_repository: SpikeEventRepositoryPort,
        min_count: int = 2,
        ratio: float = 2.0,
        recent_window_hours: int = 24,
        baseline_window_days: int = 7,
        suppression_window_hours: int = 6,
        sample_size: int = 5,
    ) -> None:
        self._cluster_repository = cluster_repository
        self._spike_event_repository = spike_event_repository
        self._min_count = min_count
        self._ratio = ratio
        self._recent_window_hours = recent_window_hours
        self._baseline_window_days = baseline_window_days
        self._suppression_window_seconds = suppression_window_hours * 3600
        self._sample_size = sample_size

    def run(self) -> SpikeDetectionResult:
        now = datetime.now(timezone.utc)
        window_start = now - timedelta(hours=self._recent_window_hours)

        examined = 0
        recorded = 0
        suppressed = 0

        for volume in self._cluster_repository.cluster_volumes(
            recent_window_hours=self._recent_window_hours,
            baseline_window_days=self._baseline_window_days,
            sample_size=self._sample_size,
        ):
            examined += 1
            if volume.last_window_count < self._min_count:
                continue
            normalised_baseline = max(volume.daily_baseline, 1.0)
            if volume.last_window_count < self._ratio * normalised_baseline:
                continue

            if self._spike_event_repository.has_recent_event_for(
                volume.cluster_id, within_seconds=self._suppression_window_seconds
            ):
                suppressed += 1
                continue

            event = SpikeEvent(
                cluster_id=volume.cluster_id,
                window_start=window_start,
                window_end=now,
                count=volume.last_window_count,
                baseline=volume.daily_baseline,
                ratio=volume.last_window_count / normalised_baseline,
                sample_feedback_ids=list(volume.sample_feedback_ids),
                alerted_at=None,  # set by the digest job when the alert email goes out
            )
            self._spike_event_repository.add(event)
            recorded += 1

        return SpikeDetectionResult(
            clusters_examined=examined,
            spikes_recorded=recorded,
            suppressed_recent=suppressed,
        )
