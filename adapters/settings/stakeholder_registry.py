"""Loads the configured digest stakeholders from `config_files/stakeholders.yaml`."""

from __future__ import annotations

from pathlib import Path
from typing import Iterable

import yaml

from domain.stakeholder import Stakeholder


def load_stakeholders(config_path: Path) -> tuple[Stakeholder, ...]:
    if not config_path.exists():
        return ()
    raw = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    entries = raw.get("stakeholders") or []
    return tuple(_parse_stakeholder(entry) for entry in entries)


def _parse_stakeholder(entry: dict) -> Stakeholder:
    return Stakeholder(
        name=str(entry["name"]),
        email=str(entry["email"]),
        receives_hourly=bool(entry.get("receives_hourly", False)),
        receives_daily=bool(entry.get("receives_daily", True)),
    )


def filter_for_digest(
    stakeholders: Iterable[Stakeholder], digest_type: str
) -> tuple[Stakeholder, ...]:
    """Return only stakeholders who opted in to this digest cadence."""
    if digest_type == "hourly":
        return tuple(s for s in stakeholders if s.receives_hourly)
    if digest_type == "daily":
        return tuple(s for s in stakeholders if s.receives_daily)
    return tuple(stakeholders)
