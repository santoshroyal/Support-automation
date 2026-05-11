"""Lexical full-text search over knowledge_chunk.

Builds a `tsquery` from the user's query string with `plainto_tsquery`,
which is forgiving — it strips punctuation and joins terms with `&`,
so "video player crash" matches a chunk containing "...the video player
crashes...". Filters chunks via the `@@` operator and ranks them by
`ts_rank`.

The 'simple' configuration (matching the generated `content_tsvector`
on the chunk table) gives us exact-token matches without
language-specific stemming — important for ticket IDs (`TOI-4521`) and
version numbers (`v8.4`) that English stemmers would mangle.
"""

from __future__ import annotations

from typing import Iterable

from sqlalchemy import func, select

from adapters.persistence.database import session_scope
from adapters.persistence.orm_models import KnowledgeChunkOrm, KnowledgeDocumentOrm
from adapters.retrieval._chunk_row import CandidateRow


class LexicalIndex:
    def top_k(self, query_text: str, k: int) -> Iterable[CandidateRow]:
        if not query_text or not query_text.strip():
            return []

        with session_scope() as session:
            tsquery = func.plainto_tsquery("simple", query_text)
            rank = func.ts_rank(KnowledgeChunkOrm.content_tsvector, tsquery)
            statement = (
                select(
                    KnowledgeChunkOrm.id,
                    KnowledgeChunkOrm.knowledge_document_id,
                    KnowledgeChunkOrm.content,
                    KnowledgeDocumentOrm.source,
                    KnowledgeDocumentOrm.source_id,
                    KnowledgeDocumentOrm.source_url,
                    KnowledgeDocumentOrm.title,
                    rank.label("rank_value"),
                )
                .join(
                    KnowledgeDocumentOrm,
                    KnowledgeDocumentOrm.id == KnowledgeChunkOrm.knowledge_document_id,
                )
                .where(KnowledgeChunkOrm.content_tsvector.op("@@")(tsquery))
                .order_by(rank.desc())
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
