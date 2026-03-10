"""Tests for SearchService — application-layer search orchestration.

Uses protocol test doubles (no mocking framework). Runs locally without
GPU, DB, or network dependencies.
"""

from __future__ import annotations

import pytest
from uuid import UUID, uuid4

from cortex.domain.chunk import Chunk, ChunkResult, ScoredChunk
from cortex.domain.document import Document, FileType
from cortex.domain.entity import Entity, EntityExtraction, RerankResult
from cortex.application.search_service import SearchService


# -- Protocol test doubles --

class FakeEmbedder:
    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        return [[0.0] * 1024 for _ in texts]

    async def embed_query(self, query: str) -> list[float]:
        return [0.0] * 1024


class FakeChunkRepo:
    def __init__(self, chunks: list[ScoredChunk] | None = None):
        self._chunks = chunks or []
        self.last_bm25_query: str | None = None

    async def save_chunks(self, chunks: list[Chunk]) -> None:
        pass

    async def delete_by_document(self, document_id: UUID) -> None:
        pass

    async def get_by_document(self, document_id: UUID) -> list[Chunk]:
        return []

    async def vector_search(self, query_vec: list[float], top_k: int = 50) -> list[ScoredChunk]:
        return self._chunks[:top_k]

    async def bm25_search(self, query: str, top_k: int = 50) -> list[ScoredChunk]:
        self.last_bm25_query = query
        return self._chunks[:top_k]


class FakeDocRepo:
    def __init__(self, docs: dict[UUID, Document] | None = None):
        self._docs = docs or {}

    async def save(self, document: Document) -> None:
        pass

    async def get(self, document_id: UUID) -> Document | None:
        return self._docs.get(document_id)

    async def get_by_hash(self, file_hash: str) -> Document | None:
        return None

    async def list_all(self, **kwargs) -> list[Document]:
        return list(self._docs.values())

    async def update_status(self, document_id: UUID, status: str, error_message: str | None = None) -> None:
        pass

    async def update(self, document: Document) -> None:
        pass

    async def delete(self, document_id: UUID) -> None:
        pass


def _make_doc(doc_id: UUID) -> Document:
    from datetime import datetime, UTC
    return Document(
        id=doc_id,
        title="Test Doc",
        original_filename="test.txt",
        file_type=FileType.TXT,
        file_size_bytes=100,
        file_hash="abc123",
        mime_type="text/plain",
        original_path="originals/test.txt",
        status="ready",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )


def _make_scored_chunk(doc_id: UUID, text: str = "test chunk", score: float = 0.9) -> ScoredChunk:
    return ScoredChunk(
        chunk_id=uuid4(),
        document_id=doc_id,
        chunk_text=text,
        chunk_index=0,
        start_char=0,
        end_char=len(text),
        section_heading=None,
        page_number=None,
        score=score,
    )


# -- Tests --

class TestBM25QueryParsing:
    """Tests for SearchService._parse_bm25_query (static method)."""

    def test_plain_keywords(self):
        result = SearchService._parse_bm25_query("hello world")
        assert result == "hello world"

    def test_quoted_phrase(self):
        result = SearchService._parse_bm25_query('"machine learning"')
        assert result == "PHRASE:machine learning"

    def test_phrase_with_keywords_preserves_both(self):
        result = SearchService._parse_bm25_query('"neural network" deep learning')
        assert result.startswith("MIXED:")
        assert "neural network" in result
        assert "deep learning" in result
        # Keywords should use OR mode by default
        kw_part = result.split("|", 1)[1]
        assert kw_part.startswith("OR:")

    def test_boolean_and(self):
        result = SearchService._parse_bm25_query("term1 AND term2")
        assert result.startswith("AND:")
        assert "term1" in result
        assert "term2" in result

    def test_boolean_and_with_phrase(self):
        result = SearchService._parse_bm25_query('"exact phrase" AND keyword1 AND keyword2')
        assert result.startswith("MIXED:")
        assert "exact phrase" in result
        assert "AND:" in result
        assert "keyword1" in result
        assert "keyword2" in result
        # AND operator itself must not appear as a term in the keyword portion
        kw_part = result.split("|", 1)[1]
        assert kw_part.startswith("AND:")
        terms_after_prefix = kw_part[4:]
        assert "AND" not in terms_after_prefix.split()

    def test_empty_query(self):
        result = SearchService._parse_bm25_query("")
        assert result == ""

    def test_no_quotes(self):
        result = SearchService._parse_bm25_query("simple keyword search")
        assert not result.startswith("PHRASE:")
        assert not result.startswith("MIXED:")
        assert not result.startswith("AND:")


