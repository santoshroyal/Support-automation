"""Local JIRA knowledge source — reads simplified JIRA issue JSON fixtures.

Each file in `data_fixtures/knowledge/jira/` has the shape:

    {
      "key": "TOI-4521",
      "summary": "...",
      "description": "...",
      "status": "In Progress",
      "priority": "High",
      "fix_versions": ["8.4"],
      "components": ["iOS", "Video Player"],
      "assignee": "...",
      "reporter": "...",
      "created": "2026-04-21T10:15:00Z",
      "updated": "2026-05-04T11:30:00Z",
      "url": "https://...",
      "labels": ["customer-impact"]
    }

The adapter formats the issue's structured fields into a single readable
`raw_body` so the chunker / retriever / drafter all see the same bundled
context (status + fix version + summary + description), which is the
shape that matters for matching incoming feedback.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from domain.knowledge_document import KnowledgeDocument, KnowledgeSourceKind


class LocalJiraKnowledgeSource:
    kind: KnowledgeSourceKind = KnowledgeSourceKind.JIRA

    def __init__(self, fixtures_dir: Path) -> None:
        self._fixtures_dir = fixtures_dir

    def fetch_updated(self, since: datetime | None) -> Iterable[KnowledgeDocument]:
        if not self._fixtures_dir.exists():
            return
        for path in sorted(self._fixtures_dir.glob("*.json")):
            document = self._load(path)
            if since is not None and document.last_updated_at <= since:
                continue
            yield document

    def _load(self, path: Path) -> KnowledgeDocument:
        data = json.loads(path.read_text(encoding="utf-8"))
        body = _format_issue_body(data)
        return KnowledgeDocument(
            source=self.kind,
            source_id=str(data["key"]),
            title=f"{data['key']}: {data.get('summary', '').strip()}",
            raw_body=body,
            source_url=data.get("url"),
            last_updated_at=_parse_timestamp(data.get("updated") or data["created"]),
        )


def _format_issue_body(data: dict) -> str:
    lines = [
        f"Status: {data.get('status', 'Unknown')}",
        f"Priority: {data.get('priority', 'Unknown')}",
    ]
    fix_versions = data.get("fix_versions") or []
    if fix_versions:
        lines.append(f"Fix versions: {', '.join(fix_versions)}")
    components = data.get("components") or []
    if components:
        lines.append(f"Components: {', '.join(components)}")
    assignee = data.get("assignee")
    if assignee:
        lines.append(f"Assignee: {assignee}")
    if data.get("resolution"):
        lines.append(f"Resolution: {data['resolution']}")

    summary = (data.get("summary") or "").strip()
    if summary:
        lines.append("")
        lines.append(f"Summary: {summary}")

    description = (data.get("description") or "").strip()
    if description:
        lines.append("")
        lines.append(description)

    return "\n".join(lines)


def _parse_timestamp(value: str) -> datetime:
    if value.endswith("Z"):
        value = value[:-1] + "+00:00"
    parsed = datetime.fromisoformat(value)
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
