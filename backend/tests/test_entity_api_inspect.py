"""Entity API inspection — runs inside the API container.

Verifies Step 3.4: Entity endpoints return real entity data from the
knowledge graph and relational store.

Usage (from GPU server):
  cd infrastructure
  docker compose exec -T api python - < ../backend/tests/test_entity_api_inspect.py
"""

import asyncio
import os
import tempfile
import random
import string

from httpx import AsyncClient

BASE = "http://localhost:8080"

_SALT = ''.join(random.choices(string.ascii_lowercase, k=8))

DOC_CONTENT = (
    f"[{_SALT}] Dr. Marie Curie conducted pioneering research on radioactivity "
    "at the University of Paris. She discovered polonium and radium. "
    "Pierre Curie was a French physicist who collaborated with Marie Curie. "
    "Albert Einstein developed the theory of relativity at Princeton University."
)


async def upload_and_wait(client, filename, content):
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", dir="/tmp", delete=False) as f:
        f.write(content)
        tmp = f.name
    with open(tmp, "rb") as f:
        r = await client.post("/api/v1/documents", files={"file": (filename, f, "text/plain")})
    os.unlink(tmp)
    doc_id = r.json()["id"]
    print(f"  Uploaded {filename} → {doc_id}")

    for _ in range(60):
        await asyncio.sleep(2)
        r = await client.get(f"/api/v1/documents/{doc_id}")
        status = r.json()["status"]
        if status == "ready":
            print(f"  {filename} ready")
            return doc_id
        if status == "failed":
            raise RuntimeError(f"Ingestion failed for {filename}: {r.json()}")
    raise TimeoutError(f"{filename} did not reach ready within 120s")


async def main():
    async with AsyncClient(base_url=BASE, timeout=120) as client:
        # 1. Upload a document
        print("1. Uploading document...")
        doc_id = await upload_and_wait(client, f"entity_test_{_SALT}.txt", DOC_CONTENT)

        # 2. GET /entities — list all entities
        print("\n2. GET /entities (list all)...")
        r = await client.get("/api/v1/entities")
        assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
        data = r.json()
        assert "entities" in data
        assert "total" in data
        entities = data["entities"]
        print(f"  Found {data['total']} entities, showing {len(entities)}")
        for e in entities[:5]:
            print(f"    {e['name']} ({e['entity_type']}) — {e['mention_count']} mentions, {e['document_count']} docs")

        # 3. GET /entities?entity_type=person — filter by type
        print("\n3. GET /entities?entity_type=person...")
        r = await client.get("/api/v1/entities", params={"entity_type": "person"})
        assert r.status_code == 200
        person_entities = r.json()["entities"]
        print(f"  Found {r.json()['total']} person entities")
        for e in person_entities[:3]:
            print(f"    {e['name']}")

        # 4. GET /entities/{id} — entity detail
        if entities:
            eid = entities[0]["id"]
            print(f"\n4. GET /entities/{eid}...")
            r = await client.get(f"/api/v1/entities/{eid}")
            assert r.status_code == 200
            detail = r.json()
            print(f"  Entity: {detail['entity']['name']} ({detail['entity']['entity_type']})")
            print(f"  Documents: {len(detail['documents'])}")
            for d in detail["documents"]:
                print(f"    {d['title']}")
            print(f"  Related entities: {len(detail['related_entities'])}")
            for re in detail["related_entities"][:5]:
                print(f"    {re['name']} ({re['entity_type']})")

            # 5. GET /entities/{id}/related
            print(f"\n5. GET /entities/{eid}/related...")
            r = await client.get(f"/api/v1/entities/{eid}/related")
            assert r.status_code == 200
            related = r.json()
            print(f"  {len(related)} related entities")
            for re in related[:5]:
                print(f"    {re['name']} ({re['entity_type']})")

            # 6. GET /graph/explore
            print(f"\n6. GET /graph/explore?entity_id={eid}...")
            r = await client.get("/api/v1/graph/explore", params={"entity_id": eid})
            assert r.status_code == 200
            explore = r.json()
            print(f"  Center: {explore['center']['name']}")
            print(f"  Related: {len(explore['related_entities'])}")
            print(f"  Documents: {len(explore['documents'])}")

        # 7. GET /documents/{id}/entities — per-document entities
        print(f"\n7. GET /documents/{doc_id}/entities...")
        r = await client.get(f"/api/v1/documents/{doc_id}/entities")
        assert r.status_code == 200
        doc_entities = r.json()["entities"]
        print(f"  {len(doc_entities)} entities in document")
        for e in doc_entities[:5]:
            print(f"    {e['name']} ({e['entity_type']})")

        # 8. 404 for nonexistent entity
        print("\n8. GET /entities/{bad_id} — 404 check...")
        r = await client.get("/api/v1/entities/00000000-0000-0000-0000-000000000000")
        assert r.status_code == 404
        print("  Got 404 as expected")

        # Cleanup
        print(f"\n9. Cleanup: deleting document {doc_id}...")
        r = await client.delete(f"/api/v1/documents/{doc_id}")
        assert r.status_code == 200
        print("  Deleted")

        print("\n✓ All entity API checks passed!")


if __name__ == "__main__":
    asyncio.run(main())
