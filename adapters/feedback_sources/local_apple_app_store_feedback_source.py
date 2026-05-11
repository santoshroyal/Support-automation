"""Local Apple App Store feedback source — reads JSON fixtures instead of calling App Store Connect.

One adapter instance is created per app. Every RawFeedback it produces is
tagged with the app's slug and `Platform.IOS` (App Store is iOS-only).

Each fixture file is a JSON document with this shape:

{
  "external_id": "apple_review_2026_05_04_001",
  "nickname": "ReadingFan",
  "star_rating": 2,
  "title": "Audio briefings won't play on iOS 17.4",
  "body": "Tapping play just spins forever. iPhone 14 Pro, latest version.",
  "received_at": "2026-05-04T08:30:00Z",
  "territory": "IND",
  "language_hint": "en",
  "app_version": "8.3.1"
}

The combined `text` we hand to the pipeline concatenates title + body so
the classifier and clustering see the full review.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from domain.app import App
from domain.feedback import FeedbackChannel, Platform, RawFeedback


class LocalAppleAppStoreFeedbackSource:
    channel: FeedbackChannel = FeedbackChannel.APPLE_APP_STORE

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
            platform=Platform.IOS,
            external_id=str(data["external_id"]),
            author_identifier=str(data.get("nickname", "Anonymous")),
            text=_compose_text(data),
            received_at=_parse_timestamp(data["received_at"]),
            metadata={
                "star_rating": data.get("star_rating"),
                "territory": data.get("territory"),
                "fixture_path": str(path),
            },
            language_hint=data.get("language_hint"),
            store_review_id=str(data["external_id"]),
            app_version=data.get("app_version"),
        )


def _compose_text(data: dict) -> str:
    title = data.get("title")
    body = data.get("body", "")
    if title:
        return f"{title}\n\n{body}".strip()
    return body


def _parse_timestamp(value: str) -> datetime:
    if value.endswith("Z"):
        value = value[:-1] + "+00:00"
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed
