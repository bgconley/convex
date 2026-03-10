from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class SearchFilters(BaseModel):
    file_types: list[str] | None = None
    collection_ids: list[UUID] | None = None
    date_from: datetime | None = None
    date_to: datetime | None = None
    tags: list[str] | None = None
    entity_types: list[str] | None = None


class SearchRequest(BaseModel):
    query: str
    top_k: int = 10
    filters: SearchFilters | None = None
    include_graph: bool = True
    rerank: bool = True


class ScoreBreakdown(BaseModel):
    vector_score: float | None = None
    bm25_score: float | None = None
    graph_score: float | None = None
    rerank_score: float | None = None


class EntityMentionResponse(BaseModel):
    name: str
    entity_type: str
    confidence: float


class SearchResultResponse(BaseModel):
    chunk_id: UUID
    document_id: UUID
    document_title: str
    document_type: str
    chunk_text: str
    highlighted_snippet: str
    section_heading: str | None = None
    page_number: int | None = None
    score: float
    score_breakdown: ScoreBreakdown
    entities: list[EntityMentionResponse] = []
    chunk_start_char: int
    chunk_end_char: int
    anchor_id: str | None = None


class SearchResponse(BaseModel):
    query: str
    results: list[SearchResultResponse]
    total_candidates: int
    search_time_ms: float


class DocumentSearchResultResponse(BaseModel):
    document_id: UUID
    document_title: str
    document_type: str
    score: float
    score_breakdown: ScoreBreakdown
    best_chunk_snippet: str
    best_chunk_section: str | None = None
    best_chunk_page: int | None = None
    best_chunk_anchor_id: str | None = None
    chunk_count: int


class DocumentSearchResponse(BaseModel):
    query: str
    results: list[DocumentSearchResultResponse]
    total_documents: int
    search_time_ms: float
