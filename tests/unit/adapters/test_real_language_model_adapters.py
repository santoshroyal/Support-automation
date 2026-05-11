"""Real LLM adapters with mocked subprocess / HTTP — no external dependencies."""

import json
import subprocess
from unittest.mock import patch

import pytest

from adapters.language_models._response_parsing import LanguageModelResponseError
from adapters.language_models.claude_code_language_model import ClaudeCodeLanguageModel
from adapters.language_models.codex_cli_language_model import CodexCliLanguageModel
from adapters.language_models.ollama_gemma_language_model import OllamaGemmaLanguageModel


def _completed(stdout="", stderr="", returncode=0):
    return subprocess.CompletedProcess(args=[], returncode=returncode, stdout=stdout, stderr=stderr)


# ─── Claude Code ──────────────────────────────────────────────────────────────


def test_claude_code_parses_json_from_stdout():
    model = ClaudeCodeLanguageModel(executable="claude")
    fake_response = '{"category": "bug", "severity": "high"}'

    with patch("shutil.which", return_value="/usr/local/bin/claude"):
        with patch("subprocess.run", return_value=_completed(stdout=fake_response)):
            result = model.complete("classify this")

    assert result == {"category": "bug", "severity": "high"}


def test_claude_code_handles_markdown_fenced_response():
    model = ClaudeCodeLanguageModel(executable="claude")
    fake_response = '```json\n{"category": "praise"}\n```'

    with patch("subprocess.run", return_value=_completed(stdout=fake_response)):
        assert model.complete("classify") == {"category": "praise"}


def test_claude_code_health_returns_false_when_executable_missing():
    model = ClaudeCodeLanguageModel(executable="claude_missing")
    with patch("shutil.which", return_value=None):
        assert model.is_healthy() is False


def test_claude_code_raises_on_nonzero_exit():
    model = ClaudeCodeLanguageModel(executable="claude")
    with patch("subprocess.run", return_value=_completed(returncode=1, stderr="boom")):
        with pytest.raises(LanguageModelResponseError):
            model.complete("classify")


def test_claude_code_raises_on_timeout():
    model = ClaudeCodeLanguageModel(executable="claude", timeout_seconds=1)
    with patch(
        "subprocess.run",
        side_effect=subprocess.TimeoutExpired(cmd=["claude"], timeout=1),
    ):
        with pytest.raises(LanguageModelResponseError):
            model.complete("classify")


# ─── Codex CLI ────────────────────────────────────────────────────────────────


def test_codex_cli_parses_response():
    model = CodexCliLanguageModel(executable="codex")
    with patch("subprocess.run", return_value=_completed(stdout='{"category":"bug"}')):
        assert model.complete("classify") == {"category": "bug"}


def test_codex_cli_health_check_false_when_missing():
    model = CodexCliLanguageModel(executable="codex_missing")
    with patch("shutil.which", return_value=None):
        assert model.is_healthy() is False


# ─── Ollama Gemma ─────────────────────────────────────────────────────────────


class _FakeHttpResponse:
    def __init__(self, json_data, status_code=200, text=""):
        self._json = json_data
        self.status_code = status_code
        self.text = text or json.dumps(json_data)

    def json(self):
        if isinstance(self._json, Exception):
            raise self._json
        return self._json


def test_ollama_health_true_when_model_listed():
    model = OllamaGemmaLanguageModel(model="gemma3:latest")
    response = _FakeHttpResponse(json_data={"models": [{"name": "gemma3:latest"}]})
    with patch("httpx.get", return_value=response):
        assert model.is_healthy() is True


def test_ollama_health_false_when_model_absent():
    model = OllamaGemmaLanguageModel(model="gemma3:latest")
    response = _FakeHttpResponse(json_data={"models": [{"name": "llama3:latest"}]})
    with patch("httpx.get", return_value=response):
        assert model.is_healthy() is False


def test_ollama_complete_parses_response_text():
    model = OllamaGemmaLanguageModel(model="gemma3:latest")
    response = _FakeHttpResponse(
        json_data={"response": '{"category": "praise"}', "done": True}
    )
    with patch("httpx.post", return_value=response):
        assert model.complete("classify") == {"category": "praise"}


def test_ollama_raises_on_non_200():
    model = OllamaGemmaLanguageModel(model="gemma3:latest")
    response = _FakeHttpResponse(json_data={}, status_code=500, text="oops")
    with patch("httpx.post", return_value=response):
        with pytest.raises(LanguageModelResponseError):
            model.complete("classify")
