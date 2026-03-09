# Cortex: Implementation Plan

## Document Version: 1.0
## Date: 2026-03-08
## Reference: APP_SPEC.md, ARCHITECTURE_BRAINSTORM.md

---

## Implementation Philosophy

This plan follows a **phased, vertical-slice approach**. Each phase delivers a working end-to-end feature (frontend → API → backend → database). This means the application is usable after each phase, not just at the end.

**Estimated total effort:** 4 phases across ~6-8 weeks of focused development.

---

## Phase 1: Foundation & Core Pipeline (MVP)

**Goal:** Upload a document, parse it, chunk it, embed it, store it, and search it. View the original document. This is the minimum viable knowledge base.

**Deliverables:**
- Docker infrastructure running
- PostgreSQL with pgvector initialized
- FastAPI server with document upload/list/view/search endpoints
- Docling parsing → Chonkie chunking → Qwen3 embedding pipeline
- Basic vector similarity search
- macOS app with document upload, library view, document viewer, and basic search

---

### Step 1.1: Infrastructure Setup

**Files to create:**
- `infrastructure/docker-compose.yml`
- `infrastructure/postgres/Dockerfile`
- `infrastructure/postgres/init.sql`
- `infrastructure/postgres/postgresql.conf`
- `infrastructure/.env.example`
- `infrastructure/scripts/setup.sh`

**Tasks:**

1. **Create the custom PostgreSQL Dockerfile**
   - Base: `paradedb/paradedb:latest-pg16` (includes pgvector + pg_search)
   - Install Apache AGE from source (PG16/1.5.0 branch)
   - Copy custom postgresql.conf

2. **Write `init.sql` (extensions only — tables managed by Alembic)**
   - `CREATE EXTENSION IF NOT EXISTS vector;`
   - `CREATE EXTENSION IF NOT EXISTS pg_search;` (may be auto-created by ParadeDB image)
   - `LOAD 'age'; SET search_path ...;`
   - `SELECT create_graph('knowledge_graph');`
   - **Do NOT create tables here** — Alembic is the single source of truth for schema.
     init.sql only handles extensions and the AGE graph, which are outside Alembic's scope.

3. **Write `postgresql.conf`**
   - Tuned for 128GB RAM system (see APP_SPEC Section 7.2)

4. **Write `docker-compose.yml`**
   - Services: postgres, redis, embedder (TEI), api, worker
   - GPU passthrough for embedder, api, worker
   - Named volumes for persistence
   - Health checks on postgres and redis

5. **Write `setup.sh`**
   - Pulls images, builds custom postgres, starts everything
   - Waits for health checks
   - Runs Alembic migrations

6. **Verification:**
   - `docker compose up` starts all services
   - `psql` connects and can query with pgvector, pg_search, AGE extensions
   - TEI responds to health check on port 8081
   - Redis responds to PING

---

### Step 1.2: Backend Project Scaffolding (Layered Architecture)

**Files to create:**
- `backend/pyproject.toml`
- `backend/Dockerfile`
- `backend/src/cortex/__init__.py`
- `backend/src/cortex/__main__.py` — entry point for `python -m cortex`
- `backend/src/cortex/bootstrap.py` — composition root (wires dependencies)
- `backend/src/cortex/settings.py` — Pydantic `BaseSettings`
- `backend/src/cortex/domain/__init__.py`
- `backend/src/cortex/domain/document.py` — Document entity, value objects
- `backend/src/cortex/domain/chunk.py` — Chunk entity
- `backend/src/cortex/domain/entity.py` — NER entity types
- `backend/src/cortex/domain/ports.py` — Abstract interfaces (`typing.Protocol`)
- `backend/src/cortex/application/__init__.py`
- `backend/src/cortex/schemas/__init__.py`
- `backend/src/cortex/schemas/document_schemas.py`
- `backend/src/cortex/schemas/search_schemas.py`
- `backend/src/cortex/infrastructure/__init__.py`
- `backend/src/cortex/infrastructure/persistence/__init__.py`
- `backend/src/cortex/infrastructure/persistence/database.py` — AsyncSession factory
- `backend/src/cortex/infrastructure/persistence/tables.py` — SQLAlchemy ORM models
- `backend/src/cortex/entrypoints/__init__.py`
- `backend/src/cortex/entrypoints/app.py` — FastAPI app factory
- `backend/src/cortex/entrypoints/router.py`
- `backend/src/cortex/entrypoints/status.py`
- `backend/alembic/alembic.ini`
- `backend/alembic/env.py`

**Architecture notes:**
- Follow the **layered architecture** from the coding guidelines: `domain/` → `application/` → `infrastructure/` → `entrypoints/`
- Dependencies point inward. `application/` depends on `domain/` ports only, never on `infrastructure/`.
- `bootstrap.py` is the composition root — the **single** module that imports both `application/` and `infrastructure/` to wire concrete adapters to abstract ports.
- No ambiguous `models/` directory. Split into: `domain/` (entities), `schemas/` (Pydantic transport types), `infrastructure/persistence/tables.py` (ORM).
- No `utils/` junk drawer. Domain-specific helpers live in their relevant module.

**Tasks:**

1. **Set up Python project with `uv`**
   - `pyproject.toml` with all dependencies (see APP_SPEC Section 8)
   - Use Python 3.11+
   - `src/` layout (PyPA recommended)

2. **Define domain layer (`domain/`)**
   - `document.py`: Document dataclass/entity with id, title, file_type, status, metadata
   - `chunk.py`: Chunk entity with text, start/end offsets, token_count, section context
   - `entity.py`: Entity types (NER results)
   - `ports.py`: All abstract interfaces using `typing.Protocol`:
     - `ParserPort`, `ChunkerPort`, `EmbedderPort`, `RerankerPort`, `NERPort`
     - `DocumentRepository`, `ChunkRepository`, `GraphPort`, `FileStoragePort`
   - Domain types must NOT import from `infrastructure/` or `entrypoints/`

3. **Define Pydantic schemas (`schemas/`)**
   - Request/response models per APP_SPEC Section 4.3
   - These are **transport types**, separate from domain entities
   - `document_schemas.py`: DocumentUploadResponse, DocumentMetadata, DocumentContent
   - `search_schemas.py`: SearchRequest, SearchResponse, SearchResult, ScoreBreakdown

