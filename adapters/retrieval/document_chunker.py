"""Recursive character splitter for chunking knowledge documents.

The strategy mirrors LangChain's `RecursiveCharacterTextSplitter` but is
~50 lines of pure Python, no langchain dependency:

  1. Try to split on the largest separator first (`"\\n\\n"`).
  2. If a resulting segment is still longer than `chunk_size`, recursively
     split it on the next-smaller separator (`"\\n"`, then `". "`, then
     `" "`, then character-level as a last resort).
  3. Once segments are small enough, glue adjacent ones together — but
     never crossing `chunk_size` — to maximise the use of each chunk.
  4. Re-attach `chunk_overlap` characters from the end of one chunk to the
     start of the next, so context isn't cut at a hard boundary.

Defaults follow the plan: chunk_size=500, chunk_overlap=100,
separators=["\\n\\n", "\\n", ". ", " "].

The output is a list of dicts: `{"chunk_index": int, "content": str}`.
The caller adds the embedding and upserts into KnowledgeChunkOrm.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Chunk:
    chunk_index: int
    content: str


_DEFAULT_SEPARATORS = ["\n\n", "\n", ". ", " "]


class DocumentChunker:
    def __init__(
        self,
        chunk_size: int = 500,
        chunk_overlap: int = 100,
        separators: list[str] | None = None,
    ) -> None:
        if chunk_overlap >= chunk_size:
            raise ValueError("chunk_overlap must be smaller than chunk_size")
        self._chunk_size = chunk_size
        self._chunk_overlap = chunk_overlap
        self._separators = separators or _DEFAULT_SEPARATORS

    def split(self, text: str) -> list[Chunk]:
        text = (text or "").strip()
        if not text:
            return []

        # 1. Recursively cut text down so every segment fits inside chunk_size.
        segments = self._recursive_split(text, self._separators)
        # 2. Coalesce adjacent segments greedily up to chunk_size.
        merged = self._merge_until_full(segments)
        # 3. Add overlap so the next chunk re-shows the tail of the previous.
        with_overlap = self._add_overlap(merged)
        return [Chunk(chunk_index=index, content=content) for index, content in enumerate(with_overlap)]

    # ─── internals ────────────────────────────────────────────────────────

    def _recursive_split(self, text: str, separators: list[str]) -> list[str]:
        if len(text) <= self._chunk_size:
            return [text]
        # Skip empty separators (Python's str.split rejects them) so callers
        # can pass `separators=[""]` to force pure character-boundary splitting.
        usable_separators = [sep for sep in separators if sep]
        if not usable_separators:
            return [text[i : i + self._chunk_size] for i in range(0, len(text), self._chunk_size)]
        head, *rest = usable_separators
        pieces = text.split(head)
        out: list[str] = []
        for piece in pieces:
            if not piece:
                continue
            if len(piece) <= self._chunk_size:
                out.append(piece)
            else:
                out.extend(self._recursive_split(piece, rest))
        return out

    def _merge_until_full(self, segments: list[str]) -> list[str]:
        merged: list[str] = []
        current = ""
        for segment in segments:
            candidate = (current + " " + segment).strip() if current else segment.strip()
            if len(candidate) <= self._chunk_size:
                current = candidate
            else:
                if current:
                    merged.append(current)
                # If a single segment is larger than chunk_size, keep it as-is
                # (recursive_split should have prevented this, but be defensive).
                current = segment.strip()
                if len(current) > self._chunk_size:
                    merged.append(current[: self._chunk_size])
                    current = current[self._chunk_size :]
        if current:
            merged.append(current)
        return merged

    def _add_overlap(self, chunks: list[str]) -> list[str]:
        if self._chunk_overlap == 0 or len(chunks) < 2:
            return chunks
        out = [chunks[0]]
        for previous, current in zip(chunks, chunks[1:]):
            tail = previous[-self._chunk_overlap :]
            out.append(f"{tail} {current}".strip())
        return out
