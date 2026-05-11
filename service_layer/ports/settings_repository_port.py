"""Port for DB-backed settings (UI-editable runtime configuration)."""

from __future__ import annotations

from typing import Any, Protocol


class SettingsRepositoryPort(Protocol):
    def get(self, key: str, default: Any = None) -> Any: ...

    def set(self, key: str, value: Any, actor: str = "system") -> None: ...

    def all(self) -> dict[str, Any]: ...
