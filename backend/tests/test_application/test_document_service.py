"""Tests for DocumentService — document listing with tags filter.

Uses protocol test doubles (no mocking framework). Runs locally without
GPU, DB, or network dependencies.
"""

from __future__ import annotations

import pytest
from datetime import UTC, datetime
from uuid import UUID, uuid4

from cortex.domain.document import Document, DocumentMetadata, FileType, ProcessingStatus
from cortex.application.document_service import DocumentService


# -- Protocol test doubles --


class FakeDocRepo:
    """Test double that supports file_type, tags, limit, offset filtering."""

    def __init__(self, docs: list[Document] | None = None):
        self._docs = docs or []

    async def save(self, document: Document) -> None:
        self._docs.append(document)

    async def get(self, document_id: UUID) -> Document | None:
        return next((d for d in self._docs if d.id == document_id), None)

    async def get_by_hash(self, file_hash: str) -> Document | None:
        return next((d for d in self._docs if d.file_hash == file_hash), None)

    async def list_all(
        self,
        file_type: str | None = None,
        status: str | None = None,
        collection_id: UUID | None = None,
        tags: list[str] | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Document]:
        result = list(self._docs)
        if file_type is not None:
            result = [d for d in result if d.file_type.value == file_type]
        if status is not None:
            result = [d for d in result if d.status.value == status]
        if collection_id is not None:
            result = [d for d in result if d.collection_id == collection_id]
        if tags is not None and len(tags) > 0:
            tag_set = set(tags)
            result = [d for d in result if not tag_set.isdisjoint(d.tags)]
        return result[offset : offset + limit]

    async def count(
        self,
        file_type: str | None = None,
        status: str | None = None,
        collection_id: UUID | None = None,
        tags: list[str] | None = None,
    ) -> int:
        result = list(self._docs)
        if file_type is not None:
            result = [d for d in result if d.file_type.value == file_type]
        if status is not None:
            result = [d for d in result if d.status.value == status]
        if collection_id is not None:
            result = [d for d in result if d.collection_id == collection_id]
        if tags is not None and len(tags) > 0:
            tag_set = set(tags)
            result = [d for d in result if not tag_set.isdisjoint(d.tags)]
        return len(result)

    async def update_status(self, document_id: UUID, status: str, error_message: str | None = None) -> None:
        pass

    async def update(self, document: Document) -> None:
        pass

    async def delete(self, document_id: UUID) -> None:
        self._docs = [d for d in self._docs if d.id != document_id]

    async def search_by_title_prefix(self, prefix: str, limit: int = 5) -> list[Document]:
        return [d for d in self._docs if d.title.lower().startswith(prefix.lower())][:limit]

    async def total_file_size(self) -> int:
        return sum(d.file_size_bytes for d in self._docs)

    async def distinct_tags(self) -> list[str]:
        tags: set[str] = set()
        for d in self._docs:
            tags.update(d.tags)
        return sorted(tags)


class FakeFileStorage:
    async def save_original(self, file_data: bytes, document_id: UUID, filename: str) -> str:
        return f"originals/{document_id}/{filename}"

    async def get_original_path(self, document_id: UUID):
        return None

    async def save_thumbnail(self, image_data: bytes, document_id: UUID) -> str:
        return f"thumbnails/{document_id}.png"

    async def delete_document_files(self, document_id: UUID) -> None:
        pass


# -- Helpers --


def _make_doc(
    tags: list[str] | None = None,
    file_type: FileType = FileType.PDF,
    doc_id: UUID | None = None,
) -> Document:
    now = datetime.now(UTC)
    return Document(
        id=doc_id or uuid4(),
        title="Test Doc",
        original_filename="test.pdf",
        file_type=file_type,
        file_size_bytes=1024,
        file_hash=str(uuid4()),
        mime_type="application/pdf",
        original_path="originals/test.pdf",
        status=ProcessingStatus.READY,
        created_at=now,
        updated_at=now,
        tags=tags or [],
    )


# -- Tests --


@pytest.mark.asyncio
async def test_list_documents_no_filters():
    docs = [_make_doc(), _make_doc()]
    service = DocumentService(FakeDocRepo(docs), FakeFileStorage())
    result, total = await service.list_documents()
    assert len(result) == 2
    assert total == 2


@pytest.mark.asyncio
async def test_list_documents_filter_by_tags():
    d1 = _make_doc(tags=["ml", "research"])
    d2 = _make_doc(tags=["finance"])
    d3 = _make_doc(tags=["ml", "finance"])
    service = DocumentService(FakeDocRepo([d1, d2, d3]), FakeFileStorage())

    result, total = await service.list_documents(tags=["ml"])
    assert total == 2
    ids = {d.id for d in result}
    assert d1.id in ids
    assert d3.id in ids
    assert d2.id not in ids


@pytest.mark.asyncio
async def test_list_documents_filter_by_tags_and_file_type():
    d1 = _make_doc(tags=["ml"], file_type=FileType.PDF)
    d2 = _make_doc(tags=["ml"], file_type=FileType.DOCX)
    d3 = _make_doc(tags=["finance"], file_type=FileType.PDF)
    service = DocumentService(FakeDocRepo([d1, d2, d3]), FakeFileStorage())

    result, total = await service.list_documents(tags=["ml"], file_type="pdf")
    assert total == 1
    assert result[0].id == d1.id


@pytest.mark.asyncio
async def test_list_documents_tags_empty_list_ignored():
    docs = [_make_doc(tags=["ml"]), _make_doc()]
    service = DocumentService(FakeDocRepo(docs), FakeFileStorage())

    result, total = await service.list_documents(tags=[])
    assert total == 2


@pytest.mark.asyncio
async def test_list_documents_tags_no_match():
    docs = [_make_doc(tags=["ml"]), _make_doc(tags=["finance"])]
    service = DocumentService(FakeDocRepo(docs), FakeFileStorage())

    result, total = await service.list_documents(tags=["biology"])
    assert total == 0
    assert len(result) == 0


@pytest.mark.asyncio
async def test_list_documents_multiple_tags_overlap():
    """Tags filter uses overlap (OR) — document matches if it has ANY of the requested tags."""
    d1 = _make_doc(tags=["ml"])
    d2 = _make_doc(tags=["finance"])
    d3 = _make_doc(tags=["biology"])
    service = DocumentService(FakeDocRepo([d1, d2, d3]), FakeFileStorage())

    result, total = await service.list_documents(tags=["ml", "finance"])
    assert total == 2
    ids = {d.id for d in result}
    assert d1.id in ids
    assert d2.id in ids
