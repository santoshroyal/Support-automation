"""App — represents one Times Internet news product.

Each piece of feedback ingested by the system is tagged with the app it's
about (Times of India, Economic Times, Navbharat Times, etc.) so the
dashboard can filter, the spike detector can scope its baselines per app,
and digests can be split by app if stakeholders want.

The `slug` is the short, lowercase identifier used in URLs, fixture
folder names, and database rows. The other fields tell each adapter
which external resource to read.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class App:
    slug: str  # short identifier used in URLs / fixtures / DB rows; e.g. "toi"
    name: str  # human-readable; e.g. "Times of India"
    play_package_name: str | None = None  # e.g. "com.toi.reader.activities"
    apple_bundle_id: str | None = None  # e.g. "com.timesinternet.toi"
    gmail_label: str | None = None  # which Gmail label this app's support email is tagged with
