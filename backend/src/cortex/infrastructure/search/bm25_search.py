"""BM25 full-text search adapter using ParadeDB pg_search.

pg_search provides BM25 full-text search via the Tantivy engine. Operators:
  - `|||` — match disjunction (OR): rows containing any query term
  - `&&&` — match conjunction (AND): rows containing all query terms
  - `###` — phrase match: rows containing the exact phrase
  - `pdb.score(key_field)` — BM25 relevance score

The legacy `@@@` operator is still supported but we use the newer syntax.
Index creation is handled by Alembic migration (add_bm25_indexes).
"""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from cortex.domain.chunk import ScoredChunk

# Prefixes used by SearchService._parse_bm25_query
_PHRASE_PREFIX = "PHRASE:"
_MIXED_PREFIX = "MIXED:"
_AND_PREFIX = "AND:"


class BM25SearchAdapter:
    """Performs BM25 keyword search on chunks using pg_search indexes."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def search(self, query: str, top_k: int = 50) -> list[ScoredChunk]:
        """Search chunks by BM25 relevance using pg_search.

        Query format (set by SearchService._parse_bm25_query):
          - "PHRASE:<text>"  → exact phrase search (### operator)
          - "AND:<text>"     → conjunction search (&&& operator)
          - "MIXED:<phrase>|OR:<kw>" or "MIXED:<phrase>|AND:<kw>" → phrase + keyword, merged
          - plain text       → disjunction search (||| operator)
        """
        if not query.strip():
            return []

        if query.startswith(_MIXED_PREFIX):
            parts = query[len(_MIXED_PREFIX):].split("|", 1)
            phrase = parts[0]
            kw_part = parts[1] if len(parts) > 1 else ""
            return await self._mixed_search(phrase, kw_part, top_k)
        elif query.startswith(_PHRASE_PREFIX):
            phrase = query[len(_PHRASE_PREFIX):]
            return await self._phrase_search(phrase, top_k)
        elif query.startswith(_AND_PREFIX):
            terms = query[len(_AND_PREFIX):]
            return await self._conjunction_search(terms, top_k)
        else:
            return await self._disjunction_search(query, top_k)

    async def _disjunction_search(self, query: str, top_k: int) -> list[ScoredChunk]:
        """BM25 disjunction search (OR) using ||| operator."""
        safe_query = query.replace("'", "''")
        sql = text(
            "SELECT c.id, c.document_id, c.chunk_text, c.chunk_index, "
            "c.start_char, c.end_char, c.section_heading, c.page_number, "
            "pdb.score(c.id) AS bm25_score "
            "FROM chunks c "
            "JOIN documents d ON d.id = c.document_id "
            f"WHERE d.status = 'ready' AND c.chunk_text ||| '{safe_query}' "
            "ORDER BY bm25_score DESC "
            f"LIMIT {int(top_k)}"
        )
        return await self._execute(sql)

    async def _conjunction_search(self, query: str, top_k: int) -> list[ScoredChunk]:
        """BM25 conjunction search (AND) using &&& operator."""
        safe_query = query.replace("'", "''")
        sql = text(
            "SELECT c.id, c.document_id, c.chunk_text, c.chunk_index, "
            "c.start_char, c.end_char, c.section_heading, c.page_number, "
            "pdb.score(c.id) AS bm25_score "
            "FROM chunks c "
            "JOIN documents d ON d.id = c.document_id "
            f"WHERE d.status = 'ready' AND c.chunk_text &&& '{safe_query}' "
            "ORDER BY bm25_score DESC "
            f"LIMIT {int(top_k)}"
        )
        return await self._execute(sql)

    async def _phrase_search(self, phrase: str, top_k: int) -> list[ScoredChunk]:
        """BM25 phrase search using ### operator."""
        safe_phrase = phrase.replace("'", "''")
        sql = text(
            "SELECT c.id, c.document_id, c.chunk_text, c.chunk_index, "
            "c.start_char, c.end_char, c.section_heading, c.page_number, "
            "pdb.score(c.id) AS bm25_score "
            "FROM chunks c "
            "JOIN documents d ON d.id = c.document_id "
            f"WHERE d.status = 'ready' AND c.chunk_text ### '{safe_phrase}' "
            "ORDER BY bm25_score DESC "
            f"LIMIT {int(top_k)}"
        )
        return await self._execute(sql)

    async def _mixed_search(
        self, phrase: str, kw_part: str, top_k: int
    ) -> list[ScoredChunk]:
        """Combined phrase + keyword search. Runs both, merges by highest score.

        kw_part format: "AND:<terms>" or "OR:<terms>" or plain terms (defaults to OR).
        """
        phrase_results = await self._phrase_search(phrase, top_k)

        keyword_results: list[ScoredChunk] = []
        if kw_part.startswith("AND:"):
            keywords = kw_part[4:]
            if keywords.strip():
                keyword_results = await self._conjunction_search(keywords, top_k)
        elif kw_part.startswith("OR:"):
            keywords = kw_part[3:]
            if keywords.strip():
                keyword_results = await self._disjunction_search(keywords, top_k)
        elif kw_part.strip():
            keyword_results = await self._disjunction_search(kw_part, top_k)

        # Merge: deduplicate by chunk_id, keep highest score
        seen: dict[str, ScoredChunk] = {}
        for chunk in phrase_results + keyword_results:
            key = str(chunk.chunk_id)
            if key not in seen or chunk.score > seen[key].score:
                seen[key] = chunk

        merged = sorted(seen.values(), key=lambda c: c.score, reverse=True)
        return merged[:top_k]

    async def _execute(self, sql) -> list[ScoredChunk]:
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
