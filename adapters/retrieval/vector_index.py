"""Vector similarity search over knowledge_chunk.

Uses pgvector's `cosine_distance` (the `<=>` operator) ordered ascending
— the smaller the distance, the more similar. The HNSW index built on
`knowledge_chunk.embedding` makes this fast at production scale. Returns
the top-K chunks plus the document metadata the citation builder will
need (source, source_id, source_url, title).
"""

from __future__ import annotations

from typing import Iterable

from sqlalchemy import select

from adapters.persistence.database import session_scope
from adapters.persistence.orm_models import KnowledgeChunkOrm, KnowledgeDocumentOrm
from adapters.retrieval._chunk_row import CandidateRow


class VectorIndex:
    def top_k(self, query_embedding: list[float], k: int) -> Iterable[CandidateRow]:
        with session_scope() as session:
            distance = KnowledgeChunkOrm.embedding.cosine_distance(query_embedding)
            statement = (
                select(
                    KnowledgeChunkOrm.id,
                    KnowledgeChunkOrm.knowledge_document_id,
                    KnowledgeChunkOrm.content,
                    KnowledgeDocumentOrm.source,
                    KnowledgeDocumentOrm.source_id,
                    KnowledgeDocumentOrm.source_url,
                    KnowledgeDocumentOrm.title,
                    distance.label("distance"),
                )
                .join(
                    KnowledgeDocumentOrm,
                    KnowledgeDocumentOrm.id == KnowledgeChunkOrm.knowledge_document_id,
                )
                .where(KnowledgeChunkOrm.embedding.is_not(None))
                .order_by(distance.asc())
                .limit(k)
            )
            rows = session.execute(statement).all()

        return [
            CandidateRow(
                knowledge_chunk_id=row[0],
                knowledge_document_id=row[1],
                content=row[2],
                source=row[3],
                source_id=row[4],
                source_url=row[5],
                source_title=row[6],
                rank=index + 1,
                raw_score=float(row[7]),
            )
            for index, row in enumerate(rows)
        ]
