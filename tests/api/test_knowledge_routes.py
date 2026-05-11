"""Knowledge-source health endpoint."""

from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from adapters.persistence.in_memory_knowledge_repository import (
    InMemoryKnowledgeRepository,
)
from domain.knowledge_document import (
    KnowledgeChunk,
    KnowledgeDocument,
    KnowledgeSourceKind,
)
from entrypoints.composition_root import reset_app_for_tests
from entrypoints.web_api.dependencies import knowledge_repository
from entrypoints.web_api.main import create_app


@pytest.fixture
def seeded_repo():
    repo = InMemoryKnowledgeRepository()
    now = datetime.now(timezone.utc)

    fresh_doc = KnowledgeDocument(
        source=KnowledgeSourceKind.CONFLUENCE,
        source_id="page-1",
        title="Fresh Confluence page",
        raw_body="Fresh content",
        last_updated_at=now - timedelta(hours=2),
    )
    stale_doc = KnowledgeDocument(
        source=KnowledgeSourceKind.JIRA,
        source_id="JIRA-1",
        title="Stale JIRA",
        raw_body="Old",
        last_updated_at=now - timedelta(hours=20),
    )
    very_stale_doc = KnowledgeDocument(
        source=KnowledgeSourceKind.GOOGLE_SHEETS,
        source_id="sheet-1",
        title="Very stale sheet",
        raw_body="Ancient",
        last_updated_at=now - timedelta(days=10),
    )
    repo.upsert_document(fresh_doc)
    repo.upsert_document(stale_doc)
    repo.upsert_document(very_stale_doc)
    repo.replace_chunks(
        fresh_doc.id,
        [
            KnowledgeChunk(
                knowledge_document_id=fresh_doc.id,
                chunk_index=0,
                content="hi",
                embedding=[0.0] * 768,
            )
        ],
    )
    return repo


def _client(repo):
    reset_app_for_tests()
    app = create_app()
    app.dependency_overrides[knowledge_repository] = lambda: repo
    return TestClient(app)


def test_returns_one_entry_per_source_kind(seeded_repo):
    client = _client(seeded_repo)

    response = client.get("/api/knowledge/sources")

    assert response.status_code == 200
    body = response.json()
    sources_by_kind = {entry["source"]: entry for entry in body["sources"]}
    assert set(sources_by_kind) == {"confluence", "jira", "google_sheets"}


def test_freshness_classification_matches_age(seeded_repo):
    client = _client(seeded_repo)

    response = client.get("/api/knowledge/sources")

    by_kind = {entry["source"]: entry for entry in response.json()["sources"]}
    assert by_kind["confluence"]["freshness"] == "fresh"
    assert by_kind["jira"]["freshness"] == "stale"
    assert by_kind["google_sheets"]["freshness"] == "very_stale"


def test_totals_match_seeded_state(seeded_repo):
    client = _client(seeded_repo)

    response = client.get("/api/knowledge/sources")

    body = response.json()
    assert body["total_documents"] == 3
    assert body["total_chunks"] == 1


def test_empty_source_is_classified_empty():
    empty_repo = InMemoryKnowledgeRepository()
    client = _client(empty_repo)

    response = client.get("/api/knowledge/sources")

    body = response.json()
    assert body["total_documents"] == 0
    for entry in body["sources"]:
        assert entry["freshness"] == "empty"
        assert entry["document_count"] == 0