4. **Create FastAPI application (`entrypoints/app.py`)**
   - App factory function that accepts `CompositionRoot`
   - CORS middleware (allow macOS app origin)
   - Lifespan handler for DB connection pool
   - Mount API router at `/api/v1`

5. **SQLAlchemy ORM models (`infrastructure/persistence/tables.py`)**
   - SQLAlchemy 2.0 async models for: documents, chunks, entities, entity_mentions, collections, document_images
   - pgvector column type for embeddings
   - These are **infrastructure** concerns, not domain

6. **Database session management (`infrastructure/persistence/database.py`)**
   - AsyncSession factory with asyncpg
   - Dependency injection for FastAPI

7. **Composition root (`bootstrap.py`)**
   - Imports Settings, creates infrastructure adapters, creates application services
   - Wires adapters to ports via constructor injection
   - This is the **only** module that knows about both layers

8. **Settings (`settings.py`)**
   - `pydantic_settings.BaseSettings` with `model_config = SettingsConfigDict(env_file=".env")`
   - Database URL, Redis URL, embedder URL, data dir, model names

9. **Alembic setup**
   - Initial migration that creates all tables
   - Configure for async engine

10. **Health endpoint (`entrypoints/status.py`)**
    - `GET /api/v1/health` — checks DB, Redis, TEI connectivity

11. **Backend Dockerfile**
    - Python 3.11 slim base
    - Install system deps (libmagic for python-magic, etc.)
    - `pip install torch --index-url https://download.pytorch.org/whl/cu128` for CUDA
    - Copy and install Python package
    - Expose port 8080, run uvicorn

12. **Verification:**
    - `python -m cortex` starts FastAPI without errors
    - `GET /api/v1/health` returns 200
    - Alembic migration creates tables in PostgreSQL
    - Domain module imports work without importing infrastructure (verify clean dependency direction)

---

### Step 1.3: Document Upload & Storage

**Files to create:**
- `backend/src/cortex/entrypoints/documents.py` — FastAPI route handlers
- `backend/src/cortex/application/document_service.py` — Use-case orchestration
- `backend/src/cortex/infrastructure/file_storage.py` — `FileStoragePort` implementation
- `backend/src/cortex/infrastructure/persistence/document_repo.py` — `DocumentRepository` implementation

**Tasks:**

1. **File storage adapter (`infrastructure/file_storage.py`)**
   - Implements `FileStoragePort` from `domain/ports.py`
   - `save_original(file, document_id)` — saves to `/data/originals/{doc_id}/{filename}`
   - `get_original_path(document_id)` — returns file path
   - `compute_file_hash(file)` — SHA-256 hash for deduplication
   - `delete_document_files(document_id)` — cleanup

2. **Document repository (`infrastructure/persistence/document_repo.py`)**
   - Implements `DocumentRepository` from `domain/ports.py`
   - SQLAlchemy async CRUD operations
   - Translates between ORM table models and domain entities

3. **Document service (`application/document_service.py`)**
   - Depends on `DocumentRepository` and `FileStoragePort` (protocols, not concrete types)
   - Orchestrates upload → hash check → store → enqueue processing

4. **Document upload endpoint (`entrypoints/documents.py`)**
   - `POST /api/v1/documents` — multipart file upload
   - Validates file type (PDF, MD, DOCX, XLSX, TXT, PNG, JPG, TIFF)
   - Validates file size (configurable max, default 100MB)
   - Computes file hash, checks for duplicates
   - **Duplicate handling:** If hash matches an existing document, return existing document ID with `is_duplicate=True` (HTTP 200, not 409). No new record created.
   - Creates document record with status=`"uploading"` → stores file → status=`"stored"` → enqueues async processing
   - Returns DocumentUploadResponse with document_id and status

5. **Document CRUD endpoints**
   - `GET /api/v1/documents` — paginated list with filtering (type, collection, tags, status)
   - `GET /api/v1/documents/{id}` — document metadata
   - `GET /api/v1/documents/{id}/content?view=structured` — rendered content (HTML, markdown, JSON)
   - `GET /api/v1/documents/{id}/content?view=fidelity` — original file URL for native rendering
   - `GET /api/v1/documents/{id}/original` — stream original file binary
   - `GET /api/v1/documents/{id}/thumbnail` — thumbnail image (PNG)
   - `GET /api/v1/documents/{id}/chunks` — all chunks for this document (Phase 1)
   - `GET /api/v1/documents/{id}/entities` — extracted entities (available after Phase 3)
   - `POST /api/v1/documents/{id}/reprocess` — explicitly re-run ingestion pipeline
   - `DELETE /api/v1/documents/{id}` — delete document + files + chunks + entities + graph nodes
   - `PATCH /api/v1/documents/{id}` — update tags, collection, favorite

6. **Verification:**
   - Upload a PDF via curl/httpie → file saved on disk, record in DB with status=`"uploading"`→`"stored"`
   - List documents returns the uploaded document
   - Download original returns the same file
   - `GET /documents/{id}/thumbnail` returns PNG image
   - `GET /documents/{id}/content` returns rendered HTML/markdown
   - Duplicate upload returns existing document ID with `is_duplicate=True`

---

### Step 1.4: Document Parsing Service

**Files to create:**
- `backend/src/cortex/infrastructure/ml/docling_parser.py` — `ParserPort` implementation

**Tasks:**

1. **Implement DocumentParser class with GPU acceleration**
   - Initialize Docling DocumentConverter with CUDA-optimized settings:
     ```python
     AcceleratorOptions(device=AcceleratorDevice.AUTO)  # auto-detect CUDA
     ThreadedPdfPipelineOptions(
         layout_batch_size=32,   # default 4; increase for RTX 3090 throughput
         ocr_batch_size=32,      # default 4; increase for GPU OCR
         table_batch_size=4,     # GPU batching not yet supported for tables
     )
     ```
   - `parse(file_path, file_type) -> ParseResult`
   - PDF: Docling for structure (GPU-accelerated: ~0.5s/page) → PyMuPDF for thumbnail + images
   - DOCX: Docling for structure → python-docx fallback if needed
   - XLSX: openpyxl for formatted reading → convert to structured JSON
   - Markdown: markdown-it-py for parsing → render to HTML
   - **Plain text (.txt):** Read file directly; wrap in `<pre>` for rendered_html; no ML parsing needed
   - **Images (.png, .jpg, .tiff):** Docling with OCR for text extraction; store original as both content and thumbnail; rendered_html wraps `<img>` tag
   - Returns ParseResult with: text, structured_content (JSON), rendered_html, metadata, images, thumbnail, page_count
   - **IMPORTANT:** Call `torch.cuda.empty_cache()` after each document to prevent VRAM leaks (known Docling issue)

