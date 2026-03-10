"""Inspection script for the full ingestion pipeline inside the container.

Run inside the container (not via Celery — directly exercises the service):
  docker compose exec -T api python /app/tests/test_ingestion_inspect.py

Or for worker:
  docker compose exec -T worker python /app/tests/test_ingestion_inspect.py
"""

import asyncio
import logging
import os

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")


async def main():
    from pathlib import Path
    from cortex.bootstrap import CompositionRoot
    from cortex.settings import Settings

    settings = Settings()
    root = CompositionRoot(settings)

    # Create a test markdown document
    test_md = Path("/tmp/test_ingest.md")
    test_md.write_text("""# Machine Learning Overview

Machine learning is a branch of artificial intelligence focused on building applications that learn from data and improve their accuracy over time without being programmed to do so.

## Supervised Learning

Supervised learning uses labeled datasets to train algorithms that to classify data or predict outcomes accurately. As input data is fed into the model, the model adjusts its weights until it has been fitted appropriately.

## Unsupervised Learning

Unsupervised learning uses machine learning algorithms to analyze and cluster unlabeled datasets. These algorithms discover hidden patterns or data groupings without the need for human intervention.

# Applications

Machine learning has numerous applications including natural language processing, computer vision, recommendation systems, fraud detection, and autonomous vehicles.
""")

    # Upload via document service
    file_data = test_md.read_bytes()
    doc, is_dup = await root.document_service.upload("test_ingest.md", file_data)
    if is_dup:
        print(f"Document already exists: {doc.id} — deleting and re-uploading")
        await root.document_service.delete(doc.id)
        doc, is_dup = await root.document_service.upload("test_ingest.md", file_data)

    print(f"Uploaded: id={doc.id} status={doc.status.value}")

    # Run ingestion directly (not via Celery)
    print("\nRunning ingestion pipeline...")
    await root.ingestion_service.ingest(doc.id)

    # Verify results
    doc = await root.document_service.get(doc.id)
    print(f"\nPost-ingestion status: {doc.status.value}")
    print(f"Page count: {doc.metadata.page_count}")
    print(f"Word count: {doc.metadata.word_count}")
    print(f"Has rendered_html: {doc.rendered_html is not None and len(doc.rendered_html) > 0}")
    print(f"Has rendered_markdown: {doc.rendered_markdown is not None and len(doc.rendered_markdown) > 0}")
    print(f"Has parsed_content: {doc.parsed_content is not None}")

    # Check chunks
    chunks = await root.chunk_repo.get_by_document(doc.id)
    print(f"\nChunks: {len(chunks)}")
    for c in chunks:
        has_emb = c.embedding is not None and len(c.embedding) > 0
        sec = c.section_heading or "(none)"
        print(f"  [{c.chunk_index}] tokens={c.token_count} emb={has_emb} sec={repr(sec)} text={repr(c.chunk_text[:50])}...")

    # Test vector search
    print("\nVector search for 'supervised learning algorithms':")
    query_vec = await root.embedder.embed_query("supervised learning algorithms")
    results = await root.chunk_repo.vector_search(query_vec, top_k=3)
    for r in results:
        print(f"  score={r.score:.4f} sec={repr(r.section_heading)} text={repr(r.chunk_text[:60])}...")

    # Cleanup
    await root.document_service.delete(doc.id)
    print(f"\nCleaned up document {doc.id}")
    await root.embedder.close()
    print("Done.")


if __name__ == "__main__":
    asyncio.run(main())
