from __future__ import annotations

from pathlib import Path
from uuid import UUID

from fastapi import APIRouter, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse

from cortex.schemas.document_schemas import (
    DocumentContentResponse,
    DocumentListResponse,
    DocumentMetadataResponse,
    DocumentUpdateRequest,
    DocumentUploadResponse,
)

router = APIRouter()


def _doc_to_response(doc) -> DocumentMetadataResponse:
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
    limit: int = 50,
    offset: int = 0,
):
    doc_service = request.app.state.document_service
    docs, total = await doc_service.list_documents(
        file_type=file_type,
        status=status,
        collection_id=collection_id,
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

    # Structured view
    if doc.rendered_html:
        content = doc.rendered_html
        fmt = "html"
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
    # Entity extraction is Phase 3
    return {"entities": [], "message": "Entity extraction not yet implemented"}


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
    doc = await doc_service.update(
        document_id,
        title=body.title,
        tags=body.tags,
        collection_id=body.collection_id,
        is_favorite=body.is_favorite,
    )
    if doc is None:
        raise HTTPException(status_code=404, detail="Document not found")
    return _doc_to_response(doc)
