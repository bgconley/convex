import asyncio

import httpx
import redis.asyncio as aioredis
from fastapi import APIRouter, Request, WebSocket
from starlette.websockets import WebSocketDisconnect

from cortex.schemas.stats_schemas import DashboardResponse, StatsResponse
from cortex.infrastructure.processing_events import PROCESSING_CHANNEL

router = APIRouter()


@router.get("/health")
async def health_check(request: Request) -> dict:
    settings = request.app.state.settings
    checks: dict[str, str] = {}

    # Check PostgreSQL
    try:
        from sqlalchemy import text
        from sqlalchemy.ext.asyncio import create_async_engine

        engine = create_async_engine(settings.database_url, pool_pre_ping=True)
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        await engine.dispose()
        checks["postgres"] = "healthy"
    except Exception as e:
        checks["postgres"] = f"unhealthy: {e}"

    # Check Redis
    try:
        r = aioredis.from_url(settings.redis_url)
        await r.ping()
        await r.aclose()
        checks["redis"] = "healthy"
    except Exception as e:
        checks["redis"] = f"unhealthy: {e}"

    # Check ML services (existing GPU server infrastructure)
    ml_services = {
        "embedder": (settings.embedder_url, "/health"),
        "reranker": (settings.reranker_url, "/health"),
        "ner": (settings.ner_url, "/healthz"),
    }
    for name, (url, health_path) in ml_services.items():
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(f"{url}{health_path}")
                if resp.status_code == 200:
                    checks[name] = "healthy"
                else:
                    checks[name] = f"unhealthy: status {resp.status_code}"
        except Exception as e:
            checks[name] = f"unhealthy: {e}"

    all_healthy = all(v == "healthy" for v in checks.values())
    return {
        "status": "healthy" if all_healthy else "degraded",
        "checks": checks,
    }


@router.get("/status/processing")
async def processing_status(request: Request) -> dict:
    """Queue/processing status for polling fallback when WebSocket is unavailable."""
    doc_repo = request.app.state.doc_repo

    in_progress_statuses = [
        "uploading",
        "stored",
        "parsing",
        "parsed",
        "chunking",
        "chunked",
        "embedding",
        "embedded",
        "extracting_entities",
        "entities_extracted",
        "building_graph",
    ]

    by_status: dict[str, int] = {}
    total_in_progress = 0
    for status in in_progress_statuses:
        count = await doc_repo.count(status=status)
        by_status[status] = count
        total_in_progress += count

    active_documents: list[dict] = []
    processing_events = getattr(request.app.state, "processing_events", None)
    if processing_events is not None:
        active_documents = await processing_events.get_processing_snapshot()

    return {
        "total_in_progress": total_in_progress,
        "by_status": by_status,
        "active_documents": active_documents,
    }


@router.websocket("/ws/events")
async def ws_events(websocket: WebSocket) -> None:
    """Redis pub/sub bridge for live processing events."""
    await websocket.accept()

    settings = websocket.app.state.settings
    redis = aioredis.from_url(settings.redis_url, decode_responses=True)
    pubsub = redis.pubsub()
    await pubsub.subscribe(PROCESSING_CHANNEL)

    try:
        while True:
            message = await pubsub.get_message(
                ignore_subscribe_messages=True,
                timeout=1.0,
            )
            if message and message.get("data"):
                await websocket.send_text(message["data"])
            await asyncio.sleep(0.05)
    except WebSocketDisconnect:
        pass
    finally:
        try:
            await pubsub.unsubscribe(PROCESSING_CHANNEL)
            await pubsub.close()
        finally:
            await redis.aclose()


@router.get("/stats", response_model=StatsResponse)
async def get_stats(request: Request) -> StatsResponse:
    doc_repo = request.app.state.doc_repo
    chunk_repo = request.app.state.chunk_repo
    entity_repo = request.app.state.entity_repo

    doc_count = await doc_repo.count()
    chunk_count = await chunk_repo.count()
    entity_count = await entity_repo.count()
    total_size = await doc_repo.total_file_size()

    return StatsResponse(
        document_count=doc_count,
        chunk_count=chunk_count,
        entity_count=entity_count,
        total_file_size_bytes=total_size,
    )


@router.get("/dashboard", response_model=DashboardResponse)
async def get_dashboard(request: Request) -> DashboardResponse:
    """Aggregated system dashboard: health + stats + processing metrics + search analytics."""
    settings = request.app.state.settings
    metrics = request.app.state.metrics

    # Health checks (reuse logic from health_check)
    health = await health_check(request)

    # Corpus stats
    doc_repo = request.app.state.doc_repo
    chunk_repo = request.app.state.chunk_repo
    entity_repo = request.app.state.entity_repo

    stats = StatsResponse(
        document_count=await doc_repo.count(),
        chunk_count=await chunk_repo.count(),
        entity_count=await entity_repo.count(),
        total_file_size_bytes=await doc_repo.total_file_size(),
    )

    return DashboardResponse(
        health=health,
        corpus=stats,
        ingestion=metrics.get_ingestion_metrics(),
        search=metrics.get_search_metrics(),
    )
