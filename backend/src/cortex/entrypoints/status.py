import httpx
from fastapi import APIRouter, Request

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

    # Check TEI embedder
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(f"{settings.embedder_url}/health")
            if resp.status_code == 200:
                checks["embedder"] = "healthy"
            else:
                checks["embedder"] = f"unhealthy: status {resp.status_code}"
    except Exception as e:
        checks["embedder"] = f"unhealthy: {e}"

    all_healthy = all(v == "healthy" for v in checks.values())
    return {
        "status": "healthy" if all_healthy else "degraded",
        "checks": checks,
    }
