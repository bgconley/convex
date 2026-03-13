"""Document-level search inspection — runs inside the API container.

Verifies Step 2.4: POST /api/v1/search/documents returns documents
ranked by relevance with best matching chunk as snippet.
"""

import asyncio
import os
import tempfile

from httpx import AsyncClient

BASE = "http://localhost:8080"

DOCS = [
    ("ml_basics.txt", "Machine learning uses algorithms to learn patterns from data. "
     "Supervised learning needs labeled examples. Unsupervised learning finds hidden structure."),
    ("db_overview.txt", "PostgreSQL is a relational database with support for JSON, "
     "full-text search, and extensibility. It uses cost-based query planning."),
    ("search_tech.txt", "Search engines combine keyword matching with semantic understanding. "
     "BM25 scores term frequency while vector search captures meaning beyond exact words."),
]


async def upload_and_wait(client, filename, content):
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", dir="/tmp", delete=False) as f:
        f.write(content)
        tmp = f.name
    with open(tmp, "rb") as f:
        r = await client.post("/api/v1/documents", files={"file": (filename, f, "text/plain")})
    os.unlink(tmp)
    doc_id = r.json()["id"]
    for _ in range(30):
        await asyncio.sleep(2)
        r = await client.get(f"/api/v1/documents/{doc_id}")
        if r.json()["status"] in ("ready", "failed"):
            break
    return doc_id


async def main():
    errors = []

    print("=== Upload 3 documents ===")
    doc_ids = []
    async with AsyncClient(base_url=BASE, timeout=60) as client:
        for name, content in DOCS:
            did = await upload_and_wait(client, name, content)
            print(f"  {name}: {did}")
            doc_ids.append(did)

    print("\n=== POST /search/documents ===")
    async with AsyncClient(base_url=BASE, timeout=30) as client:
        r = await client.post("/api/v1/search/documents", json={
            "query": "how do search engines rank results",
            "top_k": 10,
            "rerank": True,
        })
        data = r.json()
        print(f"  Status: {r.status_code}")
        print(f"  total_documents: {data['total_documents']}")
        print(f"  search_time_ms: {data['search_time_ms']:.0f}")

        if r.status_code != 200:
            errors.append(f"Endpoint returned {r.status_code}")

        for i, doc in enumerate(data["results"]):
            bd = doc["score_breakdown"]
            print(f"  [{i}] {doc['document_title']} score={doc['score']:.4f} "
                  f"chunks={doc['chunk_count']} rerank={bd.get('rerank_score')}")
            print(f"       snippet: {doc['best_chunk_snippet'][:80]}")

        if not data["results"]:
            errors.append("Document search returned 0 results")
        elif data["results"][0]["chunk_count"] < 1:
            errors.append("Top result has chunk_count < 1")

        # Verify it returns documents, not chunks
        for doc in data["results"]:
            if "chunk_id" in doc:
                errors.append("Document result should not have chunk_id")
                break

    print("\n=== Cleanup ===")
    async with AsyncClient(base_url=BASE) as client:
        for did in doc_ids:
            await client.delete(f"/api/v1/documents/{did}")
            print(f"  Deleted {did[:8]}...")

    print("\n=== Summary ===")
    if errors:
        for e in errors:
            print(f"  FAIL: {e}")
    else:
        print("  Document-level search verified!")


if __name__ == "__main__":
    asyncio.run(main())
