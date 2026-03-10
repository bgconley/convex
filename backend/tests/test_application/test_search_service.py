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
    """Test double with separate vector and BM25 result lists."""

    def __init__(
        self,
        vec_chunks: list[ScoredChunk] | None = None,
        bm25_chunks: list[ScoredChunk] | None = None,
    ):
        self._vec_chunks = vec_chunks or []
        self._bm25_chunks = bm25_chunks or []
        self.last_bm25_query: str | None = None

    async def save_chunks(self, chunks: list[Chunk]) -> None:
        pass

    async def delete_by_document(self, document_id: UUID) -> None:
        pass

    async def get_by_document(self, document_id: UUID) -> list[Chunk]:
        return []

    async def vector_search(self, query_vec: list[float], top_k: int = 50) -> list[ScoredChunk]:
        return self._vec_chunks[:top_k]

    async def bm25_search(self, query: str, top_k: int = 50) -> list[ScoredChunk]:
        self.last_bm25_query = query
        return self._bm25_chunks[:top_k]


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


def _make_scored_chunk(
    doc_id: UUID,
    chunk_id: UUID | None = None,
    text: str = "test chunk",
    score: float = 0.9,
    chunk_index: int = 0,
) -> ScoredChunk:
    return ScoredChunk(
        chunk_id=chunk_id or uuid4(),
        document_id=doc_id,
        chunk_text=text,
        chunk_index=chunk_index,
        start_char=0,
        end_char=len(text),
        section_heading=None,
        page_number=None,
        score=score,
    )


# -- Tests --

class TestBM25QueryParsing:
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
    @pytest.mark.asyncio
    async def test_bm25_search_calls_repo(self):
        doc_id = uuid4()
        chunk = _make_scored_chunk(doc_id, text="some text about BM25", score=0.85)
        chunk_repo = FakeChunkRepo(bm25_chunks=[chunk])
        doc_repo = FakeDocRepo({doc_id: _make_doc(doc_id)})

        service = SearchService(embedder=FakeEmbedder(), chunk_repo=chunk_repo, doc_repo=doc_repo)
        response = await service.bm25_search("BM25")

        assert chunk_repo.last_bm25_query == "BM25"
        assert len(response.results) == 1
        assert response.results[0].document_title == "Test Doc"
        assert response.results[0].bm25_score == 0.85

    @pytest.mark.asyncio
    async def test_bm25_search_phrase_query(self):
        doc_id = uuid4()
        chunk = _make_scored_chunk(doc_id, text="exact phrase match", score=0.95)
        chunk_repo = FakeChunkRepo(bm25_chunks=[chunk])
        doc_repo = FakeDocRepo({doc_id: _make_doc(doc_id)})

        service = SearchService(embedder=FakeEmbedder(), chunk_repo=chunk_repo, doc_repo=doc_repo)
        response = await service.bm25_search('"exact phrase"')

        assert chunk_repo.last_bm25_query is not None
        assert chunk_repo.last_bm25_query.startswith("PHRASE:")

    @pytest.mark.asyncio
    async def test_bm25_search_respects_file_type_filter(self):
        doc_id = uuid4()
        chunk = _make_scored_chunk(doc_id, text="filtered content", score=0.8)
        chunk_repo = FakeChunkRepo(bm25_chunks=[chunk])
        doc_repo = FakeDocRepo({doc_id: _make_doc(doc_id)})

        service = SearchService(embedder=FakeEmbedder(), chunk_repo=chunk_repo, doc_repo=doc_repo)
        response = await service.bm25_search("content", file_type="pdf")
        assert len(response.results) == 0

    @pytest.mark.asyncio
    async def test_bm25_search_empty_query(self):
        service = SearchService(embedder=FakeEmbedder(), chunk_repo=FakeChunkRepo(), doc_repo=FakeDocRepo())
        response = await service.bm25_search("")
        assert len(response.results) == 0


