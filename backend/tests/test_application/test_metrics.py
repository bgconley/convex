"""Tests for MetricsCollector and metrics integration.

Uses fakeredis — no real Redis needed. Runs locally.
"""

from __future__ import annotations

from unittest.mock import patch
from uuid import uuid4

import fakeredis

from cortex.infrastructure.metrics_collector import MetricsCollector


def _make_collector() -> MetricsCollector:
    """Create a MetricsCollector backed by fakeredis."""
    collector = MetricsCollector(redis_url="redis://localhost:6379/0")
    collector._redis = fakeredis.FakeRedis()
    return collector


class TestIngestionMetrics:
    def test_empty_metrics(self) -> None:
        collector = _make_collector()
        metrics = collector.get_ingestion_metrics()
        assert metrics["total_processed"] == 0
        assert metrics["error_rate"] == 0.0

    def test_record_success(self) -> None:
        collector = _make_collector()
        doc_id = uuid4()
        collector.record_ingestion(
            document_id=doc_id,
            success=True,
            total_ms=5000.0,
            stage_timings={"parse": 2000.0, "chunk": 500.0, "embed": 1500.0, "ner": 800.0},
            chunk_count=15,
            entity_count=7,
        )
        metrics = collector.get_ingestion_metrics()
        assert metrics["total_processed"] == 1
        assert metrics["success_count"] == 1
        assert metrics["error_count"] == 0
        assert metrics["error_rate"] == 0.0
        assert metrics["avg_duration_ms"] == 5000.0
        assert metrics["avg_stage_ms"]["parse"] == 2000.0
        assert len(metrics["recent"]) == 1
        assert metrics["recent"][0]["chunk_count"] == 15

    def test_record_failure(self) -> None:
        collector = _make_collector()
        collector.record_ingestion(
            document_id=uuid4(),
            success=False,
            total_ms=1200.0,
            stage_timings={"parse": 1200.0},
        )
        metrics = collector.get_ingestion_metrics()
        assert metrics["error_count"] == 1
        assert metrics["error_rate"] == 1.0

    def test_error_rate_calculation(self) -> None:
        collector = _make_collector()
        for i in range(8):
            collector.record_ingestion(
                document_id=uuid4(), success=True,
                total_ms=1000.0, stage_timings={},
            )
        for i in range(2):
            collector.record_ingestion(
                document_id=uuid4(), success=False,
                total_ms=500.0, stage_timings={},
            )
        metrics = collector.get_ingestion_metrics()
        assert metrics["total_processed"] == 10
        assert metrics["error_rate"] == 0.2

    def test_average_stage_timings(self) -> None:
        collector = _make_collector()
        collector.record_ingestion(
            document_id=uuid4(), success=True, total_ms=3000.0,
            stage_timings={"parse": 1000.0, "embed": 2000.0},
        )
        collector.record_ingestion(
            document_id=uuid4(), success=True, total_ms=5000.0,
            stage_timings={"parse": 3000.0, "embed": 2000.0},
        )
        metrics = collector.get_ingestion_metrics()
        assert metrics["avg_stage_ms"]["parse"] == 2000.0
        assert metrics["avg_stage_ms"]["embed"] == 2000.0

    def test_recent_is_newest_first(self) -> None:
        collector = _make_collector()
        ids = [uuid4() for _ in range(3)]
        for doc_id in ids:
            collector.record_ingestion(
                document_id=doc_id, success=True,
                total_ms=1000.0, stage_timings={},
            )
        metrics = collector.get_ingestion_metrics()
        # lpush puts most recent first
        assert metrics["recent"][0]["document_id"] == str(ids[2])

    def test_cross_process_visibility(self) -> None:
        """Two MetricsCollectors sharing the same Redis see each other's ingestion records."""
        fake_redis = fakeredis.FakeRedis()
        c1 = MetricsCollector(redis_url="redis://localhost:6379/0")
        c1._redis = fake_redis
        c2 = MetricsCollector(redis_url="redis://localhost:6379/0")
        c2._redis = fake_redis

        # c1 records (simulates worker)
        c1.record_ingestion(
            document_id=uuid4(), success=True,
            total_ms=3000.0, stage_timings={"parse": 1000.0},
        )
        # c2 reads (simulates API dashboard)
        metrics = c2.get_ingestion_metrics()
        assert metrics["total_processed"] == 1
        assert metrics["success_count"] == 1


class TestSearchMetrics:
    def test_empty_metrics(self) -> None:
        collector = _make_collector()
        metrics = collector.get_search_metrics()
        assert metrics["total_queries"] == 0
        assert metrics["p50_ms"] == 0.0

    def test_record_search(self) -> None:
        collector = _make_collector()
        collector.record_search(
            query="test query",
            total_ms=150.0,
            result_count=5,
            component_ms={"retrieval": 100.0, "rerank": 50.0},
        )
        metrics = collector.get_search_metrics()
        assert metrics["total_queries"] == 1
        assert metrics["avg_latency_ms"] == 150.0
        assert metrics["recent"][0]["query"] == "test query"
        assert metrics["recent"][0]["component_ms"]["retrieval"] == 100.0

    def test_percentile_calculation(self) -> None:
        collector = _make_collector()
        for i in range(1, 101):
            collector.record_search(
                query=f"q{i}", total_ms=float(i), result_count=1,
            )
        metrics = collector.get_search_metrics()
        assert metrics["total_queries"] == 100
        assert metrics["p50_ms"] == 51.0
        assert metrics["p95_ms"] == 96.0
        assert metrics["p99_ms"] == 100.0

    def test_avg_result_count(self) -> None:
        collector = _make_collector()
        collector.record_search(query="a", total_ms=10.0, result_count=5)
        collector.record_search(query="b", total_ms=20.0, result_count=15)
        metrics = collector.get_search_metrics()
        assert metrics["avg_result_count"] == 10.0

    def test_recent_limit(self) -> None:
        collector = _make_collector()
        for i in range(20):
            collector.record_search(
                query=f"query_{i}", total_ms=10.0, result_count=1,
            )
        metrics = collector.get_search_metrics()
        assert len(metrics["recent"]) == 10
        assert metrics["recent"][0]["query"] == "query_19"
