from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import func, select, update, delete
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from cortex.domain.document import Document, DocumentMetadata, FileType, ProcessingStatus
from cortex.infrastructure.persistence.tables import DocumentRow


class PGDocumentRepository:
    """DocumentRepository implementation using PostgreSQL via SQLAlchemy."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def save(self, document: Document) -> None:
        async with self._session_factory() as session:
            row = DocumentRow(
                id=document.id,
                title=document.title,
                original_filename=document.original_filename,
                file_type=document.file_type.value,
                file_size_bytes=document.file_size_bytes,
                file_hash=document.file_hash,
                mime_type=document.mime_type,
                original_path=document.original_path,
                status=document.status.value,
                thumbnail_path=document.thumbnail_path,
                parsed_content=document.parsed_content,
                rendered_markdown=document.rendered_markdown,
                rendered_html=document.rendered_html,
                page_count=document.metadata.page_count,
                word_count=document.metadata.word_count,
                language=document.metadata.language,
                author=document.metadata.author,
                tags=document.tags,
                is_favorite=document.is_favorite,
                collection_id=document.collection_id,
                created_at=document.created_at,
                updated_at=document.updated_at,
            )
            session.add(row)
            await session.commit()

    async def get(self, document_id: UUID) -> Document | None:
        async with self._session_factory() as session:
            row = await session.get(DocumentRow, document_id)
            if row is None:
                return None
            return self._to_domain(row)

    async def get_by_hash(self, file_hash: str) -> Document | None:
        async with self._session_factory() as session:
            stmt = select(DocumentRow).where(DocumentRow.file_hash == file_hash)
            result = await session.execute(stmt)
            row = result.scalar_one_or_none()
            if row is None:
                return None
            return self._to_domain(row)

    async def list_all(
        self,
        file_type: str | None = None,
        status: str | None = None,
        collection_id: UUID | None = None,
        tags: list[str] | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Document]:
        async with self._session_factory() as session:
            stmt = select(DocumentRow).order_by(DocumentRow.created_at.desc())
            if file_type is not None:
                stmt = stmt.where(DocumentRow.file_type == file_type)
            if status is not None:
                stmt = stmt.where(DocumentRow.status == status)
            if collection_id is not None:
                stmt = stmt.where(DocumentRow.collection_id == collection_id)
            if tags is not None and len(tags) > 0:
                stmt = stmt.where(DocumentRow.tags.overlap(tags))
            stmt = stmt.limit(limit).offset(offset)
            result = await session.execute(stmt)
            return [self._to_domain(row) for row in result.scalars().all()]

    async def count(
        self,
        file_type: str | None = None,
        status: str | None = None,
        collection_id: UUID | None = None,
        tags: list[str] | None = None,
    ) -> int:
        from sqlalchemy import func

        async with self._session_factory() as session:
            stmt = select(func.count(DocumentRow.id))
            if file_type is not None:
                stmt = stmt.where(DocumentRow.file_type == file_type)
            if status is not None:
                stmt = stmt.where(DocumentRow.status == status)
            if collection_id is not None:
                stmt = stmt.where(DocumentRow.collection_id == collection_id)
            if tags is not None and len(tags) > 0:
                stmt = stmt.where(DocumentRow.tags.overlap(tags))
            result = await session.execute(stmt)
            return result.scalar_one()

    async def update_status(
        self, document_id: UUID, status: str, error_message: str | None = None
    ) -> None:
        async with self._session_factory() as session:
            values: dict = {
                "status": status,
                "updated_at": datetime.now(UTC),
            }
            if error_message is not None:
                values["error_message"] = error_message
            if status == ProcessingStatus.READY.value:
                values["processed_at"] = datetime.now(UTC)
            stmt = (
                update(DocumentRow)
                .where(DocumentRow.id == document_id)
                .values(**values)
            )
            await session.execute(stmt)
            await session.commit()

    async def update(self, document: Document) -> None:
        async with self._session_factory() as session:
            stmt = (
                update(DocumentRow)
                .where(DocumentRow.id == document.id)
                .values(
                    title=document.title,
                    thumbnail_path=document.thumbnail_path,
                    parsed_content=document.parsed_content,
                    rendered_markdown=document.rendered_markdown,
                    rendered_html=document.rendered_html,
                    page_count=document.metadata.page_count,
                    word_count=document.metadata.word_count,
                    language=document.metadata.language,
                    author=document.metadata.author,
                    status=document.status.value,
                    tags=document.tags,
                    is_favorite=document.is_favorite,
                    collection_id=document.collection_id,
                    updated_at=datetime.now(UTC),
                )
            )
            await session.execute(stmt)
            await session.commit()

    async def delete(self, document_id: UUID) -> None:
        async with self._session_factory() as session:
            stmt = delete(DocumentRow).where(DocumentRow.id == document_id)
            await session.execute(stmt)
            await session.commit()

    async def search_by_title_prefix(self, prefix: str, limit: int = 5) -> list[Document]:
        async with self._session_factory() as session:
            stmt = (
                select(DocumentRow)
                .where(DocumentRow.title.ilike(f"{prefix}%"))
                .order_by(DocumentRow.updated_at.desc())
                .limit(limit)
            )
            result = await session.execute(stmt)
            return [self._to_domain(row) for row in result.scalars().all()]

    async def total_file_size(self) -> int:
        async with self._session_factory() as session:
            stmt = select(func.coalesce(func.sum(DocumentRow.file_size_bytes), 0))
            result = await session.execute(stmt)
            return result.scalar_one()

    async def distinct_tags(self) -> list[str]:
        async with self._session_factory() as session:
            stmt = select(
                func.unnest(DocumentRow.tags).label("tag")
            ).distinct().order_by("tag")
            result = await session.execute(stmt)
            return [row[0] for row in result.all()]

    @staticmethod
    def _to_domain(row: DocumentRow) -> Document:
        return Document(
            id=row.id,
            title=row.title,
            original_filename=row.original_filename,
            file_type=FileType(row.file_type),
            file_size_bytes=row.file_size_bytes,
            file_hash=row.file_hash,
            mime_type=row.mime_type,
            original_path=row.original_path,
            status=ProcessingStatus(row.status),
            thumbnail_path=row.thumbnail_path,
            parsed_content=row.parsed_content,
            rendered_markdown=row.rendered_markdown,
            rendered_html=row.rendered_html,
            metadata=DocumentMetadata(
                page_count=row.page_count,
                word_count=row.word_count,
                language=row.language,
                author=row.author,
            ),
            error_message=row.error_message,
            created_at=row.created_at,
            updated_at=row.updated_at,
            processed_at=row.processed_at,
            collection_id=row.collection_id,
            tags=row.tags or [],
            is_favorite=row.is_favorite,
        )
