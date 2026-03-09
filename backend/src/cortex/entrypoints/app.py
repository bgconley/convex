from contextlib import asynccontextmanager
from collections.abc import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from cortex.settings import Settings


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    # Startup: nothing to do yet — DB pool is created in bootstrap
    yield
    # Shutdown: cleanup handled by garbage collection


def create_app(settings: Settings | None = None) -> FastAPI:
    if settings is None:
        settings = Settings()

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

    # Store settings on app state for access in endpoints
    app.state.settings = settings

    # Import and mount routers
    from cortex.entrypoints.router import api_router

    app.include_router(api_router, prefix="/api/v1")

    return app
