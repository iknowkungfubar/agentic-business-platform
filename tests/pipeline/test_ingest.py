"""Unit tests for the document ingester."""

from __future__ import annotations

import pytest

from core.pipeline.ingest import DocumentIngester


class TestDocumentIngester:
    @pytest.fixture
    def ingester(self):
        return DocumentIngester()

    def test_ingest_txt_file(self, tmp_path, ingester):
        doc_path = tmp_path / "test.txt"
        doc_path.write_text("Hello, world!")
        doc = ingester.ingest(str(doc_path))
        assert doc.content == "Hello, world!"
        assert doc.metadata["file_type"] == "txt"

    def test_ingest_md_file(self, tmp_path, ingester):
        doc_path = tmp_path / "readme.md"
        doc_path.write_text("# Heading\n\nContent here.")
        doc = ingester.ingest(str(doc_path))
        assert "# Heading" in doc.content
        assert doc.metadata["file_type"] == "md"

    def test_ingest_python_file(self, tmp_path, ingester):
        doc_path = tmp_path / "script.py"
        doc_path.write_text("def foo():\n    pass")
        doc = ingester.ingest(str(doc_path))
        assert "def foo()" in doc.content
        assert doc.metadata["file_type"] == "py"

    def test_metadata_includes_file_info(self, tmp_path, ingester):
        doc_path = tmp_path / "data.txt"
        doc_path.write_text("test data")
        doc = ingester.ingest(str(doc_path))
        assert "file_name" in doc.metadata
        assert "file_size" in doc.metadata
        assert "ingested_at" in doc.metadata
        assert doc.metadata["file_name"] == "data.txt"

    def test_document_has_unique_id(self, tmp_path, ingester):
        doc_path = tmp_path / "a.txt"
        doc_path.write_text("a")
        doc1 = ingester.ingest(str(doc_path))
        doc2 = ingester.ingest(str(doc_path))
        assert doc1.id != doc2.id

    def test_file_not_found(self, ingester):
        with pytest.raises(FileNotFoundError):
            ingester.ingest("/nonexistent/path.txt")

    def test_empty_file_raises_error(self, tmp_path, ingester):
        doc_path = tmp_path / "empty.txt"
        doc_path.write_text("")
        with pytest.raises(ValueError, match="empty|no content"):
            ingester.ingest(str(doc_path))

    def test_unsupported_extension(self, tmp_path, ingester):
        doc_path = tmp_path / "data.xyz"
        doc_path.write_text("some data")
        with pytest.raises(ValueError, match="Unsupported"):
            ingester.ingest(str(doc_path))

    def test_supported_extensions_listed(self, ingester):
        assert ".txt" in ingester.SUPPORTED_EXTENSIONS
        assert ".md" in ingester.SUPPORTED_EXTENSIONS
        assert ".pdf" in ingester.SUPPORTED_EXTENSIONS
        assert ".py" in ingester.SUPPORTED_EXTENSIONS
        assert ".json" in ingester.SUPPORTED_EXTENSIONS
