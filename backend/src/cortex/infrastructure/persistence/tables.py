from datetime import UTC, datetime
from uuid import uuid4

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class CollectionRow(Base):
    __tablename__ = "collections"

    id: Mapped[uuid4] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    icon: Mapped[str | None] = mapped_column(String(100))
    parent_id: Mapped[uuid4 | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("collections.id")
    )
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))

    documents: Mapped[list["DocumentRow"]] = relationship(back_populates="collection")


class DocumentRow(Base):
    __tablename__ = "documents"

    id: Mapped[uuid4] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    original_filename: Mapped[str] = mapped_column(Text, nullable=False)
    file_type: Mapped[str] = mapped_column(String(20), nullable=False)
    file_size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    file_hash: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    mime_type: Mapped[str] = mapped_column(String(100), nullable=False)

    original_path: Mapped[str] = mapped_column(Text, nullable=False)
    thumbnail_path: Mapped[str | None] = mapped_column(Text)

    parsed_content: Mapped[dict | None] = mapped_column(JSONB)
    rendered_markdown: Mapped[str | None] = mapped_column(Text)
    rendered_html: Mapped[str | None] = mapped_column(Text)

    page_count: Mapped[int | None] = mapped_column(Integer)
    word_count: Mapped[int | None] = mapped_column(Integer)
    language: Mapped[str] = mapped_column(String(10), default="en")
    author: Mapped[str | None] = mapped_column(Text)
    subject: Mapped[str | None] = mapped_column(Text)

    status: Mapped[str] = mapped_column(String(30), nullable=False, default="uploading")
    error_message: Mapped[str | None] = mapped_column(Text)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    collection_id: Mapped[uuid4 | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("collections.id", ondelete="SET NULL")
    )
    tags: Mapped[list[str]] = mapped_column(ARRAY(Text), default=list)
    is_favorite: Mapped[bool] = mapped_column(Boolean, default=False)

    collection: Mapped[CollectionRow | None] = relationship(back_populates="documents")
    chunks: Mapped[list["ChunkRow"]] = relationship(
        back_populates="document", cascade="all, delete-orphan"
    )
    images: Mapped[list["DocumentImageRow"]] = relationship(
        back_populates="document", cascade="all, delete-orphan"
    )


class ChunkRow(Base):
    __tablename__ = "chunks"
    __table_args__ = (UniqueConstraint("document_id", "chunk_index"),)

    id: Mapped[uuid4] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    document_id: Mapped[uuid4] = mapped_column(
        UUID(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False
    )

    chunk_text: Mapped[str] = mapped_column(Text, nullable=False)
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    start_char: Mapped[int] = mapped_column(Integer, nullable=False)
    end_char: Mapped[int] = mapped_column(Integer, nullable=False)
    token_count: Mapped[int] = mapped_column(Integer, nullable=False)

    section_heading: Mapped[str | None] = mapped_column(Text)
    section_level: Mapped[int | None] = mapped_column(Integer)
    page_number: Mapped[int | None] = mapped_column(Integer)

    embedding = mapped_column(Vector(1024))

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))

    document: Mapped[DocumentRow] = relationship(back_populates="chunks")


class EntityRow(Base):
    __tablename__ = "entities"
    __table_args__ = (UniqueConstraint("normalized_name", "entity_type"),)

    id: Mapped[uuid4] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    entity_type: Mapped[str] = mapped_column(String(50), nullable=False)
    normalized_name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    document_count: Mapped[int] = mapped_column(Integer, default=0)
    mention_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))

    mentions: Mapped[list["EntityMentionRow"]] = relationship(
        back_populates="entity", cascade="all, delete-orphan"
    )


class EntityMentionRow(Base):
    __tablename__ = "entity_mentions"
    __table_args__ = (UniqueConstraint("entity_id", "chunk_id", "start_char"),)

    id: Mapped[uuid4] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    entity_id: Mapped[uuid4] = mapped_column(
        UUID(as_uuid=True), ForeignKey("entities.id", ondelete="CASCADE"), nullable=False
    )
    chunk_id: Mapped[uuid4] = mapped_column(
        UUID(as_uuid=True), ForeignKey("chunks.id", ondelete="CASCADE"), nullable=False
    )
    document_id: Mapped[uuid4] = mapped_column(
        UUID(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False
    )

    mention_text: Mapped[str] = mapped_column(Text, nullable=False)
    start_char: Mapped[int] = mapped_column(Integer, nullable=False)
    end_char: Mapped[int] = mapped_column(Integer, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))

    entity: Mapped[EntityRow] = relationship(back_populates="mentions")


class DocumentImageRow(Base):
    __tablename__ = "document_images"

    id: Mapped[uuid4] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    document_id: Mapped[uuid4] = mapped_column(
        UUID(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False
    )
    image_path: Mapped[str] = mapped_column(Text, nullable=False)
    page_number: Mapped[int | None] = mapped_column(Integer)
    caption: Mapped[str | None] = mapped_column(Text)
    alt_text: Mapped[str | None] = mapped_column(Text)
    width: Mapped[int | None] = mapped_column(Integer)
    height: Mapped[int | None] = mapped_column(Integer)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))

    document: Mapped[DocumentRow] = relationship(back_populates="images")
