from __future__ import annotations

from pathlib import Path
from typing import Protocol
from uuid import UUID

from cortex.domain.chunk import Chunk, ChunkResult, ScoredChunk  # noqa: F401
from cortex.domain.collection import Collection
from cortex.domain.document import Document, ParseResult
from cortex.domain.entity import Entity, EntityExtraction, EntityMention, RerankResult


class ParserPort(Protocol):
    """Parses documents into structured content."""

    async def parse(self, file_path: Path, file_type: str) -> ParseResult: ...


class ChunkerPort(Protocol):
    """Chunks text into retrieval-sized pieces."""

    def chunk_document(
        self, text: str, structured_content: dict
    ) -> list[ChunkResult]: ...


class EmbedderPort(Protocol):
    """Embeds text into dense vectors."""

    async def embed_texts(self, texts: list[str]) -> list[list[float]]: ...
    async def embed_query(self, query: str) -> list[float]: ...


class RerankerPort(Protocol):
    """Reranks search candidates by relevance."""

    async def rerank(
        self, query: str, documents: list[str], top_k: int
    ) -> list[RerankResult]: ...


class NERPort(Protocol):
    """Extracts named entities from text."""

    async def extract_entities(
        self, chunks: list[Chunk], threshold: float = 0.4
    ) -> list[EntityExtraction]: ...


class DocumentRepository(Protocol):
    """Persists and retrieves document records."""

    async def save(self, document: Document) -> None: ...
    async def get(self, document_id: UUID) -> Document | None: ...
    async def get_by_hash(self, file_hash: str) -> Document | None: ...
    async def list_all(
        self,
        file_type: str | None = None,
        status: str | None = None,
        collection_id: UUID | None = None,
        tags: list[str] | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Document]: ...
    async def count(
        self,
        file_type: str | None = None,
        status: str | None = None,
        collection_id: UUID | None = None,
        tags: list[str] | None = None,
    ) -> int: ...
    async def update_status(
        self, document_id: UUID, status: str, error_message: str | None = None
    ) -> None: ...
    async def update(self, document: Document) -> None: ...
    async def delete(self, document_id: UUID) -> None: ...
    async def search_by_title_prefix(
        self, prefix: str, limit: int = 5
    ) -> list[Document]: ...
    async def distinct_tags(self) -> list[str]: ...
    async def total_file_size(self) -> int: ...


class ChunkRepository(Protocol):
    """Persists and retrieves chunks with vectors."""

    async def save_chunks(self, chunks: list[Chunk]) -> None: ...
    async def delete_by_document(self, document_id: UUID) -> None: ...
    async def get_by_document(self, document_id: UUID) -> list[Chunk]: ...
    async def vector_search(
        self, query_vec: list[float], top_k: int = 50
    ) -> list[ScoredChunk]: ...
    async def bm25_search(
        self, query: str, top_k: int = 50
    ) -> list[ScoredChunk]: ...
    async def count(self) -> int: ...


class EntityRepository(Protocol):
    """Persists and retrieves entities and their mentions."""

    async def upsert_entities(
        self,
        document_id: UUID,
        extractions: list[EntityExtraction],
        chunk_ids: list[UUID],
    ) -> list[Entity]: ...
    async def get_by_document(self, document_id: UUID) -> list[Entity]: ...
    async def list_all(
        self, entity_type: str | None = None, limit: int = 100, offset: int = 0
    ) -> list[Entity]: ...
    async def get(self, entity_id: UUID) -> Entity | None: ...
    async def count(self, entity_type: str | None = None) -> int: ...
    async def distinct_types(self) -> list[str]: ...
    async def search_by_prefix(self, prefix: str, limit: int = 5) -> list[Entity]: ...
    async def get_mentions_by_chunk_ids(
        self, chunk_ids: list[UUID]
    ) -> dict[UUID, list[EntityMention]]: ...
    async def delete_by_document(self, document_id: UUID) -> None: ...


class GraphPort(Protocol):
    """Knowledge graph operations via Apache AGE."""

    async def add_document_entities(
        self,
        document_id: UUID,
        document_title: str,
        entities: list[EntityExtraction],
        chunk_ids: list[UUID],
    ) -> None: ...
    async def get_related_entities(
        self, entity_id: UUID, hops: int = 2
    ) -> list[Entity]: ...
    async def get_related_by_name(
        self, normalized_name: str, hops: int = 2, limit: int = 20
    ) -> list[dict]: ...
    async def get_entity_documents(
        self, entity_id: UUID
    ) -> list[tuple[UUID, str]]: ...
    async def get_document_entities(
        self, document_id: UUID
    ) -> list[Entity]: ...
    async def delete_document(self, document_id: UUID) -> None: ...


class GraphSearchPort(Protocol):
    """Graph-based search via entity expansion."""

    async def search_by_entities(
        self, entity_names: list[str], top_k: int = 50
    ) -> list[ScoredChunk]: ...


class CollectionRepository(Protocol):
    """Persists and retrieves collections."""

    async def save(self, collection: Collection) -> None: ...
    async def get(self, collection_id: UUID) -> Collection | None: ...
    async def list_all(
        self,
        parent_id: UUID | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Collection]: ...
    async def count(self, parent_id: UUID | None = None) -> int: ...
    async def update(self, collection: Collection) -> None: ...
    async def delete(self, collection_id: UUID) -> None: ...


class FileStoragePort(Protocol):
    """Stores and retrieves files on disk."""

    async def save_original(
        self, file_data: bytes, document_id: UUID, filename: str
    ) -> str: ...
    async def get_original_path(self, document_id: UUID) -> Path | None: ...
    async def save_thumbnail(
        self, image_data: bytes, document_id: UUID
    ) -> str: ...
    async def delete_document_files(self, document_id: UUID) -> None: ...
    def compute_file_hash(self, file_data: bytes) -> str: ...


class MetricsPort(Protocol):
    """Collects operational metrics."""

    def record_ingestion(
        self,
        document_id: UUID,
        success: bool,
        total_ms: float,
        stage_timings: dict[str, float],
        chunk_count: int = 0,
        entity_count: int = 0,
    ) -> None: ...

    def record_search(
        self,
        query: str,
        total_ms: float,
        result_count: int,
        component_ms: dict[str, float] | None = None,
    ) -> None: ...

    def get_ingestion_metrics(self) -> dict: ...
    def get_search_metrics(self) -> dict: ...
    def close(self) -> None: ...


class ProcessingEventsPort(Protocol):
    """Publishes and tracks processing events for real-time updates."""

    async def publish(self, event: dict) -> None: ...
    async def get_processing_snapshot(self) -> list[dict]: ...
    async def close(self) -> None: ...
