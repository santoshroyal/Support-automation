"""Stakeholder — recipient of digest emails and spike alerts."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Stakeholder:
    name: str
    email: str
    receives_hourly: bool = False
    receives_daily: bool = True
