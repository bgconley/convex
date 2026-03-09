from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from uuid import UUID, uuid4


@dataclass
class Entity:
    id: UUID
    name: str
    entity_type: str
    normalized_name: str
    description: str | None = None
    document_count: int = 0
    mention_count: int = 0
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass
class EntityExtraction:
    """Output from NER, before persistence."""

    text: str
    label: str
    confidence: float
    start_char: int
    end_char: int
    chunk_id: UUID | None = None
    normalized_name: str = ""

    def __post_init__(self) -> None:
        if not self.normalized_name:
            self.normalized_name = self.text.lower().strip()


@dataclass
class RerankResult:
    """Output from the reranker."""

    index: int
    score: float
    text: str
