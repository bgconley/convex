"""Entity service — use-case orchestration for entity browsing and graph exploration."""

from __future__ import annotations

from uuid import UUID

from cortex.domain.entity import Entity
from cortex.domain.ports import EntityRepository, GraphPort


class EntityService:
    """Coordinates entity queries across the relational store and knowledge graph."""

    def __init__(
        self,
        entity_repo: EntityRepository,
        graph_repo: GraphPort,
    ) -> None:
        self._entity_repo = entity_repo
        self._graph_repo = graph_repo

    async def list_entities(
        self,
        entity_type: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[list[Entity], int]:
        entities = await self._entity_repo.list_all(
            entity_type=entity_type, limit=limit, offset=offset
        )
        total = await self._entity_repo.count(entity_type=entity_type)
        return entities, total

    async def get(self, entity_id: UUID) -> Entity | None:
        return await self._entity_repo.get(entity_id)

    async def list_entity_types(self) -> list[str]:
        return await self._entity_repo.distinct_types()

    async def get_entity_documents(
        self, entity_id: UUID
    ) -> list[tuple[UUID, str]]:
        return await self._graph_repo.get_entity_documents(entity_id)

    async def get_related_entities(
        self, entity_id: UUID, hops: int = 2
    ) -> list[Entity]:
        return await self._graph_repo.get_related_entities(entity_id, hops=hops)

    async def get_document_entities(self, document_id: UUID) -> list[Entity]:
        return await self._entity_repo.get_by_document(document_id)
