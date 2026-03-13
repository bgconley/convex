"""Entity and graph exploration API endpoints."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, Request

from cortex.schemas.entity_schemas import (
    EntityDetailResponse,
    EntityDocumentResponse,
    EntityListResponse,
    EntityResponse,
    EntityTypeListResponse,
    GraphExploreResponse,
    RelatedEntityResponse,
)
from cortex.infrastructure.ml.gliner_ner import ENTITY_LABELS

router = APIRouter()
graph_router = APIRouter()


def _entity_to_response(entity) -> EntityResponse:
    return EntityResponse(
        id=entity.id,
        name=entity.name,
        entity_type=entity.entity_type,
        normalized_name=entity.normalized_name,
        description=entity.description,
        document_count=entity.document_count,
        mention_count=entity.mention_count,
        created_at=entity.created_at,
        updated_at=entity.updated_at,
    )


@router.get("", response_model=EntityListResponse)
async def list_entities(
    request: Request,
    entity_type: str | None = None,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
):
    entity_service = request.app.state.entity_service
    entities, total = await entity_service.list_entities(
        entity_type=entity_type, limit=limit, offset=offset
    )
    return EntityListResponse(
        entities=[_entity_to_response(e) for e in entities],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/types", response_model=EntityTypeListResponse)
async def list_entity_types(request: Request):
    entity_service = request.app.state.entity_service
    persisted_types = await entity_service.list_entity_types()

    ordered_types: list[str] = []
    seen: set[str] = set()
    for entity_type in ENTITY_LABELS:
        if entity_type not in seen:
            ordered_types.append(entity_type)
            seen.add(entity_type)
    for entity_type in persisted_types:
        if entity_type not in seen:
            ordered_types.append(entity_type)
            seen.add(entity_type)

    return EntityTypeListResponse(entity_types=ordered_types)


@router.get("/{entity_id}", response_model=EntityDetailResponse)
async def get_entity(entity_id: UUID, request: Request):
    entity_service = request.app.state.entity_service
    entity = await entity_service.get(entity_id)
    if entity is None:
        raise HTTPException(status_code=404, detail="Entity not found")

    documents = await entity_service.get_entity_documents(entity_id)
    related = await entity_service.get_related_entities(entity_id, hops=2)

    return EntityDetailResponse(
        entity=_entity_to_response(entity),
        documents=[
            EntityDocumentResponse(document_id=doc_id, title=title)
            for doc_id, title in documents
        ],
        related_entities=[
            RelatedEntityResponse(
                name=r.name,
                entity_type=r.entity_type,
                normalized_name=r.normalized_name,
            )
            for r in related
        ],
    )


@router.get("/{entity_id}/related", response_model=list[RelatedEntityResponse])
async def get_related_entities(
    entity_id: UUID,
    request: Request,
    hops: int = Query(default=2, ge=1, le=4),
):
    entity_service = request.app.state.entity_service
    entity = await entity_service.get(entity_id)
    if entity is None:
        raise HTTPException(status_code=404, detail="Entity not found")

    related = await entity_service.get_related_entities(entity_id, hops=hops)
    return [
        RelatedEntityResponse(
            name=r.name,
            entity_type=r.entity_type,
            normalized_name=r.normalized_name,
        )
        for r in related
    ]


@graph_router.get("/explore", response_model=GraphExploreResponse)
async def explore_graph(
    request: Request,
    entity_id: UUID = Query(..., description="Starting entity ID"),
    hops: int = Query(default=2, ge=1, le=4),
):
    entity_service = request.app.state.entity_service
    entity = await entity_service.get(entity_id)
    if entity is None:
        raise HTTPException(status_code=404, detail="Entity not found")

    related = await entity_service.get_related_entities(entity_id, hops=hops)
    documents = await entity_service.get_entity_documents(entity_id)

    return GraphExploreResponse(
        center=_entity_to_response(entity),
        related_entities=[
            RelatedEntityResponse(
                name=r.name,
                entity_type=r.entity_type,
                normalized_name=r.normalized_name,
            )
            for r in related
        ],
        documents=[
            EntityDocumentResponse(document_id=doc_id, title=title)
            for doc_id, title in documents
        ],
    )
