"""Knowledge graph inspection — runs inside the API container.

Verifies Step 3.2: upload two documents with shared entities, verify
graph nodes, MENTIONS edges, and CO_OCCURS edges are created.
"""

import asyncio
import os
import tempfile
import random
import string

from httpx import AsyncClient

BASE = "http://localhost:8080"

# Add random suffix to avoid duplicate detection from prior failed runs
_SALT = ''.join(random.choices(string.ascii_lowercase, k=8))

DOC_A = (
    f"[{_SALT}] Elon Musk founded SpaceX in 2002. SpaceX developed the Falcon 9 rocket "
    "and the Starship vehicle. The company is headquartered in Hawthorne, California."
)

DOC_B = (
    f"[{_SALT}] Elon Musk is also the CEO of Tesla. Tesla produces electric vehicles "
    "at its Fremont factory. Musk acquired Twitter in 2022 and renamed it to X."
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

    print("=== Upload 2 documents with shared entities ===")
    async with AsyncClient(base_url=BASE, timeout=60) as client:
        id_a, status_a = await upload_and_wait(client, "spacex_doc.txt", DOC_A)
        print(f"  Doc A: {id_a} ({status_a})")
        id_b, status_b = await upload_and_wait(client, "tesla_doc.txt", DOC_B)
        print(f"  Doc B: {id_b} ({status_b})")

    if status_a != "ready" or status_b != "ready":
        print(f"ERROR: docs not ready: A={status_a}, B={status_b}")
        # Check worker logs
        return

    from cortex.bootstrap import CompositionRoot
    from cortex.settings import Settings
    from uuid import UUID

    root = CompositionRoot(Settings())

    # 1. Check graph has entities for each doc
    print("\n=== Graph: Document entities for Doc A ===")
    doc_a_entities = await root.graph_repo.get_document_entities(UUID(id_a))
    print(f"  Entities: {len(doc_a_entities)}")
    for e in doc_a_entities:
        print(f"    {e.entity_type:20s} | {e.name}")
    if not doc_a_entities:
        errors.append("No entities in graph for Doc A")

    print("\n=== Graph: Document entities for Doc B ===")
    doc_b_entities = await root.graph_repo.get_document_entities(UUID(id_b))
    print(f"  Entities: {len(doc_b_entities)}")
    for e in doc_b_entities:
        print(f"    {e.entity_type:20s} | {e.name}")
    if not doc_b_entities:
        errors.append("No entities in graph for Doc B")

    # 2. CO_OCCURS: entities related to "elon musk"
    print("\n=== Graph: CO_OCCURS from 'elon musk' ===")
    related = await root.graph_repo.get_related_by_name("elon musk", hops=2)
    print(f"  Related: {len(related)}")
    for r in related:
        print(f"    {r['type']:20s} | {r['name']}")
    if not related:
        errors.append("No CO_OCCURS for elon musk")

    # 3. Documents mentioning "elon musk"
    print("\n=== Graph: Documents mentioning 'elon musk' ===")
    docs = await root.graph_repo.get_entity_documents_by_name("elon musk")
    print(f"  Documents: {len(docs)}")
    for d in docs:
        print(f"    {d['document_id']} | {d['title']}")
    if len(docs) < 2:
        errors.append(f"Expected >=2 docs for elon musk, got {len(docs)}")

    # Cleanup
    print("\n=== Cleanup ===")
    async with AsyncClient(base_url=BASE) as client:
        await client.delete(f"/api/v1/documents/{id_a}")
        await client.delete(f"/api/v1/documents/{id_b}")
    await root.graph_repo.delete_document(UUID(id_a))
    await root.graph_repo.delete_document(UUID(id_b))
    print("  Done")

    print("\n=== Summary ===")
    if errors:
        for e in errors:
            print(f"  FAIL: {e}")
    else:
        print("  All graph checks passed!")


if __name__ == "__main__":
    asyncio.run(main())
