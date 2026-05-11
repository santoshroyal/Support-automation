"""HybridKnowledgeRetriever — exercise RRF fusion logic with fake indexes.

Tests the merge math without spinning up Postgres.
"""

from uuid import UUID, uuid4

from adapters.retrieval._chunk_row import CandidateRow
from adapters.retrieval.hybrid_retriever import HybridKnowledgeRetriever


class _FakeEmbedder:
    dimension = 4

    def embed(self, text: str) -> list[float]:
        return [1.0, 0.0, 0.0, 0.0]

    def embed_batch(self, texts):
        return [self.embed(t) for t in texts]


class _StaticIndex:
    def __init__(self, rows: list[CandidateRow]) -> None:
        self._rows = rows
        self.last_query = None

    def top_k(self, query, k):
        self.last_query = query
        return self._rows[:k]


def _row(*, chunk_id: UUID, rank: int, title: str = "doc") -> CandidateRow:
    return CandidateRow(
        knowledge_chunk_id=chunk_id,
        knowledge_document_id=uuid4(),
        content=f"chunk {rank}",
        source="confluence",
        source_id="ID",
        source_url="https://example.com",
        source_title=title,
        rank=rank,
        raw_score=0.0,
    )


def test_chunk_in_both_indexes_outranks_chunk_in_one():
    shared = uuid4()
    only_vector = uuid4()
    vector_rows = [_row(chunk_id=shared, rank=1), _row(chunk_id=only_vector, rank=2)]
    lexical_rows = [_row(chunk_id=shared, rank=1)]

    retriever = HybridKnowledgeRetriever(
        embedding_model=_FakeEmbedder(),
        vector_index=_StaticIndex(vector_rows),
        lexical_index=_StaticIndex(lexical_rows),
    )

    results = list(retriever.retrieve("anything", top_k=2))

    assert len(results) == 2
    assert results[0].knowledge_chunk_id == shared  # appeared in both → highest score
    assert results[1].knowledge_chunk_id == only_vector


def test_top_k_caps_results():
    rows = [_row(chunk_id=uuid4(), rank=index + 1) for index in range(20)]

    retriever = HybridKnowledgeRetriever(
        embedding_model=_FakeEmbedder(),
        vector_index=_StaticIndex(rows),
        lexical_index=_StaticIndex([]),
    )

    results = list(retriever.retrieve("query", top_k=5))

    assert len(results) == 5


def test_empty_query_short_circuits():
    retriever = HybridKnowledgeRetriever(
        embedding_model=_FakeEmbedder(),
        vector_index=_StaticIndex([_row(chunk_id=uuid4(), rank=1)]),
        lexical_index=_StaticIndex([_row(chunk_id=uuid4(), rank=1)]),
    )

    assert list(retriever.retrieve("", top_k=8)) == []


def test_score_is_returned():
    chunk_id = uuid4()
    retriever = HybridKnowledgeRetriever(
        embedding_model=_FakeEmbedder(),
        vector_index=_StaticIndex([_row(chunk_id=chunk_id, rank=1)]),
        lexical_index=_StaticIndex([_row(chunk_id=chunk_id, rank=1)]),
    )

    [result] = list(retriever.retrieve("query", top_k=1))

    # Two rank-1 hits with RRF k=60 → 2 * (1 / 61).
    expected = 2 * (1 / 61)
    assert abs(result.score - expected) < 1e-9
