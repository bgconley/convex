"""Knowledge graph repository using Apache AGE (graph extension for PostgreSQL).

AGE stores graph data in the 'knowledge_graph' graph created by init.sql.
Cypher queries are executed via the ag_catalog.cypher() SQL function.

Node types:
  - Document: {doc_id, title}
  - Entity: {normalized_name, type, name}

Edge types:
  - MENTIONS: Document -> Entity (with count, confidence)
  - CO_OCCURS: Entity -> Entity (with count, for entities in same chunk)
"""

from __future__ import annotations

import logging
from uuid import UUID, uuid4

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from cortex.domain.entity import Entity, EntityExtraction
from cortex.infrastructure.persistence.tables import EntityRow

logger = logging.getLogger(__name__)

# AGE requires these commands before any cypher() call.
# asyncpg doesn't allow multiple statements in one execute().
_AGE_PREAMBLE = [
    "LOAD 'age'",
    'SET search_path = ag_catalog, "$user", public',
]


class AGEGraphRepository:
    """GraphPort implementation using Apache AGE."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    @staticmethod
    async def _load_age(session: AsyncSession) -> None:
        """Execute AGE preamble statements."""
        for stmt in _AGE_PREAMBLE:
            await session.execute(text(stmt))

    @staticmethod
    async def _cypher(session: AsyncSession, sql: str):
        """Execute raw SQL containing Cypher.

        Uses exec_driver_sql to avoid SQLAlchemy interpreting
        Cypher edge labels like [:MENTIONS] as bind parameters.
        """
        raw_conn = await session.connection()
        return await raw_conn.exec_driver_sql(sql)

    async def add_document_entities(
        self,
        document_id: UUID,
        document_title: str,
        entities: list[EntityExtraction],
        chunk_ids: list[UUID],
    ) -> None:
        """Populate the knowledge graph for a document's extracted entities."""
        if not entities:
            return

        async with self._session_factory() as session:
            await self._load_age(session)

            # 1. Create/merge Document node
            safe_title = document_title.replace("'", "\\'")
            await self._cypher(session,
                f"SELECT * FROM cypher('knowledge_graph', $$ "
                f"MERGE (d:Document {{doc_id: '{document_id}'}}) "
                f"SET d.title = '{safe_title}' "
                f"RETURN d "
                f"$$) as (v agtype)"
            )

            # 2. Create/merge Entity nodes and MENTIONS edges
            for entity in entities:
                safe_norm = entity.normalized_name.replace("'", "\\'")
                safe_name = entity.text.replace("'", "\\'")
                safe_label = entity.label.replace("'", "\\'")

                await self._cypher(session,
                    f"SELECT * FROM cypher('knowledge_graph', $$ "
                    f"MERGE (e:Entity {{normalized_name: '{safe_norm}', type: '{safe_label}'}}) "
                    f"SET e.name = '{safe_name}' "
                    f"WITH e "
                    f"MATCH (d:Document {{doc_id: '{document_id}'}}) "
                    f"MERGE (d)-[r:MENTIONS]->(e) "
                    f"SET r.count = coalesce(r.count, 0) + 1, "
                    f"    r.confidence = {entity.confidence} "
                    f"RETURN e "
                    f"$$) as (v agtype)"
                )

            # 3. Create CO_OCCURS edges for entities in the same chunk
            chunk_entity_map: dict[UUID, list[EntityExtraction]] = {}
            for e in entities:
                if e.chunk_id is not None:
                    chunk_entity_map.setdefault(e.chunk_id, []).append(e)

            for chunk_id, chunk_entities in chunk_entity_map.items():
                for i, e1 in enumerate(chunk_entities):
                    for e2 in chunk_entities[i + 1:]:
                        safe_n1 = e1.normalized_name.replace("'", "\\'")
                        safe_n2 = e2.normalized_name.replace("'", "\\'")
                        if safe_n1 == safe_n2:
                            continue
                        await self._cypher(session,
                            f"SELECT * FROM cypher('knowledge_graph', $$ "
                            f"MATCH (a:Entity {{normalized_name: '{safe_n1}'}}), "
                            f"      (b:Entity {{normalized_name: '{safe_n2}'}}) "
                            f"MERGE (a)-[r:CO_OCCURS]->(b) "
                            f"SET r.count = coalesce(r.count, 0) + 1 "
                            f"RETURN r "
                            f"$$) as (v agtype)"
                        )

            await session.commit()
            logger.info(
                "Added %d entities to graph for document %s",
                len(entities), document_id,
            )

    async def get_related_entities(
        self, entity_id: UUID, hops: int = 2
    ) -> list[Entity]:
        """Traverse CO_OCCURS edges to find related entities."""
        async with self._session_factory() as session:
            row = await session.get(EntityRow, entity_id)
            if row is None:
                return []
            related_dicts = await self.get_related_by_name(row.normalized_name, hops=hops)
            return [
                Entity(
                    id=uuid4(),
                    name=r["name"],
                    entity_type=r["type"],
                    normalized_name=r["normalized_name"],
                )
                for r in related_dicts
            ]

    async def get_related_by_name(
        self, normalized_name: str, hops: int = 2, limit: int = 20
    ) -> list[dict]:
        """Find entities related via CO_OCCURS edges."""
        safe_name = normalized_name.replace("'", "\\'")

        async with self._session_factory() as session:
            await self._load_age(session)
            result = await self._cypher(session,
                f"SELECT * FROM cypher('knowledge_graph', $$ "
                f"MATCH (start:Entity {{normalized_name: '{safe_name}'}}) "
                f"-[:CO_OCCURS*1..{hops}]-(related:Entity) "
                f"WHERE related.normalized_name <> '{safe_name}' "
                f"RETURN DISTINCT related.normalized_name, related.type, related.name "
                f"LIMIT {int(limit)} "
                f"$$) as (normalized_name agtype, type agtype, name agtype)"
            )
            rows = result.fetchall()
            return [
                {
                    "normalized_name": _unquote_agtype(row[0]),
                    "type": _unquote_agtype(row[1]),
                    "name": _unquote_agtype(row[2]),
                }
                for row in rows
            ]

    async def get_entity_documents(
        self, entity_id: UUID
    ) -> list[tuple[UUID, str]]:
        """Get documents that mention a given entity."""
        async with self._session_factory() as session:
            row = await session.get(EntityRow, entity_id)
            if row is None:
                return []
            doc_dicts = await self.get_entity_documents_by_name(row.normalized_name)
            return [(d["document_id"], d["title"]) for d in doc_dicts]

    async def get_entity_documents_by_name(
        self, normalized_name: str
    ) -> list[dict]:
        """Get documents mentioning an entity by its normalized name."""
        safe_name = normalized_name.replace("'", "\\'")

        async with self._session_factory() as session:
            await self._load_age(session)
            result = await self._cypher(session,
                f"SELECT * FROM cypher('knowledge_graph', $$ "
                f"MATCH (d:Document)-[:MENTIONS]->(e:Entity {{normalized_name: '{safe_name}'}}) "
                f"RETURN d.doc_id, d.title "
                f"$$) as (doc_id agtype, title agtype)"
            )
            rows = result.fetchall()
            return [
                {
                    "document_id": _unquote_agtype(row[0]),
                    "title": _unquote_agtype(row[1]),
                }
                for row in rows
            ]

    async def get_document_entities(
        self, document_id: UUID
    ) -> list[Entity]:
        """Get entities mentioned in a document from the graph."""
        async with self._session_factory() as session:
            await self._load_age(session)
            result = await self._cypher(session,
                f"SELECT * FROM cypher('knowledge_graph', $$ "
                f"MATCH (d:Document {{doc_id: '{document_id}'}})-[:MENTIONS]->(e:Entity) "
                f"RETURN e.normalized_name, e.type, e.name "
                f"$$) as (normalized_name agtype, type agtype, name agtype)"
            )
            rows = result.fetchall()
            return [
                Entity(
                    id=uuid4(),
                    name=_unquote_agtype(row[2]),
                    entity_type=_unquote_agtype(row[1]),
                    normalized_name=_unquote_agtype(row[0]),
                )
                for row in rows
            ]

    async def delete_document(self, document_id: UUID) -> None:
        """Remove a document node and its MENTIONS edges from the graph."""
        async with self._session_factory() as session:
            await self._load_age(session)
            await self._cypher(session,
                f"SELECT * FROM cypher('knowledge_graph', $$ "
                f"MATCH (d:Document {{doc_id: '{document_id}'}}) "
                f"DETACH DELETE d "
                f"$$) as (v agtype)"
            )
            await session.commit()


def _unquote_agtype(val) -> str:
    """AGE returns agtype values as JSON-encoded strings."""
    s = str(val)
    if s.startswith('"') and s.endswith('"'):
        return s[1:-1]
    return s
