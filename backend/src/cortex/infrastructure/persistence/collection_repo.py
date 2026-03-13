from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from cortex.domain.collection import Collection
from cortex.infrastructure.persistence.tables import CollectionRow


class PGCollectionRepository:
    """CollectionRepository implementation using PostgreSQL via SQLAlchemy."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def save(self, collection: Collection) -> None:
        async with self._session_factory() as session:
            row = CollectionRow(
                id=collection.id,
                name=collection.name,
                description=collection.description,
                icon=collection.icon,
                parent_id=collection.parent_id,
                sort_order=collection.sort_order,
                filter_json=collection.filter_json,
                created_at=collection.created_at,
                updated_at=collection.updated_at,
            )
            session.add(row)
            await session.commit()

    async def get(self, collection_id: UUID) -> Collection | None:
        async with self._session_factory() as session:
            row = await session.get(CollectionRow, collection_id)
            if row is None:
                return None
            return self._to_domain(row)

    async def list_all(
        self,
        parent_id: UUID | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Collection]:
        async with self._session_factory() as session:
            stmt = select(CollectionRow).order_by(
                CollectionRow.sort_order, CollectionRow.name
            )
            if parent_id is not None:
                stmt = stmt.where(CollectionRow.parent_id == parent_id)
            stmt = stmt.limit(limit).offset(offset)
            result = await session.execute(stmt)
            return [self._to_domain(row) for row in result.scalars().all()]

    async def count(self, parent_id: UUID | None = None) -> int:
        async with self._session_factory() as session:
            stmt = select(func.count(CollectionRow.id))
            if parent_id is not None:
                stmt = stmt.where(CollectionRow.parent_id == parent_id)
            result = await session.execute(stmt)
            return result.scalar_one()

    async def update(self, collection: Collection) -> None:
        async with self._session_factory() as session:
            stmt = (
                update(CollectionRow)
                .where(CollectionRow.id == collection.id)
                .values(
                    name=collection.name,
                    description=collection.description,
                    icon=collection.icon,
                    parent_id=collection.parent_id,
                    sort_order=collection.sort_order,
                    filter_json=collection.filter_json,
                    updated_at=datetime.now(UTC),
                )
            )
            await session.execute(stmt)
            await session.commit()

    async def delete(self, collection_id: UUID) -> None:
        async with self._session_factory() as session:
            stmt = delete(CollectionRow).where(CollectionRow.id == collection_id)
            await session.execute(stmt)
            await session.commit()

    @staticmethod
    def _to_domain(row: CollectionRow) -> Collection:
        return Collection(
            id=row.id,
            name=row.name,
            description=row.description,
            icon=row.icon,
            parent_id=row.parent_id,
            sort_order=row.sort_order,
            filter_json=row.filter_json,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )
