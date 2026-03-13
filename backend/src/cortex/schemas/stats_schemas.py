from __future__ import annotations

from pydantic import BaseModel


class StatsResponse(BaseModel):
    document_count: int
    chunk_count: int
    entity_count: int
    total_file_size_bytes: int
