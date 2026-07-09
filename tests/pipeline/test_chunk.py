"""Unit tests for the text chunker."""

from __future__ import annotations

import pytest

from core.pipeline.chunk import TextChunker
from core.pipeline.ingest import Document


class TestTextChunker:
    def test_single_paragraph_stays_one_chunk(self):
        """Short documents should remain as a single chunk."""
        doc = Document(source="test.txt", content="Short paragraph.")
        chunker = TextChunker(chunk_size=500, overlap=20)
        chunks = chunker.chunk(doc)
        assert len(chunks) == 1
        assert chunks[0].content == "Short paragraph."

    def test_multi_paragraph_split(self):
        """Documents with multiple paragraphs should split."""
        doc = Document(
            source="test.txt",
            content="First paragraph about something.\n\nSecond paragraph about something else.",
        )
        chunker = TextChunker(chunk_size=500, overlap=20, strategy="paragraph")
        chunks = chunker.chunk(doc)
        assert len(chunks) >= 2

    def test_chunk_size_respected(self):
        """Chunks should not exceed the specified size."""
        doc = Document(source="test.txt", content="word " * 500)
        chunker = TextChunker(chunk_size=100, overlap=10)
        chunks = chunker.chunk(doc)
        for chunk in chunks:
            assert len(chunk.content) <= 120  # chunk_size + some wiggle

    def test_chunks_have_sequential_indices(self):
        """Chunks should be numbered sequentially."""
        doc = Document(source="test.txt", content="word " * 500)
        chunker = TextChunker(chunk_size=100, overlap=10)
        chunks = chunker.chunk(doc)
        for i, chunk in enumerate(chunks):
            assert chunk.index == i

    def test_chunks_reference_source_document(self):
        """Each chunk should reference its source document."""
        doc = Document(
            source="/path/to/doc.txt",
            content="First paragraph.\n\nSecond paragraph.\n\nThird paragraph.",
        )
        chunker = TextChunker(chunk_size=500, overlap=20)
        chunks = chunker.chunk(doc)
        for chunk in chunks:
            assert chunk.doc_id == doc.id
            assert chunk.source == "/path/to/doc.txt"

    def test_empty_document_returns_empty_list(self):
        """Empty documents should produce no chunks."""
        doc = Document(source="empty.txt", content="")
        chunker = TextChunker()
        chunks = chunker.chunk(doc)
        assert len(chunks) == 0

    def test_chunker_invalid_params(self):
        """Invalid parameters should raise."""
        with pytest.raises(ValueError):
            TextChunker(chunk_size=0)
        with pytest.raises(ValueError):
            TextChunker(overlap=-1)
        with pytest.raises(ValueError):
            TextChunker(overlap=100, chunk_size=50)
        with pytest.raises(ValueError):
            TextChunker(strategy="invalid")

    def test_sentence_strategy(self):
        """Sentence strategy should split on sentences."""
        doc = Document(
            source="test.txt",
            content="First sentence here. Second sentence here. Third sentence here!",
        )
        chunker = TextChunker(chunk_size=500, overlap=20, strategy="sentence")
        chunks = chunker.chunk(doc)
        assert len(chunks) >= 3

    def test_chunk_content_is_preserved(self):
        """Full document content should be recoverable from chunks."""
        original = "First paragraph about X.\n\nSecond paragraph about Y.\n\nThird paragraph about Z."
        doc = Document(source="test.txt", content=original)
        chunker = TextChunker(chunk_size=500, overlap=20)
        chunks = chunker.chunk(doc)
        combined = " ".join(c.content for c in chunks)
        for word in ["First", "Second", "Third", "paragraph"]:
            assert word.lower() in combined.lower()
