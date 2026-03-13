import httpx
from fastapi import APIRouter, Request

from cortex.schemas.stats_schemas import StatsResponse

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
        import redis.asyncio as aioredis

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
