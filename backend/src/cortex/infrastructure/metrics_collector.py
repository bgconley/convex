"""Metrics collector for Cortex.

Ingestion metrics use Redis (shared between API and Celery worker processes).
Search metrics use in-memory storage (API process only).
Data retention: last 1000 ingestion records, last 5000 search records.
"""

from __future__ import annotations

import json
import logging
import threading
from collections import deque
from dataclasses import dataclass, field
from uuid import UUID

import redis

logger = logging.getLogger(__name__)

INGESTION_KEY = "cortex:metrics:ingestion"
INGESTION_MAX = 1000


@dataclass
class SearchRecord:
    query: str
    total_ms: float
    result_count: int
    component_ms: dict[str, float]


class MetricsCollector:
    """Hybrid metrics store: Redis for ingestion (cross-process), in-memory for search.

    Both API and Celery worker write ingestion records to the same Redis list.
    Only the API process records and reads search metrics (in-memory).
    """

    def __init__(self, redis_url: str) -> None:
        self._redis = redis.from_url(redis_url)
        self._search_records: deque[SearchRecord] = deque(maxlen=5000)
        self._search_lock = threading.Lock()

    def record_ingestion(
        self,
        document_id: UUID,
        success: bool,
        total_ms: float,
        stage_timings: dict[str, float],
        chunk_count: int = 0,
        entity_count: int = 0,
    ) -> None:
        record = {
            "document_id": str(document_id),
            "success": success,
            "total_ms": round(total_ms, 1),
            "stage_timings": {k: round(v, 1) for k, v in stage_timings.items()},
            "chunk_count": chunk_count,
            "entity_count": entity_count,
        }
        try:
            pipe = self._redis.pipeline()
            pipe.lpush(INGESTION_KEY, json.dumps(record))
            pipe.ltrim(INGESTION_KEY, 0, INGESTION_MAX - 1)
            pipe.execute()
        except Exception:
            logger.warning("Failed to write ingestion metrics to Redis", exc_info=True)

    def record_search(
        self,
        query: str,
        total_ms: float,
        result_count: int,
        component_ms: dict[str, float] | None = None,
    ) -> None:
        with self._search_lock:
            self._search_records.append(
                SearchRecord(
                    query=query,
                    total_ms=total_ms,
                    result_count=result_count,
                    component_ms=component_ms or {},
                )
            )

    def get_ingestion_metrics(self) -> dict:
        try:
            raw = self._redis.lrange(INGESTION_KEY, 0, INGESTION_MAX - 1)
        except Exception:
            logger.warning("Failed to read ingestion metrics from Redis", exc_info=True)
            raw = []

        records = []
        for item in raw:
            try:
                records.append(json.loads(item))
            except (json.JSONDecodeError, TypeError):
                continue

        if not records:
            return {
                "total_processed": 0,
                "success_count": 0,
                "error_count": 0,
                "error_rate": 0.0,
                "avg_duration_ms": 0.0,
                "avg_stage_ms": {},
                "recent": [],
            }

        successes = [r for r in records if r["success"]]
        failures = [r for r in records if not r["success"]]
        durations = [r["total_ms"] for r in records]

        # Average per-stage timing across successes
        stage_sums: dict[str, float] = {}
        stage_counts: dict[str, int] = {}
        for r in successes:
            for stage, ms in r["stage_timings"].items():
                stage_sums[stage] = stage_sums.get(stage, 0.0) + ms
                stage_counts[stage] = stage_counts.get(stage, 0) + 1

        avg_stages = {
            stage: round(stage_sums[stage] / stage_counts[stage], 1)
            for stage in stage_sums
        }

        # Records are already newest-first (lpush)
        recent = [
            {
                "document_id": r["document_id"],
                "success": r["success"],
                "total_ms": r["total_ms"],
                "chunk_count": r["chunk_count"],
                "entity_count": r["entity_count"],
            }
            for r in records[:10]
        ]

        return {
            "total_processed": len(records),
            "success_count": len(successes),
            "error_count": len(failures),
            "error_rate": round(len(failures) / len(records), 4),
            "avg_duration_ms": round(sum(durations) / len(durations), 1),
            "avg_stage_ms": avg_stages,
            "recent": recent,
        }

    def get_search_metrics(self) -> dict:
        with self._search_lock:
            records = list(self._search_records)

        if not records:
            return {
                "total_queries": 0,
                "avg_latency_ms": 0.0,
                "p50_ms": 0.0,
                "p95_ms": 0.0,
                "p99_ms": 0.0,
                "avg_result_count": 0.0,
                "recent": [],
            }

        latencies = sorted(r.total_ms for r in records)
        n = len(latencies)

        recent = [
            {
                "query": r.query,
                "total_ms": round(r.total_ms, 1),
                "result_count": r.result_count,
                "component_ms": {k: round(v, 1) for k, v in r.component_ms.items()},
            }
            for r in list(reversed(records))[:10]
        ]

        return {
            "total_queries": n,
            "avg_latency_ms": round(sum(latencies) / n, 1),
            "p50_ms": round(latencies[int(n * 0.50)], 1),
            "p95_ms": round(latencies[min(int(n * 0.95), n - 1)], 1),
            "p99_ms": round(latencies[min(int(n * 0.99), n - 1)], 1),
            "avg_result_count": round(
                sum(r.result_count for r in records) / n, 1,
            ),
            "recent": recent,
        }

    def close(self) -> None:
        try:
            self._redis.close()
        except AttributeError:
            self._redis.connection_pool.disconnect()
