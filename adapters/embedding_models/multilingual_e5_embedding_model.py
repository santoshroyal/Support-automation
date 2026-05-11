"""Local multilingual sentence-transformer adapter.

Runs `intfloat/multilingual-e5-base` from the sentence-transformers library.
Produces 768-dimensional vectors aligned across languages — a Hindi review
about a video crash and an English review about a video crash end up close
to each other in the vector space, which is what makes cross-language
clustering possible at all.

CPU-only. The model is downloaded the first time the adapter is instantiated
(~250 MB, cached at ~/.cache/huggingface/). Subsequent runs load from disk
in a few seconds.

Per the e5 paper's recipe, queries should be prefixed with "query: " and
documents with "passage: ". For our use case (clustering feedback by
similarity), every text plays both roles, so we use "passage: " uniformly.
That's a deliberate simplification — the difference at our scale is small,
and using one prefix keeps the index consistent.
"""

from __future__ import annotations

from typing import Iterable


_MODEL_NAME = "intfloat/multilingual-e5-base"
_DIMENSION = 768
_PASSAGE_PREFIX = "passage: "


class MultilingualE5EmbeddingModel:
    name: str = "multilingual_e5_base"

    def __init__(self, model_name: str = _MODEL_NAME) -> None:
        # Lazy import so the rest of the codebase doesn't pay torch/sentence-transformers
        # import cost when the embedding model isn't actually being used (CLI doesn't
        # need it for ingestion, web API doesn't need it for read endpoints, etc.).
        from sentence_transformers import SentenceTransformer

        self._model = SentenceTransformer(model_name)

    @property
    def dimension(self) -> int:
        return _DIMENSION

    def embed(self, text: str) -> list[float]:
        prefixed = _PASSAGE_PREFIX + text
        vector = self._model.encode(prefixed, normalize_embeddings=True)
        return [float(value) for value in vector]

    def embed_batch(self, texts: Iterable[str]) -> list[list[float]]:
        prefixed = [_PASSAGE_PREFIX + text for text in texts]
        if not prefixed:
            return []
        vectors = self._model.encode(prefixed, normalize_embeddings=True)
        return [[float(v) for v in row] for row in vectors]
