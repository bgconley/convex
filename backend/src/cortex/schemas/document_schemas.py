from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class DocumentUploadResponse(BaseModel):
    id: UUID
    status: str
    message: str
    is_duplicate: bool = False


class DocumentMetadataResponse(BaseModel):
    id: UUID
    title: str
    original_filename: str
    file_type: str
    file_size_bytes: int
    mime_type: str
    status: str
    page_count: int | None = None
    word_count: int | None = None
    language: str | None = None
    author: str | None = None
    tags: list[str] = []
    is_favorite: bool = False
    collection_id: UUID | None = None
    content_preview: str | None = None
    created_at: datetime
    updated_at: datetime
    processed_at: datetime | None = None
    error_message: str | None = None


class DocumentContentResponse(BaseModel):
    id: UUID
    format: str
    content: str
    original_url: str
    metadata: DocumentMetadataResponse


class DocumentUpdateRequest(BaseModel):
    tags: list[str] | None = None
    collection_id: UUID | None = None
    is_favorite: bool | None = None
    title: str | None = None


class DocumentListResponse(BaseModel):
    documents: list[DocumentMetadataResponse]
    total: int
    limit: int
    offset: int


class ProcessingEvent(BaseModel):
    event_type: str
    document_id: UUID
    status: str
    progress_pct: float | None = None
    stage_label: str | None = None
    error_message: str | None = None
