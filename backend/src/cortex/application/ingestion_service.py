from __future__ import annotations

import logging
import time
from pathlib import Path
from uuid import UUID

from cortex.domain.chunk import Chunk
from cortex.domain.document import ProcessingStatus
from cortex.domain.ports import (
    ChunkRepository,
    ChunkerPort,
    DocumentRepository,
    EmbedderPort,
    EntityRepository,
    FileStoragePort,
    GraphPort,
    MetricsPort,
    NERPort,
    ParserPort,
)

logger = logging.getLogger(__name__)


class IngestionService:
    """Orchestrates the full document ingestion pipeline.

    Pipeline: parse → chunk → embed → store
    NER and graph steps are added in Phase 3.

    Depends on domain ports only — no infrastructure imports.
    """

    def __init__(
        self,
        parser: ParserPort,
        chunker: ChunkerPort,
        embedder: EmbedderPort,
        doc_repo: DocumentRepository,
        chunk_repo: ChunkRepository,
        file_storage: FileStoragePort,
        ner: NERPort | None = None,
        entity_repo: EntityRepository | None = None,
        graph_repo: GraphPort | None = None,
        metrics: MetricsPort | None = None,
    ) -> None:
        self._parser = parser
        self._chunker = chunker
        self._embedder = embedder
        self._doc_repo = doc_repo
        self._chunk_repo = chunk_repo
        self._file_storage = file_storage
        self._ner = ner
        self._entity_repo = entity_repo
        self._graph_repo = graph_repo
        self._metrics = metrics

    async def ingest(self, document_id: UUID) -> None:
        """Run the full ingestion pipeline for a document.

        Idempotent: deletes existing chunks before re-processing.
        Sets transitional status on entry, completed status on exit.
        """
        doc = await self._doc_repo.get(document_id)
        if doc is None:
            raise ValueError(f"Document {document_id} not found")

        extractions: list = []  # populated by NER step, used by graph step
        stage_timings: dict[str, float] = {}
        chunk_count = 0
        entity_count = 0
        pipeline_start = time.monotonic()

        try:
            # 1. Parse
            await self._doc_repo.update_status(document_id, ProcessingStatus.PARSING.value)
            logger.info(
                "Parsing document %s (%s)", document_id, doc.file_type.value,
                extra={"document_id": str(document_id)},
            )

            t0 = time.monotonic()
            file_path = await self._file_storage.get_original_path(document_id)
            if file_path is None:
                raise FileNotFoundError(f"Original file not found for {document_id}")

            parse_result = await self._parser.parse(file_path, doc.file_type.value)
            stage_timings["parse"] = (time.monotonic() - t0) * 1000

            await self._doc_repo.update_status(document_id, ProcessingStatus.PARSED.value)
            logger.info("Parsed: %d chars, %d words", len(parse_result.text), parse_result.metadata.word_count or 0)

            # Store parsed content on the document record
            doc.parsed_content = parse_result.structured
            doc.rendered_markdown = parse_result.rendered_markdown
            doc.rendered_html = parse_result.rendered_html
            doc.metadata = parse_result.metadata
            if parse_result.page_count is not None:
                doc.metadata.page_count = parse_result.page_count
            await self._doc_repo.update(doc)

            # Save thumbnail if generated
            if hasattr(parse_result, '_thumbnail_data') and parse_result._thumbnail_data:
                await self._file_storage.save_thumbnail(parse_result._thumbnail_data, document_id)

            # 2. Chunk
            await self._doc_repo.update_status(document_id, ProcessingStatus.CHUNKING.value)
            logger.info("Chunking document %s", document_id)

            t0 = time.monotonic()
            chunk_results = self._chunker.chunk_document(
                parse_result.text,
                parse_result.structured,
            )
            stage_timings["chunk"] = (time.monotonic() - t0) * 1000

            await self._doc_repo.update_status(document_id, ProcessingStatus.CHUNKED.value)
            chunk_count = len(chunk_results)
            logger.info("Chunked into %d pieces", chunk_count)

            # Delete existing chunks (idempotent)
            await self._chunk_repo.delete_by_document(document_id)

            # Create Chunk domain objects
            chunks = [
                Chunk.new(
                    document_id=document_id,
                    chunk_text=cr.text,
                    chunk_index=cr.index,
                    start_char=cr.start_char,
                    end_char=cr.end_char,
                    token_count=cr.token_count,
                    section_heading=cr.section_heading,
                    section_level=cr.section_level,
                )
                for cr in chunk_results
            ]

            # 3. Embed
            await self._doc_repo.update_status(document_id, ProcessingStatus.EMBEDDING.value)
            logger.info("Embedding %d chunks", len(chunks))

            t0 = time.monotonic()
            texts = [c.chunk_text for c in chunks]
            if texts:
                vectors = await self._embedder.embed_texts(texts)
                for chunk, vec in zip(chunks, vectors):
                    chunk.embedding = vec
            stage_timings["embed"] = (time.monotonic() - t0) * 1000

            await self._doc_repo.update_status(document_id, ProcessingStatus.EMBEDDED.value)
            logger.info("Embedded %d chunks", len(chunks))

            # 4. Store chunks with embeddings
            await self._chunk_repo.save_chunks(chunks)

            # 5. NER — extract named entities from chunks
            if self._ner and self._entity_repo:
                await self._doc_repo.update_status(
                    document_id, ProcessingStatus.EXTRACTING_ENTITIES.value
                )
                logger.info("Extracting entities from %d chunks", len(chunks))

                t0 = time.monotonic()
                extractions = await self._ner.extract_entities(chunks, threshold=0.4)
                chunk_ids = [c.id for c in chunks]
                await self._entity_repo.upsert_entities(document_id, extractions, chunk_ids)
                stage_timings["ner"] = (time.monotonic() - t0) * 1000

                await self._doc_repo.update_status(
                    document_id, ProcessingStatus.ENTITIES_EXTRACTED.value
                )
                entity_count = len(extractions)
                logger.info("Extracted %d entities", entity_count)

            # 6. Knowledge graph — add document + entities to AGE graph
            if self._graph_repo and extractions:
                await self._doc_repo.update_status(
                    document_id, ProcessingStatus.BUILDING_GRAPH.value
                )
                logger.info("Building knowledge graph for document %s", document_id)

                t0 = time.monotonic()
                await self._graph_repo.add_document_entities(
                    document_id=document_id,
                    document_title=doc.title,
                    entities=extractions,
                    chunk_ids=[c.id for c in chunks],
                )
                stage_timings["graph"] = (time.monotonic() - t0) * 1000

                logger.info("Knowledge graph updated for document %s", document_id)

            # 7. Done
            await self._doc_repo.update_status(document_id, ProcessingStatus.READY.value)
            total_ms = (time.monotonic() - pipeline_start) * 1000
            logger.info(
                "Ingestion complete for document %s (%.0fms)",
                document_id, total_ms,
                extra={"document_id": str(document_id), "duration_ms": round(total_ms, 1)},
            )

            if self._metrics:
                self._metrics.record_ingestion(
                    document_id=document_id,
                    success=True,
                    total_ms=total_ms,
                    stage_timings=stage_timings,
                    chunk_count=chunk_count,
                    entity_count=entity_count,
                )

        except Exception:
            total_ms = (time.monotonic() - pipeline_start) * 1000
            logger.exception("Ingestion failed for document %s", document_id)
            await self._doc_repo.update_status(
                document_id,
                ProcessingStatus.FAILED.value,
                error_message=f"Ingestion failed: see worker logs",
            )
            if self._metrics:
                self._metrics.record_ingestion(
                    document_id=document_id,
                    success=False,
                    total_ms=total_ms,
                    stage_timings=stage_timings,
                    chunk_count=chunk_count,
                    entity_count=entity_count,
                )
            raise
