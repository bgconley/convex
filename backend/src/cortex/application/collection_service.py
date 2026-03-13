"""Collection service — use-case orchestration for collection CRUD."""

from __future__ import annotations

from uuid import UUID

from cortex.domain.collection import Collection
from cortex.domain.ports import CollectionRepository


class CollectionService:
    """Manages collection lifecycle operations."""

    def __init__(self, collection_repo: CollectionRepository) -> None:
        self._repo = collection_repo

    async def create(
        self,
        name: str,
        description: str | None = None,
        icon: str | None = None,
        parent_id: UUID | None = None,
        sort_order: int = 0,
        filter_json: dict | None = None,
    ) -> Collection:
        collection = Collection.new(
            name=name,
            description=description,
            icon=icon,
            parent_id=parent_id,
            sort_order=sort_order,
            filter_json=filter_json,
        )
        await self._repo.save(collection)
        return collection

    async def get(self, collection_id: UUID) -> Collection | None:
        return await self._repo.get(collection_id)

    async def list_collections(
        self,
        parent_id: UUID | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[list[Collection], int]:
        collections = await self._repo.list_all(
            parent_id=parent_id, limit=limit, offset=offset
        )
        total = await self._repo.count(parent_id=parent_id)
        return collections, total

    async def update(
        self,
        collection_id: UUID,
        fields: set[str],
        name: str | None = None,
        description: str | None = None,
        icon: str | None = None,
        parent_id: UUID | None = None,
        sort_order: int | None = None,
        filter_json: dict | None = None,
    ) -> Collection | None:
        collection = await self._repo.get(collection_id)
        if collection is None:
            return None
        if "name" in fields and name is not None:
            collection.name = name
        if "description" in fields:
            collection.description = description
        if "icon" in fields:
            collection.icon = icon
        if "parent_id" in fields:
            collection.parent_id = parent_id
        if "sort_order" in fields and sort_order is not None:
            collection.sort_order = sort_order
        if "filter_json" in fields:
            collection.filter_json = filter_json
        await self._repo.update(collection)
        return collection

    async def delete(self, collection_id: UUID) -> bool:
        collection = await self._repo.get(collection_id)
        if collection is None:
            return False
        await self._repo.delete(collection_id)
        return True
