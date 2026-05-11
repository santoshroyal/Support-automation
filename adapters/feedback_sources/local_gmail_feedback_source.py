"""Local Gmail feedback source — reads JSON fixtures instead of calling the Gmail API.

One adapter instance is created per app whose Gmail feedback we want to ingest.
The adapter is constructed with that app and the path to its fixture folder
(e.g. `data_fixtures/feedback/gmail/toi/`). Every RawFeedback it produces is
tagged with the right `app_slug`. Email platform is `UNKNOWN` at ingestion;
the classifier may infer it later from the body.

Each fixture file is a JSON document with this shape:

{
  "external_id": "msg_abc123",
  "thread_id": "thread_xyz",
  "from": "user@example.com",
  "subject": "App keeps crashing",
  "body": "...",
  "received_at": "2026-04-30T11:30:00Z",
  "language_hint": "en",
  "app_version": "8.3.1",
  "device": "Pixel 7"
}
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from domain.app import App
from domain.feedback import FeedbackChannel, Platform, RawFeedback


class LocalGmailFeedbackSource:
    channel: FeedbackChannel = FeedbackChannel.GMAIL

    def __init__(self, app: App, fixtures_dir: Path) -> None:
        self._app = app
        self._fixtures_dir = fixtures_dir

    @property
    def app_slug(self) -> str:
        return self._app.slug

    def fetch_new(self, since: datetime | None) -> Iterable[RawFeedback]:
        if not self._fixtures_dir.exists():
            return
        for path in sorted(self._fixtures_dir.glob("*.json")):
            raw = self._load(path)
            if since is not None and raw.received_at <= since:
                continue
            yield raw

    def _load(self, path: Path) -> RawFeedback:
        data = json.loads(path.read_text(encoding="utf-8"))
        return RawFeedback(
            channel=self.channel,
            app_slug=self._app.slug,
            platform=Platform.UNKNOWN,
            external_id=str(data["external_id"]),
            author_identifier=str(data.get("from", "unknown@example.com")),
            text=_compose_text(data),
            received_at=_parse_timestamp(data["received_at"]),
            metadata={
                "subject": data.get("subject"),
                "fixture_path": str(path),
            },
            language_hint=data.get("language_hint"),
            gmail_thread_id=data.get("thread_id"),
            app_version=data.get("app_version"),
            device_info=data.get("device"),
        )


def _compose_text(data: dict) -> str:
    subject = data.get("subject")
    body = data.get("body", "")
    if subject:
        return f"Subject: {subject}\n\n{body}"
    return body


def _parse_timestamp(value: str) -> datetime:
    if value.endswith("Z"):
        value = value[:-1] + "+00:00"
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed
