from __future__ import annotations

import logging
import time
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from uuid import uuid4

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

from cortex.bootstrap import CompositionRoot
from cortex.infrastructure.logging import configure_logging, request_id_var
from cortex.settings import Settings

logger = logging.getLogger(__name__)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Assigns a correlation ID and logs every HTTP request/response."""

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint,
    ) -> Response:
        req_id = request.headers.get("X-Request-ID") or uuid4().hex[:12]
        request_id_var.set(req_id)

        start = time.monotonic()
        status_code = 500
        try:
            response = await call_next(request)
            status_code = response.status_code
            response.headers["X-Request-ID"] = req_id
            return response
        except Exception:
            raise
        finally:
            duration_ms = (time.monotonic() - start) * 1000
            logger.info(
                "%s %s %d %.1fms",
                request.method,
                request.url.path,
                status_code,
                duration_ms,
                extra={
                    "method": request.method,
                    "path": request.url.path,
                    "status_code": status_code,
                    "duration_ms": round(duration_ms, 1),
                },
            )


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    yield
    root = getattr(app.state, "composition_root", None)
    if root is not None:
        try:
            await root.aclose()
        except Exception:
            logger.exception("Failed to close composition root resources")


def create_app(settings: Settings | None = None) -> FastAPI:
    if settings is None:
        settings = Settings()

    configure_logging(level=settings.log_level, json_format=settings.log_json)

    root = CompositionRoot(settings)

    app = FastAPI(
        title="Cortex",
        description="Personal Knowledge Base API",
        version="0.1.0",
        lifespan=lifespan,
    )

    app.add_middleware(RequestLoggingMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Expose services on app state for endpoint access
    app.state.composition_root = root
    app.state.settings = settings
    app.state.document_service = root.document_service
    app.state.ingestion_service = root.ingestion_service
    app.state.search_service = root.search_service
    app.state.entity_service = root.entity_service
    app.state.collection_service = root.collection_service
    app.state.file_storage = root.file_storage
    app.state.chunk_repo = root.chunk_repo
    app.state.doc_repo = root.doc_repo
    app.state.entity_repo = root.entity_repo
    app.state.metrics = root.metrics
    app.state.processing_events = root.processing_events

    from cortex.entrypoints.router import api_router

    app.include_router(api_router, prefix="/api/v1")

    return app
