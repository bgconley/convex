from __future__ import annotations

from uuid import UUID

from cortex.domain.document import Document, FileType, ProcessingStatus
from cortex.domain.ports import DocumentRepository, EntityRepository, FileStoragePort, GraphPort
from cortex.infrastructure.file_storage import LocalFileStorage


ALLOWED_EXTENSIONS: dict[str, FileType] = {
    ".pdf": FileType.PDF,
    ".md": FileType.MARKDOWN,
    ".markdown": FileType.MARKDOWN,
    ".docx": FileType.DOCX,
    ".xlsx": FileType.XLSX,
    ".txt": FileType.TXT,
    ".png": FileType.PNG,
    ".jpg": FileType.JPG,
    ".jpeg": FileType.JPG,
    ".tiff": FileType.TIFF,
    ".tif": FileType.TIFF,
}

MIME_TYPES: dict[FileType, str] = {
    FileType.PDF: "application/pdf",
    FileType.MARKDOWN: "text/markdown",
    FileType.DOCX: "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    FileType.XLSX: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    FileType.TXT: "text/plain",
    FileType.PNG: "image/png",
    FileType.JPG: "image/jpeg",
    FileType.TIFF: "image/tiff",
}

MAX_FILE_SIZE = 100 * 1024 * 1024  # 100 MB


class DocumentService:
    """Use-case orchestration for document CRUD.

    Depends on DocumentRepository and FileStoragePort (protocols).
    """

    def __init__(
        self,
        doc_repo: DocumentRepository,
        file_storage: FileStoragePort,
        entity_repo: EntityRepository | None = None,
        graph_repo: GraphPort | None = None,
    ) -> None:
        self._doc_repo = doc_repo
        self._file_storage = file_storage
        self._entity_repo = entity_repo
        self._graph_repo = graph_repo

    async def upload(
        self,
        filename: str,
        file_data: bytes,
    ) -> tuple[Document, bool]:
        """Upload a document. Returns (document, is_duplicate).

        If the file hash already exists, returns the existing document.
        """
        # Validate extension
        ext = self._get_extension(filename)
        file_type = ALLOWED_EXTENSIONS.get(ext)
        if file_type is None:
            raise ValueError(
                f"Unsupported file type: {ext}. "
                f"Allowed: {', '.join(ALLOWED_EXTENSIONS.keys())}"
            )

        # Validate size
        if len(file_data) > MAX_FILE_SIZE:
            raise ValueError(
                f"File too large: {len(file_data)} bytes. Max: {MAX_FILE_SIZE} bytes."
            )

        # Compute hash and check for duplicates
        file_hash = LocalFileStorage.compute_file_hash(file_data)
        existing = await self._doc_repo.get_by_hash(file_hash)
        if existing is not None:
            return existing, True

        # Create document entity
        doc = Document.new(
            title=self._derive_title(filename),
            original_filename=filename,
            file_type=file_type,
            file_size_bytes=len(file_data),
            file_hash=file_hash,
            mime_type=MIME_TYPES.get(file_type, "application/octet-stream"),
            original_path="",  # set after storage
        )

        # Store file on disk
        relative_path = await self._file_storage.save_original(
            file_data, doc.id, filename
        )
        doc.original_path = relative_path

        # Transition to stored
        doc.status = ProcessingStatus.STORED

        # Persist document record
        await self._doc_repo.save(doc)

        return doc, False

    async def get(self, document_id: UUID) -> Document | None:
        return await self._doc_repo.get(document_id)

    async def list_documents(
        self,
        file_type: str | None = None,
        status: str | None = None,
        collection_id: UUID | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[Document], int]:
        docs = await self._doc_repo.list_all(
            file_type=file_type,
            status=status,
            collection_id=collection_id,
            limit=limit,
            offset=offset,
        )
        total = await self._doc_repo.count(
            file_type=file_type,
            status=status,
            collection_id=collection_id,
        )
        return docs, total

    async def update(
        self,
        document_id: UUID,
        title: str | None = None,
        tags: list[str] | None = None,
        collection_id: UUID | None = None,
        is_favorite: bool | None = None,
    ) -> Document | None:
        doc = await self._doc_repo.get(document_id)
        if doc is None:
            return None
        if title is not None:
            doc.title = title
        if tags is not None:
            doc.tags = tags
        if collection_id is not None:
            doc.collection_id = collection_id
        if is_favorite is not None:
            doc.is_favorite = is_favorite
        await self._doc_repo.update(doc)
        return doc

    async def delete(self, document_id: UUID) -> bool:
        doc = await self._doc_repo.get(document_id)
        if doc is None:
            return False
        # Clean up graph nodes and entity mentions before deleting the document
        if self._graph_repo:
            await self._graph_repo.delete_document(document_id)
        if self._entity_repo:
            await self._entity_repo.delete_by_document(document_id)
        await self._file_storage.delete_document_files(document_id)
        await self._doc_repo.delete(document_id)
        return True

    @staticmethod
    def _get_extension(filename: str) -> str:
        from pathlib import PurePosixPath
        return PurePosixPath(filename).suffix.lower()

    @staticmethod
    def _derive_title(filename: str) -> str:
        from pathlib import PurePosixPath
        return PurePosixPath(filename).stem.replace("_", " ").replace("-", " ")
