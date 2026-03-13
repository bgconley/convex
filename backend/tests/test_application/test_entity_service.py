"""Tests for EntityService — application-layer entity browsing and graph exploration.

Uses protocol test doubles (no mocking framework). Runs locally without
GPU, DB, or network dependencies.
"""

from __future__ import annotations

import pytest
from datetime import UTC, datetime
from uuid import UUID, uuid4

from cortex.domain.entity import Entity, EntityExtraction
from cortex.application.entity_service import EntityService


# -- Protocol test doubles --


class FakeEntityRepo:
    """EntityRepository test double."""

    def __init__(self, entities: list[Entity] | None = None):
        self._entities = entities or []

    async def upsert_entities(
        self, document_id: UUID, extractions: list[EntityExtraction], chunk_ids: list[UUID]
    ) -> list[Entity]:
        return []

    async def get_by_document(self, document_id: UUID) -> list[Entity]:
        return self._entities

    async def list_all(
        self, entity_type: str | None = None, limit: int = 100, offset: int = 0
    ) -> list[Entity]:
        filtered = self._entities
        if entity_type:
            filtered = [e for e in filtered if e.entity_type == entity_type]
        return filtered[offset : offset + limit]

    async def get(self, entity_id: UUID) -> Entity | None:
        for e in self._entities:
            if e.id == entity_id:
                return e
        return None

    async def count(self, entity_type: str | None = None) -> int:
        if entity_type:
            return len([e for e in self._entities if e.entity_type == entity_type])
        return len(self._entities)

    async def distinct_types(self) -> list[str]:
        return sorted({e.entity_type for e in self._entities})

    async def delete_by_document(self, document_id: UUID) -> None:
        pass


class FakeGraphRepo:
    """GraphPort test double."""

    def __init__(
        self,
        related: list[Entity] | None = None,
        documents: list[tuple[UUID, str]] | None = None,
    ):
        self._related = related or []
        self._documents = documents or []

    async def add_document_entities(
        self, document_id: UUID, document_title: str,
        entities: list[EntityExtraction], chunk_ids: list[UUID],
    ) -> None:
        pass

    async def get_related_entities(self, entity_id: UUID, hops: int = 2) -> list[Entity]:
        return self._related

    async def get_related_by_name(
        self, normalized_name: str, hops: int = 2, limit: int = 20
    ) -> list[dict]:
        return []

    async def get_entity_documents(self, entity_id: UUID) -> list[tuple[UUID, str]]:
        return self._documents

    async def get_document_entities(self, document_id: UUID) -> list[Entity]:
        return []

    async def delete_document(self, document_id: UUID) -> None:
        pass


# -- Helpers --


def _make_entity(
    name: str = "Python",
    entity_type: str = "technology",
    doc_count: int = 3,
    mention_count: int = 7,
    entity_id: UUID | None = None,
) -> Entity:
    return Entity(
        id=entity_id or uuid4(),
        name=name,
        entity_type=entity_type,
        normalized_name=name.lower().strip(),
        document_count=doc_count,
        mention_count=mention_count,
    )


# -- Tests --


@pytest.mark.asyncio
async def test_list_entities_returns_all():
    entities = [_make_entity("Python"), _make_entity("FastAPI", "software")]
    service = EntityService(
        entity_repo=FakeEntityRepo(entities),
        graph_repo=FakeGraphRepo(),
    )
    result, total = await service.list_entities()
    assert len(result) == 2
    assert total == 2


@pytest.mark.asyncio
async def test_list_entities_filters_by_type():
    entities = [
        _make_entity("Python", "technology"),
        _make_entity("FastAPI", "software"),
        _make_entity("PostgreSQL", "technology"),
    ]
    service = EntityService(
        entity_repo=FakeEntityRepo(entities),
        graph_repo=FakeGraphRepo(),
    )
    result, total = await service.list_entities(entity_type="technology")
    assert len(result) == 2
    assert total == 2
    assert all(e.entity_type == "technology" for e in result)


@pytest.mark.asyncio
async def test_list_entities_pagination():
    entities = [_make_entity(f"Entity{i}") for i in range(5)]
    service = EntityService(
        entity_repo=FakeEntityRepo(entities),
        graph_repo=FakeGraphRepo(),
    )
    result, total = await service.list_entities(limit=2, offset=1)
    assert len(result) == 2
    assert total == 5


@pytest.mark.asyncio
async def test_get_entity_found():
    eid = uuid4()
    entity = _make_entity("Python", entity_id=eid)
    service = EntityService(
        entity_repo=FakeEntityRepo([entity]),
        graph_repo=FakeGraphRepo(),
    )
    result = await service.get(eid)
    assert result is not None
    assert result.name == "Python"


@pytest.mark.asyncio
async def test_get_entity_not_found():
    service = EntityService(
        entity_repo=FakeEntityRepo([]),
        graph_repo=FakeGraphRepo(),
    )
    result = await service.get(uuid4())
    assert result is None


@pytest.mark.asyncio
async def test_get_entity_documents():
    eid = uuid4()
    doc1 = (uuid4(), "Architecture Guide")
    doc2 = (uuid4(), "Setup Manual")
    service = EntityService(
        entity_repo=FakeEntityRepo([_make_entity(entity_id=eid)]),
        graph_repo=FakeGraphRepo(documents=[doc1, doc2]),
    )
    docs = await service.get_entity_documents(eid)
    assert len(docs) == 2
    assert docs[0][1] == "Architecture Guide"


@pytest.mark.asyncio
async def test_get_related_entities():
    eid = uuid4()
    related = [
        _make_entity("FastAPI", "software"),
        _make_entity("PostgreSQL", "technology"),
    ]
    service = EntityService(
        entity_repo=FakeEntityRepo([_make_entity(entity_id=eid)]),
        graph_repo=FakeGraphRepo(related=related),
    )
    result = await service.get_related_entities(eid, hops=2)
    assert len(result) == 2
    assert result[0].name == "FastAPI"


@pytest.mark.asyncio
async def test_get_document_entities():
    doc_id = uuid4()
    entities = [_make_entity("Python"), _make_entity("Docker")]
    service = EntityService(
        entity_repo=FakeEntityRepo(entities),
        graph_repo=FakeGraphRepo(),
    )
    result = await service.get_document_entities(doc_id)
    assert len(result) == 2


@pytest.mark.asyncio
async def test_list_entity_types_returns_distinct_sorted_types():
    entities = [
        _make_entity("Python", "technology"),
        _make_entity("FastAPI", "software"),
        _make_entity("Docker", "technology"),
    ]
    service = EntityService(
        entity_repo=FakeEntityRepo(entities),
        graph_repo=FakeGraphRepo(),
    )
    result = await service.list_entity_types()
    assert result == ["software", "technology"]