class TestHybridSearch:
    """Tests for SearchService.search — hybrid vector + BM25 with RRF."""

    @pytest.mark.asyncio
    async def test_hybrid_runs_both_retrieval_paths(self):
        doc_id = uuid4()
        chunk_id = uuid4()
        vec_chunk = _make_scored_chunk(doc_id, chunk_id=chunk_id, text="shared chunk", score=0.9)
        bm25_chunk = _make_scored_chunk(doc_id, chunk_id=chunk_id, text="shared chunk", score=1.2)
        chunk_repo = FakeChunkRepo(vec_chunks=[vec_chunk], bm25_chunks=[bm25_chunk])
        doc_repo = FakeDocRepo({doc_id: _make_doc(doc_id)})

        service = SearchService(embedder=FakeEmbedder(), chunk_repo=chunk_repo, doc_repo=doc_repo)
        response = await service.search("test query")

        assert len(response.results) == 1
        result = response.results[0]
        # Both scores should be present
        assert result.vector_score is not None
        assert result.bm25_score is not None

    @pytest.mark.asyncio
    async def test_hybrid_merges_disjoint_results(self):
        """Chunks appearing in only one signal list still appear in results."""
        doc_id = uuid4()
        vec_only_id = uuid4()
        bm25_only_id = uuid4()
        vec_chunk = _make_scored_chunk(doc_id, chunk_id=vec_only_id, text="vector only", score=0.8, chunk_index=0)
        bm25_chunk = _make_scored_chunk(doc_id, chunk_id=bm25_only_id, text="bm25 only", score=1.0, chunk_index=1)
        chunk_repo = FakeChunkRepo(vec_chunks=[vec_chunk], bm25_chunks=[bm25_chunk])
        doc_repo = FakeDocRepo({doc_id: _make_doc(doc_id)})

        service = SearchService(embedder=FakeEmbedder(), chunk_repo=chunk_repo, doc_repo=doc_repo)
        response = await service.search("test", top_k=10)

        assert len(response.results) == 2
        ids = {r.chunk_id for r in response.results}
        assert vec_only_id in ids
        assert bm25_only_id in ids

    @pytest.mark.asyncio
    async def test_rrf_ranks_shared_chunks_higher(self):
        """A chunk in both vector and BM25 lists should rank above one in only one list."""
        doc_id = uuid4()
        shared_id = uuid4()
        vec_only_id = uuid4()

        shared_vec = _make_scored_chunk(doc_id, chunk_id=shared_id, text="shared", score=0.7, chunk_index=0)
        vec_only = _make_scored_chunk(doc_id, chunk_id=vec_only_id, text="vec only", score=0.9, chunk_index=1)
        shared_bm25 = _make_scored_chunk(doc_id, chunk_id=shared_id, text="shared", score=0.5, chunk_index=0)

        chunk_repo = FakeChunkRepo(
            vec_chunks=[vec_only, shared_vec],  # vec_only is rank 1, shared is rank 2
            bm25_chunks=[shared_bm25],          # shared is rank 1 in BM25
        )
        doc_repo = FakeDocRepo({doc_id: _make_doc(doc_id)})

        service = SearchService(embedder=FakeEmbedder(), chunk_repo=chunk_repo, doc_repo=doc_repo)
        response = await service.search("test", top_k=10)

        assert len(response.results) == 2
        # Shared chunk should rank first because it appears in both lists
        assert response.results[0].chunk_id == shared_id

    @pytest.mark.asyncio
    async def test_hybrid_score_breakdown(self):
        doc_id = uuid4()
        chunk_id = uuid4()
        vec_chunk = _make_scored_chunk(doc_id, chunk_id=chunk_id, text="test", score=0.85)
        bm25_chunk = _make_scored_chunk(doc_id, chunk_id=chunk_id, text="test", score=1.1)
        chunk_repo = FakeChunkRepo(vec_chunks=[vec_chunk], bm25_chunks=[bm25_chunk])
        doc_repo = FakeDocRepo({doc_id: _make_doc(doc_id)})

        service = SearchService(embedder=FakeEmbedder(), chunk_repo=chunk_repo, doc_repo=doc_repo)
        response = await service.search("test")

        result = response.results[0]
        assert result.vector_score == 0.85
        assert result.bm25_score == 1.1
        # RRF score should be w_vec/(k+1) + w_bm25/(k+1) since both are rank 1
        expected_rrf = 0.6 / (60 + 1) + 0.4 / (60 + 1)
        assert abs(result.score - expected_rrf) < 1e-6

    @pytest.mark.asyncio
    async def test_hybrid_empty_bm25(self):
        """If BM25 returns nothing, results come from vector only."""
        doc_id = uuid4()
        vec_chunk = _make_scored_chunk(doc_id, text="vector hit", score=0.9)
        chunk_repo = FakeChunkRepo(vec_chunks=[vec_chunk], bm25_chunks=[])
        doc_repo = FakeDocRepo({doc_id: _make_doc(doc_id)})

        service = SearchService(embedder=FakeEmbedder(), chunk_repo=chunk_repo, doc_repo=doc_repo)
        response = await service.search("test")

        assert len(response.results) == 1
        assert response.results[0].vector_score == 0.9
        assert response.results[0].bm25_score is None


class TestHighlightSnippet:
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
        terms = SearchService._extract_highlight_terms('"phrase" AND rest')
        assert "phrase" in terms
        assert "rest" in terms
        assert "AND" not in terms
