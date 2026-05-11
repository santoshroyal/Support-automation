"""SyncKnowledgeBase exercised against fakes."""

from datetime import datetime, timezone
from typing import Iterable

from adapters.persistence.in_memory_knowledge_repository import (
    InMemoryKnowledgeRepository,
)
from adapters.retrieval.document_chunker import DocumentChunker
from domain.knowledge_document import KnowledgeDocument, KnowledgeSourceKind
from service_layer.use_cases.sync_knowledge_base import SyncKnowledgeBase


class _StaticConfluenceSource:
    kind = KnowledgeSourceKind.CONFLUENCE

    def __init__(self, documents: list[KnowledgeDocument]) -> None:
        self._documents = documents

    def fetch_updated(self, since) -> Iterable[KnowledgeDocument]:
        for doc in self._documents:
            if since is None or doc.last_updated_at > since:
                yield doc


class _ConstantEmbedder:
    """Returns a fixed unit-vector for every text. Good enough for unit tests."""

    dimension = 4

    def embed(self, text: str) -> list[float]:
        return [1.0, 0.0, 0.0, 0.0]

    def embed_batch(self, texts) -> list[list[float]]:
        return [self.embed(t) for t in texts]


def _doc(source_id: str, body: str) -> KnowledgeDocument:
    return KnowledgeDocument(
        source=KnowledgeSourceKind.CONFLUENCE,
        source_id=source_id,
        title=f"Doc {source_id}",
        raw_body=body,
        last_updated_at=datetime(2026, 5, 5, tzinfo=timezone.utc),
    )


def test_first_sync_inserts_documents_and_chunks():
    repo = InMemoryKnowledgeRepository()
    source = _StaticConfluenceSource(
        [_doc("A", "First doc body."), _doc("B", "Second doc body.")]
    )

    use_case = SyncKnowledgeBase(
        sources=[source],
        knowledge_repository=repo,
        embedding_model=_ConstantEmbedder(),
        chunker=DocumentChunker(chunk_size=200, chunk_overlap=20),
    )
    result = use_case.run()

    assert result.total_documents == 2
    assert result.total_chunks >= 2
    assert len(list(repo.list_documents())) == 2


def test_re_sync_replaces_chunks_for_existing_doc():
    repo = InMemoryKnowledgeRepository()

    source = _StaticConfluenceSource([_doc("A", "Original body content.")])
    SyncKnowledgeBase(
        sources=[source],
        knowledge_repository=repo,
        embedding_model=_ConstantEmbedder(),
        chunker=DocumentChunker(chunk_size=200, chunk_overlap=20),
    ).run()

    initial_chunk_count = repo.count_chunks()

    # Now the source returns the SAME doc id but with much longer body.
    longer = _doc("A", "Longer body. " * 100)  # ~1300 chars
    source_v2 = _StaticConfluenceSource([longer])
    SyncKnowledgeBase(
        sources=[source_v2],
        knowledge_repository=repo,
        embedding_model=_ConstantEmbedder(),
        chunker=DocumentChunker(chunk_size=200, chunk_overlap=20),
    ).run()

    # Same number of documents (upsert), but chunks should reflect the new body.
    assert len(list(repo.list_documents())) == 1
    assert repo.count_chunks() > initial_chunk_count


def test_per_source_counts_are_reported():
    repo = InMemoryKnowledgeRepository()
    source = _StaticConfluenceSource([_doc("A", "Body."), _doc("B", "Body.")])

    result = SyncKnowledgeBase(
        sources=[source],
        knowledge_repository=repo,
        embedding_model=_ConstantEmbedder(),
    ).run()

    assert result.per_source[0].source is KnowledgeSourceKind.CONFLUENCE
    assert result.per_source[0].documents_synced == 2