2. **GPU configuration for Docling**
   - Docling uses PyTorch CUDA — requires `torch` with CUDA support in Docker image
   - The worker container already has GPU passthrough (`NVIDIA_VISIBLE_DEVICES: all`)
   - Docling auto-detects CUDA via `torch.cuda.is_available()` — no extra config needed for basic use
   - For OCR: use EasyOCR (GPU-compatible), NOT RapidOCR with default ONNX backend (ignores GPU)
   - GPU performance benchmarks (NVIDIA L4):
     - Layout detection: 14.4x faster than CPU (44ms vs 633ms per page)
     - Table recognition: 4.3x faster (400ms vs 1.74s per table)
     - OCR: 8.1x faster (1.6s vs 13s per page)
     - Overall: ~6.5x faster (0.48s vs 3.1s per page)
   - On RTX 3090 with batch_size=32: expect ~5-8 pages/sec for standard PDFs
   - VRAM usage: ~1-2 GB for Docling's ML models (layout RT-DETR + TableFormer)

3. **Thumbnail generation**
   - PDF: PyMuPDF `page.get_pixmap()` → PIL Image → save as PNG
   - DOCX/XLSX: generate a simple icon-based thumbnail or use first-page rendering
   - Markdown: skip thumbnail or use text preview

4. **Image extraction**
   - PDF: PyMuPDF extract embedded images → save to `/data/images/{doc_id}/`
   - DOCX: python-docx extract images
   - Store image records in document_images table

5. **Verification:**
   - Parse a multi-page PDF → get structured content with headings, paragraphs, tables
   - Parse a DOCX → get formatted content
   - Parse an XLSX → get sheet data with formatting
   - Parse Markdown → get rendered HTML
   - Parse a .txt file → get plain text content wrapped in HTML
   - Parse a .png image → get OCR-extracted text (if any) + image stored
   - Thumbnails generated for each
   - Verify GPU is being used: check `nvidia-smi` shows Docling process using VRAM during PDF parsing
   - Benchmark: 10-page PDF should parse in < 5 seconds on RTX 3090 (vs ~30s on CPU)

---

### Step 1.5: Chunking Service

**Files to create:**
- `backend/src/cortex/infrastructure/ml/chonkie_chunker.py` — `ChunkerPort` implementation

**Tasks:**

1. **Implement ChunkerService class**
   - Initialize Chonkie SemanticChunker (primary) and RecursiveChunker (fallback)
   - `chunk_document(text, structured_content) -> list[ChunkResult]`
   - Use SemanticChunker with Qwen3-Embedding-0.6B tokenizer
   - Config: chunk_size=512, chunk_overlap=64, similarity_threshold=0.5

2. **Section context preservation**
   - Build section map from DoclingDocument structured content
   - Map each chunk's character range to its containing section heading
   - Store section_heading and section_level per chunk

3. **Handle edge cases**
   - Very short documents (< 512 tokens): single chunk
   - Very long documents: process in batches to avoid memory issues
   - Tables: keep table content together when possible

4. **Verification:**
   - Chunk a 10-page document → get ~20-40 chunks with proper overlaps
   - Each chunk has section context
   - Chunk text + positions can reconstruct original

---

### Step 1.6: Embedding Service

**Files to create:**
- `backend/src/cortex/infrastructure/ml/tei_embedder.py` — `EmbedderPort` implementation

**Tasks:**

1. **Implement EmbeddingClient class**
   - HTTP client to TEI service
   - `embed_texts(texts: list[str]) -> list[list[float]]` — batch embedding
   - `embed_query(query: str) -> list[float]` — single query embedding with instruction prefix
   - Batch size management (max batch tokens from TEI config)
   - Retry logic for transient failures

2. **Integrate with pgvector storage**
   - After embedding, UPDATE chunks table with embedding vectors
   - Use pgvector's vector type

3. **Verification:**
   - Embed a list of 10 texts → get 10 vectors of 1024 dimensions each
   - Vectors stored in PostgreSQL, queryable with `<=>` operator
   - Nearest neighbor search returns semantically similar chunks

---

### Step 1.7: Ingestion Pipeline (Celery Task)

**Files to create:**
- `backend/src/cortex/tasks/celery_app.py`
- `backend/src/cortex/tasks/ingest.py`
- `backend/src/cortex/application/ingestion_service.py` — Use-case orchestration (depends on domain ports only)

**Tasks:**

1. **Celery configuration**
   - Redis broker and result backend
   - Task serialization with JSON
   - Concurrency: 2 workers (to manage GPU memory)

2. **Implement ingestion task (`ingest_document`)**
   - Input: document_id
   - Steps (set transitional status on entry, completed status on exit — matches APP_SPEC canonical lifecycle):
     1. Fetch document record from DB
     2. Set status=`"parsing"` → Parse document (GPU-accelerated via Docling CUDA) → status=`"parsed"`
     3. Call `torch.cuda.empty_cache()` to release Docling VRAM
     4. Store parsed content, rendered HTML, metadata, images in DB
     5. Set status=`"chunking"` → Chunk document → status=`"chunked"`
     6. Store chunks in DB
     7. Set status=`"embedding"` → Batch embed all chunks → status=`"embedded"`
     8. Store embeddings in chunks table
     9. (BM25 indexing is automatic — pg_search updates transactionally with chunk inserts)
     10. Update status → `"ready"`
     - **Each status transition pushes a `ProcessingEvent` via Redis pub/sub → WebSocket**
   - Error handling: catch exceptions, set status="failed", store error_message
   - Idempotent: can re-run safely (deletes existing chunks first)
   - **GPU note:** Docling (parse), TEI (embed), GLiNER (NER), and mxbai (rerank) all share the RTX 3090. Total VRAM ~8-11 GB out of 24 GB. During ingestion, Docling + GLiNER run sequentially (not concurrently) to avoid peak VRAM contention.

