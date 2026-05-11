"""Local Google Sheets knowledge source — reads CSV fixtures.

Each CSV file in `data_fixtures/knowledge/sheets/` becomes ONE
`KnowledgeDocument` with a body that lays out every row as a Markdown
table-style block. The retriever can then surface the whole tracker as a
unit when a query matches any row.

Why one document per CSV (rather than one per row): support staff
typically refer to the bug tracker as a single artefact ("see the master
bug tracker for ETAs"), and chunking the body re-splits it into
search-friendly pieces anyway.
"""

from __future__ import annotations

import csv
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from domain.knowledge_document import KnowledgeDocument, KnowledgeSourceKind


class LocalGoogleSheetsKnowledgeSource:
    kind: KnowledgeSourceKind = KnowledgeSourceKind.GOOGLE_SHEETS

    def __init__(self, fixtures_dir: Path) -> None:
        self._fixtures_dir = fixtures_dir

    def fetch_updated(self, since: datetime | None) -> Iterable[KnowledgeDocument]:
        if not self._fixtures_dir.exists():
            return
        for path in sorted(self._fixtures_dir.glob("*.csv")):
            # Use file mtime as the "last updated" signal — fixtures don't
            # carry their own timestamps. The real Sheets adapter uses the
            # `modifiedTime` from the Drive API.
            mtime = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
            if since is not None and mtime <= since:
                continue
            yield self._load(path, mtime)

    def _load(self, path: Path, modified_at: datetime) -> KnowledgeDocument:
        with path.open(encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            rows = list(reader)
            headers = reader.fieldnames or []

        body = _format_sheet(headers, rows, title=path.stem)
        return KnowledgeDocument(
            source=self.kind,
            source_id=path.stem,
            title=path.stem.replace("_", " ").title(),
            raw_body=body,
            source_url=None,
            last_updated_at=modified_at,
        )


def _format_sheet(headers: list[str], rows: list[dict], title: str) -> str:
    """Render the sheet as a small descriptive text block per row."""
    if not headers or not rows:
        return f"# {title}\n\n(empty sheet)"

    lines = [f"# {title.replace('_', ' ').title()}", ""]
    for row in rows:
        # Each row becomes a labelled paragraph so chunking can keep a row intact.
        cells = [f"{header}: {row.get(header, '').strip()}" for header in headers if row.get(header)]
        lines.append(" | ".join(cells))
        lines.append("")
    return "\n".join(lines).strip()
