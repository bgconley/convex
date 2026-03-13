from __future__ import annotations

import json
from datetime import UTC, datetime
from uuid import UUID

import redis.asyncio as aioredis


PROCESSING_CHANNEL = "cortex:events:processing"
PROCESSING_ACTIVE_KEY = "cortex:processing:active"
TERMINAL_STATUSES = {"ready", "failed"}


class RedisProcessingEvents:
    """Redis-backed processing event publisher and active-status tracker."""

    def __init__(self, redis_url: str) -> None:
        self._redis = aioredis.from_url(redis_url, decode_responses=True)

    async def publish(self, event: dict) -> None:
        payload = dict(event)
        payload.setdefault("timestamp", datetime.now(UTC).isoformat())
        serialized = json.dumps(payload, default=str)

        await self._redis.publish(PROCESSING_CHANNEL, serialized)

        document_id = payload.get("document_id")
        status = payload.get("status")
        if document_id and status:
            if status in TERMINAL_STATUSES:
                await self._redis.hdel(PROCESSING_ACTIVE_KEY, str(document_id))
            else:
                await self._redis.hset(
                    PROCESSING_ACTIVE_KEY, str(document_id), serialized
                )

    async def get_processing_snapshot(self) -> list[dict]:
        raw_values = await self._redis.hvals(PROCESSING_ACTIVE_KEY)
        events: list[dict] = []
        for raw in raw_values:
            try:
                events.append(json.loads(raw))
            except json.JSONDecodeError:
                continue
        return events

    async def publish_status(
        self,
        *,
        document_id: UUID,
        status: str,
        event_type: str = "status_changed",
        progress_pct: float | None = None,
        stage_label: str | None = None,
        error_message: str | None = None,
    ) -> None:
        event = {
            "event_type": event_type,
            "document_id": str(document_id),
            "status": status,
            "progress_pct": progress_pct,
            "stage_label": stage_label,
            "error_message": error_message,
        }
        await self.publish(event)

    async def close(self) -> None:
        await self._redis.aclose()
