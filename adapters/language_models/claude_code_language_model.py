"""Claude Code language-model adapter — invokes the `claude` CLI as a subprocess.

Uses the user's terminal Claude Code subscription. No Anthropic API key set
or required. Each `complete()` call is a one-shot `claude -p "<prompt>"`
invocation; we capture stdout and parse the JSON object out of the response.

Health check: `claude --version`. If the binary isn't on PATH or the call
fails for any reason, the adapter reports unhealthy and the router falls
back to the next configured model.
"""

from __future__ import annotations

import shutil
import subprocess
from typing import Any

from adapters.language_models._response_parsing import (
    LanguageModelResponseError,
    parse_json_from_response,
)


class ClaudeCodeLanguageModel:
    name: str = "claude_code"

    def __init__(
        self,
        executable: str = "claude",
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
                [self._executable, "-p", prompt],
                capture_output=True,
                text=True,
                timeout=self._timeout_seconds,
            )
        except subprocess.TimeoutExpired as exc:
            raise LanguageModelResponseError(
                f"`{self._executable} -p` timed out after {self._timeout_seconds}s."
            ) from exc
        except FileNotFoundError as exc:
            raise LanguageModelResponseError(
                f"`{self._executable}` not found on PATH."
            ) from exc

        if result.returncode != 0:
            raise LanguageModelResponseError(
                f"`{self._executable} -p` failed (exit {result.returncode}): "
                f"{result.stderr.strip()}"
            )

        return parse_json_from_response(result.stdout)
