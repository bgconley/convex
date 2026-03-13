from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class StatsResponse(BaseModel):
    document_count: int
    chunk_count: int
    entity_count: int
    total_file_size_bytes: int


class DashboardResponse(BaseModel):
    health: dict[str, Any]
    corpus: StatsResponse
    ingestion: dict[str, Any]
    search: dict[str, Any]
