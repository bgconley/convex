from fastapi import APIRouter

from cortex.entrypoints.status import router as status_router

api_router = APIRouter()
api_router.include_router(status_router, tags=["system"])

# Additional routers will be added as steps progress:
# api_router.include_router(documents_router, prefix="/documents", tags=["documents"])
# api_router.include_router(search_router, prefix="/search", tags=["search"])
# api_router.include_router(entities_router, prefix="/entities", tags=["entities"])
# api_router.include_router(collections_router, prefix="/collections", tags=["collections"])
