"""Hybrid knowledge retriever — vector + lexical with reciprocal rank fusion.

Phase 1c-2 (matches plan section 8 + ADR-012):

  1. Embed the query with the local multilingual-e5 model.
  2. Vector top-K  (default 20) — semantic similarity via pgvector cosine.
  3. Lexical top-K (default 20) — full-text search via PostgreSQL tsvector.
  4. Merge via reciprocal rank fusion:
        score(chunk) = sum over indexes of 1 / (rrf_k + rank_in_that_index)
     The default rrf_k = 60 is the value the original RRF paper uses; it
     reasonably balances "high in one index" against "in both indexes".
  5. Return the top-N (default 8) RetrievedChunk records — that's what
     the drafter feeds the language model along with the user's complaint.

Why both signals: the vector index catches Hindi-vs-English paraphrases
and synonym matches; the lexical index catches the exact tokens that
embedding similarity misses (ticket IDs `TOI-4521`, version strings
`v8.4`, error messages, model numbers).

Each RetrievedChunk carries the citation breadcrumb the drafter pastes
into its reply (source URL, source title, snippet) so support staff can
verify every claim.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Iterable
from uuid import UUID

from adapters.retrieval._chunk_row import CandidateRow
from adapters.retrieval.lexical_index import LexicalIndex
from adapters.retrieval.vector_index import VectorIndex
from service_layer.ports.embedding_model_port import EmbeddingModelPort
from service_layer.ports.knowledge_retriever_port import RetrievedChunk

_RRF_K = 60


class HybridKnowledgeRetriever:
    def __init__(
        self,
        embedding_model: EmbeddingModelPort,
        vector_index: VectorIndex | None = None,
        lexical_index: LexicalIndex | None = None,
        candidate_top_k: int = 20,
    ) -> None:
        self._embedding_model = embedding_model
        self._vector_index = vector_index or VectorIndex()
        self._lexical_index = lexical_index or LexicalIndex()
        self._candidate_top_k = candidate_top_k

    def retrieve(self, query_text: str, top_k: int = 8) -> Iterable[RetrievedChunk]:
        query = (query_text or "").strip()
        if not query:
            return []

        embedding = self._embedding_model.embed(query)
        vector_rows = list(self._vector_index.top_k(embedding, self._candidate_top_k))
        lexical_rows = list(self._lexical_index.top_k(query, self._candidate_top_k))

        return _fuse(vector_rows, lexical_rows, top_k=top_k)


def _fuse(
    vector_rows: list[CandidateRow],
    lexical_rows: list[CandidateRow],
    top_k: int,
) -> list[RetrievedChunk]:
    scores: dict[UUID, float] = defaultdict(float)
    rows_by_id: dict[UUID, CandidateRow] = {}

    for row in vector_rows:
        scores[row.knowledge_chunk_id] += 1.0 / (_RRF_K + row.rank)
        rows_by_id.setdefault(row.knowledge_chunk_id, row)

    for row in lexical_rows:
        scores[row.knowledge_chunk_id] += 1.0 / (_RRF_K + row.rank)
        # Don't overwrite a vector-row entry; both rows reference the same
        # underlying chunk, the citation metadata is identical.
        rows_by_id.setdefault(row.knowledge_chunk_id, row)

    ranked = sorted(scores.items(), key=lambda item: item[1], reverse=True)
    out: list[RetrievedChunk] = []
    for chunk_id, score in ranked[:top_k]:
        row = rows_by_id[chunk_id]
        out.append(
            RetrievedChunk(
                knowledge_chunk_id=row.knowledge_chunk_id,
                knowledge_document_id=row.knowledge_document_id,
                content=row.content,
                source_url=row.source_url,
                source_title=row.source_title,
                score=score,
            )
        )
    return out
