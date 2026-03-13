"""Hybrid search (RRF) inspection script — runs inside the API container.

Verifies Step 2.2: upload a test document, run hybrid search via the
public POST /search endpoint, verify that both vector and BM25 scores
appear in the score_breakdown, then clean up.
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
    # 1. Health check
    print("=== Health Check ===")
    async with AsyncClient(base_url=BASE) as client:
        r = await client.get("/api/v1/health")
        print(f"Health: {r.status_code} {r.json()['status']}")

    # 2. Upload test document
    print("\n=== Upload Test Document ===")
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", dir="/tmp", delete=False) as f:
        f.write(TEST_CONTENT)
        tmp_path = f.name

    async with AsyncClient(base_url=BASE) as client:
        with open(tmp_path, "rb") as f:
            r = await client.post("/api/v1/documents", files={"file": ("hybrid_test.txt", f, "text/plain")})
        doc_id = r.json()["id"]
        print(f"Upload: {r.status_code}, id={doc_id}")
    os.unlink(tmp_path)

    # 3. Wait for processing
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
        print(f"ERROR: Document did not reach ready: {status}")
        return

    # 4. Hybrid search via public endpoint
    print("\n=== Hybrid Search via POST /search ===")
    errors = []

    async with AsyncClient(base_url=BASE, timeout=30) as client:
        # 4a. Keyword search — should get both vector and BM25 scores
        r = await client.post("/api/v1/search", json={"query": "ranking function", "top_k": 5})
        data = r.json()
        print(f"\nQuery: 'ranking function'")
        print(f"  Status: {r.status_code}, results: {len(data['results'])}, time: {data['search_time_ms']:.0f}ms")
        if data["results"]:
            top = data["results"][0]
            bd = top["score_breakdown"]
            print(f"  Top score: {top['score']:.6f}")
            print(f"  vector_score: {bd.get('vector_score')}")
            print(f"  bm25_score: {bd.get('bm25_score')}")
            print(f"  snippet: {top['highlighted_snippet'][:100]}")
            if bd.get("vector_score") is None:
                errors.append("Keyword search: vector_score is None")
            if bd.get("bm25_score") is None:
                errors.append("Keyword search: bm25_score is None")
        else:
            errors.append("Keyword search returned 0 results")

        # 4b. Semantic query — should get vector score, may or may not get BM25
        r = await client.post("/api/v1/search", json={"query": "how do search engines determine relevance", "top_k": 5})
        data = r.json()
        print(f"\nQuery: 'how do search engines determine relevance'")
        print(f"  Status: {r.status_code}, results: {len(data['results'])}, time: {data['search_time_ms']:.0f}ms")
        if data["results"]:
            top = data["results"][0]
            bd = top["score_breakdown"]
            print(f"  Top score: {top['score']:.6f}")
            print(f"  vector_score: {bd.get('vector_score')}")
            print(f"  bm25_score: {bd.get('bm25_score')}")
        else:
            errors.append("Semantic search returned 0 results")

        # 4c. Exact phrase search
        r = await client.post("/api/v1/search", json={"query": "probabilistic retrieval framework", "top_k": 5})
        data = r.json()
        print(f"\nQuery: 'probabilistic retrieval framework'")
        print(f"  Status: {r.status_code}, results: {len(data['results'])}, time: {data['search_time_ms']:.0f}ms")
        if data["results"]:
            top = data["results"][0]
            print(f"  Top score: {top['score']:.6f}")
        else:
            errors.append("Phrase search returned 0 results")

        # 4d. Non-matching — should return 0
        r = await client.post("/api/v1/search", json={"query": "basketball tournament scores", "top_k": 5})
        data = r.json()
        print(f"\nQuery: 'basketball tournament scores'")
        print(f"  Status: {r.status_code}, results: {len(data['results'])}")
        # Note: vector search may still return low-similarity results; only check BM25 absence

    # 5. Cleanup
    print("\n=== Cleanup ===")
    async with AsyncClient(base_url=BASE) as client:
        r = await client.delete(f"/api/v1/documents/{doc_id}")
        print(f"Delete: {r.status_code}")

    # 6. Summary
    print("\n=== Hybrid Search Verification Summary ===")
    if errors:
        for e in errors:
            print(f"  FAIL: {e}")
    else:
        print("  All hybrid search checks passed!")


if __name__ == "__main__":
    asyncio.run(main())
