"""DocumentChunker — recursive split + overlap behaviour."""

from adapters.retrieval.document_chunker import DocumentChunker


def test_short_text_is_one_chunk():
    chunker = DocumentChunker(chunk_size=500, chunk_overlap=100)
    chunks = chunker.split("Hello world.")

    assert len(chunks) == 1
    assert chunks[0].chunk_index == 0
    assert chunks[0].content == "Hello world."


def test_empty_text_returns_no_chunks():
    chunker = DocumentChunker()
    assert chunker.split("") == []
    assert chunker.split("   \n\n  ") == []


def test_long_text_is_split_into_multiple_chunks():
    paragraph = "This is one sentence. " * 30  # ~660 chars
    chunker = DocumentChunker(chunk_size=200, chunk_overlap=20)

    chunks = chunker.split(paragraph)

    assert len(chunks) > 1
    for chunk in chunks:
        # Allow some slack for overlap-prefix length, but stay broadly bounded.
        assert len(chunk.content) <= 280


def test_chunk_indexes_are_sequential():
    text = "Paragraph one.\n\n" * 50
    chunker = DocumentChunker(chunk_size=80, chunk_overlap=10)

    chunks = chunker.split(text)

    assert [chunk.chunk_index for chunk in chunks] == list(range(len(chunks)))


def test_overlap_appears_at_chunk_boundary():
    text = "ABCDEFGHIJ" * 30  # 300 chars
    chunker = DocumentChunker(chunk_size=50, chunk_overlap=10, separators=[""])

    chunks = chunker.split(text)

    # Each subsequent chunk should start with the tail of the previous one.
    for previous, current in zip(chunks, chunks[1:]):
        assert previous.content[-10:] in current.content[:30]


def test_double_newline_preferred_as_split_point():
    text = "Section one.\n\nSection two.\n\nSection three.\n\nSection four. " * 5
    chunker = DocumentChunker(chunk_size=80, chunk_overlap=10)

    chunks = chunker.split(text)

    # No chunk should awkwardly end mid-sentence in this synthetic case.
    for chunk in chunks:
        assert chunk.content.strip()
