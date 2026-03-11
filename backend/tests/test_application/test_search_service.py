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


class FakeReranker:
    """Reranker test double — returns scores in reverse order of input to verify reordering."""

    def __init__(self, scores: list[float] | None = None):
        self._scores = scores
        self.called = False

    async def rerank(self, query: str, documents: list[str], top_k: int) -> list[RerankResult]:
        self.called = True
        if self._scores:
            return [
                RerankResult(index=i, score=s, text=documents[i])
                for i, s in enumerate(self._scores[:top_k])
                if i < len(documents)
            ]
        # Default: score inversely by position (last input scores highest)
        n = min(len(documents), top_k)
        return [
            RerankResult(index=i, score=float(n - i), text=documents[i])
            for i in range(n)
        ]


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


class TestReranking:
    """Tests for neural reranking integration in SearchService.search."""

    @pytest.mark.asyncio
    async def test_reranker_is_called_when_provided(self):
        doc_id = uuid4()
        chunk = _make_scored_chunk(doc_id, text="test content", score=0.9)
        chunk_repo = FakeChunkRepo(vec_chunks=[chunk], bm25_chunks=[chunk])
        doc_repo = FakeDocRepo({doc_id: _make_doc(doc_id)})
        reranker = FakeReranker(scores=[7.5])

        service = SearchService(
            embedder=FakeEmbedder(), chunk_repo=chunk_repo,
            doc_repo=doc_repo, reranker=reranker,
        )
        response = await service.search("test")

        assert reranker.called
        assert len(response.results) == 1
        assert response.results[0].rerank_score == 7.5
        assert response.results[0].score == 7.5  # rerank score becomes primary

    @pytest.mark.asyncio
    async def test_reranker_reorders_results(self):
        doc_id = uuid4()
        id_a = uuid4()
        id_b = uuid4()
        chunk_a = _make_scored_chunk(doc_id, chunk_id=id_a, text="A", score=0.9, chunk_index=0)
        chunk_b = _make_scored_chunk(doc_id, chunk_id=id_b, text="B", score=0.8, chunk_index=1)
        chunk_repo = FakeChunkRepo(vec_chunks=[chunk_a, chunk_b], bm25_chunks=[])
        doc_repo = FakeDocRepo({doc_id: _make_doc(doc_id)})
        # Reranker scores B higher than A
        reranker = FakeReranker(scores=[3.0, 8.0])

        service = SearchService(
            embedder=FakeEmbedder(), chunk_repo=chunk_repo,
            doc_repo=doc_repo, reranker=reranker,
        )
        response = await service.search("test", top_k=10)

        assert len(response.results) == 2
        # B should be first after reranking
        assert response.results[0].chunk_id == id_b
        assert response.results[0].rerank_score == 8.0
        assert response.results[1].chunk_id == id_a
        assert response.results[1].rerank_score == 3.0

    @pytest.mark.asyncio
    async def test_reranker_skipped_when_flag_false(self):
        doc_id = uuid4()
        chunk = _make_scored_chunk(doc_id, text="test", score=0.9)
        chunk_repo = FakeChunkRepo(vec_chunks=[chunk], bm25_chunks=[])
        doc_repo = FakeDocRepo({doc_id: _make_doc(doc_id)})
        reranker = FakeReranker()

        service = SearchService(
            embedder=FakeEmbedder(), chunk_repo=chunk_repo,
            doc_repo=doc_repo, reranker=reranker,
        )
        response = await service.search("test", rerank=False)

        assert not reranker.called
        assert response.results[0].rerank_score is None

    @pytest.mark.asyncio
    async def test_reranker_skipped_when_none(self):
        doc_id = uuid4()
        chunk = _make_scored_chunk(doc_id, text="test", score=0.9)
        chunk_repo = FakeChunkRepo(vec_chunks=[chunk], bm25_chunks=[])
        doc_repo = FakeDocRepo({doc_id: _make_doc(doc_id)})

        service = SearchService(
            embedder=FakeEmbedder(), chunk_repo=chunk_repo,
            doc_repo=doc_repo, reranker=None,
        )
        response = await service.search("test")

        assert response.results[0].rerank_score is None

    @pytest.mark.asyncio
    async def test_score_breakdown_includes_rerank(self):
        doc_id = uuid4()
        chunk_id = uuid4()
        vec_chunk = _make_scored_chunk(doc_id, chunk_id=chunk_id, text="test", score=0.85)
        bm25_chunk = _make_scored_chunk(doc_id, chunk_id=chunk_id, text="test", score=1.1)
        chunk_repo = FakeChunkRepo(vec_chunks=[vec_chunk], bm25_chunks=[bm25_chunk])
        doc_repo = FakeDocRepo({doc_id: _make_doc(doc_id)})
        reranker = FakeReranker(scores=[6.5])

        service = SearchService(
            embedder=FakeEmbedder(), chunk_repo=chunk_repo,
            doc_repo=doc_repo, reranker=reranker,
        )
        response = await service.search("test")

        result = response.results[0]
        assert result.vector_score == 0.85
        assert result.bm25_score == 1.1
        assert result.rerank_score == 6.5
        assert result.score == 6.5  # rerank score is the final score


