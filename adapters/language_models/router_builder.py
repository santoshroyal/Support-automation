"""Build a LanguageModelRouter from a YAML configuration.

Reads `config_files/language_models.yaml` (or another path) and constructs
the chain of adapters. The Recorded adapter is always appended last so
the pipeline can fall through to placeholders if every real model is
unavailable — keeping cron runs from failing in degraded environments.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from adapters.language_models.claude_code_language_model import ClaudeCodeLanguageModel
from adapters.language_models.codex_cli_language_model import CodexCliLanguageModel
from adapters.language_models.language_model_router import LanguageModelRouter
from adapters.language_models.ollama_gemma_language_model import OllamaGemmaLanguageModel
from adapters.language_models.recorded_response_language_model import (
    RecordedResponseLanguageModel,
)
from service_layer.ports.language_model_port import LanguageModelPort


def build_language_model_router(
    config_path: Path,
    recordings_dir: Path,
    default_response: dict[str, Any] | None = None,
) -> LanguageModelRouter:
    chain_config = _load_chain(config_path)
    candidates: list[LanguageModelPort] = []
    has_recorded = False

    for entry in chain_config:
        kind = entry.get("kind")
        if kind == "claude_code":
            candidates.append(
                ClaudeCodeLanguageModel(
                    executable=entry.get("executable", "claude"),
                    timeout_seconds=float(entry.get("timeout_seconds", 60)),
                )
            )
        elif kind == "codex_cli":
            candidates.append(
                CodexCliLanguageModel(
                    executable=entry.get("executable", "codex"),
                    timeout_seconds=float(entry.get("timeout_seconds", 60)),
                )
            )
        elif kind == "ollama_gemma":
            candidates.append(
                OllamaGemmaLanguageModel(
                    model=entry.get("model", "gemma3:latest"),
                    base_url=entry.get("base_url", "http://localhost:11434"),
                    timeout_seconds=float(entry.get("timeout_seconds", 60)),
                )
            )
        elif kind == "recorded":
            candidates.append(
                RecordedResponseLanguageModel.from_directory(
                    directory=recordings_dir,
                    default_response=default_response,
                )
            )
            has_recorded = True
        else:
            raise ValueError(f"Unknown language-model kind: {kind!r} in {config_path}")

    if not has_recorded:
        # Always append the Recorded adapter as a final fallback so a
        # stale or absent CLI never breaks the cron pipeline.
        candidates.append(
            RecordedResponseLanguageModel.from_directory(
                directory=recordings_dir,
                default_response=default_response,
            )
        )

    return LanguageModelRouter(candidates=candidates)


def _load_chain(config_path: Path) -> list[dict[str, Any]]:
    if not config_path.exists():
        # Missing config = recorded-only operation.
        return [{"kind": "recorded"}]
    raw = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    chain = raw.get("chain")
    if not chain:
        return [{"kind": "recorded"}]
    return list(chain)
