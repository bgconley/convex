"""Graph-enhanced search inspection — runs inside the API container.

Verifies Step 3.3: search with graph expansion returns graph_score
in score_breakdown and discovers entity-related results.

Usage (from GPU server):
  cd infrastructure
  docker compose exec -T api python - < ../backend/tests/test_graph_search_inspect.py
"""

import asyncio
import os
import tempfile
import random
import string

from httpx import AsyncClient

BASE = "http://localhost:8080"

# Random suffix to avoid duplicate detection from prior runs
_SALT = ''.join(random.choices(string.ascii_lowercase, k=8))

DOC_A = (
    f"[{_SALT}] Dr. Marie Curie conducted pioneering research on radioactivity. "
    "She discovered the elements polonium and radium at the University of Paris. "
    "Curie was the first woman to win a Nobel Prize."
)

DOC_B = (
    f"[{_SALT}] Pierre Curie was a French physicist who studied crystallography "
    "and magnetism. He married Marie Curie in 1895. Together they researched "
    "radioactivity at the University of Paris and shared the Nobel Prize in Physics."
)

DOC_C = (
    f"[{_SALT}] The Nobel Prize in Physics has been awarded to many scientists. "
    "Albert Einstein received it for the photoelectric effect. "
    "The University of Paris has produced several laureates."
)


async def upload_and_wait(client, filename, content):
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", dir="/tmp", delete=False) as f:
        f.write(content)
        tmp = f.name
    with open(tmp, "rb") as f:
        r = await client.post("/api/v1/documents", files={"file": (filename, f, "text/plain")})
    os.unlink(tmp)
    doc_id = r.json()["id"]
    for _ in range(45):
        await asyncio.sleep(2)
        r = await client.get(f"/api/v1/documents/{doc_id}")
        status = r.json()["status"]
        if status in ("ready", "failed"):
            break
    return doc_id, status


async def main():
    errors = []
    doc_ids = []

    print("=== Step 3.3: Graph-Enhanced Search ===\n")

    # 1. Upload 3 documents with shared entities
    print("--- Upload 3 documents with shared entities ---")
    async with AsyncClient(base_url=BASE, timeout=60) as client:
        id_a, status_a = await upload_and_wait(client, "curie_marie.txt", DOC_A)
        print(f"  Doc A (Marie Curie):  {id_a} ({status_a})")
        doc_ids.append(id_a)

        id_b, status_b = await upload_and_wait(client, "curie_pierre.txt", DOC_B)
        print(f"  Doc B (Pierre Curie): {id_b} ({status_b})")
        doc_ids.append(id_b)

        id_c, status_c = await upload_and_wait(client, "nobel_prize.txt", DOC_C)
        print(f"  Doc C (Nobel Prize):  {id_c} ({status_c})")
        doc_ids.append(id_c)

    if not all(s == "ready" for s in [status_a, status_b, status_c]):
        print(f"\nERROR: docs not ready: A={status_a}, B={status_b}, C={status_c}")
        return

    # 2. Search with graph enabled
    print("\n--- Search: 'Marie Curie' with graph enabled ---")
    async with AsyncClient(base_url=BASE, timeout=30) as client:
        r = await client.post("/api/v1/search", json={
            "query": "Marie Curie",
            "top_k": 10,
            "include_graph": True,
            "rerank": True,
        })
        assert r.status_code == 200, f"Search failed: {r.status_code}"
        data = r.json()

    print(f"  Results: {len(data['results'])}")
    print(f"  Total candidates: {data['total_candidates']}")
    print(f"  Search time: {data['search_time_ms']:.1f}ms")

    def _s(v):
        return f"{v:>8}" if v is not None else f"{'-':>8}"

    has_graph_score = False
    for i, result in enumerate(data["results"][:5]):
        bd = result["score_breakdown"]
        gs = bd.get("graph_score")
        if gs is not None:
            has_graph_score = True
        print(f"  [{i}] score={result['score']:.4f}  "
              f"vec={_s(bd.get('vector_score'))}  "
              f"bm25={_s(bd.get('bm25_score'))}  "
              f"graph={_s(gs)}  "
              f"rerank={_s(bd.get('rerank_score'))}  "
              f"doc={result['document_title'][:40]}")

    if not has_graph_score:
        errors.append("No graph_score in any search result")
    else:
        print("  OK: graph_score present in results")

    if len(data["results"]) < 2:
        errors.append(f"Expected >=2 results, got {len(data['results'])}")

    # 3. Search with graph disabled — no graph_score expected
    print("\n--- Search: 'Marie Curie' with graph DISABLED ---")
    async with AsyncClient(base_url=BASE, timeout=30) as client:
        r = await client.post("/api/v1/search", json={
            "query": "Marie Curie",
            "top_k": 10,
            "include_graph": False,
            "rerank": True,
        })
        data_no_graph = r.json()

    no_graph_has_score = any(
        r["score_breakdown"].get("graph_score") is not None
        for r in data_no_graph["results"]
    )
    if no_graph_has_score:
        errors.append("graph_score present when include_graph=false")
    else:
        print("  OK: no graph_score when graph disabled")

    # 4. Entity-related search: search for "Pierre Curie" should find
    #    Marie Curie docs via graph expansion (co-occurring entities)
    print("\n--- Search: 'Pierre Curie' — graph should link to Marie Curie docs ---")
    async with AsyncClient(base_url=BASE, timeout=30) as client:
        r = await client.post("/api/v1/search", json={
            "query": "Pierre Curie",
            "top_k": 10,
            "include_graph": True,
            "rerank": True,
        })
        data_pierre = r.json()

    doc_ids_in_results = {r["document_id"] for r in data_pierre["results"]}
    print(f"  Results: {len(data_pierre['results'])}")
    print(f"  Unique docs: {len(doc_ids_in_results)}")
    if len(doc_ids_in_results) >= 2:
        print("  OK: multiple documents found (graph expansion working)")
    else:
        print("  NOTE: only 1 document found (graph may not have expanded)")

    # 5. Document-level search with graph
    print("\n--- Document search: 'radioactivity Nobel Prize' with graph ---")
    async with AsyncClient(base_url=BASE, timeout=30) as client:
        r = await client.post("/api/v1/search/documents", json={
            "query": "radioactivity Nobel Prize",
            "top_k": 5,
            "include_graph": True,
            "rerank": True,
        })
        data_docs = r.json()

    print(f"  Documents: {len(data_docs['results'])}")
    for i, doc in enumerate(data_docs["results"]):
        bd = doc["score_breakdown"]
        print(f"  [{i}] score={doc['score']:.4f}  "
              f"graph={_s(bd.get('graph_score'))}  "
              f"chunks={doc['chunk_count']}  "
              f"doc={doc['document_title'][:40]}")

    # Cleanup
    print("\n--- Cleanup ---")
    async with AsyncClient(base_url=BASE) as client:
        for did in doc_ids:
            await client.delete(f"/api/v1/documents/{did}")
    print("  Done")

    # Summary
    print("\n=== Summary ===")
    if errors:
        for e in errors:
            print(f"  FAIL: {e}")
    else:
        print("  All graph-enhanced search checks passed!")


if __name__ == "__main__":
    asyncio.run(main())
