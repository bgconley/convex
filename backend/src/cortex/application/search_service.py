from __future__ import annotations

import asyncio
import re
import time
from uuid import UUID, uuid4

from cortex.domain.chunk import Chunk, ScoredChunk
from collections import deque

from cortex.domain.ports import (
    ChunkRepository,
    DocumentRepository,
    EmbedderPort,
    EntityRepository,
    GraphSearchPort,
    NERPort,
    RerankerPort,
)


class SearchService:
    """Use-case orchestration for hybrid search.

    Phase 1: vector-only search (embed query → pgvector HNSW).
    Phase 2: hybrid vector + BM25 with Reciprocal Rank Fusion.
    Phase 3: graph expansion — entity-based retrieval via knowledge graph.

    Depends on domain ports only — no infrastructure imports.
    """

    # RRF parameters
    RRF_K = 60
    # Weights without graph signal
    RRF_W_VEC = 0.6
    RRF_W_BM25 = 0.4
    # Weights with graph signal (per ARCHITECTURE_BRAINSTORM.md §6.6)
    RRF_W_VEC_GRAPH = 0.5
    RRF_W_BM25_GRAPH = 0.3
    RRF_W_GRAPH = 0.2

    MAX_RECENT_QUERIES = 50

    def __init__(
        self,
        embedder: EmbedderPort,
        chunk_repo: ChunkRepository,
        doc_repo: DocumentRepository,
        reranker: RerankerPort | None = None,
        ner: NERPort | None = None,
        graph_search: GraphSearchPort | None = None,
        entity_repo: EntityRepository | None = None,
    ) -> None:
        self._embedder = embedder
        self._chunk_repo = chunk_repo
        self._doc_repo = doc_repo
        self._reranker = reranker
        self._ner = ner
        self._graph_search = graph_search
        self._entity_repo = entity_repo
        self._recent_queries: deque[str] = deque(maxlen=self.MAX_RECENT_QUERIES)

    async def search(
        self,
        query: str,
        top_k: int = 10,
        file_type: str | None = None,
        rerank: bool = True,
        include_graph: bool = True,
    ) -> SearchResponse:
        """Hybrid search: vector + BM25 (+ graph) with RRF, then neural reranking.

        1. Run vector, BM25, and graph search concurrently
        2. Compute RRF scores to merge and rank (top 50)
        3. Rerank top candidates with mxbai-rerank-large-v2 (if available)
        4. Enrich with document metadata
        """
        start = time.monotonic()

        # 1. Parallel retrieval (vector + BM25 + optional graph)
        parsed_bm25_query = self._parse_bm25_query(query)
        vec_coro = self._vector_search(query, top_k=50)
        bm25_coro = self._chunk_repo.bm25_search(parsed_bm25_query, top_k=50)

        graph_enabled = (
            include_graph
            and self._ner is not None
            and self._graph_search is not None
        )
        if graph_enabled:
            graph_coro = self._graph_entity_search(query, top_k=50)
            vec_results, bm25_results, graph_results = await asyncio.gather(
                vec_coro, bm25_coro, graph_coro,
            )
        else:
            vec_results, bm25_results = await asyncio.gather(vec_coro, bm25_coro)
            graph_results = []

        # 2. RRF fusion (3-way if graph results present, 2-way otherwise)
        fused = self._rrf_fusion(vec_results, bm25_results, graph_results)

        # 3. Neural reranking (optional)
        rerank_scores: dict[UUID, float] = {}
        if rerank and self._reranker and fused:
            rerank_scores = await self._rerank_candidates(query, fused, top_k)

        # 4. If reranked, reorder by rerank score; otherwise keep RRF order
        if rerank_scores:
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
                    graph_score=candidate.graph_score,
                    rerank_score=rerank_score,
                    chunk_start_char=candidate.start_char,
                    chunk_end_char=candidate.end_char,
                    anchor_id=anchor_id,
                )
            )

            if len(results) >= top_k:
                break

        elapsed_ms = (time.monotonic() - start) * 1000

        # Track successful searches for recent query suggestions
        if results:
            self._record_query(query)

        return SearchResponse(
            query=query,
            results=results,
            total_candidates=len(fused),
            search_time_ms=elapsed_ms,
        )

    async def get_suggestions(
        self, prefix: str, limit: int = 5,
    ) -> SuggestionsResult:
        """Return search suggestions matching prefix from 3 sources."""
        prefix_lower = prefix.lower()

        # Recent searches matching prefix
        recent = [
            q for q in self._recent_queries
            if q.lower().startswith(prefix_lower) and q.lower() != prefix_lower
        ][:limit]

        # Entity names matching prefix
        entities: list[EntitySuggestion] = []
        if self._entity_repo:
            matched = await self._entity_repo.search_by_prefix(prefix, limit=limit)
            entities = [
                EntitySuggestion(
                    id=e.id, name=e.name, entity_type=e.entity_type,
                )
                for e in matched
            ]

        # Document titles matching prefix
        documents: list[DocumentSuggestion] = []
        matched_docs = await self._doc_repo.search_by_title_prefix(prefix, limit=limit)
        documents = [
            DocumentSuggestion(id=d.id, title=d.title)
            for d in matched_docs
        ]

        return SuggestionsResult(
            query=prefix,
            recent_searches=recent,
            entities=entities,
            documents=documents,
        )

    def _record_query(self, query: str) -> None:
        """Record a search query for recent suggestions (deduped)."""
        normalized = query.strip()
        if not normalized:
            return
        # Remove existing instance to move it to front
        try:
            self._recent_queries.remove(normalized)
        except ValueError:
            pass
        self._recent_queries.appendleft(normalized)

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
                    graph_score=None,
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

    async def document_search(
        self,
        query: str,
        top_k: int = 10,
        file_type: str | None = None,
        rerank: bool = True,
        include_graph: bool = True,
    ) -> DocumentSearchResponse:
        """Document-level search: aggregate chunk scores per document.

        Runs the full hybrid search pipeline (vector + BM25 + graph + RRF + rerank),
        then groups results by document_id. Each document's score is the max
        chunk score, and the top-scoring chunk provides the snippet.
        """
        start = time.monotonic()

        # Run chunk-level search with scaled top_k for good document coverage.
        # More chunks retrieved → more unique documents in the aggregation.
        chunk_top_k = min(top_k * 5, 200)
        chunk_response = await self.search(
            query=query, top_k=chunk_top_k, file_type=file_type, rerank=rerank,
            include_graph=include_graph,
        )

        # Aggregate by document
        doc_groups: dict[UUID, list[SearchResultItem]] = {}
        for result in chunk_response.results:
            doc_groups.setdefault(result.document_id, []).append(result)

        # Build document-level results: max score, best chunk as snippet
        doc_results: list[DocumentSearchResult] = []
        for doc_id, chunks in doc_groups.items():
            best = max(chunks, key=lambda c: c.score)
            doc_results.append(DocumentSearchResult(
                document_id=doc_id,
                document_title=best.document_title,
                document_type=best.document_type,
                score=best.score,
                vector_score=best.vector_score,
                bm25_score=best.bm25_score,
                graph_score=best.graph_score,
                rerank_score=best.rerank_score,
                best_chunk_snippet=best.highlighted_snippet,
                best_chunk_section=best.section_heading,
                best_chunk_page=best.page_number,
                best_chunk_anchor_id=best.anchor_id,
                chunk_count=len(chunks),
            ))

        doc_results.sort(key=lambda d: d.score, reverse=True)
        doc_results = doc_results[:top_k]

        elapsed_ms = (time.monotonic() - start) * 1000

        return DocumentSearchResponse(
            query=query,
            results=doc_results,
            total_documents=len(doc_groups),
            search_time_ms=elapsed_ms,
        )

    # -- Internal methods --

    async def _vector_search(self, query: str, top_k: int = 50) -> list[ScoredChunk]:
        """Embed the query and run pgvector HNSW search."""
        query_vec = await self._embedder.embed_query(query)
        return await self._chunk_repo.vector_search(query_vec, top_k=top_k)

    async def _graph_entity_search(self, query: str, top_k: int = 50) -> list[ScoredChunk]:
        """Extract entities from query via NER, then expand via knowledge graph.

        Creates a temporary Chunk from the query text to reuse the NERPort
        interface, extracts entity names, and delegates to GraphSearchPort.
        """
        # Use lower threshold for short query text (vs 0.4 for ingestion)
        dummy = Chunk(
            id=uuid4(), document_id=uuid4(), chunk_text=query,
            chunk_index=0, start_char=0, end_char=len(query), token_count=0,
        )
        try:
            extractions = await self._ner.extract_entities([dummy], threshold=0.3)
        except Exception:
            return []

        if not extractions:
            return []

        entity_names = list({e.normalized_name for e in extractions})
        try:
            return await self._graph_search.search_by_entities(entity_names, top_k)
        except Exception:
            return []

    def _rrf_fusion(
        self,
        vec_results: list[ScoredChunk],
        bm25_results: list[ScoredChunk],
        graph_results: list[ScoredChunk] | None = None,
    ) -> list[FusedChunk]:
        """Reciprocal Rank Fusion: merge vector, BM25, and optional graph ranked lists.

        When graph results are present:
          RRF = 0.5/(k+rank_vec) + 0.3/(k+rank_bm25) + 0.2/(k+rank_graph)
        Without graph:
          RRF = 0.6/(k+rank_vec) + 0.4/(k+rank_bm25)

        Chunks appearing in only one list get score from that list only.
        Returns fused candidates sorted by RRF score descending (top 50).
        """
        k = self.RRF_K
        use_graph = bool(graph_results)

        if use_graph:
            w_vec = self.RRF_W_VEC_GRAPH
            w_bm25 = self.RRF_W_BM25_GRAPH
            w_graph = self.RRF_W_GRAPH
        else:
            w_vec = self.RRF_W_VEC
            w_bm25 = self.RRF_W_BM25
            w_graph = 0.0

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

        graph_rank: dict[UUID, int] = {}
        graph_score_map: dict[UUID, float] = {}
        if graph_results:
            for rank, chunk in enumerate(graph_results, start=1):
                graph_rank[chunk.chunk_id] = rank
                graph_score_map[chunk.chunk_id] = chunk.score

        # Collect all unique chunk IDs
        all_ids = set(vec_rank.keys()) | set(bm25_rank.keys()) | set(graph_rank.keys())

        # Build chunk lookup for metadata
        chunk_lookup: dict[UUID, ScoredChunk] = {}
        for c in vec_results:
            chunk_lookup[c.chunk_id] = c
        for c in bm25_results:
            if c.chunk_id not in chunk_lookup:
                chunk_lookup[c.chunk_id] = c
        if graph_results:
            for c in graph_results:
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
            if cid in graph_rank:
                rrf += w_graph / (k + graph_rank[cid])

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
                graph_score=graph_score_map.get(cid),
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
        "score", "vector_score", "bm25_score", "graph_score",
    )

    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)


