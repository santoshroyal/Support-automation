"""DetectComplaintSpike exercised against a fake cluster repository."""

from datetime import datetime, timedelta, timezone
from typing import Iterable
from uuid import uuid4

from adapters.persistence.in_memory_spike_event_repository import (
    InMemorySpikeEventRepository,
)
from domain.spike_event import SpikeEvent
from service_layer.ports.feedback_cluster_repository_port import ClusterVolume
from service_layer.use_cases.detect_complaint_spike import DetectComplaintSpike


class _FakeClusterRepo:
    def __init__(self, volumes: list[ClusterVolume]) -> None:
        self._volumes = volumes

    def cluster_volumes(self, recent_window_hours, baseline_window_days, sample_size=5):
        return self._volumes

    def get_cluster(self, cluster_id):
        return None  # not used by this use case


def _volume(*, recent: int, baseline: float) -> ClusterVolume:
    return ClusterVolume(
        cluster_id=uuid4(),
        last_window_count=recent,
        daily_baseline=baseline,
        sample_feedback_ids=tuple(uuid4() for _ in range(min(recent, 3))),
    )


def test_records_spike_when_count_and_ratio_thresholds_met():
    cluster_repo = _FakeClusterRepo(
        volumes=[_volume(recent=5, baseline=1.0)]  # ratio 5.0, count 5
    )
    spike_repo = InMemorySpikeEventRepository()

    use_case = DetectComplaintSpike(
        cluster_repository=cluster_repo,
        spike_event_repository=spike_repo,
        min_count=2,
        ratio=2.0,
    )
    result = use_case.run()

    assert result.spikes_recorded == 1
    assert len(spike_repo) == 1


def test_skips_when_count_too_low():
    cluster_repo = _FakeClusterRepo(volumes=[_volume(recent=1, baseline=0.0)])
    spike_repo = InMemorySpikeEventRepository()
    use_case = DetectComplaintSpike(
        cluster_repository=cluster_repo,
        spike_event_repository=spike_repo,
        min_count=2,
        ratio=2.0,
    )

    result = use_case.run()

    assert result.spikes_recorded == 0


def test_skips_when_ratio_below_threshold():
    cluster_repo = _FakeClusterRepo(volumes=[_volume(recent=4, baseline=4.0)])
    spike_repo = InMemorySpikeEventRepository()
    use_case = DetectComplaintSpike(
        cluster_repository=cluster_repo,
        spike_event_repository=spike_repo,
        min_count=2,
        ratio=2.0,
    )

    result = use_case.run()

    assert result.spikes_recorded == 0


def test_baseline_clamped_at_one_avoids_divide_by_zero():
    """A cluster of 3 with baseline 0 should fire (ratio 3 >= 2.0)."""
    cluster_repo = _FakeClusterRepo(volumes=[_volume(recent=3, baseline=0.0)])
    spike_repo = InMemorySpikeEventRepository()
    use_case = DetectComplaintSpike(
        cluster_repository=cluster_repo,
        spike_event_repository=spike_repo,
        min_count=2,
        ratio=2.0,
    )

    result = use_case.run()

    assert result.spikes_recorded == 1


def test_recent_event_for_cluster_suppresses_re_alert():
    volume = _volume(recent=5, baseline=1.0)
    cluster_repo = _FakeClusterRepo(volumes=[volume])
    spike_repo = InMemorySpikeEventRepository()
    # Pre-seed a recent event for the same cluster.
    now = datetime.now(timezone.utc)
    spike_repo.add(
        SpikeEvent(
            cluster_id=volume.cluster_id,
            window_start=now - timedelta(hours=1),
            window_end=now,
            count=5,
            baseline=1.0,
            ratio=5.0,
        )
    )

    use_case = DetectComplaintSpike(
        cluster_repository=cluster_repo,
        spike_event_repository=spike_repo,
        min_count=2,
        ratio=2.0,
        suppression_window_hours=6,
    )
    result = use_case.run()

    assert result.spikes_recorded == 0
    assert result.suppressed_recent == 1
