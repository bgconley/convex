from __future__ import annotations

from fastapi import APIRouter, Request

from cortex.schemas.search_schemas import (
    ScoreBreakdown,
    SearchRequest,
    SearchResponse,
    SearchResultResponse,
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
