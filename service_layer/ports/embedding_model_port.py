"""Port for the local sentence embedding model."""

from __future__ import annotations

from typing import Iterable, Protocol


class EmbeddingModelPort(Protocol):
    @property
    def dimension(self) -> int: ...

    def embed(self, text: str) -> list[float]: ...

    def embed_batch(self, texts: Iterable[str]) -> list[list[float]]: ...
