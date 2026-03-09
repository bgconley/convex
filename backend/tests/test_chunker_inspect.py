"""One-shot script to inspect Docling structured dict and test chunker.

Run inside the container:
  docker compose exec -T api python /app/tests/test_chunker_inspect.py
"""

import asyncio
import json
from pathlib import Path

SAMPLE = """# Introduction

Machine learning is a subset of artificial intelligence that focuses on building systems that learn from data. These systems improve their performance over time without being explicitly programmed. The field has grown rapidly over the past decade.

Deep learning, a subset of machine learning, uses neural networks with many layers. These deep neural networks have achieved remarkable results in image recognition, natural language processing, and game playing.

# Methods

## Supervised Learning

In supervised learning, the model is trained on labeled data. The training data consists of input-output pairs, and the model learns to map inputs to outputs. Common algorithms include linear regression, decision trees, and support vector machines.

## Unsupervised Learning

Unsupervised learning involves training on data without labels. The model must discover structure and patterns in the data on its own. Clustering and dimensionality reduction are common unsupervised techniques. K-means clustering and principal component analysis are widely used methods.

# Results

The experiments showed that deep learning models outperformed traditional machine learning methods on all benchmarks. The transformer architecture achieved the highest accuracy across all tasks, with an average improvement of 15 percent over the baseline methods.
"""


async def main():
    test_md = Path("/tmp/test_chunk.md")
    test_md.write_text(SAMPLE)

    from cortex.infrastructure.ml.docling_parser import DoclingParser
    from cortex.infrastructure.ml.chonkie_chunker import ChonkieChunker

    parser = DoclingParser()
    pr = await parser.parse(test_md, "markdown")

    # Inspect structured dict
    d = pr.structured
    print("=== STRUCTURED DICT TOP KEYS ===")
    print(list(d.keys()))

    for key in ["texts", "body", "main-text", "main_text"]:
        items = d.get(key, [])
        if items and isinstance(items, list):
            print(f"\n=== {key}: {len(items)} items ===")
            for i, item in enumerate(items[:10]):
                if isinstance(item, dict):
                    label = item.get("label", item.get("type", "?"))
                    text = item.get("text", "")[:80]
                    print(f"  [{i}] label={label} text={repr(text)}")

    # Also dump a small sample of the full dict
    print("\n=== FIRST 2000 CHARS OF JSON ===")
    print(json.dumps(d, indent=2, default=str)[:2000])

    # Now test the chunker at chunk_size=512 (production config)
    print("\n=== CHUNKER (chunk_size=512) ===")
    chunker = ChonkieChunker(chunk_size=512)
    chunks = chunker.chunk_document(pr.text, pr.structured)
    print(f"chunks: {len(chunks)}")
    for c in chunks:
        sec = c.section_heading or "(none)"
        preview = c.text[:70].replace("\n", " ").strip()
        print(f"  [{c.index}] tokens={c.token_count} sec={repr(sec)} start={c.start_char} end={c.end_char}")
        print(f"         {repr(preview)}...")


if __name__ == "__main__":
    asyncio.run(main())
