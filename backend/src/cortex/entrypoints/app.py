from contextlib import asynccontextmanager
from collections.abc import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from cortex.bootstrap import CompositionRoot
from cortex.settings import Settings


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    yield


def create_app(settings: Settings | None = None) -> FastAPI:
    if settings is None:
        settings = Settings()

    root = CompositionRoot(settings)

    app = FastAPI(
        title="Cortex",
        description="Personal Knowledge Base API",
        version="0.1.0",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Expose services on app state for endpoint access
    app.state.settings = settings
    app.state.document_service = root.document_service
    app.state.ingestion_service = root.ingestion_service
    app.state.search_service = root.search_service
    app.state.entity_service = root.entity_service
    app.state.file_storage = root.file_storage
    app.state.chunk_repo = root.chunk_repo

    from cortex.entrypoints.router import api_router

    app.include_router(api_router, prefix="/api/v1")

    return app