3. **Status reporting + WebSocket events**
   - Store progress in Redis (percentage, current stage)
   - Expose via `GET /api/v1/status/processing` (polling fallback)
   - **Implement `/ws/events` WebSocket endpoint** in `entrypoints/app.py`:
     - Push `ProcessingEvent` messages to connected clients on every status transition
     - Event types: `status_changed`, `processing_progress`, `processing_complete`, `processing_failed`
     - Use Redis pub/sub to bridge worker → API → WebSocket (worker publishes, API subscribes and pushes)
   - **Implement `WebSocketClient` in frontend** (`Infrastructure/WebSocketClient.swift`):
     - Connect on app launch, reconnect on disconnect
     - Parse `ProcessingEvent` JSON, notify `IngestionService` which updates UI

4. **Verification:**
   - Upload a PDF → task runs automatically → document reaches `"ready"` status
   - Chunks exist in DB with embeddings
   - WebSocket client receives `processing_complete` event when done
   - Duplicate upload (same file, different name) returns existing document ID, does NOT re-process
   - Explicit reprocess via `POST /documents/{id}/reprocess` re-runs pipeline

---

### Step 1.8: Basic Vector Search

**Files to create:**
- `backend/src/cortex/entrypoints/search.py` — Search route handlers
- `backend/src/cortex/application/search_service.py` — Search orchestration (depends on domain ports)
- `backend/src/cortex/infrastructure/search/vector_search.py` — pgvector HNSW search
- `backend/src/cortex/infrastructure/persistence/chunk_repo.py` — `ChunkRepository` implementation

**Tasks:**

1. **Implement basic search endpoint**
   - `POST /api/v1/search` with SearchRequest body
   - Embed query via TEI
   - Vector similarity search via pgvector HNSW: `ORDER BY embedding <=> query_vec LIMIT top_k`
   - Return results with chunk text, document metadata, score

2. **Result enrichment with anchor data**
   - Join with documents table for title, type, dates
   - Generate highlighted snippet (bold query terms in chunk text)
   - Include section heading context
   - **Include anchor fields for "jump to hit":**
     - `chunk_start_char`, `chunk_end_char` — character offsets in full document text
     - `page_number` — for PDF scroll-to-page
     - `anchor_id` — e.g., `"chunk-7"` for HTML anchor navigation in structured views

3. **Anchor injection in rendered content**
   - When serving `GET /documents/{id}/content?view=structured`, inject `<span id="chunk-N">` anchors into rendered HTML at each chunk boundary
   - Frontend can then scroll to `#chunk-N` when user clicks a search result

4. **Verification:**
   - Upload 5+ diverse documents
   - Search for a concept mentioned in one → that document's chunks rank highest
   - Search results include `page_number` and `anchor_id` fields
   - Search latency < 100ms (vector only, no reranking yet)

---

### Step 1.9: macOS App — Project Setup & SPM Multi-Target Architecture

**Files to create:**
- `frontend/Package.swift` — SPM manifest with compiler-enforced dependencies
- `frontend/Sources/Domain/Document.swift` — Document struct (Sendable, Equatable)
- `frontend/Sources/Domain/SearchResult.swift`
- `frontend/Sources/Domain/Entity.swift`
- `frontend/Sources/Domain/Collection.swift`
- `frontend/Sources/Domain/Ports.swift` — DocumentRepositoryPort, SearchPort protocols
- `frontend/Sources/AppCore/DocumentService.swift` — Depends on Domain ports only
- `frontend/Sources/AppCore/SearchService.swift`
- `frontend/Sources/AppCore/IngestionService.swift`
- `frontend/Sources/Infrastructure/APIClient.swift` — URLSession HTTP client
- `frontend/Sources/Infrastructure/APIDocumentRepository.swift` — Implements DocumentRepositoryPort
- `frontend/Sources/Infrastructure/APISearchRepository.swift` — Implements SearchPort
- `frontend/Sources/Infrastructure/WebSocketClient.swift` — Real-time processing event stream
- `frontend/Sources/Bootstrap/CompositionRoot.swift` — Wires concrete to abstract
- `frontend/Sources/Bootstrap/Settings.swift`
- `frontend/Sources/CortexApp/CortexApp.swift` — @main entry point
- `frontend/Sources/CortexApp/ContentView.swift` — Root NavigationSplitView

**Architecture notes:**
- Follow the **SPM multi-target architecture** from the coding guidelines
- Each target is a separate Swift module with compiler-enforced dependency boundaries
- `Domain` depends on nothing; `AppCore` and `Infrastructure` depend only on `Domain`; `Bootstrap` wires all three; `CortexApp` depends on `Bootstrap`
- Domain entities are **value types (structs)**, `Sendable`, and `Equatable`
- Port protocols use `package` access level and `Sendable` conformance
- Services use `any ProtocolName` existentials for dependency injection
- No `Utilities/` or `Helpers/` directories — put markdown rendering in `Infrastructure/`, thumbnail loading in `Infrastructure/`
- One primary type per file, named after the type
- Tests use protocol test doubles (final classes) — no mocking framework needed

**Tasks:**

1. **Create SPM package**
   - `Package.swift` with all 5 targets and dependency graph (see APP_SPEC Section 9.1)
   - Minimum deployment target: macOS 14.0 (Sonoma)
   - Add swift-markdown package dependency on Infrastructure target

2. **Define Domain target**
   - `Document.swift`: `package struct Document: Sendable, Equatable, Codable` with id, title, fileType, status, dates
   - `Ports.swift`: `package protocol DocumentRepositoryPort: Sendable`, `package protocol SearchPort: Sendable`
   - File type enum with SF Symbol icon mapping
   - Processing status enum
   - Domain types must NOT import Foundation networking or UI frameworks

3. **Define AppCore target**
   - `DocumentService.swift`: depends on `any DocumentRepositoryPort` (protocol, not concrete type)
   - `SearchService.swift`: depends on `any SearchPort`, includes debounce logic
   - `IngestionService.swift`: upload orchestration + status tracking

4. **Define Infrastructure target**
   - `APIClient.swift`: base URL configurable, generic request/response via URLSession + async/await, multipart upload
   - `APIDocumentRepository.swift`: implements `DocumentRepositoryPort` using `APIClient`
   - `APISearchRepository.swift`: implements `SearchPort` using `APIClient`

