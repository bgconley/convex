from __future__ import annotations

from uuid import UUID

from sqlalchemy import delete, select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from cortex.domain.chunk import Chunk, ScoredChunk
from cortex.infrastructure.persistence.tables import ChunkRow


class PGChunkRepository:
    """ChunkRepository implementation using PostgreSQL + pgvector."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def save_chunks(self, chunks: list[Chunk]) -> None:
        async with self._session_factory() as session:
            for chunk in chunks:
                row = ChunkRow(
                    id=chunk.id,
                    document_id=chunk.document_id,
                    chunk_text=chunk.chunk_text,
                    chunk_index=chunk.chunk_index,
                    start_char=chunk.start_char,
                    end_char=chunk.end_char,
                    token_count=chunk.token_count,
                    section_heading=chunk.section_heading,
                    section_level=chunk.section_level,
                    page_number=chunk.page_number,
                    embedding=chunk.embedding,
                )
                session.add(row)
            await session.commit()

    async def delete_by_document(self, document_id: UUID) -> None:
        async with self._session_factory() as session:
            stmt = delete(ChunkRow).where(ChunkRow.document_id == document_id)
            await session.execute(stmt)
            await session.commit()

    async def get_by_document(self, document_id: UUID) -> list[Chunk]:
        async with self._session_factory() as session:
            stmt = (
                select(ChunkRow)
                .where(ChunkRow.document_id == document_id)
                .order_by(ChunkRow.chunk_index)
            )
            result = await session.execute(stmt)
            return [self._to_domain(row) for row in result.scalars().all()]

    async def vector_search(
        self, query_vec: list[float], top_k: int = 50
    ) -> list[ScoredChunk]:
        vec_str = "[" + ",".join(str(v) for v in query_vec) + "]"
        sql = text(
            f"SELECT c.id, c.document_id, c.chunk_text, c.chunk_index, "
            f"c.start_char, c.end_char, c.section_heading, c.page_number, "
            f"1 - (c.embedding <=> '{vec_str}'::vector) as similarity "
            f"FROM chunks c "
            f"WHERE c.embedding IS NOT NULL "
            f"ORDER BY c.embedding <=> '{vec_str}'::vector "
            f"LIMIT {top_k}"
        )
        async with self._session_factory() as session:
            result = await session.execute(sql)
            rows = result.fetchall()
            return [
                ScoredChunk(
                    chunk_id=row[0],
                    document_id=row[1],
                    chunk_text=row[2],
                    chunk_index=row[3],
                    start_char=row[4],
                    end_char=row[5],
                    section_heading=row[6],
                    page_number=row[7],
                    score=float(row[8]),
                )
                for row in rows
            ]

    async def bm25_search(
        self, query: str, top_k: int = 50
    ) -> list[ScoredChunk]:
        from cortex.infrastructure.search.bm25_search import BM25SearchAdapter

        adapter = BM25SearchAdapter(self._session_factory)
        return await adapter.search(query, top_k=top_k)

    async def count(self) -> int:
        from sqlalchemy import func

        async with self._session_factory() as session:
            stmt = select(func.count(ChunkRow.id))
            result = await session.execute(stmt)
            return result.scalar_one()

    @staticmethod
    def _to_domain(row: ChunkRow) -> Chunk:
        return Chunk(
            id=row.id,
            document_id=row.document_id,
            chunk_text=row.chunk_text,
            chunk_index=row.chunk_index,
            start_char=row.start_char,
            end_char=row.end_char,
            token_count=row.token_count,
            section_heading=row.section_heading,
            section_level=row.section_level,
            page_number=row.page_number,
            embedding=list(row.embedding) if row.embedding is not None else None,
            created_at=row.created_at,
        )
