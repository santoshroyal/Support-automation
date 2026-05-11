"""Local Confluence knowledge source — reads Markdown fixtures with YAML frontmatter.

Each file in `data_fixtures/knowledge/confluence/` has this shape:

    ---
    source: confluence
    source_id: TOI-FAQ-001
    title: Video Player Troubleshooting (TOI app)
    space: TOI
    url: https://...
    last_updated_at: 2026-05-02T11:30:00Z
    labels: [public-support, video]
    ---

    # Markdown body...

The adapter yields one `KnowledgeDocument` per file. The file's frontmatter
metadata becomes the document's identifying fields; the body is everything
after the closing `---`.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

import yaml

from domain.knowledge_document import KnowledgeDocument, KnowledgeSourceKind


class LocalConfluenceKnowledgeSource:
    kind: KnowledgeSourceKind = KnowledgeSourceKind.CONFLUENCE

    def __init__(self, fixtures_dir: Path) -> None:
        self._fixtures_dir = fixtures_dir

    def fetch_updated(self, since: datetime | None) -> Iterable[KnowledgeDocument]:
        if not self._fixtures_dir.exists():
            return
        for path in sorted(self._fixtures_dir.glob("*.md")):
            document = self._load(path)
            if since is not None and document.last_updated_at <= since:
                continue
            yield document

    def _load(self, path: Path) -> KnowledgeDocument:
        text = path.read_text(encoding="utf-8")
        frontmatter, body = _split_frontmatter(text)
        return KnowledgeDocument(
            source=self.kind,
            source_id=str(frontmatter["source_id"]),
            title=str(frontmatter["title"]),
            raw_body=body.strip(),
            source_url=frontmatter.get("url"),
            last_updated_at=_parse_timestamp(frontmatter["last_updated_at"]),
        )


def _split_frontmatter(text: str) -> tuple[dict, str]:
    """Split a `--- ... ---\\n<body>` Markdown file into (frontmatter dict, body)."""
    if not text.startswith("---"):
        raise ValueError("Confluence fixture missing YAML frontmatter (expected leading '---').")
    parts = text.split("---", 2)
    if len(parts) < 3:
        raise ValueError("Confluence fixture has malformed frontmatter (no closing '---').")
    frontmatter = yaml.safe_load(parts[1]) or {}
    body = parts[2].lstrip("\n")
    return frontmatter, body


def _parse_timestamp(value) -> datetime:
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    text = str(value)
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    parsed = datetime.fromisoformat(text)
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
