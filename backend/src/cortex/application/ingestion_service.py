from __future__ import annotations

import logging
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
    ) -> None:
        self._parser = parser
        self._chunker = chunker
        self._embedder = embedder
        self._doc_repo = doc_repo
        self._chunk_repo = chunk_repo
        self._file_storage = file_storage
        self._ner = ner
        self._entity_repo = entity_repo

    async def ingest(self, document_id: UUID) -> None:
        """Run the full ingestion pipeline for a document.

        Idempotent: deletes existing chunks before re-processing.
        Sets transitional status on entry, completed status on exit.
        """
        doc = await self._doc_repo.get(document_id)
        if doc is None:
            raise ValueError(f"Document {document_id} not found")

        try:
            # 1. Parse
            await self._doc_repo.update_status(document_id, ProcessingStatus.PARSING.value)
            logger.info("Parsing document %s (%s)", document_id, doc.file_type.value)

            file_path = await self._file_storage.get_original_path(document_id)
            if file_path is None:
                raise FileNotFoundError(f"Original file not found for {document_id}")

            parse_result = await self._parser.parse(file_path, doc.file_type.value)

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

            chunk_results = self._chunker.chunk_document(
                parse_result.text,
                parse_result.structured,
            )

            await self._doc_repo.update_status(document_id, ProcessingStatus.CHUNKED.value)
            logger.info("Chunked into %d pieces", len(chunk_results))

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

            texts = [c.chunk_text for c in chunks]
            if texts:
                vectors = await self._embedder.embed_texts(texts)
                for chunk, vec in zip(chunks, vectors):
                    chunk.embedding = vec

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

                extractions = await self._ner.extract_entities(chunks, threshold=0.4)
                chunk_ids = [c.id for c in chunks]
                await self._entity_repo.upsert_entities(document_id, extractions, chunk_ids)

                await self._doc_repo.update_status(
                    document_id, ProcessingStatus.ENTITIES_EXTRACTED.value
                )
                logger.info("Extracted %d entities", len(extractions))

            # 6. Done (graph step added in Step 3.2)
            await self._doc_repo.update_status(document_id, ProcessingStatus.READY.value)
            logger.info("Ingestion complete for document %s", document_id)

        except Exception:
            logger.exception("Ingestion failed for document %s", document_id)
            await self._doc_repo.update_status(
                document_id,
                ProcessingStatus.FAILED.value,
                error_message=f"Ingestion failed: see worker logs",
            )
            raise
