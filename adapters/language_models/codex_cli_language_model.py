"""Codex CLI language-model adapter — invokes the `codex` CLI as a subprocess.

Uses the user's terminal Codex / OpenAI subscription. Same shape as the
Claude Code adapter; only the executable name and command differ.

Health check: `codex --version`. The router falls back to the next model
if the binary isn't installed or the version probe fails.
"""

from __future__ import annotations

import shutil
import subprocess
from typing import Any

from adapters.language_models._response_parsing import (
    LanguageModelResponseError,
    parse_json_from_response,
)


class CodexCliLanguageModel:
    name: str = "codex_cli"

    def __init__(
        self,
        executable: str = "codex",
        timeout_seconds: float = 60.0,
    ) -> None:
        self._executable = executable
        self._timeout_seconds = timeout_seconds

    def is_healthy(self) -> bool:
        if shutil.which(self._executable) is None:
            return False
        try:
            result = subprocess.run(
                [self._executable, "--version"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            return result.returncode == 0
        except (subprocess.SubprocessError, OSError):
            return False

    def complete(self, prompt: str, schema: dict[str, Any] | None = None) -> Any:
        try:
            result = subprocess.run(
                [self._executable, "exec", prompt],
                capture_output=True,
                text=True,
                timeout=self._timeout_seconds,
            )
        except subprocess.TimeoutExpired as exc:
            raise LanguageModelResponseError(
                f"`{self._executable} exec` timed out after {self._timeout_seconds}s."
            ) from exc
        except FileNotFoundError as exc:
            raise LanguageModelResponseError(
                f"`{self._executable}` not found on PATH."
            ) from exc

        if result.returncode != 0:
            raise LanguageModelResponseError(
                f"`{self._executable} exec` failed (exit {result.returncode}): "
                f"{result.stderr.strip()}"
            )

        return parse_json_from_response(result.stdout)
