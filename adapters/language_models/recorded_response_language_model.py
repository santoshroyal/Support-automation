"""Recorded-response language-model adapter.

Used in tests and continuous integration. Implements `LanguageModelPort`
without making any network call or running any subprocess: it looks up
the response for a given prompt by deterministic hash, in a directory of
JSON files.

File format under `data_fixtures/language_model_responses/<some_name>.json`:

    {
      "label": "human-readable description (optional)",
      "prompt_signature": "sha256_hex_of_prompt",
      "response": { ... arbitrary JSON the use case expects ... }
    }

The recorded adapter loads every JSON file in the directory at construction
time and indexes them by `prompt_signature`. At lookup time it hashes the
incoming prompt and finds the recording.

Defaults: if a prompt has no recording AND a `default_response` was passed,
the adapter returns that default (with a label of `default`). This lets the
classification pipeline run end-to-end before every individual prompt has
been recorded; the response is uniform but the structure is exercised.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from domain.exceptions import UnknownLanguageModelError


class RecordedResponseLanguageModel:
    name: str = "recorded"

    def __init__(
        self,
        recordings: dict[str, Any] | None = None,
        default_response: Any | None = None,
    ) -> None:
        self._recordings: dict[str, Any] = dict(recordings or {})
        self._default_response = default_response

    @classmethod
    def from_directory(
        cls, directory: Path, default_response: Any | None = None
    ) -> "RecordedResponseLanguageModel":
        recordings: dict[str, Any] = {}
        if directory.exists():
            for path in sorted(directory.glob("*.json")):
                payload = json.loads(path.read_text(encoding="utf-8"))
                signature = payload.get("prompt_signature")
                response = payload.get("response")
                if signature is None or response is None:
                    raise ValueError(
                        f"{path} is missing 'prompt_signature' or 'response'"
                    )
                recordings[str(signature)] = response
        return cls(recordings=recordings, default_response=default_response)

    def is_healthy(self) -> bool:
        return True  # No external dependencies.

    def complete(self, prompt: str, schema: dict[str, Any] | None = None) -> Any:
        signature = hash_prompt(prompt)
        if signature in self._recordings:
            return self._recordings[signature]
        if self._default_response is not None:
            return self._default_response
        raise UnknownLanguageModelError(
            f"No recorded response for prompt with signature {signature[:12]}…; "
            "either record the prompt or supply a default_response."
        )


def hash_prompt(prompt: str) -> str:
    """Stable hash used as the recording key.

    Trim trailing whitespace so an editor adding a newline doesn't invalidate
    every existing recording. Otherwise hash the bytes of the prompt as-is.
    """
    return hashlib.sha256(prompt.rstrip().encode("utf-8")).hexdigest()