class TestDocumentSearch:
    """Tests for SearchService.document_search — document-level aggregation."""

    @pytest.mark.asyncio
    async def test_aggregates_chunks_by_document(self):
        doc_a = uuid4()
        doc_b = uuid4()
        # Doc A has 2 chunks, Doc B has 1 chunk
        chunks_vec = [
            _make_scored_chunk(doc_a, text="A chunk 1", score=0.9, chunk_index=0),
            _make_scored_chunk(doc_a, text="A chunk 2", score=0.7, chunk_index=1),
            _make_scored_chunk(doc_b, text="B chunk 1", score=0.8, chunk_index=0),
        ]
        chunk_repo = FakeChunkRepo(vec_chunks=chunks_vec, bm25_chunks=[])
        doc_repo = FakeDocRepo({doc_a: _make_doc(doc_a), doc_b: _make_doc(doc_b)})

        service = SearchService(embedder=FakeEmbedder(), chunk_repo=chunk_repo, doc_repo=doc_repo)
        response = await service.document_search("test", top_k=10, rerank=False)

        assert response.total_documents == 2
        assert len(response.results) == 2

    @pytest.mark.asyncio
    async def test_uses_max_score_per_document(self):
        doc_id = uuid4()
        chunks_vec = [
            _make_scored_chunk(doc_id, text="high score chunk", score=0.95, chunk_index=0),
            _make_scored_chunk(doc_id, text="low score chunk", score=0.5, chunk_index=1),
        ]
        chunk_repo = FakeChunkRepo(vec_chunks=chunks_vec, bm25_chunks=[])
        doc_repo = FakeDocRepo({doc_id: _make_doc(doc_id)})

        service = SearchService(embedder=FakeEmbedder(), chunk_repo=chunk_repo, doc_repo=doc_repo)
        response = await service.document_search("test", rerank=False)

        assert len(response.results) == 1
        # Score should be from the highest-scoring chunk
        assert response.results[0].chunk_count == 2

    @pytest.mark.asyncio
    async def test_includes_best_chunk_snippet(self):
        doc_id = uuid4()
        chunk = _make_scored_chunk(doc_id, text="the best matching text here", score=0.9)
        chunk_repo = FakeChunkRepo(vec_chunks=[chunk], bm25_chunks=[])
        doc_repo = FakeDocRepo({doc_id: _make_doc(doc_id)})

        service = SearchService(embedder=FakeEmbedder(), chunk_repo=chunk_repo, doc_repo=doc_repo)
        response = await service.document_search("matching", rerank=False)

        assert len(response.results) == 1
        assert "matching" in response.results[0].best_chunk_snippet.lower() or "<mark>" in response.results[0].best_chunk_snippet

    @pytest.mark.asyncio
    async def test_respects_top_k(self):
        docs = {}
        chunks = []
        for i in range(5):
            did = uuid4()
            docs[did] = _make_doc(did)
            chunks.append(_make_scored_chunk(did, text=f"doc {i}", score=0.9 - i * 0.1, chunk_index=0))
        chunk_repo = FakeChunkRepo(vec_chunks=chunks, bm25_chunks=[])
        doc_repo = FakeDocRepo(docs)

        service = SearchService(embedder=FakeEmbedder(), chunk_repo=chunk_repo, doc_repo=doc_repo)
        response = await service.document_search("doc", top_k=3, rerank=False)

        assert len(response.results) == 3


