"""Classification — LLM-derived structured fields for a single Feedback."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import UUID


def _now() -> datetime:
    return datetime.now(timezone.utc)


class FeedbackCategory(str, Enum):
    BUG = "bug"
    FEATURE_REQUEST = "feature_request"
    CONTENT_QUALITY = "content_quality"
    SUBSCRIPTION_BILLING = "subscription_billing"
    LOGIN_ACCOUNT = "login_account"
    USABILITY = "usability"
    PERFORMANCE = "performance"
    PRAISE = "praise"
    OTHER = "other"


class Severity(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class Sentiment(str, Enum):
    NEGATIVE = "negative"
    NEUTRAL = "neutral"
    POSITIVE = "positive"


@dataclass
class Classification:
    feedback_id: UUID
    category: FeedbackCategory
    severity: Severity
    sentiment: Sentiment
    sub_category: str | None = None
    entities: dict[str, Any] = field(default_factory=dict)
    requires_followup: bool = True
    language_model_used: str = "unknown"
    classified_at: datetime = field(default_factory=_now)