5. **Define Bootstrap target**
   - `CompositionRoot.swift`: creates `APIClient`, creates repo adapters, creates services
   - `Settings.swift`: backend URL, user preferences

6. **Define CortexApp target**
   - `CortexApp.swift`: `@main`, creates `CompositionRoot`, passes services to views
   - `ContentView.swift`: `NavigationSplitView` (sidebar / document list / document detail)
   - Empty state with import prompt

7. **Verification:**
   - `swift build` succeeds with clean dependency graph
   - App launches, connects to backend API
   - Domain target compiles with no Infrastructure imports (enforced by SPM)
   - Can see health status in UI

---

### Step 1.10: macOS App — Document Library & Import

**Files to create:**
- `frontend/Sources/CortexApp/Library/DocumentLibraryView.swift`
- `frontend/Sources/CortexApp/Library/DocumentGridItem.swift`
- `frontend/Sources/CortexApp/Library/DocumentListRow.swift`
- `frontend/Sources/CortexApp/Ingestion/DocumentDropZone.swift`
- `frontend/Sources/CortexApp/Ingestion/ImportProgressView.swift`
- `frontend/Sources/Infrastructure/ThumbnailLoader.swift`

**Tasks:**

1. **Document library view**
   - Grid view with thumbnails (LazyVGrid, adaptive columns)
   - List view with Table (title, type, date, size)
   - View mode toggle in toolbar
   - Sort options: date added, title, type, size
   - Pull-to-refresh / auto-refresh after import

2. **Document grid item**
   - Thumbnail image (loaded async from backend)
   - Document title (2-line truncation)
   - File type icon badge
   - Processing status indicator (spinner for in-progress)
   - Context menu: Open, Favorite, Delete (Collections deferred to Phase 4)

3. **Document import**
   - Drag-and-drop zone (visible when library is empty, or as overlay on drag)
   - File picker via `.fileImporter()` with UTType filtering
   - Toolbar "Import" button (Cmd+I)
   - Supports multi-file selection
   - Progress view showing upload + processing status per file

4. **Thumbnail loading**
   - Async image loading from `GET /api/v1/documents/{id}/thumbnail`
   - In-memory cache (NSCache)
   - Placeholder icon while loading

5. **Verification:**
   - Drag a PDF onto the app → upload starts → progress shown → document appears in grid
   - Grid shows thumbnails for processed documents
   - List view shows sortable table
   - Can delete documents from context menu

---

### Step 1.11: macOS App — Document Viewer

**Files to create:**
- `frontend/Sources/CortexApp/Viewer/DocumentDetailView.swift`
- `frontend/Sources/CortexApp/Viewer/PDFDocumentView.swift`
- `frontend/Sources/CortexApp/Viewer/MarkdownDocumentView.swift`
- `frontend/Sources/CortexApp/Viewer/HTMLDocumentView.swift`
- `frontend/Sources/CortexApp/Viewer/SpreadsheetView.swift`
- `frontend/Sources/CortexApp/Viewer/PlainTextView.swift` — monospace text viewer
- `frontend/Sources/CortexApp/Viewer/ImageDocumentView.swift` — zoomable image viewer
- `frontend/Sources/CortexApp/Viewer/QuickLookView.swift` — NSViewRepresentable<QLPreviewView> for fidelity mode
- `frontend/Sources/Infrastructure/MarkdownRenderer.swift`

**Tasks:**

1. **DocumentDetailView (router)**
   - Receives document ID from library selection
   - Fetches document content from API
   - Routes to appropriate viewer based on file_type
   - Toolbar: title, metadata, entity chips (Phase 3), tags
   - Loading state while content fetches