class FakeNER:
    """NER test double — extracts pre-configured entities from any chunk text."""

    def __init__(self, extractions: list[EntityExtraction] | None = None):
        self._extractions = extractions or []
        self.called = False

    async def extract_entities(
        self, chunks: list[Chunk], threshold: float = 0.4
    ) -> list[EntityExtraction]:
        self.called = True
        return self._extractions


class FakeGraphSearch:
    """GraphSearch test double — returns pre-configured scored chunks."""

    def __init__(self, chunks: list[ScoredChunk] | None = None):
        self._chunks = chunks or []
        self.called = False
        self.last_entity_names: list[str] | None = None

    async def search_by_entities(
        self, entity_names: list[str], top_k: int = 50
    ) -> list[ScoredChunk]:
        self.called = True
        self.last_entity_names = entity_names
        return self._chunks[:top_k]


class TestGraphEnhancedSearch:
    """Tests for graph-enhanced search (Step 3.3)."""

    @pytest.mark.asyncio
    async def test_graph_search_runs_with_vector_and_bm25(self):
        """When include_graph=True and NER+graph are wired, all three signals run."""
        doc_id = uuid4()
        chunk_id = uuid4()
        chunk = _make_scored_chunk(doc_id, chunk_id=chunk_id, text="John Smith works at Acme", score=0.9)
        graph_chunk = _make_scored_chunk(doc_id, chunk_id=chunk_id, text="John Smith works at Acme", score=0.8)
        chunk_repo = FakeChunkRepo(vec_chunks=[chunk], bm25_chunks=[chunk])
        doc_repo = FakeDocRepo({doc_id: _make_doc(doc_id)})
        ner = FakeNER(extractions=[
            EntityExtraction(text="John Smith", label="person", confidence=0.95,
                             start_char=0, end_char=10),
        ])
        graph_search = FakeGraphSearch(chunks=[graph_chunk])

        service = SearchService(
            embedder=FakeEmbedder(), chunk_repo=chunk_repo,
            doc_repo=doc_repo, ner=ner, graph_search=graph_search,
        )
        response = await service.search("John Smith", include_graph=True)

        assert ner.called
        assert graph_search.called
        assert len(response.results) == 1

    @pytest.mark.asyncio
    async def test_rrf_weights_change_with_graph(self):
        """With graph results, RRF uses 3-way weights (0.5/0.3/0.2)."""
        doc_id = uuid4()
        chunk_id = uuid4()
        chunk = _make_scored_chunk(doc_id, chunk_id=chunk_id, text="entity chunk", score=0.9)
        graph_chunk = _make_scored_chunk(doc_id, chunk_id=chunk_id, text="entity chunk", score=0.8)
        chunk_repo = FakeChunkRepo(vec_chunks=[chunk], bm25_chunks=[chunk])
        doc_repo = FakeDocRepo({doc_id: _make_doc(doc_id)})
        ner = FakeNER(extractions=[
            EntityExtraction(text="entity", label="technology", confidence=0.9,
                             start_char=0, end_char=6),
        ])
        graph_search = FakeGraphSearch(chunks=[graph_chunk])

        service = SearchService(
            embedder=FakeEmbedder(), chunk_repo=chunk_repo,
            doc_repo=doc_repo, ner=ner, graph_search=graph_search,
        )
        response = await service.search("entity", include_graph=True)

        result = response.results[0]
        # With 3-way RRF: score = 0.5/(60+1) + 0.3/(60+1) + 0.2/(60+1)
        expected_rrf = 0.5 / 61 + 0.3 / 61 + 0.2 / 61
        assert abs(result.score - expected_rrf) < 1e-6

    @pytest.mark.asyncio
    async def test_graph_score_in_results(self):
        """Graph score appears in search result score breakdown."""
        doc_id = uuid4()
        chunk_id = uuid4()
        vec_chunk = _make_scored_chunk(doc_id, chunk_id=chunk_id, text="test", score=0.85)
        graph_chunk = _make_scored_chunk(doc_id, chunk_id=chunk_id, text="test", score=0.7)
        chunk_repo = FakeChunkRepo(vec_chunks=[vec_chunk], bm25_chunks=[])
        doc_repo = FakeDocRepo({doc_id: _make_doc(doc_id)})
        ner = FakeNER(extractions=[
            EntityExtraction(text="test", label="technology", confidence=0.8,
                             start_char=0, end_char=4),
        ])
        graph_search = FakeGraphSearch(chunks=[graph_chunk])

        service = SearchService(
            embedder=FakeEmbedder(), chunk_repo=chunk_repo,
            doc_repo=doc_repo, ner=ner, graph_search=graph_search,
        )
        response = await service.search("test", include_graph=True)

        result = response.results[0]
        assert result.vector_score == 0.85
        assert result.graph_score == 0.7
        assert result.bm25_score is None

    @pytest.mark.asyncio
    async def test_include_graph_false_disables_graph(self):
        """When include_graph=False, NER and graph search are not called."""
        doc_id = uuid4()
        chunk = _make_scored_chunk(doc_id, text="test", score=0.9)
        chunk_repo = FakeChunkRepo(vec_chunks=[chunk], bm25_chunks=[])
        doc_repo = FakeDocRepo({doc_id: _make_doc(doc_id)})
        ner = FakeNER(extractions=[
            EntityExtraction(text="test", label="technology", confidence=0.8,
                             start_char=0, end_char=4),
        ])
        graph_search = FakeGraphSearch(chunks=[chunk])

        service = SearchService(
            embedder=FakeEmbedder(), chunk_repo=chunk_repo,
            doc_repo=doc_repo, ner=ner, graph_search=graph_search,
        )
        response = await service.search("test", include_graph=False)

        assert not ner.called
        assert not graph_search.called
        # Without graph, RRF uses 2-way weights (0.6/0.4)
        result = response.results[0]
        expected_rrf = 0.6 / 61  # vec only, rank 1
        assert abs(result.score - expected_rrf) < 1e-6
        assert result.graph_score is None

    @pytest.mark.asyncio
    async def test_no_entities_found_falls_back(self):
        """If NER extracts no entities, graph signal is empty and 2-way RRF is used."""
        doc_id = uuid4()
        chunk_id = uuid4()
        chunk = _make_scored_chunk(doc_id, chunk_id=chunk_id, text="test", score=0.9)
        chunk_repo = FakeChunkRepo(vec_chunks=[chunk], bm25_chunks=[chunk])
        doc_repo = FakeDocRepo({doc_id: _make_doc(doc_id)})
        ner = FakeNER(extractions=[])  # No entities found
        graph_search = FakeGraphSearch()

        service = SearchService(
            embedder=FakeEmbedder(), chunk_repo=chunk_repo,
            doc_repo=doc_repo, ner=ner, graph_search=graph_search,
        )
        response = await service.search("something generic", include_graph=True)

        assert ner.called
        assert not graph_search.called  # Not called because no entities
        assert len(response.results) == 1
        # Falls back to 2-way RRF since graph_results is empty
        result = response.results[0]
        expected_rrf = 0.6 / 61 + 0.4 / 61  # Both vec and bm25 at rank 1
        assert abs(result.score - expected_rrf) < 1e-6

    @pytest.mark.asyncio
    async def test_graph_only_chunk_appears_in_results(self):
        """A chunk found only by graph search still appears via RRF."""
        doc_id = uuid4()
        vec_id = uuid4()
        graph_only_id = uuid4()
        vec_chunk = _make_scored_chunk(doc_id, chunk_id=vec_id, text="vector hit", score=0.9, chunk_index=0)
        graph_chunk = _make_scored_chunk(doc_id, chunk_id=graph_only_id, text="graph hit", score=0.8, chunk_index=1)
        chunk_repo = FakeChunkRepo(vec_chunks=[vec_chunk], bm25_chunks=[])
        doc_repo = FakeDocRepo({doc_id: _make_doc(doc_id)})
        ner = FakeNER(extractions=[
            EntityExtraction(text="entity", label="person", confidence=0.9,
                             start_char=0, end_char=6),
        ])
        graph_search = FakeGraphSearch(chunks=[graph_chunk])

        service = SearchService(
            embedder=FakeEmbedder(), chunk_repo=chunk_repo,
            doc_repo=doc_repo, ner=ner, graph_search=graph_search,
        )
        response = await service.search("entity query", top_k=10, include_graph=True)

        assert len(response.results) == 2
        ids = {r.chunk_id for r in response.results}
        assert vec_id in ids
        assert graph_only_id in ids
        # Graph-only chunk should have graph_score but no vector/bm25 score
        graph_result = next(r for r in response.results if r.chunk_id == graph_only_id)
        assert graph_result.graph_score == 0.8
        assert graph_result.vector_score is None
        assert graph_result.bm25_score is None


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
