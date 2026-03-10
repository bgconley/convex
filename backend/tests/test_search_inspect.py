"""Inspection script for search inside the container.

Tests the full flow: upload documents → ingest → search → verify results.

Run inside the container:
  docker compose exec -T api python /app/tests/test_search_inspect.py
"""

import asyncio
import json
import logging

logging.basicConfig(level=logging.WARNING)


DOCUMENTS = {
    "ml_intro.md": """# Machine Learning

Machine learning is a branch of artificial intelligence that uses data and algorithms
to imitate the way humans learn, gradually improving its accuracy. It enables computers
to find hidden patterns without being explicitly programmed.

## Neural Networks

Neural networks are computing systems inspired by biological neural networks. They
consist of layers of interconnected nodes that process information using connectionist
approaches to computation.
""",
    "databases.md": """# Database Systems

A database is an organized collection of structured information stored electronically.
Relational databases use tables with rows and columns. PostgreSQL is an advanced
open-source relational database with support for vector similarity search.

## Vector Databases

Vector databases store high-dimensional vectors and enable similarity search. pgvector
is a PostgreSQL extension that adds vector operations and indexing.
""",
    "cooking.md": """# Italian Cooking

Italian cuisine is characterized by its simplicity, with many dishes having only a few
ingredients. Pasta, olive oil, tomatoes, and fresh herbs are staples. Traditional recipes
are often passed down through generations of Italian families.

## Pasta Types

There are hundreds of pasta shapes, each suited to different sauces. Long pasta like
spaghetti pairs well with light sauces, while short pasta like penne holds heavier sauces.
""",
}


async def main():
    from pathlib import Path
    from cortex.bootstrap import CompositionRoot
    from cortex.settings import Settings

    root = CompositionRoot(Settings())
    doc_ids = []

    # Upload and ingest all documents
    for filename, content in DOCUMENTS.items():
        test_file = Path(f"/tmp/{filename}")
        test_file.write_text(content)
        file_data = test_file.read_bytes()
        doc, is_dup = await root.document_service.upload(filename, file_data)
        if is_dup:
            await root.document_service.delete(doc.id)
            doc, _ = await root.document_service.upload(filename, file_data)
        doc_ids.append(doc.id)
        await root.ingestion_service.ingest(doc.id)
        print(f"Ingested: {filename} -> {doc.id}")

    # Search tests
    queries = [
        "neural networks and deep learning",
        "PostgreSQL vector similarity search",
        "Italian pasta recipes",
        "how do computers learn from data",
    ]

    for query in queries:
        result = await root.search_service.search(query, top_k=3)
        print(f"\nQuery: {repr(query)}")
        print(f"  time: {result.search_time_ms:.1f}ms, candidates: {result.total_candidates}")
        for r in result.results:
            print(f"  score={r.score:.4f} doc={repr(r.document_title)} sec={repr(r.section_heading)}")
            print(f"    anchor={r.anchor_id} chars={r.chunk_start_char}-{r.chunk_end_char}")
            print(f"    snippet: {r.highlighted_snippet[:80]}...")

    # Cleanup
    for doc_id in doc_ids:
        await root.document_service.delete(doc_id)
    await root.embedder.close()
    print("\nCleaned up. Done.")


if __name__ == "__main__":
    asyncio.run(main())
