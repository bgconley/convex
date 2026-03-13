from __future__ import annotations

from pathlib import Path
from uuid import UUID

import pytest

from cortex.application.ingestion_service import IngestionService
from cortex.domain.chunk import Chunk, ChunkResult
from cortex.domain.document import (
    Document,
    DocumentMetadata,
    FileType,
    ParseResult,
    ProcessingStatus,
)


class FakeParser:
    async def parse(self, file_path: Path, file_type: str) -> ParseResult:
        return ParseResult(
            text="Grace Hopper built compilers.",
            structured={"kind": "text"},
            rendered_html="<pre>Grace Hopper built compilers.</pre>",
            rendered_markdown="Grace Hopper built compilers.",
            metadata=DocumentMetadata(word_count=4),
        )


class FakeChunker:
    def chunk_document(self, text: str, structured_content: dict) -> list[ChunkResult]:
        return [
            ChunkResult(
                text=text,
                index=0,
                start_char=0,
                end_char=len(text),
                token_count=4,
                section_heading=None,
                section_level=None,
            )
        ]


class FakeEmbedder:
    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        return [[0.1] * 1024 for _ in texts]


class FakeDocRepo:
    def __init__(self, doc: Document) -> None:
        self.doc = doc
        self.status_updates: list[str] = []
        self.error_messages: list[str | None] = []

    async def get(self, document_id: UUID) -> Document | None:
        if document_id == self.doc.id:
            return self.doc
        return None

    async def update_status(
        self, document_id: UUID, status: str, error_message: str | None = None
    ) -> None:
        assert document_id == self.doc.id
        self.doc.status = ProcessingStatus(status)
        if error_message is not None:
            self.doc.error_message = error_message
        elif status != ProcessingStatus.FAILED.value:
            self.doc.error_message = None
        self.status_updates.append(status)
        self.error_messages.append(error_message)

    async def update(self, document: Document) -> None:
        self.doc = document


class FakeChunkRepo:
    def __init__(self) -> None:
        self.saved_chunks: list[Chunk] = []
        self.deleted_document_ids: list[UUID] = []

    async def save_chunks(self, chunks: list[Chunk]) -> None:
        self.saved_chunks = list(chunks)

    async def delete_by_document(self, document_id: UUID) -> None:
        self.deleted_document_ids.append(document_id)


class FakeFileStorage:
    def __init__(self, original_path: Path) -> None:
        self.original_path = original_path

    async def get_original_path(self, document_id: UUID) -> Path | None:
        return self.original_path

    async def save_thumbnail(self, image_data: bytes, document_id: UUID) -> str:
        return "thumb.png"


class FailingNER:
    async def extract_entities(
        self, chunks: list[Chunk], threshold: float = 0.4
    ) -> list:
        raise RuntimeError("NER exploded")


class FakeEntityRepo:
    def __init__(self) -> None:
        self.deleted_document_ids: list[UUID] = []

    async def upsert_entities(self, document_id: UUID, extractions: list, chunk_ids: list[UUID]):
        return []

    async def delete_by_document(self, document_id: UUID) -> None:
        self.deleted_document_ids.append(document_id)


class FakeGraphRepo:
    def __init__(self) -> None:
        self.deleted_document_ids: list[UUID] = []

    async def delete_document(self, document_id: UUID) -> None:
        self.deleted_document_ids.append(document_id)


@pytest.mark.asyncio
async def test_ingest_cleans_up_partial_artifacts_after_failure(tmp_path: Path):
    source = tmp_path / "source.txt"
    source.write_text("Grace Hopper built compilers.")

    doc = Document.new(
        title="Grace Hopper",
        original_filename="source.txt",
        file_type=FileType.TXT,
        file_size_bytes=source.stat().st_size,
        file_hash="hash-1",
        mime_type="text/plain",
        original_path="originals/source.txt",
    )
    doc.status = ProcessingStatus.STORED

    doc_repo = FakeDocRepo(doc)
    chunk_repo = FakeChunkRepo()
    entity_repo = FakeEntityRepo()
    graph_repo = FakeGraphRepo()

    service = IngestionService(
        parser=FakeParser(),
        chunker=FakeChunker(),
        embedder=FakeEmbedder(),
        doc_repo=doc_repo,
        chunk_repo=chunk_repo,
        file_storage=FakeFileStorage(source),
        ner=FailingNER(),
        entity_repo=entity_repo,
        graph_repo=graph_repo,
    )

    with pytest.raises(RuntimeError, match="NER exploded"):
        await service.ingest(doc.id)

    assert chunk_repo.saved_chunks, "chunks should be saved before the failure"
    assert chunk_repo.deleted_document_ids == [doc.id, doc.id]
    assert entity_repo.deleted_document_ids == [doc.id]
    assert graph_repo.deleted_document_ids == [doc.id]
    assert doc_repo.status_updates[-1] == ProcessingStatus.FAILED.value
    assert doc.status == ProcessingStatus.FAILED
    assert doc.error_message == "Ingestion failed: see worker logs"


@pytest.mark.asyncio
async def test_ingest_clears_stale_error_message_after_success(tmp_path: Path):
    source = tmp_path / "source.txt"
    source.write_text("Grace Hopper built compilers.")

    doc = Document.new(
        title="Grace Hopper",
        original_filename="source.txt",
        file_type=FileType.TXT,
        file_size_bytes=source.stat().st_size,
        file_hash="hash-2",
        mime_type="text/plain",
        original_path="originals/source.txt",
    )
    doc.status = ProcessingStatus.FAILED
    doc.error_message = "Ingestion failed: see worker logs"

    doc_repo = FakeDocRepo(doc)
    chunk_repo = FakeChunkRepo()

    service = IngestionService(
        parser=FakeParser(),
        chunker=FakeChunker(),
        embedder=FakeEmbedder(),
        doc_repo=doc_repo,
        chunk_repo=chunk_repo,
        file_storage=FakeFileStorage(source),
    )

    await service.ingest(doc.id)

    assert doc.status == ProcessingStatus.READY
    assert doc.error_message is None
