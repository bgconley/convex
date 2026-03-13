from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class CollectionResponse(BaseModel):
    id: UUID
    name: str
    description: str | None = None
    icon: str | None = None
    parent_id: UUID | None = None
    sort_order: int
    filter_json: dict | None = None
    is_smart: bool = False
    created_at: datetime
    updated_at: datetime


class CollectionCreateRequest(BaseModel):
    name: str
    description: str | None = None
    icon: str | None = None
    parent_id: UUID | None = None
    sort_order: int = 0
    filter_json: dict | None = None


class CollectionUpdateRequest(BaseModel):
    name: str | None = None
    description: str | None = None
    icon: str | None = None
    parent_id: UUID | None = None
    sort_order: int | None = None
    filter_json: dict | None = None


class CollectionListResponse(BaseModel):
    collections: list[CollectionResponse]
    total: int
    limit: int
    offset: int
