"""Port for LLMs. Implementations subprocess to Claude Code, Codex, or call Ollama HTTP.

The use cases never know which CLI or model is in use. The router (in adapters)
selects between primary and fallbacks based on settings + health checks.
"""

from __future__ import annotations

from typing import Any, Protocol


class LanguageModelPort(Protocol):
    @property
    def name(self) -> str: ...

    def is_healthy(self) -> bool: ...

    def complete(self, prompt: str, schema: dict[str, Any] | None = None) -> Any:
        """Return a string when `schema` is None; otherwise a dict matching the schema."""
        ...
