from __future__ import annotations

import asyncio
import re
import time
from uuid import UUID

from cortex.domain.chunk import ScoredChunk
from cortex.domain.ports import ChunkRepository, DocumentRepository, EmbedderPort, RerankerPort


class SearchService:
    """Use-case orchestration for hybrid search.

    Phase 1: vector-only search (embed query → pgvector HNSW).
    Phase 2: hybrid vector + BM25 with Reciprocal Rank Fusion.
    Phase 3 adds graph expansion.

    Depends on domain ports only — no infrastructure imports.
    """

    # RRF parameters (per IMPLEMENTATION_PLAN.md Step 2.2)
    RRF_K = 60
    RRF_W_VEC = 0.6
    RRF_W_BM25 = 0.4

    def __init__(
        self,
        embedder: EmbedderPort,
        chunk_repo: ChunkRepository,
        doc_repo: DocumentRepository,
        reranker: RerankerPort | None = None,
    ) -> None:
        self._embedder = embedder
        self._chunk_repo = chunk_repo
        self._doc_repo = doc_repo
        self._reranker = reranker

    async def search(
        self,
        query: str,
        top_k: int = 10,
        file_type: str | None = None,
        rerank: bool = True,
    ) -> SearchResponse:
        """Hybrid search: vector + BM25 with RRF, then neural reranking.

        1. Run vector search and BM25 search concurrently
        2. Compute RRF scores to merge and rank (top 50)
        3. Rerank top candidates with mxbai-rerank-large-v2 (if available)
        4. Enrich with document metadata
        """
        start = time.monotonic()

        # 1. Parallel retrieval
        parsed_bm25_query = self._parse_bm25_query(query)
        vec_task = self._vector_search(query, top_k=50)
        bm25_task = self._chunk_repo.bm25_search(parsed_bm25_query, top_k=50)
        vec_results, bm25_results = await asyncio.gather(vec_task, bm25_task)

        # 2. RRF fusion
        fused = self._rrf_fusion(vec_results, bm25_results)

        # 3. Neural reranking (optional)
        rerank_scores: dict[UUID, float] = {}
        if rerank and self._reranker and fused:
            rerank_scores = await self._rerank_candidates(query, fused, top_k)

        # 4. If reranked, reorder by rerank score; otherwise keep RRF order
        if rerank_scores:
            # Reranked candidates get rerank score as primary; unreranked drop to the end
            fused.sort(
                key=lambda c: rerank_scores.get(c.chunk_id, -1.0),
                reverse=True,
            )

        # 5. Enrich with document metadata
        results: list[SearchResultItem] = []
        seen_chunks: set[UUID] = set()

        for candidate in fused:
            if candidate.chunk_id in seen_chunks:
                continue
            seen_chunks.add(candidate.chunk_id)

            doc = await self._doc_repo.get(candidate.document_id)
            if doc is None:
                continue

            if file_type and doc.file_type.value != file_type:
                continue

            snippet = self._highlight_snippet(candidate.chunk_text, query)
            anchor_id = f"chunk-{candidate.chunk_index}"

            rerank_score = rerank_scores.get(candidate.chunk_id)
            final_score = rerank_score if rerank_score is not None else candidate.score

            results.append(
                SearchResultItem(
                    chunk_id=candidate.chunk_id,
                    document_id=candidate.document_id,
                    document_title=doc.title,
                    document_type=doc.file_type.value,
                    chunk_text=candidate.chunk_text,
                    highlighted_snippet=snippet,
                    section_heading=candidate.section_heading,
                    page_number=candidate.page_number,
                    score=final_score,
                    vector_score=candidate.vector_score,
                    bm25_score=candidate.bm25_score,
                    rerank_score=rerank_score,
                    chunk_start_char=candidate.start_char,
                    chunk_end_char=candidate.end_char,
                    anchor_id=anchor_id,
                )
            )

            if len(results) >= top_k:
                break

        elapsed_ms = (time.monotonic() - start) * 1000

        return SearchResponse(
            query=query,
            results=results,
            total_candidates=len(fused),
            search_time_ms=elapsed_ms,
        )

    async def _rerank_candidates(
        self, query: str, fused: list[FusedChunk], top_k: int
    ) -> dict[UUID, float]:
        """Rerank fused candidates using the neural reranker.

        Returns a mapping of chunk_id → rerank_score for reranked candidates.
        """
        documents = [c.chunk_text for c in fused]
        rerank_results = await self._reranker.rerank(query, documents, top_k=top_k)

        scores: dict[UUID, float] = {}
        for rr in rerank_results:
            if rr.index < len(fused):
                scores[fused[rr.index].chunk_id] = rr.score
        return scores

    async def bm25_search(
        self,
        query: str,
        top_k: int = 10,
        file_type: str | None = None,
    ) -> SearchResponse:
        """BM25-only keyword search via pg_search."""
        start = time.monotonic()

        parsed_query = self._parse_bm25_query(query)
        candidates = await self._chunk_repo.bm25_search(parsed_query, top_k=top_k * 2)

        results: list[SearchResultItem] = []
        seen_chunks: set[UUID] = set()

        for candidate in candidates:
            if candidate.chunk_id in seen_chunks:
                continue
            seen_chunks.add(candidate.chunk_id)

            doc = await self._doc_repo.get(candidate.document_id)
            if doc is None:
                continue

            if file_type and doc.file_type.value != file_type:
                continue

            snippet = self._highlight_snippet(candidate.chunk_text, query)
            anchor_id = f"chunk-{candidate.chunk_index}"

            results.append(
                SearchResultItem(
                    chunk_id=candidate.chunk_id,
                    document_id=candidate.document_id,
                    document_title=doc.title,
                    document_type=doc.file_type.value,
                    chunk_text=candidate.chunk_text,
                    highlighted_snippet=snippet,
                    section_heading=candidate.section_heading,
                    page_number=candidate.page_number,
                    score=candidate.score,
                    vector_score=None,
                    bm25_score=candidate.score,
                    chunk_start_char=candidate.start_char,
                    chunk_end_char=candidate.end_char,
                    anchor_id=anchor_id,
                )
            )

            if len(results) >= top_k:
                break

        elapsed_ms = (time.monotonic() - start) * 1000

        return SearchResponse(
            query=query,
            results=results,
            total_candidates=len(candidates),
            search_time_ms=elapsed_ms,
        )

    # -- Internal methods --

    async def _vector_search(self, query: str, top_k: int = 50) -> list[ScoredChunk]:
        """Embed the query and run pgvector HNSW search."""
        query_vec = await self._embedder.embed_query(query)
        return await self._chunk_repo.vector_search(query_vec, top_k=top_k)

    def _rrf_fusion(
        self,
        vec_results: list[ScoredChunk],
        bm25_results: list[ScoredChunk],
    ) -> list[FusedChunk]:
        """Reciprocal Rank Fusion: merge vector and BM25 ranked lists.

        RRF_score = w_vec / (k + rank_vec) + w_bm25 / (k + rank_bm25)

        Chunks appearing in only one list get score from that list only.
        Returns fused candidates sorted by RRF score descending.
        """
        k = self.RRF_K
        w_vec = self.RRF_W_VEC
        w_bm25 = self.RRF_W_BM25

        # Build rank maps (1-indexed)
        vec_rank: dict[UUID, int] = {}
        vec_score: dict[UUID, float] = {}
        for rank, chunk in enumerate(vec_results, start=1):
            vec_rank[chunk.chunk_id] = rank
            vec_score[chunk.chunk_id] = chunk.score

        bm25_rank: dict[UUID, int] = {}
        bm25_score_map: dict[UUID, float] = {}
        for rank, chunk in enumerate(bm25_results, start=1):
            bm25_rank[chunk.chunk_id] = rank
            bm25_score_map[chunk.chunk_id] = chunk.score

        # Collect all unique chunk IDs
        all_ids = set(vec_rank.keys()) | set(bm25_rank.keys())

        # Build chunk lookup for metadata
        chunk_lookup: dict[UUID, ScoredChunk] = {}
        for c in vec_results:
            chunk_lookup[c.chunk_id] = c
        for c in bm25_results:
            if c.chunk_id not in chunk_lookup:
                chunk_lookup[c.chunk_id] = c

        # Compute RRF scores
        fused: list[FusedChunk] = []
        for cid in all_ids:
            rrf = 0.0
            if cid in vec_rank:
                rrf += w_vec / (k + vec_rank[cid])
            if cid in bm25_rank:
                rrf += w_bm25 / (k + bm25_rank[cid])

            chunk = chunk_lookup[cid]
            fused.append(FusedChunk(
                chunk_id=chunk.chunk_id,
                document_id=chunk.document_id,
                chunk_text=chunk.chunk_text,
                chunk_index=chunk.chunk_index,
                start_char=chunk.start_char,
                end_char=chunk.end_char,
                section_heading=chunk.section_heading,
                page_number=chunk.page_number,
                score=rrf,
                vector_score=vec_score.get(cid),
                bm25_score=bm25_score_map.get(cid),
            ))

        fused.sort(key=lambda c: c.score, reverse=True)
        return fused[:50]

    @staticmethod
    def _strip_boolean_operators(text: str) -> str:
        """Remove boolean AND operators from text, preserving the terms."""
        parts = re.split(r'\bAND\b', text)
        return ' '.join(p.strip() for p in parts if p.strip())

    @staticmethod
    def _parse_bm25_query(query: str) -> str:
        """Parse user query into a structured format for BM25 search.

        Handles:
        - Quoted phrases: "exact match" → PHRASE:exact match
        - Plain keywords: hello world → hello world (||| disjunction)
        - Boolean AND: term1 AND term2 → AND:term1 term2 (&&& conjunction)
        - Mixed phrase + keywords: "neural network" deep learning → MIXED:neural network|OR:deep learning
        - Mixed phrase + AND: "phrase" AND kw1 AND kw2 → MIXED:phrase|AND:kw1 kw2
        """
        phrases = re.findall(r'"([^"]+)"', query)
        remaining = re.sub(r'"[^"]*"', '', query).strip()

        has_and = bool(re.search(r'\bAND\b', remaining))
        clean_remaining = SearchService._strip_boolean_operators(remaining)

        if phrases and clean_remaining:
            mode = "AND" if has_and else "OR"
            return f'MIXED:{phrases[0]}|{mode}:{clean_remaining}'
        elif phrases:
            return f'PHRASE:{phrases[0]}'
        elif has_and:
            return f'AND:{clean_remaining}'
        else:
            return query

    @staticmethod
    def _extract_highlight_terms(query: str) -> list[str]:
        """Extract all terms and phrases from a query for snippet highlighting."""
        terms: list[str] = []
        phrases = re.findall(r'"([^"]+)"', query)
        terms.extend(phrases)
        remaining = re.sub(r'"[^"]*"', '', query).strip()
        remaining = SearchService._strip_boolean_operators(remaining)
        terms.extend(w for w in remaining.split() if w)
        return terms

    @staticmethod
    def _highlight_snippet(text: str, query: str, max_length: int = 200) -> str:
        """Generate a snippet with query terms and phrases wrapped in <mark> tags."""
        highlight_terms = SearchService._extract_highlight_terms(query)
        if not highlight_terms:
            return text[:max_length]

        text_lower = text.lower()

        best_pos = 0
        for term in highlight_terms:
            pos = text_lower.find(term.lower())
            if pos >= 0:
                best_pos = pos
                break

        start = max(0, best_pos - max_length // 2)
        end = min(len(text), start + max_length)
        snippet = text[start:end].strip()

        if start > 0:
            snippet = "..." + snippet
        if end < len(text):
            snippet = snippet + "..."

        sorted_terms = sorted(highlight_terms, key=len, reverse=True)
        for term in sorted_terms:
            pattern = re.compile(re.escape(term), re.IGNORECASE)
            snippet = pattern.sub(lambda m: f"<mark>{m.group()}</mark>", snippet)

        return snippet


class FusedChunk:
    """A chunk with RRF-fused score and individual signal scores."""
    __slots__ = (
        "chunk_id", "document_id", "chunk_text", "chunk_index",
        "start_char", "end_char", "section_heading", "page_number",
        "score", "vector_score", "bm25_score",
    )

    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)


class SearchResultItem:
    __slots__ = (
        "chunk_id", "document_id", "document_title", "document_type",
        "chunk_text", "highlighted_snippet", "section_heading",
        "page_number", "score", "vector_score", "bm25_score", "rerank_score",
        "chunk_start_char", "chunk_end_char", "anchor_id",
    )

    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)


class SearchResponse:
    __slots__ = ("query", "results", "total_candidates", "search_time_ms")

    def __init__(self, query: str, results: list[SearchResultItem],
                 total_candidates: int, search_time_ms: float):
        self.query = query
        self.results = results
        self.total_candidates = total_candidates
        self.search_time_ms = search_time_ms
