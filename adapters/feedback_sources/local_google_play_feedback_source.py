"""Local Google Play feedback source — reads JSON fixtures instead of calling Play Developer API.

One adapter instance is created per app. Every RawFeedback it produces is
tagged with the app's slug and `Platform.ANDROID` (Play is Android-only).

Each fixture file is a JSON document with this shape:

{
  "external_id": "play_review_2026_05_04_001",
  "author": "A Google user",
  "star_rating": 1,
  "text": "App keeps crashing on Pixel 7 after the latest update.",
  "received_at": "2026-05-04T07:42:00Z",
  "language_hint": "en",
  "app_version": "8.3.1",
  "device_model": "Pixel 7",
  "android_version": "14"
}
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from domain.app import App
from domain.feedback import FeedbackChannel, Platform, RawFeedback


class LocalGooglePlayFeedbackSource:
    channel: FeedbackChannel = FeedbackChannel.GOOGLE_PLAY

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
            platform=Platform.ANDROID,
            external_id=str(data["external_id"]),
            author_identifier=str(data.get("author", "A Google user")),
            text=str(data["text"]),
            received_at=_parse_timestamp(data["received_at"]),
            metadata={
                "star_rating": data.get("star_rating"),
                "android_version": data.get("android_version"),
                "fixture_path": str(path),
            },
            language_hint=data.get("language_hint"),
            store_review_id=str(data["external_id"]),
            app_version=data.get("app_version"),
            device_info=data.get("device_model"),
        )


def _parse_timestamp(value: str) -> datetime:
    if value.endswith("Z"):
        value = value[:-1] + "+00:00"
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed
