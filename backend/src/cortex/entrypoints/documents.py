from __future__ import annotations

import json
from pathlib import Path
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, Request, UploadFile
from fastapi.responses import FileResponse
from lxml import html as lxml_html

from cortex.schemas.document_schemas import (
    DocumentContentResponse,
    DocumentListResponse,
    DocumentMetadataResponse,
    DocumentUpdateRequest,
    DocumentUploadResponse,
)

router = APIRouter()


def _doc_to_response(doc) -> DocumentMetadataResponse:
    preview = None
    if doc.rendered_markdown:
        preview = doc.rendered_markdown[:300].strip()
    return DocumentMetadataResponse(
        id=doc.id,
        title=doc.title,
        original_filename=doc.original_filename,
        file_type=doc.file_type.value,
        file_size_bytes=doc.file_size_bytes,
        mime_type=doc.mime_type,
        status=doc.status.value,
        page_count=doc.metadata.page_count,
        word_count=doc.metadata.word_count,
        language=doc.metadata.language,
        author=doc.metadata.author,
        tags=doc.tags,
        is_favorite=doc.is_favorite,
        collection_id=doc.collection_id,
        content_preview=preview,
        created_at=doc.created_at,
        updated_at=doc.updated_at,
        processed_at=doc.processed_at,
        error_message=doc.error_message,
    )


