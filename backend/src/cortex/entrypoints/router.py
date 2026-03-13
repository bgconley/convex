from fastapi import APIRouter

from cortex.entrypoints.collections import router as collections_router
from cortex.entrypoints.documents import router as documents_router
from cortex.entrypoints.entities import graph_router, router as entities_router
from cortex.entrypoints.search import router as search_router
from cortex.entrypoints.status import router as status_router

api_router = APIRouter()
api_router.include_router(status_router, tags=["system"])
api_router.include_router(documents_router, prefix="/documents", tags=["documents"])
api_router.include_router(search_router, prefix="/search", tags=["search"])
api_router.include_router(entities_router, prefix="/entities", tags=["entities"])
api_router.include_router(graph_router, prefix="/graph", tags=["graph"])
api_router.include_router(collections_router, prefix="/collections", tags=["collections"])
