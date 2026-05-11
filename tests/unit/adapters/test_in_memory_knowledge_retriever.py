"""InMemoryKnowledgeRetriever — used in unit tests for use cases that depend on retrieval."""

from uuid import uuid4

from adapters.retrieval.in_memory_knowledge_retriever import InMemoryKnowledgeRetriever


class _KeywordEmbedder:
    """Deterministic embedder: each keyword toggles a dimension on."""

    KEYWORDS = ["video", "paywall", "otp", "font", "market"]
    dimension = len(KEYWORDS)

    def embed(self, text: str) -> list[float]:
        lower = text.lower()
        vector = [1.0 if keyword in lower else 0.0 for keyword in self.KEYWORDS]
        magnitude = sum(v * v for v in vector) ** 0.5
        if magnitude == 0:
            return [0.0] * self.dimension
        return [v / magnitude for v in vector]

    def embed_batch(self, texts):
        return [self.embed(t) for t in texts]


def test_returns_chunk_with_matching_keyword_first():
    retriever = InMemoryKnowledgeRetriever(_KeywordEmbedder())
    video_chunk = uuid4()
    paywall_chunk = uuid4()

    retriever.index(
        knowledge_chunk_id=video_chunk,
        knowledge_document_id=uuid4(),
        content="The video player keeps crashing on iOS 17.4.",
        source_url="https://example.com/video",
        source_title="Video Player",
    )
    retriever.index(
        knowledge_chunk_id=paywall_chunk,
        knowledge_document_id=uuid4(),
        content="TOI Plus paywall persists after a successful payment.",
        source_url="https://example.com/paywall",
        source_title="Paywall",
    )

    results = list(retriever.retrieve("video crash on iPhone", top_k=1))

    assert len(results) == 1
    assert results[0].knowledge_chunk_id == video_chunk
    assert results[0].source_title == "Video Player"


def test_top_k_caps_results():
    retriever = InMemoryKnowledgeRetriever(_KeywordEmbedder())
    for keyword in _KeywordEmbedder.KEYWORDS:
        retriever.index(
            knowledge_chunk_id=uuid4(),
            knowledge_document_id=uuid4(),
            content=f"A document about {keyword}.",
            source_title=keyword.title(),
        )

    results = list(retriever.retrieve("video paywall otp", top_k=2))

    assert len(results) == 2


def test_empty_query_returns_no_results():
    retriever = InMemoryKnowledgeRetriever(_KeywordEmbedder())
    retriever.index(
        knowledge_chunk_id=uuid4(),
        knowledge_document_id=uuid4(),
        content="Anything.",
    )

    assert list(retriever.retrieve("", top_k=8)) == []
    assert list(retriever.retrieve("   ", top_k=8)) == []


def test_empty_index_returns_no_results():
    retriever = InMemoryKnowledgeRetriever(_KeywordEmbedder())

    assert list(retriever.retrieve("video", top_k=8)) == []
