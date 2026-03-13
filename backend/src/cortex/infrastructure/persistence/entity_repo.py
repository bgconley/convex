"""Entity repository — persists entities and mentions in PostgreSQL."""

from __future__ import annotations

import logging
from uuid import UUID, uuid4

from sqlalchemy import delete, select, func
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from cortex.domain.entity import Entity, EntityExtraction
from cortex.infrastructure.persistence.tables import EntityMentionRow, EntityRow

logger = logging.getLogger(__name__)


class PGEntityRepository:
    """EntityRepository implementation using PostgreSQL."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def upsert_entities(
        self,
        document_id: UUID,
        extractions: list[EntityExtraction],
        chunk_ids: list[UUID],
    ) -> list[Entity]:
        """Upsert entities and create mentions.

        - Deduplicates by (normalized_name, entity_type)
        - Creates or updates entity rows
        - Creates entity_mention rows linking to chunks and documents
        - Updates aggregate counts
        """
        if not extractions:
            return []

        async with self._session_factory() as session:
            entities: list[Entity] = []

            # Group extractions by (normalized_name, entity_type)
            grouped: dict[tuple[str, str], list[EntityExtraction]] = {}
            for ext in extractions:
                key = (ext.normalized_name, ext.label)
                grouped.setdefault(key, []).append(ext)

            for (norm_name, entity_type), exts in grouped.items():
                # Upsert entity
                stmt = select(EntityRow).where(
                    EntityRow.normalized_name == norm_name,
                    EntityRow.entity_type == entity_type,
                )
                result = await session.execute(stmt)
                row = result.scalar_one_or_none()

                if row is None:
                    row = EntityRow(
                        id=uuid4(),
                        name=exts[0].text,
                        entity_type=entity_type,
                        normalized_name=norm_name,
                    )
                    session.add(row)
                    await session.flush()

                entity_id = row.id

                # Create mentions
                for ext in exts:
                    if ext.chunk_id is None:
                        continue
                    mention = EntityMentionRow(
                        id=uuid4(),
                        entity_id=entity_id,
                        chunk_id=ext.chunk_id,
                        document_id=document_id,
                        mention_text=ext.text,
                        start_char=ext.start_char,
                        end_char=ext.end_char,
                        confidence=ext.confidence,
                    )
                    session.add(mention)

                # Update counts
                mention_count = await session.scalar(
                    select(func.count()).where(EntityMentionRow.entity_id == entity_id)
                )
                doc_count = await session.scalar(
                    select(func.count(func.distinct(EntityMentionRow.document_id))).where(
                        EntityMentionRow.entity_id == entity_id
                    )
                )
                row.mention_count = mention_count or 0
                row.document_count = doc_count or 0

                entities.append(self._to_domain(row))

            await session.commit()
            logger.info("Upserted %d entities with %d mentions", len(entities), len(extractions))
            return entities

    async def get_by_document(self, document_id: UUID) -> list[Entity]:
        async with self._session_factory() as session:
            stmt = (
                select(EntityRow)
                .join(EntityMentionRow, EntityMentionRow.entity_id == EntityRow.id)
                .where(EntityMentionRow.document_id == document_id)
                .distinct()
                .order_by(EntityRow.mention_count.desc())
            )
            result = await session.execute(stmt)
            return [self._to_domain(row) for row in result.scalars().all()]

    async def list_all(
        self, entity_type: str | None = None, limit: int = 100, offset: int = 0
    ) -> list[Entity]:
        async with self._session_factory() as session:
            stmt = select(EntityRow).order_by(EntityRow.mention_count.desc())
            if entity_type:
                stmt = stmt.where(EntityRow.entity_type == entity_type)
            stmt = stmt.limit(limit).offset(offset)
            result = await session.execute(stmt)
            return [self._to_domain(row) for row in result.scalars().all()]

    async def get(self, entity_id: UUID) -> Entity | None:
        async with self._session_factory() as session:
            row = await session.get(EntityRow, entity_id)
            return self._to_domain(row) if row else None

    async def count(self, entity_type: str | None = None) -> int:
        async with self._session_factory() as session:
            stmt = select(func.count()).select_from(EntityRow)
            if entity_type:
                stmt = stmt.where(EntityRow.entity_type == entity_type)
            result = await session.scalar(stmt)
            return result or 0

    async def search_by_prefix(self, prefix: str, limit: int = 5) -> list[Entity]:
        async with self._session_factory() as session:
            stmt = (
                select(EntityRow)
                .where(EntityRow.name.ilike(f"{prefix}%"))
                .order_by(EntityRow.mention_count.desc())
                .limit(limit)
            )
            result = await session.execute(stmt)
            return [self._to_domain(row) for row in result.scalars().all()]

    async def delete_by_document(self, document_id: UUID) -> None:
        """Delete mentions for a document, recompute counts, remove orphaned entities."""
        async with self._session_factory() as session:
            # Find affected entity IDs before deleting mentions
            affected_stmt = (
                select(EntityMentionRow.entity_id)
                .where(EntityMentionRow.document_id == document_id)
                .distinct()
            )
            affected_result = await session.execute(affected_stmt)
            affected_ids = [row[0] for row in affected_result.fetchall()]

            # Delete mention rows for this document
            await session.execute(
                delete(EntityMentionRow).where(EntityMentionRow.document_id == document_id)
            )

            # Recompute counts and remove orphans
            for entity_id in affected_ids:
                mention_count = await session.scalar(
                    select(func.count()).where(EntityMentionRow.entity_id == entity_id)
                )
                if mention_count == 0:
                    # No remaining mentions — delete the entity
                    await session.execute(
                        delete(EntityRow).where(EntityRow.id == entity_id)
                    )
                else:
                    # Recompute counts
                    doc_count = await session.scalar(
                        select(func.count(func.distinct(EntityMentionRow.document_id))).where(
                            EntityMentionRow.entity_id == entity_id
                        )
                    )
                    entity_row = await session.get(EntityRow, entity_id)
                    if entity_row:
                        entity_row.mention_count = mention_count
                        entity_row.document_count = doc_count or 0

            await session.commit()

    @staticmethod
    def _to_domain(row: EntityRow) -> Entity:
        return Entity(
            id=row.id,
            name=row.name,
            entity_type=row.entity_type,
            normalized_name=row.normalized_name,
            description=row.description,
            document_count=row.document_count,
            mention_count=row.mention_count,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )
