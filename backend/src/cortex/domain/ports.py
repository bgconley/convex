from __future__ import annotations

from pathlib import Path
from typing import Protocol
from uuid import UUID

from cortex.domain.chunk import Chunk, ChunkResult, ScoredChunk
from cortex.domain.document import Document, ParseResult
from cortex.domain.entity import Entity, EntityExtraction, RerankResult


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

    def extract_entities(
        self, chunks: list[ChunkResult], threshold: float = 0.4
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
        limit: int = 50,
        offset: int = 0,
    ) -> list[Document]: ...
    async def update_status(
        self, document_id: UUID, status: str, error_message: str | None = None
    ) -> None: ...
    async def update(self, document: Document) -> None: ...
    async def delete(self, document_id: UUID) -> None: ...


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


class GraphPort(Protocol):
    """Knowledge graph operations."""

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
    async def delete_document(self, document_id: UUID) -> None: ...


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
