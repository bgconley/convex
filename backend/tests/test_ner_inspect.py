"""NER extraction inspection — runs inside the API container.

Verifies Step 3.1: upload a document with named entities, wait for
processing through NER step, verify entities are extracted and stored.
"""

import asyncio
import os
import tempfile

from httpx import AsyncClient

BASE = "http://localhost:8080"

TEST_CONTENT = (
    "Elon Musk founded SpaceX in 2002 and serves as CEO of Tesla. "
    "SpaceX is headquartered in Hawthorne, California, and has launched "
    "the Falcon 9 rocket and Starship. Tesla produces electric vehicles "
    "at its Fremont factory and Austin Gigafactory. OpenAI, which Musk "
    "co-founded, develops large language models using Python and PyTorch."
)


async def main():
    errors = []

    print("=== Health Check ===")
    async with AsyncClient(base_url=BASE) as client:
        r = await client.get("/api/v1/health")
        health = r.json()
        print(f"Health: {health['status']}")
        print(f"  ner: {health['checks'].get('ner', 'not checked')}")

    print("\n=== Upload Test Document ===")
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", dir="/tmp", delete=False) as f:
        f.write(TEST_CONTENT)
        tmp_path = f.name

    async with AsyncClient(base_url=BASE) as client:
        with open(tmp_path, "rb") as f:
            r = await client.post("/api/v1/documents", files={"file": ("ner_test.txt", f, "text/plain")})
        doc_id = r.json()["id"]
        print(f"Upload: {r.status_code}, id={doc_id}")
    os.unlink(tmp_path)

    print("\n=== Waiting for processing (including NER) ===")
    status = "unknown"
    saw_extracting = False
    for i in range(45):
        await asyncio.sleep(2)
        async with AsyncClient(base_url=BASE) as client:
            r = await client.get(f"/api/v1/documents/{doc_id}")
            status = r.json()["status"]
            if status == "extracting_entities":
                saw_extracting = True
            print(f"  [{i*2}s] status={status}")
            if status in ("ready", "failed"):
                break

    if status != "ready":
        print(f"ERROR: not ready: {status}")
        errors.append(f"Document did not reach ready: {status}")
    else:
        print(f"  Saw extracting_entities phase: {saw_extracting}")

    # Check entities in DB via the ingestion service
    print("\n=== Verify Entities ===")
    from cortex.bootstrap import CompositionRoot
    from cortex.settings import Settings
    from uuid import UUID

    root = CompositionRoot(Settings())
    doc_uuid = UUID(doc_id)

    entities = await root.entity_repo.get_by_document(doc_uuid)
    print(f"  Entities found: {len(entities)}")

    if not entities:
        errors.append("No entities found for document")
    else:
        for e in entities:
            print(f"    {e.entity_type:20s} | {e.name:30s} | mentions={e.mention_count}")

        # Check for expected entities
        names = {e.normalized_name for e in entities}
        expected = {"elon musk", "spacex", "tesla"}
        found = expected & names
        missing = expected - names
        print(f"\n  Expected entities found: {found}")
        if missing:
            print(f"  Missing expected: {missing}")
            errors.append(f"Missing expected entities: {missing}")

        # Check entity types
        types = {e.entity_type for e in entities}
        print(f"  Entity types present: {types}")

    # Cleanup
    print("\n=== Cleanup ===")
    async with AsyncClient(base_url=BASE) as client:
        r = await client.delete(f"/api/v1/documents/{doc_id}")
        print(f"Delete: {r.status_code}")

    print("\n=== NER Verification Summary ===")
    if errors:
        for e in errors:
            print(f"  FAIL: {e}")
    else:
        print("  All NER checks passed!")


if __name__ == "__main__":
    asyncio.run(main())
