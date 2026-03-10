"""Reranker adapter using the existing mxbai-rerank-large-v2 service.

The reranker runs as a shared service at RERANKER_URL (default :9006).
API contract:
  POST /v1/rerank
  Request: {"query": "...", "documents": ["...", ...], "top_k": N}
  Response: {"results": [{"index": 0, "score": 5.125}, ...]}
"""

from __future__ import annotations

import httpx

from cortex.domain.entity import RerankResult


class MxbaiReranker:
    """RerankerPort implementation — HTTP client to mxbai-rerank-large-v2 service."""

    def __init__(self, base_url: str) -> None:
        self._base_url = base_url.rstrip("/")

    async def rerank(
        self, query: str, documents: list[str], top_k: int
    ) -> list[RerankResult]:
        """Score (query, document) pairs and return top_k ordered by relevance."""
        if not documents:
            return []

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{self._base_url}/v1/rerank",
                json={
                    "query": query,
                    "documents": documents,
                    "top_k": top_k,
                },
            )
            response.raise_for_status()
            data = response.json()

        results = []
        for item in data["results"][:top_k]:
            idx = item["index"]
            results.append(
                RerankResult(
                    index=idx,
                    score=float(item["score"]),
                    text=documents[idx] if idx < len(documents) else "",
                )
            )
        return results
