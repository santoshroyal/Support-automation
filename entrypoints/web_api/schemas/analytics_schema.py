"""Analytics-endpoint response schemas.

The analytics endpoints answer two questions the dashboard asks first:

  - "How much feedback came in, day by day?"  →  `VolumeResponse`
  - "What were people complaining about?"      →  `CategoriesResponse`

Both are bounded read-only aggregations over the feedback table and the
classification table. They group by day in UTC; the dashboard converts
to IST at render time. Phase 1 aggregates in Python because volumes are
small; if that ever stops being true, the aggregations move down to
SQL behind the same response shape.
"""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel, Field


class VolumeBucket(BaseModel):
    bucket_date: date = Field(description="UTC day the count applies to (YYYY-MM-DD)")
    total: int
    by_channel: dict[str, int] = Field(default_factory=dict)
    by_platform: dict[str, int] = Field(default_factory=dict)
    by_app: dict[str, int] = Field(default_factory=dict)


class VolumeResponse(BaseModel):
    range_days: int
    buckets: list[VolumeBucket] = Field(default_factory=list)


class CategoryCount(BaseModel):
    category: str
    sub_category: str | None = None
    count: int
    severity_breakdown: dict[str, int] = Field(default_factory=dict)
    sentiment_breakdown: dict[str, int] = Field(default_factory=dict)


class CategoriesResponse(BaseModel):
    range_days: int
    total_classified_feedback: int
    categories: list[CategoryCount] = Field(default_factory=list)