@router.post("", response_model=DocumentUploadResponse)
async def upload_document(file: UploadFile, request: Request):
    doc_service = request.app.state.document_service
    file_data = await file.read()
    try:
        doc, is_duplicate = await doc_service.upload(file.filename or "untitled", file_data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Enqueue ingestion task for new documents
    if not is_duplicate:
        from cortex.tasks.ingest import ingest_document

        ingest_document.delay(str(doc.id))

    return DocumentUploadResponse(
        id=doc.id,
        status=doc.status.value,
        message="Existing document returned" if is_duplicate else "Document uploaded, processing started",
        is_duplicate=is_duplicate,
    )


@router.get("", response_model=DocumentListResponse)
async def list_documents(
    request: Request,
    file_type: str | None = None,
    status: str | None = None,
    collection_id: UUID | None = None,
    tags: list[str] | None = Query(None),
    limit: int = 50,
    offset: int = 0,
):
    doc_service = request.app.state.document_service
    docs, total = await doc_service.list_documents(
        file_type=file_type,
        status=status,
        collection_id=collection_id,
        tags=tags,
        limit=limit,
        offset=offset,
    )
    return DocumentListResponse(
        documents=[_doc_to_response(d) for d in docs],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/{document_id}", response_model=DocumentMetadataResponse)
async def get_document(document_id: UUID, request: Request):
    doc_service = request.app.state.document_service
    doc = await doc_service.get(document_id)
    if doc is None:
        raise HTTPException(status_code=404, detail="Document not found")
    return _doc_to_response(doc)


@router.get("/{document_id}/content")
async def get_document_content(
    document_id: UUID,
    request: Request,
    view: str = "structured",
):
    doc_service = request.app.state.document_service
    doc = await doc_service.get(document_id)
    if doc is None:
        raise HTTPException(status_code=404, detail="Document not found")

    settings = request.app.state.settings
    original_url = f"/api/v1/documents/{document_id}/original"

    if view == "fidelity":
        return DocumentContentResponse(
            id=doc.id,
            format="original_url",
            content=original_url,
            original_url=original_url,
            metadata=_doc_to_response(doc),
        )

    # Structured view — inject chunk anchors for search-hit navigation
    chunk_repo = request.app.state.chunk_repo
    chunks = await chunk_repo.get_by_document(document_id)

    if doc.file_type.value == "xlsx" and doc.rendered_html:
        anchored_html = _inject_chunk_anchors(doc.rendered_html, chunks)
        content = json.dumps(_spreadsheet_html_to_json(anchored_html))
        fmt = "spreadsheet_json"
    elif doc.rendered_html:
        content = _inject_chunk_anchors(doc.rendered_html, chunks)
        fmt = "html"
    elif doc.file_type.value == "markdown" and doc.rendered_markdown:
        content = _inject_chunk_anchors_into_text(doc.rendered_markdown, chunks)
        fmt = "markdown"
    elif doc.file_type.value == "txt" and doc.rendered_markdown is not None:
        content = doc.rendered_markdown
        fmt = "plain_text"
    elif doc.rendered_markdown:
        content = doc.rendered_markdown
        fmt = "markdown"
    else:
        content = ""
        fmt = "not_yet_processed"

    return DocumentContentResponse(
        id=doc.id,
        format=fmt,
        content=content,
        original_url=original_url,
        metadata=_doc_to_response(doc),
    )


def _inject_chunk_anchors(html: str, chunks: list) -> str:
    """Inject <span id="chunk-N"> anchors into rendered HTML at chunk boundaries.

    This enables search-hit navigation: the frontend scrolls to #chunk-N
    when the user clicks a search result.
    """
    if not chunks:
        return html

    # Insert anchors at the beginning of each chunk's approximate position
    # We use the chunk's section heading as a landmark to find insertion points
    for chunk in sorted(chunks, key=lambda c: c.chunk_index, reverse=True):
        anchor = f'<span id="chunk-{chunk.chunk_index}"></span>'
        # Find the chunk's text start in the HTML (best effort — HTML structure
        # may differ from plain text offsets)
        first_words = chunk.chunk_text[:40].strip()
        if first_words:
            # Escape for HTML search and find first occurrence
            import html as html_module

            search_text = html_module.escape(first_words[:20])
            pos = html.find(search_text)
            if pos >= 0:
                html = html[:pos] + anchor + html[pos:]
            else:
                # Fallback: prepend anchor to the HTML
                html = anchor + html

    return html


def _inject_chunk_anchors_into_text(text: str, chunks: list) -> str:
    """Inject raw HTML anchors into markdown/plain text using chunk start offsets."""
    if not chunks:
        return text

    anchored = text
    for chunk in sorted(chunks, key=lambda c: c.start_char, reverse=True):
        anchor = f'<span id="chunk-{chunk.chunk_index}"></span>'
        insert_at = min(max(chunk.start_char, 0), len(anchored))
        anchored = anchored[:insert_at] + anchor + anchored[insert_at:]
    return anchored


def _spreadsheet_html_to_json(html: str) -> dict:
    """Convert Docling XLSX HTML into sheet/row/cell JSON for the structured viewer."""
    try:
        root = lxml_html.fromstring(html)
    except Exception:
        return {"sheets": []}

    body = root.find("body") if root.tag.lower() != "body" else root
    container = body if body is not None else root
    children = list(container.iterchildren())

    sheets: list[dict] = []
    h2_indexes = [
        idx for idx, child in enumerate(children)
        if getattr(child, "tag", "").lower() == "h2"
    ]

    if len(h2_indexes) > 1:
        for position, start in enumerate(h2_indexes):
            end = h2_indexes[position + 1] if position + 1 < len(h2_indexes) else len(children)
            name = _normalize_cell_text(children[start].text_content()) or f"Sheet {position + 1}"
            section_tables = [
                table
                for child in children[start:end]
                for table in child.xpath(".//table | self::table")
            ]
            sheets.append(_build_sheet_payload(name, section_tables))
        return {"sheets": [sheet for sheet in sheets if sheet["rows"]]}

    captioned_tables = []
    for table in container.xpath(".//table"):
        captions = table.xpath("./caption")
        if captions:
            captioned_tables.append((captions[0].text_content(), table))
    if len(captioned_tables) > 1:
        for caption, table in captioned_tables:
            sheets.append(
                _build_sheet_payload(_normalize_cell_text(caption) or "Sheet", [table])
            )
        return {"sheets": [sheet for sheet in sheets if sheet["rows"]]}

    tables = container.xpath(".//table")
    if len(tables) > 1:
        for index, table in enumerate(tables, start=1):
            sheets.append(_build_sheet_payload(f"Sheet {index}", [table]))
        return {"sheets": [sheet for sheet in sheets if sheet["rows"]]}

    if tables:
        return {"sheets": [_build_sheet_payload("Sheet 1", tables)]}

    return {"sheets": []}


def _build_sheet_payload(name: str, tables: list) -> dict:
    rows: list[dict] = []
    for table in tables:
        for row in table.xpath(".//tr"):
            cells = row.xpath("./th|./td")
            if not cells:
                continue
            row_cells = [_normalize_cell_text(cell.text_content()) for cell in cells]
            anchor_ids = [anchor_id for anchor_id in row.xpath(".//*[@id]/@id") if anchor_id]
            rows.append(
                {
                    "id": f"{name}-row-{len(rows)}",
                    "cells": row_cells,
                    "anchor_ids": anchor_ids,
                }
            )
    return {"name": name, "rows": rows}


def _normalize_cell_text(text: str) -> str:
    return " ".join(text.split())


@router.get("/{document_id}/original")
async def get_document_original(document_id: UUID, request: Request):
    doc_service = request.app.state.document_service
    file_storage = request.app.state.file_storage

    doc = await doc_service.get(document_id)
    if doc is None:
        raise HTTPException(status_code=404, detail="Document not found")

    file_path = await file_storage.get_original_path(document_id)
    if file_path is None or not file_path.exists():
        raise HTTPException(status_code=404, detail="Original file not found")

    return FileResponse(
        path=str(file_path),
        filename=doc.original_filename,
        media_type=doc.mime_type,
    )


@router.get("/{document_id}/thumbnail")
async def get_document_thumbnail(document_id: UUID, request: Request):
    doc_service = request.app.state.document_service
    settings = request.app.state.settings

    doc = await doc_service.get(document_id)
    if doc is None:
        raise HTTPException(status_code=404, detail="Document not found")

    if doc.thumbnail_path is None:
        raise HTTPException(status_code=404, detail="Thumbnail not available")

    thumb_path = Path(settings.data_dir) / doc.thumbnail_path
    if not thumb_path.exists():
        raise HTTPException(status_code=404, detail="Thumbnail file not found")

    return FileResponse(path=str(thumb_path), media_type="image/png")


@router.get("/{document_id}/chunks")
async def get_document_chunks(document_id: UUID, request: Request):
    doc_service = request.app.state.document_service
    doc = await doc_service.get(document_id)
    if doc is None:
        raise HTTPException(status_code=404, detail="Document not found")

    chunk_repo = request.app.state.chunk_repo
    chunks = await chunk_repo.get_by_document(document_id)
    return {
        "chunks": [
            {
                "id": str(c.id),
                "chunk_index": c.chunk_index,
                "chunk_text": c.chunk_text,
                "start_char": c.start_char,
                "end_char": c.end_char,
                "section_heading": c.section_heading,
                "page_number": c.page_number,
                "token_count": c.token_count,
            }
            for c in chunks
        ]
    }


@router.get("/{document_id}/entities")
async def get_document_entities(document_id: UUID, request: Request):
    doc_service = request.app.state.document_service
    doc = await doc_service.get(document_id)
    if doc is None:
        raise HTTPException(status_code=404, detail="Document not found")

    entity_service = request.app.state.entity_service
    entities = await entity_service.get_document_entities(document_id)
    return {
        "entities": [
            {
                "id": str(e.id),
                "name": e.name,
                "entity_type": e.entity_type,
                "normalized_name": e.normalized_name,
                "document_count": e.document_count,
                "mention_count": e.mention_count,
            }
            for e in entities
        ]
    }


@router.get("/tags/all")
async def list_all_tags(request: Request):
    """Return all distinct tags across all documents, for autocomplete."""
    doc_service = request.app.state.document_service
    tags = await doc_service.list_tags()
    return {"tags": tags}


@router.post("/{document_id}/reprocess")
async def reprocess_document(document_id: UUID, request: Request):
    doc_service = request.app.state.document_service
    doc = await doc_service.get(document_id)
    if doc is None:
        raise HTTPException(status_code=404, detail="Document not found")

    from cortex.tasks.ingest import ingest_document

    ingest_document.delay(str(document_id))
    return {
        "document_id": str(document_id),
        "message": "Reprocessing started",
    }


@router.delete("/{document_id}")
async def delete_document(document_id: UUID, request: Request):
    doc_service = request.app.state.document_service
    deleted = await doc_service.delete(document_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Document not found")
    return {"deleted": True, "document_id": str(document_id)}


@router.patch("/{document_id}", response_model=DocumentMetadataResponse)
async def update_document(
    document_id: UUID, body: DocumentUpdateRequest, request: Request
):
    doc_service = request.app.state.document_service
    fields_set = body.model_fields_set
    doc = await doc_service.update(
        document_id,
        title=body.title,
        title_provided="title" in fields_set,
        tags=body.tags,
        tags_provided="tags" in fields_set,
        collection_id=body.collection_id,
        collection_id_provided="collection_id" in fields_set,
        is_favorite=body.is_favorite,
        is_favorite_provided="is_favorite" in fields_set,
    )
    if doc is None:
        raise HTTPException(status_code=404, detail="Document not found")
    return _doc_to_response(doc)
