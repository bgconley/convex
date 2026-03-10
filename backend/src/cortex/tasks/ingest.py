from __future__ import annotations

import asyncio
import logging

from cortex.tasks.celery_app import app

logger = logging.getLogger(__name__)

# Lazy-initialized composition root (per worker process)
_root = None


def _get_root():
    global _root
    if _root is None:
        from cortex.bootstrap import CompositionRoot
        from cortex.settings import Settings

        _root = CompositionRoot(Settings())
    return _root


@app.task(bind=True, name="cortex.tasks.ingest_document", max_retries=2)
def ingest_document(self, document_id: str) -> dict:
    """Celery task: run the full ingestion pipeline for a document.

    This is a sync wrapper around the async IngestionService.ingest().
    The composition root is lazy-initialized once per worker process.
    """
    from uuid import UUID

    root = _get_root()
    doc_id = UUID(document_id)

    logger.info("Starting ingestion task for document %s", document_id)

    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(root.ingestion_service.ingest(doc_id))
        finally:
            loop.close()

        logger.info("Ingestion task completed for document %s", document_id)
        return {"document_id": document_id, "status": "ready"}

    except Exception as exc:
        logger.exception("Ingestion task failed for document %s", document_id)
        raise self.retry(exc=exc, countdown=30)
