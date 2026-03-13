from __future__ import annotations

import asyncio
import logging

from cortex.tasks.celery_app import app

logger = logging.getLogger(__name__)


async def _run_ingestion(document_id: str) -> dict:
    """Create all async resources fresh for this invocation.

    Each Celery task runs in its own event loop. Async resources
    (SQLAlchemy engine, httpx client) are loop-bound and cannot
    be reused across loops. So we create a full CompositionRoot
    per task and tear it down afterward.
    """
    from uuid import UUID

    from cortex.bootstrap import CompositionRoot
    from cortex.settings import Settings

    root = CompositionRoot(Settings())
    doc_id = UUID(document_id)

    try:
        await root.ingestion_service.ingest(doc_id)
        return {"document_id": document_id, "status": "ready"}
    finally:
        await root.aclose()


@app.task(bind=True, name="cortex.tasks.ingest_document", max_retries=2)
def ingest_document(self, document_id: str) -> dict:
    """Celery task: run the full ingestion pipeline for a document."""
    logger.info("Starting ingestion task for document %s", document_id)

    try:
        result = asyncio.run(_run_ingestion(document_id))
        logger.info("Ingestion task completed for document %s", document_id)
        return result
    except Exception as exc:
        logger.exception("Ingestion task failed for document %s", document_id)
        raise self.retry(exc=exc, countdown=30)