class SearchResultItem:
    __slots__ = (
        "chunk_id", "document_id", "document_title", "document_type",
        "chunk_text", "highlighted_snippet", "section_heading",
        "page_number", "score", "vector_score", "bm25_score",
        "graph_score", "rerank_score",
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


class DocumentSearchResult:
    __slots__ = (
        "document_id", "document_title", "document_type",
        "score", "vector_score", "bm25_score", "graph_score", "rerank_score",
        "best_chunk_snippet", "best_chunk_section", "best_chunk_page",
        "best_chunk_anchor_id", "chunk_count",
    )

    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)


class DocumentSearchResponse:
    __slots__ = ("query", "results", "total_documents", "search_time_ms")

    def __init__(self, query: str, results: list[DocumentSearchResult],
                 total_documents: int, search_time_ms: float):
        self.query = query
        self.results = results
        self.total_documents = total_documents
        self.search_time_ms = search_time_ms


class EntitySuggestion:
    __slots__ = ("id", "name", "entity_type")

    def __init__(self, id: UUID, name: str, entity_type: str):
        self.id = id
        self.name = name
        self.entity_type = entity_type


class DocumentSuggestion:
    __slots__ = ("id", "title")

    def __init__(self, id: UUID, title: str):
        self.id = id
        self.title = title


class SuggestionsResult:
    __slots__ = ("query", "recent_searches", "entities", "documents")

    def __init__(
        self,
        query: str,
        recent_searches: list[str],
        entities: list[EntitySuggestion],
        documents: list[DocumentSuggestion],
    ):
        self.query = query
        self.recent_searches = recent_searches
        self.entities = entities
        self.documents = documents
