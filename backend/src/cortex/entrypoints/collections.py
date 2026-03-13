"""Collection CRUD API endpoints."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, Request

from cortex.schemas.collection_schemas import (
    CollectionCreateRequest,
    CollectionListResponse,
    CollectionResponse,
    CollectionUpdateRequest,
)

router = APIRouter()


def _collection_to_response(c) -> CollectionResponse:
    return CollectionResponse(
        id=c.id,
        name=c.name,
        description=c.description,
        icon=c.icon,
        parent_id=c.parent_id,
        sort_order=c.sort_order,
        filter_json=c.filter_json,
        is_smart=c.is_smart,
        created_at=c.created_at,
        updated_at=c.updated_at,
    )


@router.get("", response_model=CollectionListResponse)
async def list_collections(
    request: Request,
    parent_id: UUID | None = None,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
):
    service = request.app.state.collection_service
    collections, total = await service.list_collections(
        parent_id=parent_id, limit=limit, offset=offset
    )
    return CollectionListResponse(
        collections=[_collection_to_response(c) for c in collections],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/{collection_id}", response_model=CollectionResponse)
async def get_collection(collection_id: UUID, request: Request):
    service = request.app.state.collection_service
    collection = await service.get(collection_id)
    if collection is None:
        raise HTTPException(status_code=404, detail="Collection not found")
    return _collection_to_response(collection)


@router.post("", response_model=CollectionResponse, status_code=201)
async def create_collection(body: CollectionCreateRequest, request: Request):
    service = request.app.state.collection_service
    collection = await service.create(
        name=body.name,
        description=body.description,
        icon=body.icon,
        parent_id=body.parent_id,
        sort_order=body.sort_order,
        filter_json=body.filter_json,
    )
    return _collection_to_response(collection)


@router.patch("/{collection_id}", response_model=CollectionResponse)
async def update_collection(
    collection_id: UUID, body: CollectionUpdateRequest, request: Request
):
    service = request.app.state.collection_service
    collection = await service.update(
        collection_id=collection_id,
        fields=body.model_fields_set,
        name=body.name,
        description=body.description,
        icon=body.icon,
        parent_id=body.parent_id,
        sort_order=body.sort_order,
        filter_json=body.filter_json,
    )
    if collection is None:
        raise HTTPException(status_code=404, detail="Collection not found")
    return _collection_to_response(collection)


@router.delete("/{collection_id}")
async def delete_collection(collection_id: UUID, request: Request):
    service = request.app.state.collection_service
    deleted = await service.delete(collection_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Collection not found")
    return {"deleted": True, "collection_id": str(collection_id)}
