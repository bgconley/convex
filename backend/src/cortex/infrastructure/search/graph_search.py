"""Graph-based candidate retrieval via entity expansion.

Pipeline:
  1. Look up query entity names in the entities table → entity IDs
  2. Traverse CO_OCCURS edges in Apache AGE (1-hop, then 2-hop) → related entity names
  3. Look up related entities → more entity IDs
  4. Query entity_mentions + chunks for all entity IDs
  5. Score by graph distance (direct=1.0, 1-hop=0.5, 2-hop=0.25) × mention confidence
  6. Deduplicate by chunk_id (keep max score), return top-k ScoredChunks
"""

from __future__ import annotations

import logging
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from cortex.domain.chunk import ScoredChunk
from cortex.domain.ports import GraphPort

logger = logging.getLogger(__name__)

# Distance weights for scoring — closer in graph = higher weight
_WEIGHT_DIRECT = 1.0   # Query entity appears in chunk
_WEIGHT_1HOP = 0.5     # 1-hop CO_OCCURS neighbor
_WEIGHT_2HOP = 0.25    # 2-hop CO_OCCURS neighbor


class GraphSearchAdapter:
    """GraphSearchPort implementation — entity expansion via AGE + chunk lookup."""

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        graph_repo: GraphPort,
    ) -> None:
        self._session_factory = session_factory
        self._graph_repo = graph_repo

    async def search_by_entities(
        self, entity_names: list[str], top_k: int = 50
    ) -> list[ScoredChunk]:
        """Find chunks related to the given entity names via graph expansion.

        Returns chunks scored by graph distance and mention confidence,
        suitable for RRF fusion with vector and BM25 results.
        """
        if not entity_names:
            return []

        # 1. Look up query entities in PG → build distance map
        #    {normalized_name: distance_weight}
        entity_weights: dict[str, float] = {}
        for name in entity_names:
            entity_weights[name.lower().strip()] = _WEIGHT_DIRECT

        # 2. Graph expansion: for each query entity, traverse CO_OCCURS
        for name in entity_names:
            norm = name.lower().strip()
            try:
                # 1-hop neighbors
                one_hop = await self._graph_repo.get_related_by_name(
                    norm, hops=1, limit=20
                )
                one_hop_names = set()
                for r in one_hop:
                    rn = r["normalized_name"]
                    one_hop_names.add(rn)
                    if rn not in entity_weights:
                        entity_weights[rn] = _WEIGHT_1HOP

                # 2-hop neighbors (excludes already-found)
                two_hop = await self._graph_repo.get_related_by_name(
                    norm, hops=2, limit=30
                )
                for r in two_hop:
                    rn = r["normalized_name"]
                    if rn not in entity_weights:
                        entity_weights[rn] = _WEIGHT_2HOP
            except Exception:
                logger.warning(
                    "Graph expansion failed for entity '%s'", norm, exc_info=True
                )
                continue

        if not entity_weights:
            return []

        # 3. Look up entity IDs by normalized_name and map to weights
        entity_id_weights = await self._resolve_entity_ids(entity_weights)
        if not entity_id_weights:
            return []

        # 4. Query entity_mentions + chunks → scored chunks
        return await self._fetch_chunks(entity_id_weights, top_k)

    async def _resolve_entity_ids(
        self, entity_weights: dict[str, float]
    ) -> dict[UUID, float]:
        """Look up entity IDs by normalized_name, return {entity_id: weight}."""
        names = list(entity_weights.keys())
        if not names:
            return {}

        # Build parameterized IN clause
        placeholders = ", ".join(f":n{i}" for i in range(len(names)))
        params = {f"n{i}": n for i, n in enumerate(names)}

        sql = text(
            f"SELECT id, normalized_name FROM entities "
            f"WHERE normalized_name IN ({placeholders})"
        )

        async with self._session_factory() as session:
            result = await session.execute(sql, params)
            rows = result.fetchall()

        return {
            row[0]: entity_weights.get(row[1], _WEIGHT_2HOP)
            for row in rows
        }

    async def _fetch_chunks(
        self, entity_id_weights: dict[UUID, float], top_k: int
    ) -> list[ScoredChunk]:
        """Query entity_mentions + chunks, score by distance × confidence."""
        entity_ids = list(entity_id_weights.keys())
        if not entity_ids:
            return []

        # Build parameterized ANY clause
        placeholders = ", ".join(f":e{i}" for i in range(len(entity_ids)))
        params: dict[str, str | int] = {
            f"e{i}": str(eid) for i, eid in enumerate(entity_ids)
        }
        # Fetch more than top_k to allow deduplication
        fetch_limit = min(top_k * 3, 200)
        params["fetch_limit"] = fetch_limit

        sql = text(
            "SELECT em.entity_id, em.chunk_id, em.confidence, "
            "c.document_id, c.chunk_text, c.chunk_index, "
            "c.start_char, c.end_char, c.section_heading, c.page_number "
            "FROM entity_mentions em "
            "JOIN chunks c ON c.id = em.chunk_id "
            f"WHERE em.entity_id::text IN ({placeholders}) "
            "ORDER BY em.confidence DESC "
            "LIMIT :fetch_limit"
        )

        async with self._session_factory() as session:
            result = await session.execute(sql, params)
            rows = result.fetchall()

        # Score and deduplicate by chunk_id
        chunk_scores: dict[UUID, float] = {}
        chunk_data: dict[UUID, tuple] = {}

        for row in rows:
            entity_id = row[0]
            chunk_id = row[1]
            confidence = float(row[2])

            distance_weight = entity_id_weights.get(entity_id, _WEIGHT_2HOP)
            score = distance_weight * confidence

            if chunk_id not in chunk_scores or score > chunk_scores[chunk_id]:
                chunk_scores[chunk_id] = score
                chunk_data[chunk_id] = row

        # Sort by score descending, take top_k
        sorted_chunks = sorted(
            chunk_scores.items(), key=lambda x: x[1], reverse=True
        )[:top_k]

        return [
            ScoredChunk(
                chunk_id=cid,
                document_id=chunk_data[cid][3],
                chunk_text=chunk_data[cid][4],
                chunk_index=chunk_data[cid][5],
                start_char=chunk_data[cid][6],
                end_char=chunk_data[cid][7],
                section_heading=chunk_data[cid][8],
                page_number=chunk_data[cid][9],
                score=score,
            )
            for cid, score in sorted_chunks
        ]
