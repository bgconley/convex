from __future__ import annotations

import re
import time
from uuid import UUID

from cortex.domain.chunk import ScoredChunk
from cortex.domain.ports import ChunkRepository, DocumentRepository, EmbedderPort


class SearchService:
    """Use-case orchestration for semantic search.

    Phase 1: vector-only search (embed query → pgvector HNSW).
    Phase 2 adds BM25 hybrid + reranking.
    Phase 3 adds graph expansion.

    Depends on domain ports only — no infrastructure imports.
    """

    def __init__(
        self,
        embedder: EmbedderPort,
        chunk_repo: ChunkRepository,
        doc_repo: DocumentRepository,
    ) -> None:
        self._embedder = embedder
        self._chunk_repo = chunk_repo
        self._doc_repo = doc_repo

    async def search(
        self,
        query: str,
        top_k: int = 10,
        file_type: str | None = None,
    ) -> SearchResponse:
        start = time.monotonic()

        # 1. Embed query
        query_vec = await self._embedder.embed_query(query)

        # 2. Vector search (Phase 1: vector only, top_k * 2 to allow filtering)
        candidates = await self._chunk_repo.vector_search(query_vec, top_k=top_k * 2)

        # 3. Enrich with document metadata and build response
        results: list[SearchResultItem] = []
        seen_chunks: set[UUID] = set()

        for candidate in candidates:
            if candidate.chunk_id in seen_chunks:
                continue
            seen_chunks.add(candidate.chunk_id)

            doc = await self._doc_repo.get(candidate.document_id)
            if doc is None:
                continue

            # Apply file type filter
            if file_type and doc.file_type.value != file_type:
                continue

            # Generate highlighted snippet
            snippet = self._highlight_snippet(candidate.chunk_text, query)

            # Anchor ID for jump-to-hit navigation
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

    async def bm25_search(
        self,
        query: str,
        top_k: int = 10,
        file_type: str | None = None,
    ) -> SearchResponse:
        """BM25 keyword search via pg_search.

        Parses the query for phrase markers (quoted strings) and delegates
        to the ChunkRepository.bm25_search port. Results are enriched with
        document metadata, the same as vector search.
        """
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

    @staticmethod
    def _strip_boolean_operators(text: str) -> str:
        """Remove boolean AND operators from text, preserving the terms."""
        # Split on AND (case-sensitive, word boundary) and rejoin with spaces
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
        - Mixed phrase + AND: "phrase" AND kw1 AND kw2 → MIXED:neural network|AND:kw1 kw2

        The returned string is interpreted by BM25SearchAdapter.
        """
        # 1. Extract quoted phrases
        phrases = re.findall(r'"([^"]+)"', query)
        remaining = re.sub(r'"[^"]*"', '', query).strip()

        # 2. Determine if remaining keywords use AND conjunction
        has_and = bool(re.search(r'\bAND\b', remaining))
        clean_remaining = SearchService._strip_boolean_operators(remaining)

        # 3. Build the parsed query
        if phrases and clean_remaining:
            # Mixed: phrase + keywords, with conjunction mode
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
        """Extract all terms and phrases from a query for snippet highlighting.

        Returns both individual keywords and full phrases (from quoted strings).
        Boolean operators (AND) are stripped and never included as highlight terms.
        """
        terms: list[str] = []
        # Extract quoted phrases as highlight targets
        phrases = re.findall(r'"([^"]+)"', query)
        terms.extend(phrases)
        # Extract remaining individual keywords, stripping boolean operators
        remaining = re.sub(r'"[^"]*"', '', query).strip()
        remaining = SearchService._strip_boolean_operators(remaining)
        terms.extend(w for w in remaining.split() if w)
        return terms

    @staticmethod
    def _highlight_snippet(text: str, query: str, max_length: int = 200) -> str:
        """Generate a snippet with query terms and phrases wrapped in <mark> tags.

        Handles both individual keywords and quoted phrases from the query.
        Phrases are highlighted as whole units before individual terms.
        """
        highlight_terms = SearchService._extract_highlight_terms(query)
        if not highlight_terms:
            return text[:max_length]

        text_lower = text.lower()

        # Find best position to center the snippet — prefer phrase matches
        best_pos = 0
        for term in highlight_terms:
            pos = text_lower.find(term.lower())
            if pos >= 0:
                best_pos = pos
                break

        # Extract window around match
        start = max(0, best_pos - max_length // 2)
        end = min(len(text), start + max_length)
        snippet = text[start:end].strip()

        if start > 0:
            snippet = "..." + snippet
        if end < len(text):
            snippet = snippet + "..."

        # Highlight: phrases first (longer matches), then individual terms
        sorted_terms = sorted(highlight_terms, key=len, reverse=True)
        for term in sorted_terms:
            pattern = re.compile(re.escape(term), re.IGNORECASE)
            snippet = pattern.sub(lambda m: f"<mark>{m.group()}</mark>", snippet)

        return snippet


class SearchResultItem:
    __slots__ = (
        "chunk_id", "document_id", "document_title", "document_type",
        "chunk_text", "highlighted_snippet", "section_heading",
        "page_number", "score", "chunk_start_char", "chunk_end_char",
        "anchor_id",
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