class TestBM25Search:
    """Tests for SearchService.bm25_search — application-layer orchestration."""

    @pytest.mark.asyncio
    async def test_bm25_search_calls_repo(self):
        doc_id = uuid4()
        chunk = _make_scored_chunk(doc_id, "some text about BM25", 0.85)
        chunk_repo = FakeChunkRepo([chunk])
        doc_repo = FakeDocRepo({doc_id: _make_doc(doc_id)})
        embedder = FakeEmbedder()

        service = SearchService(embedder=embedder, chunk_repo=chunk_repo, doc_repo=doc_repo)
        response = await service.bm25_search("BM25")

        assert chunk_repo.last_bm25_query == "BM25"
        assert len(response.results) == 1
        assert response.results[0].document_title == "Test Doc"
        assert response.results[0].score == 0.85

    @pytest.mark.asyncio
    async def test_bm25_search_phrase_query(self):
        doc_id = uuid4()
        chunk = _make_scored_chunk(doc_id, "exact phrase match here", 0.95)
        chunk_repo = FakeChunkRepo([chunk])
        doc_repo = FakeDocRepo({doc_id: _make_doc(doc_id)})
        embedder = FakeEmbedder()

        service = SearchService(embedder=embedder, chunk_repo=chunk_repo, doc_repo=doc_repo)
        response = await service.bm25_search('"exact phrase"')

        assert chunk_repo.last_bm25_query is not None
        assert chunk_repo.last_bm25_query.startswith("PHRASE:")
        assert len(response.results) == 1

    @pytest.mark.asyncio
    async def test_bm25_search_respects_file_type_filter(self):
        doc_id = uuid4()
        chunk = _make_scored_chunk(doc_id, "filtered content", 0.8)
        chunk_repo = FakeChunkRepo([chunk])
        doc_repo = FakeDocRepo({doc_id: _make_doc(doc_id)})
        embedder = FakeEmbedder()

        service = SearchService(embedder=embedder, chunk_repo=chunk_repo, doc_repo=doc_repo)
        response = await service.bm25_search("content", file_type="pdf")

        # Doc is txt, filter is pdf — should return no results
        assert len(response.results) == 0

    @pytest.mark.asyncio
    async def test_bm25_search_empty_query(self):
        chunk_repo = FakeChunkRepo([])
        doc_repo = FakeDocRepo({})
        embedder = FakeEmbedder()

        service = SearchService(embedder=embedder, chunk_repo=chunk_repo, doc_repo=doc_repo)
        response = await service.bm25_search("")

        assert len(response.results) == 0


class TestHighlightSnippet:
    """Tests for SearchService._highlight_snippet."""

    def test_highlights_query_terms(self):
        snippet = SearchService._highlight_snippet(
            "The quick brown fox jumps over the lazy dog", "fox"
        )
        assert "<mark>fox</mark>" in snippet

    def test_case_insensitive(self):
        snippet = SearchService._highlight_snippet(
            "Machine Learning is important", "machine"
        )
        assert "<mark>Machine</mark>" in snippet

    def test_truncates_long_text(self):
        long_text = "word " * 200
        snippet = SearchService._highlight_snippet(long_text, "word", max_length=50)
        assert len(snippet) < len(long_text)

    def test_highlights_quoted_phrase(self):
        snippet = SearchService._highlight_snippet(
            "This is about neural network architectures and deep learning",
            '"neural network"',
        )
        assert "<mark>neural network</mark>" in snippet

    def test_highlights_mixed_phrase_and_keywords(self):
        snippet = SearchService._highlight_snippet(
            "Deep learning uses neural network models for inference",
            '"neural network" deep',
        )
        assert "<mark>neural network</mark>" in snippet
        assert "<mark>deep</mark>" in snippet.lower() or "<mark>Deep</mark>" in snippet


class TestExtractHighlightTerms:
    """Tests for SearchService._extract_highlight_terms."""

    def test_plain_keywords(self):
        terms = SearchService._extract_highlight_terms("hello world")
        assert "hello" in terms
        assert "world" in terms

    def test_quoted_phrase(self):
        terms = SearchService._extract_highlight_terms('"exact match"')
        assert "exact match" in terms

    def test_mixed_phrase_and_keywords(self):
        terms = SearchService._extract_highlight_terms('"neural network" deep learning')
        assert "neural network" in terms
        assert "deep" in terms
        assert "learning" in terms

    def test_boolean_and_stripped(self):
        terms = SearchService._extract_highlight_terms("term1 AND term2")
        assert "term1" in terms
        assert "term2" in terms
        assert "AND" not in terms

    def test_phrase_and_boolean_and(self):
        terms = SearchService._extract_highlight_terms('"exact phrase" AND keyword1 AND keyword2')
        assert "exact phrase" in terms
        assert "keyword1" in terms
        assert "keyword2" in terms
        assert "AND" not in terms

    def test_leading_and_after_phrase_removal(self):
        """Regression: after removing a phrase at the start, a leading AND must not survive."""
        terms = SearchService._extract_highlight_terms('"phrase" AND rest')
        assert "phrase" in terms
        assert "rest" in terms
        assert "AND" not in terms
