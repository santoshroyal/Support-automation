"""Knowledge-base health endpoint.

  GET /api/knowledge/sources   — per-source document count + freshness

Freshness thresholds are deliberately built into the API rather than the
UI, so two consumers (dashboard, future Slack bot) classify the same
state the same way. Confluence and JIRA are expected to sync every 90
minutes; Sheets daily. Thresholds are 4x and 16x the expected cadence
respectively, before the source is marked "very stale".

The endpoint never errors on an empty source — instead it returns
`freshness=empty`, since "no knowledge base yet" is different from "the
knowledge base is broken".
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends

from domain.knowledge_document import KnowledgeSourceKind
from entrypoints.web_api.dependencies import knowledge_repository
from entrypoints.web_api.schemas.knowledge_schema import (
    KnowledgeSourceFreshness,
    KnowledgeSourceHealth,
    KnowledgeSourcesResponse,
)
from service_layer.ports.knowledge_repository_port import KnowledgeRepositoryPort

router = APIRouter(prefix="/api", tags=["knowledge"])


@router.get("/knowledge/sources", response_model=KnowledgeSourcesResponse)
def list_knowledge_source_health(
    knowledge_repo: KnowledgeRepositoryPort = Depends(knowledge_repository),
) -> KnowledgeSourcesResponse:
    all_documents = list(knowledge_repo.list_documents())
    sources: list[KnowledgeSourceHealth] = []
    for source_kind in KnowledgeSourceKind:
        documents = [d for d in all_documents if d.source == source_kind]
        latest = max((d.last_updated_at for d in documents), default=None)
        sources.append(
            KnowledgeSourceHealth(
                source=source_kind.value,
                document_count=len(documents),
                latest_document_at=latest,
                freshness=_classify(source_kind, latest),
            )
        )
    return KnowledgeSourcesResponse(
        total_documents=len(all_documents),
        total_chunks=knowledge_repo.count_chunks(),
        sources=sources,
    )


# Per-source thresholds before a source is flagged stale.
# Confluence + JIRA sync every 90 min in prod; Sheets daily.
_STALE_THRESHOLDS: dict[KnowledgeSourceKind, tuple[timedelta, timedelta]] = {
    KnowledgeSourceKind.CONFLUENCE: (timedelta(hours=12), timedelta(hours=48)),
    KnowledgeSourceKind.JIRA: (timedelta(hours=12), timedelta(hours=48)),
    KnowledgeSourceKind.GOOGLE_SHEETS: (timedelta(days=2), timedelta(days=7)),
}


def _classify(
    source: KnowledgeSourceKind, latest: datetime | None
) -> KnowledgeSourceFreshness:
    if latest is None:
        return KnowledgeSourceFreshness.EMPTY
    age = datetime.now(timezone.utc) - _ensure_utc(latest)
    stale_after, very_stale_after = _STALE_THRESHOLDS[source]
    if age >= very_stale_after:
        return KnowledgeSourceFreshness.VERY_STALE
    if age >= stale_after:
        return KnowledgeSourceFreshness.STALE
    return KnowledgeSourceFreshness.FRESH


def _ensure_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value
