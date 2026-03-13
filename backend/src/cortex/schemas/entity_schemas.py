"""Pydantic schemas for entity API endpoints."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class EntityResponse(BaseModel):
    id: UUID
    name: str
    entity_type: str
    normalized_name: str
    description: str | None = None
    document_count: int
    mention_count: int
    created_at: datetime
    updated_at: datetime


class EntityListResponse(BaseModel):
    entities: list[EntityResponse]
    total: int
    limit: int
    offset: int


class EntityTypeListResponse(BaseModel):
    entity_types: list[str]


class EntityDocumentResponse(BaseModel):
    document_id: UUID
    title: str


class RelatedEntityResponse(BaseModel):
    name: str
    entity_type: str
    normalized_name: str


class EntityDetailResponse(BaseModel):
    entity: EntityResponse
    documents: list[EntityDocumentResponse]
    related_entities: list[RelatedEntityResponse]


class GraphExploreResponse(BaseModel):
    center: EntityResponse
    related_entities: list[RelatedEntityResponse]
    documents: list[EntityDocumentResponse]
