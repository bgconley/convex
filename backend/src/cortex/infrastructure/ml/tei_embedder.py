from __future__ import annotations

import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)

# Maximum texts per batch request to avoid timeouts on large documents
_DEFAULT_BATCH_SIZE = 64


class TEIEmbedder:
    """EmbedderPort implementation using the existing TEI gateway.

    The GPU server runs a TEI gateway at the configured URL that serves
    an OpenAI-compatible /v1/embeddings endpoint backed by Qwen3-Embedding-0.6B.
    """

    def __init__(
        self,
        base_url: str = "http://localhost:8080",
        model: str = "qwen3-embedder",
        batch_size: int = _DEFAULT_BATCH_SIZE,
        timeout: float = 120.0,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._batch_size = batch_size
        self._client = httpx.AsyncClient(timeout=timeout)

    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """Batch embed texts via the TEI gateway's OpenAI-compatible API.

        Splits into sub-batches of self._batch_size to avoid timeouts.
        Returns vectors in the same order as the input texts.
        """
        if not texts:
            return []

        all_embeddings: list[list[float]] = []

        for i in range(0, len(texts), self._batch_size):
            batch = texts[i : i + self._batch_size]
            embeddings = await self._request_embeddings(batch)
            all_embeddings.extend(embeddings)

        return all_embeddings

    async def embed_query(self, query: str) -> list[float]:
        """Embed a single query with instruction prefix.

        Qwen3-Embedding supports instruction-aware encoding which
        improves retrieval quality by 1-5% on benchmarks.
        """
        prefixed = f"Instruct: Retrieve relevant passages\nQuery: {query}"
        embeddings = await self.embed_texts([prefixed])
        return embeddings[0]

    async def _request_embeddings(
        self, texts: list[str]
    ) -> list[list[float]]:
        """Make a single request to the /v1/embeddings endpoint."""
        payload: dict[str, Any] = {
            "input": texts,
            "model": self._model,
        }

        response = await self._client.post(
            f"{self._base_url}/v1/embeddings",
            json=payload,
        )
        response.raise_for_status()
        data = response.json()

        # OpenAI format: {"data": [{"embedding": [...], "index": 0}, ...]}
        # Sort by index to guarantee order matches input
        items = sorted(data["data"], key=lambda x: x["index"])
        return [item["embedding"] for item in items]

    async def close(self) -> None:
        await self._client.aclose()
