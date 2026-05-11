"""Loads the configured Times Internet news apps from `config_files/apps.yaml`.

This is the single source of truth for which apps the system serves. The
composition root iterates over this list to build per-app source adapters;
the dashboard reads from it to populate filter dropdowns; reports group by it.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import yaml

from domain.app import App


@dataclass(frozen=True)
class AppRegistry:
    """In-memory registry of every configured app, keyed by slug for fast lookup."""

    apps: tuple[App, ...]

    def all(self) -> tuple[App, ...]:
        return self.apps

    def by_slug(self, slug: str) -> App | None:
        for app in self.apps:
            if app.slug == slug:
                return app
        return None

    def slugs(self) -> tuple[str, ...]:
        return tuple(app.slug for app in self.apps)

    def __iter__(self) -> Iterable[App]:
        return iter(self.apps)


def load_app_registry(config_path: Path) -> AppRegistry:
    if not config_path.exists():
        raise FileNotFoundError(f"App configuration not found at {config_path}")
    raw = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    entries = raw.get("apps") or []
    apps = tuple(_parse_app(entry) for entry in entries)
    if not apps:
        raise ValueError(f"No apps configured in {config_path}")
    _validate_unique_slugs(apps)
    return AppRegistry(apps=apps)


def _parse_app(entry: dict) -> App:
    if "slug" not in entry or "name" not in entry:
        raise ValueError(f"App entry missing required slug/name: {entry!r}")
    return App(
        slug=str(entry["slug"]),
        name=str(entry["name"]),
        play_package_name=entry.get("play_package_name"),
        apple_bundle_id=entry.get("apple_bundle_id"),
        gmail_label=entry.get("gmail_label"),
    )


def _validate_unique_slugs(apps: tuple[App, ...]) -> None:
    seen: set[str] = set()
    for app in apps:
        if app.slug in seen:
            raise ValueError(f"Duplicate app slug in registry: {app.slug!r}")
        seen.add(app.slug)