2. **PDFDocumentView**
   - NSViewRepresentable wrapping PDFView
   - Load PDF from backend URL (original file endpoint)
   - Features: zoom, scroll, page navigation, outline sidebar
   - Text search within PDF (PDFView's built-in search)

3. **MarkdownDocumentView**
   - Convert Markdown to HTML using swift-markdown
   - Inject custom CSS (system font, code highlighting, dark mode)
   - Render in WKWebView via NSViewRepresentable
   - Support for tables, code blocks, math (KaTeX)

4. **HTMLDocumentView** (for DOCX rendered content — structured view)
   - WKWebView rendering backend-provided HTML from `GET /documents/{id}/content?view=structured`
   - Custom CSS for consistent styling
   - Inject dark mode support
   - HTML includes `<span id="chunk-N">` anchors for search-hit navigation
   - **Dual-representation toggle:** Toolbar segmented control `Structured | Original`
   - Original mode: render original DOCX file via `QLPreviewView` (NSViewRepresentable wrapper around QuickLook)
   - Structured mode is default (supports anchor navigation, entity chips)

5. **SpreadsheetView** (for XLSX — structured view)
   - SwiftUI ScrollView with LazyVGrid/Table
   - Sheet tab selector
   - Cell formatting (bold, colors, alignment)
   - Horizontal and vertical scrolling
   - **Dual-representation toggle:** Same `Structured | Original` toolbar control
   - Original mode: render via `QLPreviewView` for full Excel fidelity

6. **PlainTextView**
   - SwiftUI `ScrollView` with `Text` using monospace font (`.font(.system(.body, design: .monospaced))`)
   - Content loaded from `GET /documents/{id}/content`

7. **ImageDocumentView**
   - SwiftUI `Image` with pinch-to-zoom and pan gestures
   - Load from `GET /documents/{id}/original`

8. **Verification:**
   - Click a PDF in library → renders in PDFKit with zoom/scroll
   - Click a Markdown file → renders as styled HTML
   - Click a DOCX → renders as structured HTML; toggle to Original shows QuickLook preview
   - Click an XLSX → renders as table with sheet tabs; toggle to Original shows QuickLook preview
   - Click a .txt file → renders in monospace
   - Click an image → renders with zoom/pan

---

### Step 1.12: macOS App — Basic Search

**Files to create:**
- `frontend/Sources/CortexApp/Search/SearchOverlayView.swift`
- `frontend/Sources/CortexApp/Search/SearchResultRow.swift`
- `frontend/Sources/CortexApp/Search/SearchHighlighter.swift`

**Note:** `SearchService` already exists in `AppCore/` from Step 1.9. Search highlighting lives in the `CortexApp` target since it's a view-layer concern (AttributedString formatting).

**Tasks:**

1. **SearchService**
   - `search(query:filters:) async throws -> SearchResponse`
   - Debounced search (300ms delay after typing stops)

2. **SearchOverlayView (Cmd+K)**
   - Modal overlay with search field
   - Auto-focused text field
   - Results list with highlighted snippets
   - Keyboard navigation (up/down arrows, Enter to select)
   - Escape to dismiss

3. **SearchResultRow**
   - Document type icon
   - Document title
   - Highlighted snippet (bold matched terms)
   - Section heading context
   - Relevance score
   - Click → navigate to document viewer

4. **Search highlighting**
   - Parse highlighted_snippet from backend
   - Convert to AttributedString with bold/background color for matches

5. **Integration with main view**
   - Cmd+K keyboard shortcut to open search
   - `.searchable()` modifier on NavigationSplitView for toolbar search
   - Search from toolbar uses same backend, results shown in document list

6. **Verification:**
   - Cmd+K opens search overlay
   - Type query → results appear with highlighted snippets
   - Click result → opens document viewer
   - Search latency feels interactive (< 500ms)

---

## Phase 2: Enhanced Search (Hybrid + Reranking)

**Goal:** Add BM25 keyword search, hybrid retrieval with Reciprocal Rank Fusion, and neural reranking for significantly better search quality.

---

### Step 2.1: BM25 Full-Text Search Integration

**Files to create:**
- `backend/src/cortex/infrastructure/search/bm25_search.py` — pg_search BM25 adapter

**Files to modify:**
- `backend/src/cortex/application/search_service.py`
- `backend/src/cortex/domain/ports.py` — add `bm25_search` to `ChunkRepository` protocol

**Tasks:**

1. **Create pg_search BM25 indexes** (add to Alembic migration)
   - Index on `chunks.chunk_text` with English stemmer
   - Index on `documents.title` + `documents.rendered_markdown`

2. **Implement BM25 search method in SearchOrchestrator**
   - Query pg_search with `@@@ operator`
   - Return chunk IDs with BM25 scores
   - Handle query parsing (boolean operators, phrase search)

3. **Verification:**
   - Search for an exact phrase → BM25 finds it even if semantically distant
   - Keyword-heavy searches return relevant results

---

### Step 2.2: Hybrid Search with Reciprocal Rank Fusion

**Files to modify:**
- `backend/src/cortex/application/search_service.py`

**Tasks:**

1. **Implement parallel retrieval**
   - Run vector search and BM25 search concurrently (asyncio.gather)
   - Each returns ranked list with scores

2. **Implement RRF fusion**
   - `RRF_score = w_vec / (k + rank_vec) + w_bm25 / (k + rank_bm25)`
   - Default weights: w_vec=0.6, w_bm25=0.4, k=60
   - Merge and deduplicate by chunk_id
   - Sort by combined RRF score
   - Return top 50 candidates for reranking

3. **Verification:**
   - Query that matches both semantically and by keyword → scores higher
   - Query with exact term not in embedding space → BM25 finds it
   - Hybrid results are better than either alone

---

### Step 2.3: Reranker Integration

**Files to create:**
- `backend/src/cortex/infrastructure/ml/mxbai_reranker.py` — `RerankerPort` implementation

**Files to modify:**
- `backend/src/cortex/application/search_service.py`
- `backend/src/cortex/bootstrap.py` — wire reranker to search service

**Tasks:**

1. **Implement RerankerService**
   - Load mxbai-rerank-large-v2 model (on GPU)
   - `rerank(query, documents, top_k) -> list[RerankResult]`
   - Score each (query, chunk_text) pair
   - Return reordered results with reranker scores
   - Lazy model loading (load on first use to share GPU)

2. **Integrate into search pipeline**
   - After RRF fusion, pass top-50 candidates to reranker
   - Rerank → take top_k (default 10)
   - Include rerank_score in response ScoreBreakdown

3. **Model management**
   - Load model into GPU on worker startup
   - Share model across requests (singleton pattern)
   - Consider: serve via separate container if memory contention occurs

4. **Verification:**
   - Reranked results are more relevant than RRF-only
   - Reranking adds ~200-400ms to search latency
   - GPU memory usage stable with concurrent requests

---

### Step 2.4: Document-Level Search

**Files to modify:**
- `backend/src/cortex/entrypoints/search.py` — add document search endpoint
- `backend/src/cortex/application/search_service.py` — add document aggregation

**Tasks:**

1. **Implement document-level search**
   - `POST /api/v1/search/documents`
   - Aggregate chunk scores per document (max or mean score)
   - Return documents (not chunks) ranked by relevance
   - Include top matching chunk as snippet

2. **Frontend integration**
   - Search mode toggle: "Passages" vs "Documents"
   - Document results show thumbnail, title, best matching snippet

3. **Verification:**
   - Search returns whole documents ranked by relevance
   - Top chunk from each document shown as snippet

---

### Step 2.5: Frontend Search Enhancements

**Files to modify:**
- `frontend/Sources/CortexApp/Search/SearchOverlayView.swift`
- `frontend/Sources/CortexApp/Search/SearchResultRow.swift`

**Files to create:**
- `frontend/Sources/CortexApp/Search/SearchFiltersView.swift`

**Tasks:**

1. **Search filters**
   - File type filter (dropdown: All, PDF, Markdown, DOCX, XLSX)
   - Date range filter
   - Collection filter
   - Search mode: Passages / Documents

2. **Enhanced result display**
   - Score breakdown tooltip (vector, BM25, rerank scores)
   - "More from this document" expansion
   - Result count and search time display

3. **Verification:**
   - Filters work correctly
   - Can switch between passage and document search modes
   - Score breakdown visible on hover

---

## Phase 3: Knowledge Graph & NER

**Goal:** Extract named entities from documents, build a knowledge graph, and use it to enhance search results and enable entity-based exploration.

---

### Step 3.1: NER Extraction Service

**Files to create:**
- `backend/src/cortex/infrastructure/ml/gliner_ner.py` — `NERPort` implementation

**Files to modify:**
- `backend/src/cortex/application/ingestion_service.py` — add NER step
- `backend/src/cortex/tasks/ingest.py` — call ingestion service NER step
- `backend/src/cortex/bootstrap.py` — wire NER to ingestion service

**Tasks:**

1. **Implement NERService**
   - Load GLiNER large v2.5 model
   - Define entity label set (see APP_SPEC Section 6.5)
   - `extract_entities(chunks) -> list[EntityExtraction]`
   - Process each chunk through GLiNER
   - Threshold: 0.4 (balance recall/precision)

2. **Entity deduplication and normalization**
   - Normalize entity names (lowercase, strip whitespace)
   - Merge same-name entities across chunks
   - Aggregate confidence scores and mention counts

3. **Store entities in database**
   - Upsert into entities table (unique on normalized_name + type)
   - Create entity_mentions linking entities to chunks and documents
   - Update aggregate counts

4. **Add NER step to ingestion pipeline**
   - After embedding step, run NER on all chunks
   - Status transitions: "embedded" → "extracting_entities" → "entities_extracted"
   - NER runs on GPU (GLiNER model)

5. **Verification:**
   - Upload a document → entities extracted and stored
   - Entities table shows normalized, deduplicated entities
   - Entity mentions link back to correct chunks

---

### Step 3.2: Knowledge Graph Population

**Files to create:**
- `backend/src/cortex/infrastructure/graph/age_repository.py` — `GraphPort` implementation

**Files to modify:**
- `backend/src/cortex/application/ingestion_service.py` — add graph step
- `backend/src/cortex/tasks/ingest.py` — call ingestion service graph step
- `backend/src/cortex/bootstrap.py` — wire graph repo to ingestion service

**Tasks:**

1. **Implement GraphService**
   - Create/merge Document nodes in AGE graph
   - Create/merge Entity nodes
   - Create MENTIONS edges (Document → Entity)
   - Create CO_OCCURS edges (Entity → Entity for entities in same chunk)

2. **Add graph step to ingestion pipeline**
   - After NER step, populate knowledge graph
   - Status: "entities_extracted" → "building_graph" → "ready"

3. **Graph query methods**
   - `get_related_entities(entity_id, hops=2)` — traverse graph
   - `get_entity_documents(entity_id)` — documents mentioning entity
   - `get_document_entities(document_id)` — entities in document
   - `explore_graph(start_entity, depth, limit)` — subgraph exploration

4. **Verification:**
   - Upload documents mentioning same entities → graph connects them
   - Query graph for entity → related entities returned via CO_OCCURS
   - Document → entity → related documents traversal works

---

### Step 3.3: Graph-Enhanced Search

**Files to create:**
- `backend/src/cortex/infrastructure/search/graph_search.py` — Graph-based candidate boosting

**Files to modify:**
- `backend/src/cortex/application/search_service.py`
- `backend/src/cortex/bootstrap.py` — wire graph search to search service

**Tasks:**

1. **Query-time entity extraction**
   - Run GLiNER on search query to extract entities
   - Look up entities in graph

2. **Graph expansion**
   - For each query entity, traverse 1-2 hops in graph
   - Find chunks that mention related entities
   - Score these chunks based on graph distance

3. **Integrate into RRF**
   - Add graph scores as third signal: `w_graph / (k + rank_graph)`
   - Default weight: w_graph=0.2 (reduce w_vec to 0.5, w_bm25 to 0.3)

4. **Verification:**
   - Search for "John Smith" → also finds documents about his company (via graph)
   - Graph expansion improves recall for entity-centric queries

---

### Step 3.4: Entity API Endpoints

**Files to create:**
- `backend/src/cortex/entrypoints/entities.py`
- `backend/src/cortex/schemas/entity_schemas.py`

**Tasks:**

1. **Entity endpoints**
   - `GET /api/v1/entities` — list all entities, filterable by type
   - `GET /api/v1/entities/{id}` — entity details + related documents
   - `GET /api/v1/entities/{id}/related` — related entities from graph
   - `GET /api/v1/graph/explore` — explore graph from starting entity

2. **Verification:**
   - List entities → shows all extracted entities with counts
   - Entity detail → shows documents and related entities

---

### Step 3.5: Frontend Entity Integration

**Files to create:**
- `frontend/Sources/CortexApp/Sidebar/EntityBrowserView.swift`
- `frontend/Sources/CortexApp/Viewer/EntityChipView.swift`

**Files to modify:**
- `frontend/Sources/Domain/Ports.swift` — add `EntityRepositoryPort` protocol
- `frontend/Sources/Infrastructure/APIEntityRepository.swift` — implements port
- `frontend/Sources/Bootstrap/CompositionRoot.swift` — wire entity repo
- `frontend/Sources/CortexApp/Viewer/DocumentDetailView.swift`
- `frontend/Sources/CortexApp/Sidebar/SidebarView.swift`

**Tasks:**

1. **Entity chips in document viewer**
   - Show extracted entities as colored chips below document title
   - Click entity → filter library by documents mentioning that entity
   - Entity type color coding (person=blue, org=green, tech=purple, etc.)

2. **Entity browser in sidebar**
   - "Entities" section in sidebar
   - Grouped by entity type
   - Click entity → show related documents in library view
   - Show mention count badge

3. **Search results with entities**
   - Show entity chips on search results
   - Entity-based search suggestions

4. **Verification:**
   - Document viewer shows entity chips
   - Clicking entity filters the library
   - Entity browser shows all entities grouped by type

---

## Phase 4: Polish & System Integration

**Goal:** macOS system integration, UX polish, advanced features, and operational robustness.

---

### Step 4.1: Collections & Organization

**Files to create/modify:**
- `backend/src/cortex/entrypoints/collections.py`
- `backend/src/cortex/application/collection_service.py`
- `frontend/Sources/CortexApp/Sidebar/CollectionRow.swift`

**Tasks:**

1. **Collection CRUD API**
2. **Drag documents to collections in sidebar**
3. **Nested collections (parent_id)**
4. **Smart collections (saved search queries)**
5. **Tag management (add/remove/autocomplete)**

---

### Step 4.2: Spotlight Integration (CoreSpotlight)

**Tasks:**

1. **Index documents in Spotlight**
   - Use CSSearchableItem for each document
   - Include title, content preview, file type, entities as keywords
   - Update index when documents are added/removed

2. **Handle Spotlight result taps**
   - Open Cortex app to the specific document

---

### Step 4.2.1: Search Suggestions

**Files to create:**
- `backend/src/cortex/entrypoints/search.py` — add `GET /search/suggestions` endpoint
- `frontend/Sources/CortexApp/Search/SearchSuggestionsView.swift`

**Tasks:**

1. **Implement `GET /api/v1/search/suggestions?q=prefix`**
   - Return recent search queries matching prefix
   - Return entity names matching prefix (from entities table)
   - Return document titles matching prefix
   - Limit to 5-10 suggestions per category

2. **Frontend integration**
   - Show suggestions below search field as user types
   - Selecting a suggestion fills the search field and triggers search

3. **Verification:**
   - Type partial query → suggestions appear from recent searches, entities, and titles

---

### Step 4.3: Advanced UI Polish

**Tasks:**

1. **Keyboard shortcuts throughout**
   - Full keyboard navigation
   - Vim-like j/k navigation in lists (optional)

2. **Dark mode optimization**
   - All views respect system appearance
   - Document renderers adapt CSS

3. **Onboarding experience**
   - First-launch: configure backend URL
   - Connection status indicator
   - Empty state illustrations

4. **Settings view**
   - Backend URL configuration
   - Search preferences (default weights, top_k)
   - Storage stats (document count, disk usage)

---

### Step 4.4: Backup & Restore

**Files to create:**
- `infrastructure/scripts/backup.sh`
- `infrastructure/scripts/restore.sh`

**Tasks:**

1. **Automated backup script**
   - PostgreSQL dump (pg_dump)
   - File directory tar (originals, thumbnails, images)
   - Compressed archive with timestamp

2. **Restore script**
   - Restore PostgreSQL from dump
   - Extract file archive
   - Rebuild indexes if needed

---

### Step 4.5: Monitoring & Observability

**Tasks:**

1. **Structured logging** (Python logging with JSON formatter)
2. **Processing metrics** (documents processed, average time, error rate)
3. **Search analytics** (query log, latency percentiles)
4. **System health dashboard** (accessible via API or simple web UI)

---

## Appendix A: Testing Strategy

Testing is aligned with the architectural layers. Services depend on `typing.Protocol` (Python) / Swift `protocol` — test doubles satisfy these structurally without mocking frameworks.

### Backend Tests

| Layer | Directory | Framework | Scope |
|-------|-----------|-----------|-------|
| Domain | `test_domain/` | pytest | Entity construction, value object equality, validation |
| Application | `test_application/` | pytest | Service orchestration with protocol test doubles |
| Infrastructure | `test_infrastructure/` | pytest + testcontainers | Real DB/Redis; adapter correctness |
| Entrypoints | `test_entrypoints/` | pytest + httpx | API endpoint contracts |
| End-to-end | `test_e2e/` | pytest + httpx | Full upload → process → search flow |

**Protocol test doubles (no mocking framework):**
```python
# tests/test_application/fakes.py
from cortex.domain.ports import EmbedderPort

class FakeEmbedder:
    """Satisfies EmbedderPort structurally — no base class needed."""
    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        return [[0.1] * 1024 for _ in texts]
    async def embed_query(self, query: str) -> list[float]:
        return [0.1] * 1024
```

### Frontend Tests

| Layer | Target | Framework | Scope |
|-------|--------|-----------|-------|
| Domain | `DomainTests` | XCTest | Codable conformance, entity equality |
| AppCore | `AppCoreTests` | XCTest | Service logic with protocol test doubles |
| Infrastructure | `InfrastructureTests` | XCTest | API client URL construction, response parsing |

**Protocol test doubles (no mocking framework):**
```swift
// Tests/AppCoreTests/Fakes.swift
final class FakeDocumentRepo: DocumentRepositoryPort {
    private(set) var deletedIDs: [UUID] = []
    func list(filters: DocumentFilters?) async throws -> [Document] { [] }
    func get(id: UUID) async throws -> Document { /* ... */ }
    func delete(id: UUID) async throws { deletedIDs.append(id) }
}
```

### Key Test Cases

1. Upload each supported file type → processes successfully → searchable
2. Search returns relevant results for known content
3. Duplicate document detection works
4. Large document (100+ pages) processes without OOM (GPU VRAM cleaned between parse stages via `torch.cuda.empty_cache()`)
5. Concurrent uploads don't corrupt data
6. Delete document removes all associated data (chunks, entities, graph nodes, files)
7. Search with filters returns correct subset
8. Reranker improves result ordering vs vector-only

---

## Appendix B: Development Environment Setup

### Prerequisites
- macOS with Xcode 15+ (for frontend development)
- Docker Desktop with NVIDIA GPU support on the workstation
- Python 3.11+ with uv
- Git

### Quick Start

```bash
# 1. Clone repository
git clone <repo-url> cortex && cd cortex

# 2. Start infrastructure
cd infrastructure
cp .env.example .env  # edit POSTGRES_PASSWORD
docker compose up -d

# 3. Run backend locally (for development)
cd ../backend
uv sync
uv run alembic upgrade head
uv run python -m cortex  # starts FastAPI via __main__.py

# 4. Build and run frontend (SPM-based)
cd ../frontend
swift build                 # verify SPM dependency graph compiles
open Package.swift          # opens in Xcode as SPM package
# Set backend URL in Settings, Build & Run (Cmd+R)
```

---

## Appendix C: Migration Path & Future Enhancements

### Potential Future Features (Post-V1)
- **LLM-powered Q&A**: Feed top search results to a local LLM for synthesized answers
- **Web clipper**: Browser extension to save web pages to Cortex
- **OCR pipeline**: For scanned PDFs without text layers
- **Audio/video transcription**: Whisper integration for media files
- **Multi-device sync**: Sync across multiple Macs
- **iOS companion app**: Read-only search and viewing
- **Relationship extraction**: LLM-based extraction of typed relationships between entities
- **Graph visualization**: Interactive knowledge graph explorer in the frontend
- **Auto-tagging**: LLM-generated tags and summaries for documents
- **Citation linking**: Detect and link academic citations across documents

### Technology Upgrade Path
- **Qwen3-Embedding-4B/8B**: Drop-in upgrade for better embedding quality (more VRAM)
- **ColBERT/ColPali**: Late-interaction models for potentially better retrieval
- **PostgreSQL 17+**: When AGE supports it, upgrade for latest PG features
- **vLLM**: Unified model serving for embedding + reranking + NER (single GPU process)
