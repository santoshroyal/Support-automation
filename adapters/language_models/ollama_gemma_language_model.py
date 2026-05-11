"""Ollama (Gemma) language-model adapter — talks to a local Ollama server.

Fully local. Uses the HTTP /api/generate endpoint on `http://localhost:11434`
by default; the model name is configurable so the same adapter can run
Gemma, Llama, Mistral, or any model the user has pulled.

Health check: GET /api/tags returns 200 and the configured model is in the
list. The router falls back to the next model if Ollama is not running or
the requested model isn't pulled.
"""

from __future__ import annotations

from typing import Any

import httpx

from adapters.language_models._response_parsing import (
    LanguageModelResponseError,
    parse_json_from_response,
)


class OllamaGemmaLanguageModel:
    def __init__(
        self,
        model: str = "gemma3:latest",
        base_url: str = "http://localhost:11434",
        timeout_seconds: float = 60.0,
    ) -> None:
        self._model = model
        self._base_url = base_url.rstrip("/")
        self._timeout_seconds = timeout_seconds

    @property
    def name(self) -> str:
        return f"ollama_{self._model}"

    def is_healthy(self) -> bool:
        try:
            response = httpx.get(f"{self._base_url}/api/tags", timeout=2)
        except httpx.HTTPError:
            return False
        if response.status_code != 200:
            return False
        try:
            payload = response.json()
        except ValueError:
            return False
        installed_models = {item.get("name") for item in payload.get("models", [])}
        # Match either "gemma3:latest" exactly, or the bare name without tag.
        return self._model in installed_models or self._model.split(":", 1)[0] in {
            name.split(":", 1)[0] if name else None for name in installed_models
        }

    def complete(self, prompt: str, schema: dict[str, Any] | None = None) -> Any:
        try:
            response = httpx.post(
                f"{self._base_url}/api/generate",
                json={"model": self._model, "prompt": prompt, "stream": False},
                timeout=self._timeout_seconds,
            )
        except httpx.HTTPError as exc:
            raise LanguageModelResponseError(
                f"Ollama request failed: {exc}"
            ) from exc

        if response.status_code != 200:
            raise LanguageModelResponseError(
                f"Ollama returned HTTP {response.status_code}: {response.text}"
            )

        try:
            payload = response.json()
        except ValueError as exc:
            raise LanguageModelResponseError(
                f"Ollama returned non-JSON envelope: {response.text!r}"
            ) from exc

        return parse_json_from_response(payload.get("response", ""))
