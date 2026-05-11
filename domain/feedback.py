"""Feedback entity — the central artefact of the system.

A `Feedback` is one user-submitted piece of input from any inbound channel
(Gmail email, Google Play review, Apple App Store review). It is immutable
once ingested; classifications, clusters, and drafts are stored in separate
aggregates that reference it.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import UUID, uuid4


def _now() -> datetime:
    return datetime.now(timezone.utc)


class FeedbackChannel(str, Enum):
    GMAIL = "gmail"
    GOOGLE_PLAY = "google_play"
    APPLE_APP_STORE = "apple_app_store"


class Platform(str, Enum):
    """The mobile platform the user was on when they wrote the feedback.

    Store reviews always know their platform (Play = Android, App Store = iOS).
    Email feedback often doesn't say; we record `UNKNOWN` and let the classifier
    fill it in if the body mentions an OS or device.
    """

    ANDROID = "android"
    IOS = "ios"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class RawFeedback:
    """Channel-agnostic shape produced by every `FeedbackSourcePort.fetch_new()`.

    The persistence layer turns this into a `Feedback` row; nothing else in the
    pipeline ever sees raw API payloads.

    Every raw feedback carries `app_slug` and `platform` so the system always
    knows which Times Internet app and which mobile platform it relates to.
    """

    channel: FeedbackChannel
    app_slug: str
    platform: Platform
    external_id: str
    author_identifier: str
    text: str
    received_at: datetime
    metadata: dict[str, Any] = field(default_factory=dict)
    language_hint: str | None = None
    gmail_thread_id: str | None = None
    store_review_id: str | None = None
    app_version: str | None = None
    device_info: str | None = None


@dataclass
class Feedback:
    """Persisted feedback. The `id` is assigned by the repository on insert."""

    channel: FeedbackChannel
    app_slug: str
    platform: Platform
    external_id: str
    author_identifier: str
    raw_text: str
    received_at: datetime
    id: UUID = field(default_factory=uuid4)
    normalised_text: str | None = None
    language_code: str | None = None
    app_version: str | None = None
    device_info: str | None = None
    gmail_thread_id: str | None = None
    store_review_id: str | None = None
    created_at: datetime = field(default_factory=_now)

    @classmethod
    def from_raw(cls, raw: RawFeedback) -> Feedback:
        return cls(
            channel=raw.channel,
            app_slug=raw.app_slug,
            platform=raw.platform,
            external_id=raw.external_id,
            author_identifier=raw.author_identifier,
            raw_text=raw.text,
            received_at=raw.received_at,
            language_code=raw.language_hint,
            app_version=raw.app_version,
            device_info=raw.device_info,
            gmail_thread_id=raw.gmail_thread_id,
            store_review_id=raw.store_review_id,
        )

    @property
    def dedupe_key(self) -> tuple[FeedbackChannel, str, str]:
        """Uniqueness across (channel, app, external_id).

        Including app means the same `external_id` value could theoretically
        appear in two different apps' Play consoles without colliding. In
        practice external IDs are globally unique per channel, but scoping by
        app is the safer guarantee.
        """
        return (self.channel, self.app_slug, self.external_id)
