"""LanguageModelRouter — primary + fallback chain with health-checked routing.

Use cases see one `LanguageModelPort`; behind the scenes the router holds a
list of candidate adapters (Claude Code, Codex, Ollama, Recorded). At each
`complete()` call it picks the first adapter whose `is_healthy()` returns
True and forwards the request. If that adapter raises, the router moves on
to the next healthy candidate and tries again.

Why a router rather than failing hard:
- Claude / Codex CLIs can become temporarily unavailable (login expired,
  network blip, subscription throttle). Falling through to Ollama keeps
  the pipeline running.
- Local development without any subscription should still produce some
  output. Including the Recorded adapter as the last fallback guarantees
  the cron pipeline never fails open.

Health checks happen lazily and are cached per call to `complete()` so we
don't shell out to `claude --version` on every classify-ten-rows pass; we
re-probe at the start of each unit of work.
"""

from __future__ import annotations

from typing import Any, Sequence

from domain.exceptions import UnknownLanguageModelError
from service_layer.ports.language_model_port import LanguageModelPort


class LanguageModelRouter:
    name: str = "router"

    def __init__(self, candidates: Sequence[LanguageModelPort]) -> None:
        if not candidates:
            raise ValueError("LanguageModelRouter requires at least one candidate.")
        self._candidates = list(candidates)

    def is_healthy(self) -> bool:
        return any(candidate.is_healthy() for candidate in self._candidates)

    @property
    def active_name(self) -> str:
        """Name of the first currently-healthy candidate, or 'unhealthy'."""
        for candidate in self._candidates:
            if candidate.is_healthy():
                return candidate.name
        return "unhealthy"

    def complete(self, prompt: str, schema: dict[str, Any] | None = None) -> Any:
        last_error: Exception | None = None
        any_attempted = False
        for candidate in self._candidates:
            if not candidate.is_healthy():
                continue
            any_attempted = True
            try:
                return candidate.complete(prompt, schema=schema)
            except Exception as exc:  # noqa: BLE001 — we want broad fallback
                last_error = exc

        if not any_attempted:
            raise UnknownLanguageModelError(
                "No configured language-model adapter is healthy."
            )
        raise UnknownLanguageModelError(
            f"All healthy candidates failed; last error: {last_error}"
        ) from last_error
