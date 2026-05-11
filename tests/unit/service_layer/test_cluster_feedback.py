"""ClusterFeedback exercised against fake adapters.

Uses a deterministic fake embedder that keys off keywords in the text so
we can predict which feedbacks should cluster together without needing
a real ML model in the test.
"""

from datetime import datetime, timezone

from adapters.persistence.in_memory_feedback_cluster_repository import (
    InMemoryFeedbackClusterRepository,
)
from adapters.persistence.in_memory_feedback_repository import InMemoryFeedbackRepository
from domain.feedback import Feedback, FeedbackChannel, Platform
from service_layer.use_cases.cluster_feedback import ClusterFeedback


class _KeywordEmbedder:
    """Deterministic embedder: each keyword gets a unique unit vector.

    Texts containing the same keyword(s) end up identical in vector space,
    so clustering the keyword groups them together regardless of any
    surrounding text.
    """

    KEYWORDS = ["video", "paywall", "otp", "font", "market"]
    dimension = len(KEYWORDS)

    def embed(self, text: str) -> list[float]:
        vector = [0.0] * len(self.KEYWORDS)
        lower = text.lower()
        for index, keyword in enumerate(self.KEYWORDS):
            if keyword in lower:
                vector[index] = 1.0
        # Normalise so cosine similarity is meaningful.
        magnitude = sum(value * value for value in vector) ** 0.5
        if magnitude == 0.0:
            # Sentinel "other" direction — never matches keyword vectors.
            vector[0] = 0.0
            return [1.0 if i == len(self.KEYWORDS) - 1 else 0.0 for i in range(len(self.KEYWORDS))]
        return [v / magnitude for v in vector]

    def embed_batch(self, texts):
        return [self.embed(t) for t in texts]


def _feedback(text: str, app="toi", channel=FeedbackChannel.GMAIL) -> Feedback:
    return Feedback(
        channel=channel,
        app_slug=app,
        platform=Platform.UNKNOWN,
        external_id=f"id_{abs(hash(text)) % 10_000_000}",
        author_identifier="user@example.com",
        raw_text=text,
        received_at=datetime(2026, 5, 5, tzinfo=timezone.utc),
    )


def test_two_feedbacks_about_the_same_issue_cluster_together():
    feedback_repo = InMemoryFeedbackRepository()
    cluster_repo = InMemoryFeedbackClusterRepository()

    a = _feedback("Video player keeps crashing on iPhone")
    b = _feedback("Video crashes every time, please fix", channel=FeedbackChannel.GOOGLE_PLAY)
    for f in (a, b):
        feedback_repo.add(f)

    use_case = ClusterFeedback(
        feedback_repository=feedback_repo,
        cluster_repository=cluster_repo,
        embedding_model=_KeywordEmbedder(),
    )
    result = use_case.run()

    assert result.clustered == 2
    assert result.new_clusters == 1  # second feedback joined the first's cluster
    clusters = list(cluster_repo.list_clusters())
    assert len(clusters) == 1
    assert clusters[0].member_count == 2


def test_different_issues_create_different_clusters():
    feedback_repo = InMemoryFeedbackRepository()
    cluster_repo = InMemoryFeedbackClusterRepository()

    feedback_repo.add(_feedback("Video player crash"))
    feedback_repo.add(_feedback("Paywall after payment"))
    feedback_repo.add(_feedback("OTP not received"))

    use_case = ClusterFeedback(
        feedback_repository=feedback_repo,
        cluster_repository=cluster_repo,
        embedding_model=_KeywordEmbedder(),
    )
    result = use_case.run()

    assert result.clustered == 3
    assert result.new_clusters == 3
    assert len(list(cluster_repo.list_clusters())) == 3


def test_already_clustered_feedback_is_skipped():
    feedback_repo = InMemoryFeedbackRepository()
    cluster_repo = InMemoryFeedbackClusterRepository()
    feedback_repo.add(_feedback("Video crash"))

    use_case = ClusterFeedback(
        feedback_repository=feedback_repo,
        cluster_repository=cluster_repo,
        embedding_model=_KeywordEmbedder(),
    )
    use_case.run()
    second = use_case.run()

    assert second.clustered == 0
    assert second.skipped_already_clustered == 1


def test_threshold_controls_strictness():
    feedback_repo = InMemoryFeedbackRepository()
    cluster_repo = InMemoryFeedbackClusterRepository()

    feedback_repo.add(_feedback("Video crash"))
    # Loose threshold (0.0) — anything joins the existing cluster.
    feedback_repo.add(_feedback("Paywall after payment"))

    use_case = ClusterFeedback(
        feedback_repository=feedback_repo,
        cluster_repository=cluster_repo,
        embedding_model=_KeywordEmbedder(),
        similarity_threshold=0.0,
    )
    result = use_case.run()

    assert result.clustered == 2
    assert result.new_clusters == 1  # only the first; second joined it
