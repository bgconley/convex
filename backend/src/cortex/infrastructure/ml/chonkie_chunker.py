from __future__ import annotations

import logging
from dataclasses import dataclass

from cortex.domain.chunk import ChunkResult

logger = logging.getLogger(__name__)


@dataclass
class _SectionEntry:
    heading: str
    level: int
    start_char: int


class ChonkieChunker:
    """ChunkerPort implementation using Chonkie.

    Primary: SemanticChunker — groups sentences by embedding similarity.
    Fallback: RecursiveChunker — splits by structural delimiters.

    SemanticChunker uses a lightweight embedding model for boundary detection.
    It does NOT use chunk_overlap; semantic chunks are self-contained by design.
    """

    def __init__(
        self,
        embedding_model: str = "minishlab/potion-base-32M",
        chunk_size: int = 512,
        similarity_threshold: str | float = "auto",
    ) -> None:
        self._chunk_size = chunk_size
        self._embedding_model = embedding_model
        self._similarity_threshold = similarity_threshold
        self._semantic_chunker = None
        self._recursive_chunker = None

    def _get_semantic_chunker(self):
        if self._semantic_chunker is None:
            from chonkie import SemanticChunker

            self._semantic_chunker = SemanticChunker(
                embedding_model=self._embedding_model,
                chunk_size=self._chunk_size,
                threshold=self._similarity_threshold,
            )
        return self._semantic_chunker

    def _get_recursive_chunker(self):
        if self._recursive_chunker is None:
            from chonkie import RecursiveChunker

            self._recursive_chunker = RecursiveChunker(
                tokenizer="gpt2",
                chunk_size=self._chunk_size,
                min_characters_per_chunk=24,
            )
        return self._recursive_chunker

    def chunk_document(
        self,
        text: str,
        structured_content: dict,
        strategy: str = "semantic",
    ) -> list[ChunkResult]:
        if not text or not text.strip():
            return []

        # Choose chunker
        try:
            if strategy == "semantic":
                chunker = self._get_semantic_chunker()
            else:
                chunker = self._get_recursive_chunker()

            chunks = chunker.chunk(text)
        except Exception:
            logger.warning(
                "Semantic chunking failed, falling back to recursive",
                exc_info=True,
            )
            chunker = self._get_recursive_chunker()
            chunks = chunker.chunk(text)

        # Build section map from structured content
        section_map = self._build_section_map(structured_content)

        results: list[ChunkResult] = []
        for i, chunk in enumerate(chunks):
            start = chunk.start_index
            end = chunk.end_index
            section = self._find_section(start, section_map)

            results.append(
                ChunkResult(
                    text=chunk.text,
                    index=i,
                    start_char=start,
                    end_char=end,
                    token_count=chunk.token_count,
                    section_heading=section.heading if section else None,
                    section_level=section.level if section else None,
                )
            )

        return results

    @staticmethod
    def _build_section_map(structured_content: dict) -> list[_SectionEntry]:
        """Extract section headings and their character positions from
        the DoclingDocument structured dict."""
        sections: list[_SectionEntry] = []

        if not structured_content:
            return sections

        # Docling's export_to_dict() produces a "texts" list with items
        # that have a "label" field (e.g., "section_header") and "prov"
        # with character offsets. The exact schema varies by version;
        # we look for common patterns.
        texts = structured_content.get("texts", [])
        if not texts:
            # Try the "body" or "main-text" key used by some Docling versions
            body = structured_content.get("body", structured_content.get("main-text", []))
            if isinstance(body, list):
                texts = body

        char_offset = 0
        for item in texts:
            if not isinstance(item, dict):
                continue

            label = item.get("label", item.get("type", ""))
            text_content = item.get("text", "")

            if label in (
                "section_header",
                "section-header",
                "heading",
                "title",
            ):
                # Determine heading level from the label or a "level" field
                level = item.get("level", 1)
                if isinstance(level, str):
                    # e.g., "## Heading" → count leading #
                    level = text_content.count("#") if text_content.startswith("#") else 1

                sections.append(
                    _SectionEntry(
                        heading=text_content.lstrip("# ").strip(),
                        level=int(level),
                        start_char=char_offset,
                    )
                )

            char_offset += len(text_content) + 1  # +1 for newline

        return sections

    @staticmethod
    def _find_section(
        char_pos: int, section_map: list[_SectionEntry]
    ) -> _SectionEntry | None:
        """Find the section heading that contains the given character position."""
        result = None
        for section in section_map:
            if section.start_char <= char_pos:
                result = section
            else:
                break
        return result
