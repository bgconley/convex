from __future__ import annotations

from fastapi import APIRouter, Query, Request

from cortex.schemas.search_schemas import (
    DocumentSearchResponse,
    DocumentSearchResultResponse,
    ScoreBreakdown,
    SearchRequest,
    SearchResponse,
    SearchResultResponse,
    SearchSuggestionsResponse,
    SuggestionItem,
)

router = APIRouter()


@router.post("", response_model=SearchResponse)
async def search(body: SearchRequest, request: Request):
    search_service = request.app.state.search_service
    result = await search_service.search(
        query=body.query,
        top_k=body.top_k,
        file_type=body.filters.file_types[0] if body.filters and body.filters.file_types else None,
        rerank=body.rerank,
        include_graph=body.include_graph,
    )

    return SearchResponse(
        query=result.query,
        results=[
            SearchResultResponse(
                chunk_id=r.chunk_id,
                document_id=r.document_id,
                document_title=r.document_title,
                document_type=r.document_type,
                chunk_text=r.chunk_text,
                highlighted_snippet=r.highlighted_snippet,
                section_heading=r.section_heading,
                page_number=r.page_number,
                score=r.score,
                score_breakdown=ScoreBreakdown(
                    vector_score=r.vector_score,
                    bm25_score=r.bm25_score,
                    graph_score=r.graph_score,
                    rerank_score=r.rerank_score,
                ),
                chunk_start_char=r.chunk_start_char,
                chunk_end_char=r.chunk_end_char,
                anchor_id=r.anchor_id,
            )
            for r in result.results
        ],
        total_candidates=result.total_candidates,
        search_time_ms=result.search_time_ms,
    )


@router.post("/documents", response_model=DocumentSearchResponse)
async def search_documents(body: SearchRequest, request: Request):
    """Document-level search: returns documents ranked by relevance with best matching snippet."""
    search_service = request.app.state.search_service
    result = await search_service.document_search(
        query=body.query,
        top_k=body.top_k,
        file_type=body.filters.file_types[0] if body.filters and body.filters.file_types else None,
        rerank=body.rerank,
        include_graph=body.include_graph,
    )

    return DocumentSearchResponse(
        query=result.query,
        results=[
            DocumentSearchResultResponse(
                document_id=r.document_id,
                document_title=r.document_title,
                document_type=r.document_type,
                score=r.score,
                score_breakdown=ScoreBreakdown(
                    vector_score=r.vector_score,
                    bm25_score=r.bm25_score,
                    graph_score=r.graph_score,
                    rerank_score=r.rerank_score,
                ),
                best_chunk_snippet=r.best_chunk_snippet,
                best_chunk_section=r.best_chunk_section,
                best_chunk_page=r.best_chunk_page,
                best_chunk_anchor_id=r.best_chunk_anchor_id,
                chunk_count=r.chunk_count,
            )
            for r in result.results
        ],
        total_documents=result.total_documents,
        search_time_ms=result.search_time_ms,
    )


@router.get("/suggestions", response_model=SearchSuggestionsResponse)
async def search_suggestions(
    request: Request,
    q: str = Query(min_length=2, description="Search prefix"),
    limit: int = Query(default=5, ge=1, le=10),
):
    """Return search suggestions matching a prefix from recent queries, entities, and documents."""
    search_service = request.app.state.search_service
    result = await search_service.get_suggestions(prefix=q, limit=limit)

    return SearchSuggestionsResponse(
        query=result.query,
        recent_searches=[
            SuggestionItem(value=q_str, label=q_str, type="recent")
            for q_str in result.recent_searches
        ],
        entities=[
            SuggestionItem(
                value=e.name, label=e.name, type="entity",
                id=e.id, entity_type=e.entity_type,
            )
            for e in result.entities
        ],
        documents=[
            SuggestionItem(
                value=d.title, label=d.title, type="document", id=d.id,
            )
            for d in result.documents
        ],
    )
