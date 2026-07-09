"""Regression tests for uncovered paths in the document ingester.

Covers PDF extraction fallback, PyMuPDF path, and edge cases.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from core.pipeline.ingest import DocumentIngester


class TestDocumentIngesterPDF:
    """Tests for PDF ingestion paths (uncovered code)."""

    @pytest.fixture
    def ingester(self):
        return DocumentIngester()

    def test_pdf_extension_accepted(self, ingester):
        """.pdf should be in supported extensions."""
        assert ".pdf" in ingester.SUPPORTED_EXTENSIONS

    def test_pdf_fallback_extracts_text(self, tmp_path, ingester):
        """PDF fallback extraction should extract text from basic PDF."""
        # Create a minimal PDF-like file with text in parenthesized form
        pdf_path = tmp_path / "test.pdf"
        # Minimal PDF with text "Hello PDF" using the Latin-1 encoding
        pdf_content = (
            b"%PDF-1.4\n"
            b"1 0 obj\n<</Type/Catalog/Pages 2 0 R>>\nendobj\n"
            b"2 0 obj\n<</Type/Pages/Kids[3 0 R]/Count 1>>\nendobj\n"
            b"3 0 obj\n<</Type/Page/Parent 2 0 R/MediaBox[0 0 612 792]/Contents 4 0 R>>\nendobj\n"
            b"4 0 obj\n<</Length 44>>stream\n"
            b"BT\n/F1 12 Tf\n(Hello PDF Test)Tj\nET\nendstream\nendobj\n"
            b"xref\n0 5\n0000000000 65535 f \n0000000009 00000 n \n0000000058 00000 n \n"
            b"0000000115 00000 n \n0000000266 00000 n \n"
            b"trailer\n<</Size 5/Root 1 0 R>>\nstartxref\n405\n%%EOF"
        )
        pdf_path.write_bytes(pdf_content)

        doc = ingester.ingest(str(pdf_path))
        assert doc is not None
        assert doc.metadata["file_type"] == "pdf"
        # The fallback extractor should find text in parenthesized content
        assert len(doc.content) > 0

    def test_pdf_pymupdf_path(self, tmp_path, ingester):
        """When fitz is available, it should be used for PDF extraction."""
        pdf_path = tmp_path / "test.pdf"
        pdf_path.write_text("fake pdf content")

        mock_doc = MagicMock()
        mock_page = MagicMock()
        mock_page.get_text.return_value = "Extracted text from PyMuPDF"
        mock_doc.__iter__.return_value = [mock_page]

        with patch.dict("sys.modules", {"fitz": MagicMock()}):
            import fitz

            fitz.open.return_value = mock_doc

            doc = ingester.ingest(str(pdf_path))
            assert doc is not None
            assert "PyMuPDF" in doc.content

    def test_pdf_pymupdf_import_error_falls_back(self, tmp_path, ingester):
        """When fitz is not available, fallback extractor should run."""
        pdf_path = tmp_path / "test.pdf"
        pdf_content = (
            b"%PDF-1.4\n"
            b"1 0 obj\n<</Type/Catalog/Pages 2 0 R>>\nendobj\n"
            b"2 0 obj\n<</Type/Pages/Kids[3 0 R]/Count 1>>\nendobj\n"
            b"3 0 obj\n<</Type/Page/Parent 2 0 R/MediaBox[0 0 612 792]/Contents 4 0 R>>\nendobj\n"
            b"4 0 obj\n<</Length 44>>stream\n"
            b"BT\n/F1 12 Tf\n(Hello from Fallback)Tj\nET\nendstream\nendobj\n"
            b"xref\n0 5\n0000000000 65535 f \n0000000009 00000 n \n0000000058 00000 n \n"
            b"0000000115 00000 n \n0000000266 00000 n \n"
            b"trailer\n<</Size 5/Root 1 0 R>>\nstartxref\n405\n%%EOF"
        )
        pdf_path.write_bytes(pdf_content)

        # Remove fitz from sys.modules to force ImportError path
        with patch.dict("sys.modules", {"fitz": None}):
            doc = ingester.ingest(str(pdf_path))
            assert doc is not None
            assert "Hello from Fallback" in doc.content or "Hello from Fallback" in doc.content

    def test_pdf_file_not_found(self, ingester):
        """Missing PDF should raise FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            ingester.ingest("/nonexistent/document.pdf")

    def test_unsupported_binary_file(self, tmp_path, ingester):
        """Binary files with unsupported extensions should raise."""
        doc_path = tmp_path / "data.bin"
        doc_path.write_bytes(b"\x00\x01\x02")
        with pytest.raises(ValueError, match="Unsupported"):
            ingester.ingest(str(doc_path))

    def test_js_file_type_detected(self, tmp_path, ingester):
        """.js files should be detected and ingested correctly."""
        doc_path = tmp_path / "script.js"
        doc_path.write_text("function hello() {\n  return 'world';\n}")
        doc = ingester.ingest(str(doc_path))
        assert doc.metadata["file_type"] == "js"
        assert "function hello" in doc.content

    def test_yaml_file_type_detected(self, tmp_path, ingester):
        """.yaml files should be detected and ingested."""
        doc_path = tmp_path / "config.yaml"
        doc_path.write_text("name: test\nversion: 1.0\n")
        doc = ingester.ingest(str(doc_path))
        assert doc.metadata["file_type"] == "yaml"

    def test_html_file_type_detected(self, tmp_path, ingester):
        """.html files should be detected and ingested."""
        doc_path = tmp_path / "page.html"
        doc_path.write_text("<html><body><p>Hello</p></body></html>")
        doc = ingester.ingest(str(doc_path))
        assert doc.metadata["file_type"] == "html"
