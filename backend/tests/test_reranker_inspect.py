"""Reranker integration inspection — runs inside the API container.

Verifies Step 2.3: upload a test document, search with reranking enabled,
verify rerank_score appears in score_breakdown, compare with rerank=false.
"""

import asyncio
import os
import tempfile

from httpx import AsyncClient

BASE = "http://localhost:8080"

TEST_CONTENT = (
    "BM25 is a ranking function used by search engines to estimate the "
    "relevance of documents to a given search query. It is based on the "
    "probabilistic retrieval framework developed by Robertson and Sparck Jones. "
    "The function takes into account term frequency and inverse document frequency. "
    "Neural networks are a different approach to information retrieval that uses "
    "dense vector representations learned from large corpora."
)


async def main():
    print("=== Health Check ===")
    async with AsyncClient(base_url=BASE) as client:
        r = await client.get("/api/v1/health")
        health = r.json()
        print(f"Health: {health['status']}")
        print(f"  reranker: {health['checks'].get('reranker', 'not checked')}")

    print("\n=== Upload Test Document ===")
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", dir="/tmp", delete=False) as f:
        f.write(TEST_CONTENT)
        tmp_path = f.name

    async with AsyncClient(base_url=BASE) as client:
        with open(tmp_path, "rb") as f:
            r = await client.post("/api/v1/documents", files={"file": ("rerank_test.txt", f, "text/plain")})
        doc_id = r.json()["id"]
        print(f"Upload: {r.status_code}, id={doc_id}")
    os.unlink(tmp_path)

    print("\n=== Waiting for processing ===")
    status = "unknown"
    for i in range(30):
        await asyncio.sleep(2)
        async with AsyncClient(base_url=BASE) as client:
            r = await client.get(f"/api/v1/documents/{doc_id}")
            status = r.json()["status"]
            print(f"  [{i*2}s] status={status}")
            if status in ("ready", "failed"):
                break

    if status != "ready":
        print(f"ERROR: not ready: {status}")
        return

    errors = []
    async with AsyncClient(base_url=BASE, timeout=30) as client:
        # Test 1: Search WITH reranking (default)
        print("\n=== Search WITH reranking ===")
        r = await client.post("/api/v1/search", json={"query": "ranking function", "top_k": 5, "rerank": True})
        data_reranked = r.json()
        print(f"  Status: {r.status_code}, results: {len(data_reranked['results'])}, time: {data_reranked['search_time_ms']:.0f}ms")
        if data_reranked["results"]:
            top = data_reranked["results"][0]
            bd = top["score_breakdown"]
            print(f"  score: {top['score']}")
            print(f"  vector_score: {bd.get('vector_score')}")
            print(f"  bm25_score: {bd.get('bm25_score')}")
            print(f"  rerank_score: {bd.get('rerank_score')}")
            if bd.get("rerank_score") is None:
                errors.append("Reranked search: rerank_score is None")
        else:
            errors.append("Reranked search returned 0 results")

        # Test 2: Search WITHOUT reranking
        print("\n=== Search WITHOUT reranking ===")
        r = await client.post("/api/v1/search", json={"query": "ranking function", "top_k": 5, "rerank": False})
        data_rrf = r.json()
        print(f"  Status: {r.status_code}, results: {len(data_rrf['results'])}, time: {data_rrf['search_time_ms']:.0f}ms")
        if data_rrf["results"]:
            top = data_rrf["results"][0]
            bd = top["score_breakdown"]
            print(f"  score: {top['score']}")
            print(f"  vector_score: {bd.get('vector_score')}")
            print(f"  bm25_score: {bd.get('bm25_score')}")
            print(f"  rerank_score: {bd.get('rerank_score')}")
            if bd.get("rerank_score") is not None:
                errors.append("Non-reranked search: rerank_score should be None")
        else:
            errors.append("Non-reranked search returned 0 results")

        # Test 3: Latency comparison
        if data_reranked["results"] and data_rrf["results"]:
            rerank_time = data_reranked["search_time_ms"]
            rrf_time = data_rrf["search_time_ms"]
            overhead = rerank_time - rrf_time
            print(f"\n=== Latency Comparison ===")
            print(f"  RRF only: {rrf_time:.0f}ms")
            print(f"  RRF + rerank: {rerank_time:.0f}ms")
            print(f"  Rerank overhead: {overhead:.0f}ms")

    # Cleanup
    print("\n=== Cleanup ===")
    async with AsyncClient(base_url=BASE) as client:
        r = await client.delete(f"/api/v1/documents/{doc_id}")
        print(f"Delete: {r.status_code}")

    print("\n=== Reranker Verification Summary ===")
    if errors:
        for e in errors:
            print(f"  FAIL: {e}")
    else:
        print("  All reranker checks passed!")


if __name__ == "__main__":
    asyncio.run(main())
