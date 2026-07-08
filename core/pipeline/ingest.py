"""Document ingestion — multi-source document reader.

Supports plain text (.txt), markdown (.md), and PDF (.pdf) files.
PDF extraction uses PyMuPDF when available, falls back to text-based parsing.
"""

from __future__ import annotations

import os
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


@dataclass
class Document:
    """A document ingested into the platform pipeline."""

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    source: str = ""
    content: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
    ingested_at: datetime = field(default_factory=lambda: datetime.now(UTC))


class DocumentIngester:
    """Ingests documents from files, returning structured Document objects.

    Supported file types: .txt, .md, .pdf, .py, .json, .yaml, .yml, .csv, .html
    """

    SUPPORTED_EXTENSIONS = {
        ".txt", ".md", ".pdf", ".py", ".js", ".ts", ".rs", ".java",
        ".json", ".yaml", ".yml", ".csv", ".html", ".xml",
    }

    def ingest(self, path: str) -> Document:
        """Ingest a document from a file path.

        Args:
            path: Absolute or relative path to the file.

        Returns:
            Document with extracted content and metadata.

        Raises:
            FileNotFoundError: If the file doesn't exist.
            ValueError: If the file is empty or has an unsupported extension.

        """
        filepath = Path(path)
        if not filepath.exists():
            raise FileNotFoundError(f"File not found: {path}")

        ext = filepath.suffix.lower()
        if ext not in self.SUPPORTED_EXTENSIONS:
            raise ValueError(
                f"Unsupported file type: {ext}. "
                f"Supported: {', '.join(sorted(self.SUPPORTED_EXTENSIONS))}"
            )

        content = self._read_file(filepath)
        if not content.strip():
            raise ValueError(f"File is empty or has no content: {path}")

        metadata: dict[str, Any] = {
            "file_type": ext.lstrip("."),
            "file_name": filepath.name,
            "file_size": os.path.getsize(filepath),
            "ingested_at": datetime.now(UTC).isoformat(),
        }

        return Document(
            source=str(filepath.resolve()),
            content=content,
            metadata=metadata,
        )

    def _read_file(self, filepath: Path) -> str:
        """Read content from a file, handling different formats."""
        ext = filepath.suffix.lower()

        if ext == ".pdf":
            return self._read_pdf(filepath)

        # All text-based formats
        return filepath.read_text(encoding="utf-8", errors="replace")

    def _read_pdf(self, filepath: Path) -> str:
        """Extract text from a PDF.

        Uses PyMuPDF (fitz) if available, otherwise falls back to a
        basic binary text extraction.
        """
        try:
            import fitz  # PyMuPDF
            doc = fitz.open(str(filepath))
            pages = []
            for page in doc:
                pages.append(page.get_text())
            doc.close()
            return "\n\n".join(pages)
        except ImportError:
            # Fallback: basic text extraction from raw PDF
            text = filepath.read_bytes()
            # Extract text between parentheses and BT/ET markers
            return self._extract_pdf_text(text)

    def _extract_pdf_text(self, raw: bytes) -> str:
        """Basic PDF text extraction fallback."""
        text = raw.decode("latin-1")
        lines = []
        in_text = False
        for line in text.split("\n"):
            stripped = line.strip()
            if stripped.startswith("(") and stripped.endswith(")"):
                lines.append(stripped[1:-1])
            elif stripped == "BT":
                in_text = True
            elif stripped == "ET":
                in_text = False
            elif in_text and stripped:
                lines.append(stripped)
        return "\n".join(lines)
