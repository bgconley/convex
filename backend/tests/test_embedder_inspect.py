"""Inspection script for TEI embedder inside the container.

Run inside the container:
  docker compose exec -T api python /app/tests/test_embedder_inspect.py
"""

import asyncio
import os

from cortex.infrastructure.ml.tei_embedder import TEIEmbedder


async def main():
    embedder_url = os.environ.get("EMBEDDER_URL", "http://host.docker.internal:8080")
    model = os.environ.get("EMBEDDING_MODEL", "qwen3-embedder")
    embedder = TEIEmbedder(base_url=embedder_url, model=model)

    # Test 1: batch embed
    texts = [
        "Machine learning is a subset of artificial intelligence.",
        "Deep learning uses neural networks with many layers.",
        "PostgreSQL is a relational database management system.",
        "The quick brown fox jumps over the lazy dog.",
        "Semantic search finds results by meaning, not keywords.",
    ]
    print(f"Embedding {len(texts)} texts...")
    vectors = await embedder.embed_texts(texts)
    print(f"  count={len(vectors)}")
    print(f"  dim={len(vectors[0])}")
    print(f"  first_3_values={vectors[0][:3]}")

    # Test 2: query embedding (with instruction prefix)
    print("\nEmbedding query...")
    query_vec = await embedder.embed_query("what is machine learning")
    print(f"  dim={len(query_vec)}")
    print(f"  first_3_values={query_vec[:3]}")

    # Test 3: cosine similarity (ML text should be closest to ML query)
    import math

    def cosine_sim(a, b):
        dot = sum(x * y for x, y in zip(a, b))
        norm_a = math.sqrt(sum(x * x for x in a))
        norm_b = math.sqrt(sum(x * x for x in b))
        return dot / (norm_a * norm_b) if norm_a and norm_b else 0.0

    print("\nCosine similarities to query 'what is machine learning':")
    for i, text in enumerate(texts):
        sim = cosine_sim(query_vec, vectors[i])
        print(f"  [{i}] {sim:.4f}  {text[:60]}")

    # Test 4: pgvector storage round-trip
    db_url = os.environ.get(
        "DATABASE_URL",
        "postgresql+asyncpg://cortex:cortex_dev_2024@postgres:5432/cortex",
    )
    print(f"\nTesting pgvector storage...")
    from sqlalchemy import text as sql_text
    from sqlalchemy.ext.asyncio import create_async_engine

    engine = create_async_engine(db_url)
    async with engine.connect() as conn:
        # Store a test vector and query it
        await conn.execute(sql_text(
            "CREATE TEMP TABLE test_vectors (id serial, embedding vector(1024))"
        ))
        for i, vec in enumerate(vectors):
            vec_str = "[" + ",".join(str(v) for v in vec) + "]"
            await conn.execute(sql_text(
                f"INSERT INTO test_vectors (embedding) VALUES ('{vec_str}'::vector)"
            ))

        # Find nearest neighbor to query
        qvec_str = "[" + ",".join(str(v) for v in query_vec) + "]"
        result = await conn.execute(sql_text(
            f"SELECT id, 1 - (embedding <=> '{qvec_str}'::vector) as similarity "
            f"FROM test_vectors ORDER BY embedding <=> '{qvec_str}'::vector LIMIT 3"
        ))
        rows = result.fetchall()
        print("  Top 3 nearest neighbors:")
        for row in rows:
            print(f"    id={row[0]} similarity={row[1]:.4f} text={texts[row[0]-1][:60]}")

    await engine.dispose()
    await embedder.close()
    print("\nAll checks passed.")


if __name__ == "__main__":
    asyncio.run(main())
