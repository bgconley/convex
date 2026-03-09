from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from uuid import UUID, uuid4


@dataclass
class Chunk:
    id: UUID
    document_id: UUID
    chunk_text: str
    chunk_index: int
    start_char: int
    end_char: int
    token_count: int
    section_heading: str | None = None
    section_level: int | None = None
    page_number: int | None = None
    embedding: list[float] | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    @staticmethod
    def new(
        document_id: UUID,
        chunk_text: str,
        chunk_index: int,
        start_char: int,
        end_char: int,
        token_count: int,
        section_heading: str | None = None,
        section_level: int | None = None,
        page_number: int | None = None,
    ) -> Chunk:
        return Chunk(
            id=uuid4(),
            document_id=document_id,
            chunk_text=chunk_text,
            chunk_index=chunk_index,
            start_char=start_char,
            end_char=end_char,
            token_count=token_count,
            section_heading=section_heading,
            section_level=section_level,
            page_number=page_number,
        )


@dataclass
class ChunkResult:
    """Output from the chunking step, before persistence."""

    text: str
    index: int
    start_char: int
    end_char: int
    token_count: int
    section_heading: str | None = None
    section_level: int | None = None


@dataclass
class ScoredChunk:
    """A chunk with a retrieval score, returned from search."""

    chunk_id: UUID
    document_id: UUID
    chunk_text: str
    chunk_index: int
    start_char: int
    end_char: int
    section_heading: str | None = None
    page_number: int | None = None
    score: float = 0.0
