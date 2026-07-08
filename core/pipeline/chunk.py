"""Document chunking — splits documents into overlapping chunks for processing."""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass, field
from typing import Any

from core.pipeline.ingest import Document


@dataclass
class DocumentChunk:
    """A single chunk of a document."""

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    doc_id: str = ""
    source: str = ""
    content: str = ""
    index: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)


class TextChunker:
    """Splits documents into chunks with configurable size and overlap.

    Chunking strategies:
    - Paragraph-based (splits on double newlines)
    - Sentence-based (splits on sentence boundaries)
    - Fixed-size (splits at word boundaries)
    """

    def __init__(
        self,
        chunk_size: int = 500,
        overlap: int = 50,
        strategy: str = "paragraph",
    ):
        if chunk_size <= 0:
            raise ValueError("chunk_size must be positive")
        if overlap < 0:
            raise ValueError("overlap must be non-negative")
        if overlap >= chunk_size:
            raise ValueError("overlap must be less than chunk_size")
        if strategy not in ("paragraph", "sentence", "fixed"):
            raise ValueError(f"Unknown strategy: {strategy}")

        self.chunk_size = chunk_size
        self.overlap = overlap
        self.strategy = strategy

    def chunk(self, document: Document) -> list[DocumentChunk]:
        """Split a document into chunks.

        Args:
            document: The document to chunk.

        Returns:
            List of DocumentChunk objects.

        """
        if not document.content.strip():
            return []

        segments = self._split_into_segments(document.content)
        chunks: list[DocumentChunk] = []

        for segment in segments:
            if len(segment) <= self.chunk_size:
                chunks.append(
                    DocumentChunk(
                        doc_id=document.id,
                        source=document.source,
                        content=segment.strip(),
                        index=len(chunks),
                    )
                )
            else:
                # Split large segments into fixed-size chunks
                words = segment.split()
                current_chunk: list[str] = []
                current_len = 0

                for i, word in enumerate(words):
                    word_len = len(word) + 1  # +1 for space
                    if current_len + word_len > self.chunk_size and current_chunk:
                        chunks.append(
                            DocumentChunk(
                                doc_id=document.id,
                                source=document.source,
                                content=" ".join(current_chunk),
                                index=len(chunks),
                            )
                        )
                        # Overlap: keep last N words from current chunk
                        if self.overlap > 0:
                            overlap_words: list[str] = []
                            overlap_len = 0
                            for w in reversed(current_chunk):
                                wl = len(w) + 1
                                if overlap_len + wl > self.overlap:
                                    break
                                overlap_words.insert(0, w)
                                overlap_len += wl
                            current_chunk = overlap_words
                            current_len = overlap_len
                        else:
                            current_chunk = []
                            current_len = 0

                    current_chunk.append(word)
                    current_len += word_len

                if current_chunk:
                    chunks.append(
                        DocumentChunk(
                            doc_id=document.id,
                            source=document.source,
                            content=" ".join(current_chunk),
                            index=len(chunks),
                        )
                    )

        return chunks

    def _split_into_segments(self, text: str) -> list[str]:
        """Split text into initial segments based on strategy."""
        if self.strategy == "paragraph":
            # Split on double newlines (paragraph breaks)
            segments = re.split(r"\n\s*\n", text)
            return [s.strip() for s in segments if s.strip()]

        elif self.strategy == "sentence":
            # Split on sentence boundaries
            segments = re.split(r"(?<=[.!?])\s+", text)
            return [s.strip() for s in segments if s.strip()]

        else:  # fixed
            return [text.strip()]
