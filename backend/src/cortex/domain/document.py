from __future__ import annotations

import enum
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID, uuid4


class FileType(str, enum.Enum):
    PDF = "pdf"
    MARKDOWN = "markdown"
    DOCX = "docx"
    XLSX = "xlsx"
    TXT = "txt"
    PNG = "png"
    JPG = "jpg"
    TIFF = "tiff"


class ProcessingStatus(str, enum.Enum):
    UPLOADING = "uploading"
    STORED = "stored"
    PARSING = "parsing"
    PARSED = "parsed"
    CHUNKING = "chunking"
    CHUNKED = "chunked"
    EMBEDDING = "embedding"
    EMBEDDED = "embedded"
    EXTRACTING_ENTITIES = "extracting_entities"
    ENTITIES_EXTRACTED = "entities_extracted"
    BUILDING_GRAPH = "building_graph"
    READY = "ready"
    FAILED = "failed"


@dataclass
class DocumentMetadata:
    page_count: int | None = None
    word_count: int | None = None
    language: str = "en"
    author: str | None = None
    subject: str | None = None


@dataclass
class ParseResult:
    text: str
    structured: dict
    rendered_html: str
    rendered_markdown: str
    metadata: DocumentMetadata
    images: list[ExtractedImage] = field(default_factory=list)
    thumbnail_path: str | None = None
    page_count: int | None = None


@dataclass
class ExtractedImage:
    image_path: str
    page_number: int | None = None
    caption: str | None = None
    alt_text: str | None = None
    width: int | None = None
    height: int | None = None


@dataclass
class Document:
    id: UUID
    title: str
    original_filename: str
    file_type: FileType
    file_size_bytes: int
    file_hash: str
    mime_type: str
    original_path: str
    status: ProcessingStatus = ProcessingStatus.UPLOADING
    thumbnail_path: str | None = None
    parsed_content: dict | None = None
    rendered_markdown: str | None = None
    rendered_html: str | None = None
    metadata: DocumentMetadata = field(default_factory=DocumentMetadata)
    error_message: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    processed_at: datetime | None = None
    collection_id: UUID | None = None
    tags: list[str] = field(default_factory=list)
    is_favorite: bool = False

    @staticmethod
    def new(
        title: str,
        original_filename: str,
        file_type: FileType,
        file_size_bytes: int,
        file_hash: str,
        mime_type: str,
        original_path: str,
    ) -> Document:
        return Document(
            id=uuid4(),
            title=title,
            original_filename=original_filename,
            file_type=file_type,
            file_size_bytes=file_size_bytes,
            file_hash=file_hash,
            mime_type=mime_type,
            original_path=original_path,
        )
