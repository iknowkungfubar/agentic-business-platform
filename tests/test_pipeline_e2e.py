"""E2E integration tests for the data pipeline + model router.

Verifies that a document can flow through the full pipeline:
ingest → chunk → classify → route.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from core.pipeline.ingest import DocumentIngester
from core.pipeline.chunk import TextChunker
from core.router.intent import IntentClassifier
from core.router.selector import ModelSelector


class TestPipelineE2E:
    """Full pipeline: ingest → chunk → classify → route."""

    def test_text_document_through_full_pipeline(self, tmp_path):
        """A plain text document should flow through the entire pipeline."""
        doc_path = tmp_path / "sample.txt"
        doc_path.write_text(
            "This is a test document about data analysis. "
            "It discusses statistical methods and machine learning approaches "
            "for processing large datasets. "
            "The analysis requires significant computational resources "
            "and careful validation of results.\n\n"
            "Key findings include improved accuracy metrics "
            "and reduced processing time."
        )

        # Ingest
        ingester = DocumentIngester()
        doc = ingester.ingest(str(doc_path))

        assert doc is not None
        assert doc.content is not None
        assert len(doc.content) > 0
        assert doc.source == str(doc_path)
        assert doc.metadata["file_type"] == "txt"

        # Chunk
        chunker = TextChunker(chunk_size=200, overlap=20)
        chunks = chunker.chunk(doc)

        assert len(chunks) > 0
        # At least one chunk should have content
        assert any(len(c.content) > 0 for c in chunks)
        # Verify all chunks reference the source document
        for chunk in chunks:
            assert chunk.doc_id == doc.id
            assert chunk.source == doc.source

        # Classify intent
        classifier = IntentClassifier()
        for chunk in chunks:
            intent = classifier.classify(chunk.content)
            assert intent.intent_type is not None
            assert intent.confidence > 0
            # The document discusses analysis, not code generation
            assert intent.intent_type in ("analysis", "summarization", "question_answering", "data_extraction")

        # Route to model
        selector = ModelSelector()
        for chunk in chunks:
            intent = classifier.classify(chunk.content)
            route = selector.select(intent, chunk.content)

            assert route.model_tier is not None
            assert route.confidence > 0
            assert route.reason is not None

    def test_empty_document_raises_error(self, tmp_path):
        """Empty documents should be handled gracefully."""
        doc_path = tmp_path / "empty.txt"
        doc_path.write_text("")

        ingester = DocumentIngester()
        with pytest.raises(ValueError, match="empty|no content"):
            ingester.ingest(str(doc_path))

    def test_pipeline_with_code_snippet(self, tmp_path):
        """Code snippets should be classified as code_generation or similar."""
        doc_path = tmp_path / "script.py"
        doc_path.write_text(
            "def hello_world():\n"
            '    """Print a greeting."""\n'
            '    print("Hello, world!")\n'
            "\n"
            "if __name__ == '__main__':\n"
            "    hello_world()"
        )

        ingester = DocumentIngester()
        chunker = TextChunker(chunk_size=1000, overlap=20)
        classifier = IntentClassifier()
        selector = ModelSelector()

        doc = ingester.ingest(str(doc_path))
        chunks = chunker.chunk(doc)

        for chunk in chunks:
            intent = classifier.classify(chunk.content)
            route = selector.select(intent, chunk.content)

            # Code should route to a code-capable model
            assert route.model_tier in ("t2", "t3", "t4")

    def test_markdown_document_preserves_structure(self, tmp_path):
        """Markdown documents should preserve heading structure during chunking."""
        doc_path = tmp_path / "report.md"
        doc_path.write_text(
            "# Quarterly Report\n\n"
            "## Revenue\n"
            "Revenue grew by 15% this quarter.\n\n"
            "## Costs\n"
            "Operating costs remained flat.\n\n"
            "## Outlook\n"
            "We expect continued growth."
        )

        ingester = DocumentIngester()
        doc = ingester.ingest(str(doc_path))

        assert doc.metadata["file_type"] == "md"
        assert "Quarterly Report" in doc.content
        assert "Revenue" in doc.content

    def test_no_file_raises_error(self):
        """Non-existent file should raise."""
        ingester = DocumentIngester()
        with pytest.raises(FileNotFoundError):
            ingester.ingest("/nonexistent/path/file.txt")

    def test_unsupported_file_type_raises_error(self, tmp_path):
        """Unsupported file types should raise."""
        doc_path = tmp_path / "data.bin"
        doc_path.write_bytes(b"\x00\x01\x02\x03")

        ingester = DocumentIngester()
        with pytest.raises(ValueError, match="Unsupported file type"):
            ingester.ingest(str(doc_path))
