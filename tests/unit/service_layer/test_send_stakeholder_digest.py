"""SendStakeholderDigest exercised against fake adapters."""

from datetime import datetime, timedelta, timezone
from uuid import uuid4

from adapters.persistence.in_memory_digest_log_repository import (
    InMemoryDigestLogRepository,
)
from adapters.persistence.in_memory_feedback_cluster_repository import (
    InMemoryFeedbackClusterRepository,
)
from adapters.persistence.in_memory_spike_event_repository import (
    InMemorySpikeEventRepository,
)
from domain.feedback_cluster import FeedbackCluster
from domain.spike_event import SpikeEvent
from domain.stakeholder import Stakeholder
from service_layer.use_cases.send_stakeholder_digest import SendStakeholderDigest


class _FakeSender:
    name = "fake"

    def __init__(self) -> None:
        self.sent: list[tuple[str, str, list[Stakeholder]]] = []
        self.raise_on_send = False

    def send_digest(self, recipients, subject, html_body, digest_type="digest"):
        if self.raise_on_send:
            raise RuntimeError("simulated SMTP failure")
        self.sent.append((subject, html_body, list(recipients)))


def _build_use_case(
    spike_repo, sender, lookback_hours=1, digest_type="hourly"
) -> SendStakeholderDigest:
    cluster_repo = InMemoryFeedbackClusterRepository()
    digest_log_repo = InMemoryDigestLogRepository()
    stakeholders = [
        Stakeholder(name="Eng", email="eng@example.com"),
        Stakeholder(name="PM", email="pm@example.com"),
    ]
    return SendStakeholderDigest(
        spike_event_repository=spike_repo,
        cluster_repository=cluster_repo,
        digest_log_repository=digest_log_repo,
        notification_sender=sender,
        stakeholders=stakeholders,
        lookback_hours=lookback_hours,
        digest_type=digest_type,
    )


def test_digest_with_no_spikes_still_sends_all_quiet():
    sender = _FakeSender()
    spike_repo = InMemorySpikeEventRepository()
    use_case = _build_use_case(spike_repo, sender)

    result = use_case.run()

    assert result.spikes_in_window == 0
    assert result.sent is True
    assert "all quiet" in sender.sent[0][0].lower() or "all quiet" in sender.sent[0][1].lower()


def test_recent_spikes_appear_in_html_body():
    sender = _FakeSender()
    spike_repo = InMemorySpikeEventRepository()
    cluster_repo = InMemoryFeedbackClusterRepository()
    cluster_id = uuid4()
    cluster_repo._clusters[cluster_id] = FeedbackCluster(
        id=cluster_id,
        embedding_centroid=[0.0],
        label="Stuck in login loop",
    )
    spike_repo.add(
        SpikeEvent(
            cluster_id=cluster_id,
            window_start=datetime.now(timezone.utc) - timedelta(minutes=30),
            window_end=datetime.now(timezone.utc),
            count=5,
            baseline=1.0,
            ratio=5.0,
        )
    )

    digest_log_repo = InMemoryDigestLogRepository()
    use_case = SendStakeholderDigest(
        spike_event_repository=spike_repo,
        cluster_repository=cluster_repo,
        digest_log_repository=digest_log_repo,
        notification_sender=sender,
        stakeholders=[Stakeholder(name="Eng", email="eng@example.com")],
        lookback_hours=1,
        digest_type="hourly",
    )
    result = use_case.run()

    assert result.spikes_in_window == 1
    body = sender.sent[0][1]
    assert "Stuck in login loop" in body
    assert "5.00×" in body
    assert len(digest_log_repo) == 1


def test_send_failure_is_recorded_in_digest_log():
    sender = _FakeSender()
    sender.raise_on_send = True
    spike_repo = InMemorySpikeEventRepository()
    digest_log_repo = InMemoryDigestLogRepository()
    use_case = SendStakeholderDigest(
        spike_event_repository=spike_repo,
        cluster_repository=InMemoryFeedbackClusterRepository(),
        digest_log_repository=digest_log_repo,
        notification_sender=sender,
        stakeholders=[Stakeholder(name="Eng", email="eng@example.com")],
        lookback_hours=1,
        digest_type="hourly",
    )

    result = use_case.run()

    assert result.sent is False
    assert "simulated SMTP failure" in result.error
    log_entries = list(digest_log_repo.list_recent(since=datetime.fromtimestamp(0, tz=timezone.utc)))
    assert len(log_entries) == 1
    assert "simulated SMTP failure" in log_entries[0].error
