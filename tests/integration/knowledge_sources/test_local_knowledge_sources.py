"""Integration tests for the three local knowledge-source adapters.

These read the shipped fixtures so the test catches schema drift between
fixture format and adapter parser.
"""

from datetime import datetime, timezone
from pathlib import Path

from adapters.knowledge_sources.local_confluence_knowledge_source import (
    LocalConfluenceKnowledgeSource,
)
from adapters.knowledge_sources.local_google_sheets_knowledge_source import (
    LocalGoogleSheetsKnowledgeSource,
)
from adapters.knowledge_sources.local_jira_knowledge_source import (
    LocalJiraKnowledgeSource,
)
from domain.knowledge_document import KnowledgeSourceKind

_KNOWLEDGE_ROOT = (
    Path(__file__).resolve().parents[3] / "data_fixtures" / "knowledge"
)


def test_confluence_loads_all_shipped_pages():
    source = LocalConfluenceKnowledgeSource(fixtures_dir=_KNOWLEDGE_ROOT / "confluence")

    documents = list(source.fetch_updated(since=None))

    assert len(documents) >= 6
    for document in documents:
        assert document.source is KnowledgeSourceKind.CONFLUENCE
        assert document.source_id
        assert document.title
        assert document.raw_body
        assert document.last_updated_at.tzinfo is not None


def test_confluence_extracts_video_player_doc_correctly():
    source = LocalConfluenceKnowledgeSource(fixtures_dir=_KNOWLEDGE_ROOT / "confluence")

    docs = list(source.fetch_updated(since=None))
    video_doc = next(d for d in docs if "Video Player" in d.title)

    assert "iPhone 14" in video_doc.raw_body
    assert "TOI-4521" in video_doc.raw_body
    assert "v8.4" in video_doc.raw_body


def test_jira_loads_all_shipped_issues():
    source = LocalJiraKnowledgeSource(fixtures_dir=_KNOWLEDGE_ROOT / "jira")

    issues = list(source.fetch_updated(since=None))

    assert len(issues) >= 8
    for issue in issues:
        assert issue.source is KnowledgeSourceKind.JIRA
        # The body should include status info merged with the description.
        assert "Status:" in issue.raw_body


def test_jira_includes_fix_version_in_body():
    source = LocalJiraKnowledgeSource(fixtures_dir=_KNOWLEDGE_ROOT / "jira")

    issues = list(source.fetch_updated(since=None))
    toi_4521 = next(i for i in issues if i.source_id == "TOI-4521")

    assert "Fix versions: 8.4" in toi_4521.raw_body


def test_sheets_loads_csv_as_one_document():
    source = LocalGoogleSheetsKnowledgeSource(fixtures_dir=_KNOWLEDGE_ROOT / "sheets")

    documents = list(source.fetch_updated(since=None))

    assert len(documents) >= 1
    bug_tracker = next(d for d in documents if d.source_id == "bug_tracker")
    # Each CSV row should appear as a labelled paragraph in the body.
    assert "TOI-4521" in bug_tracker.raw_body
    assert "ET-2010" in bug_tracker.raw_body
    assert "NBT-1102" in bug_tracker.raw_body


def test_since_filter_excludes_old_docs():
    source = LocalConfluenceKnowledgeSource(fixtures_dir=_KNOWLEDGE_ROOT / "confluence")
    cutoff = datetime(2030, 1, 1, tzinfo=timezone.utc)

    assert list(source.fetch_updated(since=cutoff)) == []
