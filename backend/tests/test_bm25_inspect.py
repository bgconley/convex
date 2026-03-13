"""BM25 search inspection script — runs inside the API container.

Verifies Step 2.1: upload a test document, wait for processing,
run BM25 keyword/phrase/non-matching searches, then clean up.
"""

import asyncio
import os
import tempfile
import time

from httpx import AsyncClient

from cortex.bootstrap import CompositionRoot
from cortex.settings import Settings

BASE = "http://localhost:8080"

TEST_CONTENT = (
    "BM25 is a ranking function used by search engines to estimate the "
    "relevance of documents to a given search query. It is based on the "
    "probabilistic retrieval framework. The function takes into account "
    "term frequency and inverse document frequency. Neural networks are "
    "a different approach to information retrieval that uses dense vector "
    "representations."
)


async def main():
    settings = Settings()
    root = CompositionRoot(settings)

    # 1. Health check
    print("=== Health Check ===")
    async with AsyncClient(base_url=BASE) as client:
        r = await client.get("/api/v1/health")
        print(f"Health: {r.status_code} {r.json()}")

    # 2. Upload test document
    print("\n=== Upload Test Document ===")
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", dir="/tmp", delete=False) as f:
        f.write(TEST_CONTENT)
        tmp_path = f.name

    async with AsyncClient(base_url=BASE) as client:
        with open(tmp_path, "rb") as f:
            r = await client.post(
                "/api/v1/documents",
                files={"file": ("bm25_test.txt", f, "text/plain")},
            )
        print(f"Upload: {r.status_code} {r.json()}")
        doc_id = r.json()["id"]
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
        print(f"ERROR: Document did not reach ready state: {status}")
        return

    # 4. BM25 search tests
    print("\n=== BM25 Search Tests ===")
    errors = []

    # 4a. Keyword search (OR / disjunction)
    response = await root.search_service.bm25_search("ranking function")
    print(f'Keyword "ranking function": {len(response.results)} results')
    if response.results:
        top = response.results[0]
        print(f"  score={top.score:.4f}")
        print(f"  snippet={top.highlighted_snippet[:120]}")
        if "<mark>" not in top.highlighted_snippet:
            errors.append("Keyword search: no <mark> tags in snippet")
    else:
        errors.append("Keyword search returned 0 results")

    # 4b. Phrase search (exact)
    response = await root.search_service.bm25_search('"probabilistic retrieval"')
    print(f'\nPhrase "probabilistic retrieval": {len(response.results)} results')
    if response.results:
        top = response.results[0]
        print(f"  score={top.score:.4f}")
        print(f"  snippet={top.highlighted_snippet[:120]}")
        if "<mark>" not in top.highlighted_snippet:
            errors.append("Phrase search: no <mark> tags in snippet")
    else:
        errors.append("Phrase search returned 0 results")

    # 4c. Non-matching search
    response = await root.search_service.bm25_search("basketball tournament")
    print(f'\nNon-matching "basketball tournament": {len(response.results)} results')
    if response.results:
        errors.append(f"Non-matching search returned {len(response.results)} results (expected 0)")

    # 4d. AND conjunction
    response = await root.search_service.bm25_search("term AND frequency")
    print(f'\nAND "term AND frequency": {len(response.results)} results')
    if response.results:
        top = response.results[0]
        print(f"  score={top.score:.4f}")
    else:
        errors.append("AND conjunction search returned 0 results")

    # 5. Cleanup
    print("\n=== Cleanup ===")
    async with AsyncClient(base_url=BASE) as client:
        r = await client.delete(f"/api/v1/documents/{doc_id}")
        print(f"Delete: {r.status_code}")

    # 6. Summary
    print("\n=== BM25 Verification Summary ===")
    if errors:
        for e in errors:
            print(f"  FAIL: {e}")
        print(f"\n{len(errors)} failure(s)")
    else:
        print("  All BM25 searches passed!")


if __name__ == "__main__":
    asyncio.run(main())
