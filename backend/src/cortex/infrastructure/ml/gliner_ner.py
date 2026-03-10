"""NER adapter using the existing GLiNER service.

The GLiNER service runs as a shared service at NER_URL (default :9002).
API contract:
  POST /v1/extract
  Request: {"texts": ["...", ...], "labels": [...], "threshold": 0.4}
  Response: {"results": [{"entities": [{"text": "...", "label": "...",
             "score": 0.99, "start": 0, "end": 9}]}]}
"""

from __future__ import annotations

import logging

import httpx

from cortex.domain.chunk import Chunk
from cortex.domain.entity import EntityExtraction

logger = logging.getLogger(__name__)

# Entity labels for a broad personal knowledge base.
# Covers: general, financial, technical, medical, legal, automotive,
# HR/employment, and meeting/communication domains.
#
# GLiNER is zero-shot — labels are text prompts, not a fixed taxonomy.
# We keep to ~18 broad labels to avoid quality degradation (GLiNER
# works best with <20 labels per call). Domain-specific subtypes are
# captured under broader categories (e.g. "medication" covers drugs,
# "regulation" covers laws/standards/codes).
ENTITY_LABELS = [
    # Universal
    "person",
    "organization",
    "location",
    "date",
    "monetary value",
    "product",
    "event",
    # Technical
    "technology",
    "software",
    # Medical / Health
    "medical condition",
    "medication",
    "medical procedure",
    # Legal / Regulatory
    "law",
    "regulation",
    "contract term",
    # Financial
    "financial instrument",
    "account number",
    # Automotive / Industrial
    "vehicle",
]


class GlinerNER:
    """NERPort implementation — HTTP client to GLiNER service."""

    def __init__(self, base_url: str) -> None:
        self._base_url = base_url.rstrip("/")

    async def extract_entities(
        self, chunks: list[Chunk], threshold: float = 0.4
    ) -> list[EntityExtraction]:
        """Extract named entities from chunks via the GLiNER service.

        Sends all chunk texts in a single batch request. Maps results
        back to chunk IDs and character offsets within each chunk.
        """
        if not chunks:
            return []

        texts = [c.chunk_text for c in chunks]

        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f"{self._base_url}/v1/extract",
                json={
                    "texts": texts,
                    "labels": ENTITY_LABELS,
                    "threshold": threshold,
                },
            )
            response.raise_for_status()
            data = response.json()

        all_extractions: list[EntityExtraction] = []

        for chunk, result in zip(chunks, data["results"]):
            for entity in result.get("entities", []):
                all_extractions.append(
                    EntityExtraction(
                        text=entity["text"],
                        label=entity["label"],
                        confidence=float(entity["score"]),
                        start_char=entity["start"],
                        end_char=entity["end"],
                        chunk_id=chunk.id,
                    )
                )

        logger.info(
            "Extracted %d entities from %d chunks",
            len(all_extractions), len(chunks),
        )
        return all_extractions
