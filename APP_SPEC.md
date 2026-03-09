# Cortex: Personal Knowledge Base — Application Specification

## Document Version: 1.0
## Date: 2026-03-08

---

## 1. Product Overview

### 1.1 Vision
Cortex is a personal knowledge base application that ingests documents in multiple formats (PDF, Markdown, Word, Excel), preserves their full formatting for retrieval and viewing, and provides powerful semantic search across the entire corpus. It combines a native macOS frontend with a GPU-accelerated backend running state-of-the-art ML models for embedding, NER, and reranking.

### 1.2 Target User
Single user (the owner) running the backend on a local GPU workstation (Lenovo P620) and the frontend on a Mac. This is a personal tool — no multi-tenancy, no cloud deployment.

### 1.3 Core Capabilities
1. **Document Ingestion**: Upload PDF, Markdown, DOCX, XLSX files via drag-and-drop or file picker
2. **Format Preservation**: Store original files and parsed structured representations; render documents in their native format within the app
3. **Semantic Search**: Natural language queries that find relevant information across all documents
4. **Full Document Retrieval**: View complete documents with preserved formatting, navigate to specific sections
5. **Knowledge Graph**: Automatically extract entities and relationships to enable graph-enhanced discovery
6. **Hybrid Search**: Combine vector similarity, BM25 keyword matching, and graph traversal for best results

---

## 2. System Architecture

### 2.1 Component Overview

| Component | Technology | Purpose |
|-----------|-----------|---------|
| macOS Frontend | Swift/SwiftUI + AppKit | Document management, viewing, search UI |
| API Server | Python FastAPI + Uvicorn | REST API, orchestration |
| Task Queue | Celery + Redis | Async document processing |
| Database | PostgreSQL 16 | Unified data store |
| Vector Search | pgvector (HNSW) | Semantic similarity search |
| Full-Text Search | pg_search (ParadeDB/Tantivy) | BM25 keyword search |
| Graph Database | Apache AGE | Knowledge graph (entities + relationships) |
| Embedding Model | Qwen3-Embedding-0.6B via TEI | Document and query embedding |
| Reranker | mxbai-rerank-large-v2 | Search result reranking |
| NER Model | GLiNER large v2.5 | Named entity recognition |
| Document Parser | Docling (primary, GPU-accelerated) + fallbacks | Multi-format document parsing |
| Chunker | Chonkie | Intelligent text chunking |
| File Storage | Local filesystem | Original files, thumbnails, images |

### 2.2 Infrastructure

**Docker Compose Services:**

```yaml
services:
  postgres:        # PostgreSQL 16 + pgvector + pg_search + AGE
  redis:           # Task queue broker + result backend
  embedder:        # TEI serving Qwen3-Embedding-0.6B (GPU)
  api:             # FastAPI application server
  worker:          # Celery worker for async processing (GPU access)
```

**Networking:**
- All services communicate on internal Docker network
- Only API server exposes port to host (e.g., 8080)
- macOS frontend connects to API server via `http://<workstation-ip>:8090`

### 2.3 Directory Structure

The backend follows a layered architecture with `typing.Protocol`-based dependency inversion. The frontend uses SPM multi-target modules with compiler-enforced dependency boundaries. Both follow the principle: **dependencies point inward** (entrypoints → application → domain ← infrastructure).

```
cortex/
├── backend/
│   ├── pyproject.toml              # Python project config (uv)
│   ├── alembic/                    # Database migrations
│   │   ├── alembic.ini
│   │   └── versions/
│   ├── src/
│   │   └── cortex/
│   │       ├── __init__.py
│   │       ├── __main__.py         # Entry point for `python -m cortex`
│   │       ├── bootstrap.py        # Composition root — wires all dependencies
│   │       ├── settings.py         # Pydantic BaseSettings (env vars, .env)
│   │       │
│   │       ├── domain/             # Core business types + abstract ports
│   │       │   ├── __init__.py
│   │       │   ├── document.py     # Document entity, value objects
│   │       │   ├── chunk.py        # Chunk entity
│   │       │   ├── entity.py       # NER entity types
│   │       │   └── ports.py        # Abstract interfaces (typing.Protocol)
│   │       │                       #   ParserPort, ChunkerPort, EmbedderPort,
│   │       │                       #   RerankerPort, NERPort, GraphPort,
│   │       │                       #   DocumentRepository, ChunkRepository,
│   │       │                       #   FileStorage
│   │       │
│   │       ├── application/        # Use-case orchestration (depends on domain only)
│   │       │   ├── __init__.py
│   │       │   ├── ingestion_service.py   # Orchestrates parse→chunk→embed→NER→graph
│   │       │   ├── search_service.py      # Orchestrates hybrid search + rerank
│   │       │   └── document_service.py    # CRUD operations on documents
│   │       │
│   │       ├── infrastructure/     # Concrete adapters (implements domain ports)
│   │       │   ├── __init__.py
│   │       │   ├── persistence/
│   │       │   │   ├── __init__.py
│   │       │   │   ├── database.py        # AsyncSession factory, engine setup
│   │       │   │   ├── tables.py          # SQLAlchemy 2.0 table models (ORM)
│   │       │   │   ├── document_repo.py   # DocumentRepository implementation
│   │       │   │   └── chunk_repo.py      # ChunkRepository implementation
│   │       │   ├── search/
│   │       │   │   ├── __init__.py
│   │       │   │   ├── vector_search.py   # pgvector HNSW search
│   │       │   │   ├── bm25_search.py     # pg_search BM25 search
│   │       │   │   └── graph_search.py    # Apache AGE graph traversal
│   │       │   ├── ml/
│   │       │   │   ├── __init__.py
│   │       │   │   ├── docling_parser.py  # Docling DocumentConverter (GPU)
│   │       │   │   ├── chonkie_chunker.py # Chonkie SemanticChunker
│   │       │   │   ├── tei_embedder.py    # TEI HTTP client for Qwen3-Embedding
│   │       │   │   ├── mxbai_reranker.py  # mxbai-rerank-large-v2 (GPU)
│   │       │   │   └── gliner_ner.py      # GLiNER large v2.5 (GPU)
│   │       │   ├── graph/
│   │       │   │   ├── __init__.py
│   │       │   │   └── age_repository.py  # Apache AGE Cypher operations
│   │       │   └── file_storage.py        # Local filesystem storage
│   │       │
│   │       ├── entrypoints/        # Transport layer (FastAPI routes, CLI)
│   │       │   ├── __init__.py
│   │       │   ├── app.py          # FastAPI app factory, CORS, lifespan
│   │       │   ├── router.py       # Main API router
│   │       │   ├── documents.py    # Document CRUD endpoints
│   │       │   ├── search.py       # Search endpoints
│   │       │   ├── entities.py     # Entity/graph endpoints
│   │       │   └── status.py       # Health/status endpoints
│   │       │
│   │       ├── schemas/            # Pydantic request/response schemas (transport)
│   │       │   ├── __init__.py
│   │       │   ├── document_schemas.py
│   │       │   ├── search_schemas.py
│   │       │   └── entity_schemas.py
│   │       │
│   │       └── tasks/              # Async task definitions (Celery)
│   │           ├── __init__.py
│   │           ├── celery_app.py   # Celery configuration
│   │           └── ingest.py       # Document ingestion task
│   │
│   ├── tests/
│   │   ├── conftest.py
│   │   ├── test_domain/            # Unit tests for entities, value objects
│   │   ├── test_application/       # Unit tests for services (protocol test doubles)
│   │   ├── test_infrastructure/    # Integration tests against real deps
│   │   └── test_entrypoints/       # API endpoint tests (httpx)
│   └── Dockerfile
│
├── frontend/                       # Swift/SwiftUI macOS app (SPM multi-target)
│   ├── Package.swift               # SPM manifest with compiler-enforced deps
│   ├── Sources/
│   │   ├── Domain/                 # Target: entities, value objects, ports (protocols)
│   │   │   ├── Document.swift      # Document struct (Sendable, Equatable)
│   │   │   ├── SearchResult.swift  # SearchResult struct
│   │   │   ├── Entity.swift        # Entity struct
│   │   │   ├── Collection.swift    # Collection struct
│   │   │   └── Ports.swift         # DocumentRepositoryPort, SearchPort protocols
│   │   │
│   │   ├── AppCore/                # Target: use-case services (depends: Domain)
│   │   │   ├── DocumentService.swift     # Document CRUD orchestration
│   │   │   ├── SearchService.swift       # Search orchestration + debouncing
│   │   │   └── IngestionService.swift    # Upload + status tracking
│   │   │
│   │   ├── Infrastructure/         # Target: concrete adapters (depends: Domain)
│   │   │   ├── APIClient.swift           # URLSession-based HTTP client
│   │   │   ├── APIDocumentRepository.swift # Implements DocumentRepositoryPort
│   │   │   ├── APISearchRepository.swift # Implements SearchPort
│   │   │   ├── WebSocketClient.swift     # Real-time event stream
│   │   │   ├── MarkdownRenderer.swift    # swift-markdown → HTML conversion
│   │   │   └── ThumbnailLoader.swift     # Async thumbnail loading + cache
│   │   │
│   │   ├── Bootstrap/              # Target: composition root (depends: all above)
│   │   │   ├── CompositionRoot.swift     # Wires concrete impls to protocols
│   │   │   └── Settings.swift            # Backend URL, preferences
│   │   │
│   │   └── CortexApp/              # Target: SwiftUI views + app entry (depends: Bootstrap)
│   │       ├── CortexApp.swift           # @main entry point
│   │       ├── ContentView.swift         # Root NavigationSplitView
│   │       ├── Sidebar/
│   │       │   ├── SidebarView.swift
│   │       │   └── CollectionRow.swift
│   │       ├── Library/
│   │       │   ├── DocumentLibraryView.swift
│   │       │   ├── DocumentGridItem.swift
│   │       │   └── DocumentListRow.swift
│   │       ├── Viewer/
│   │       │   ├── DocumentDetailView.swift
│   │       │   ├── PDFDocumentView.swift      # NSViewRepresentable<PDFView>
│   │       │   ├── MarkdownDocumentView.swift  # NSViewRepresentable<WKWebView>
│   │       │   ├── HTMLDocumentView.swift
│   │       │   └── SpreadsheetView.swift
│   │       ├── Search/
│   │       │   ├── SearchOverlayView.swift
│   │       │   ├── SearchResultRow.swift
│   │       │   └── SearchFiltersView.swift
│   │       └── Ingestion/
│   │           ├── DocumentDropZone.swift
│   │           ├── ImportProgressView.swift
│   │           └── ProcessingStatusView.swift
│   │
│   └── Tests/
│       ├── DomainTests/
│       ├── AppCoreTests/           # Protocol test doubles, no mocking framework
│       └── InfrastructureTests/
│
├── infrastructure/
│   ├── docker-compose.yml
│   ├── docker-compose.dev.yml
│   ├── postgres/
│   │   ├── Dockerfile              # Custom PG 16 with all extensions
│   │   ├── init.sql                # Extension creation only (tables via Alembic)
│   │   └── postgresql.conf         # Tuned configuration
│   ├── embedder/
│   │   └── docker-compose.override.yml
│   └── scripts/
│       ├── setup.sh                # One-click setup
│       ├── backup.sh               # Database backup
│       └── restore.sh              # Database restore
├── docs/
│   ├── ARCHITECTURE_BRAINSTORM.md
│   ├── APP_SPEC.md                 # This document
│   └── IMPLEMENTATION_PLAN.md
└── README.md
```

### 2.4 Dependency Direction (Compiler/Convention Enforced)

**Python backend** (enforced by convention + imports):
```
entrypoints/ → application/ → domain/ ← infrastructure/
                                  ↑
                            bootstrap.py (wires infrastructure → domain ports)
```

**Swift frontend** (enforced by SPM `dependencies` array):
```swift
// Package.swift target dependencies
Domain:         []                                    // depends on nothing
AppCore:        ["Domain"]                            // depends on domain only
Infrastructure: ["Domain"]                            // depends on domain only
Bootstrap:      ["Domain", "AppCore", "Infrastructure"] // wires everything
CortexApp:      ["Bootstrap"]                         // depends on composition root
```

Services in `application/` / `AppCore` depend on abstract ports defined in `domain/` / `Domain`. Concrete implementations in `infrastructure/` / `Infrastructure` satisfy those ports. The composition root (`bootstrap.py` / `CompositionRoot.swift`) is the **only** place that imports both.

---

## 3. Database Schema

### 3.1 PostgreSQL Extensions

```sql
-- Required extensions
CREATE EXTENSION IF NOT EXISTS vector;          -- pgvector
CREATE EXTENSION IF NOT EXISTS pg_search;       -- ParadeDB BM25
LOAD 'age';                                     -- Apache AGE
SET search_path = ag_catalog, "$user", public;
SELECT create_graph('knowledge_graph');
```

### 3.2 Core Tables

**Table creation order:** collections must be created before documents (FK dependency).

**Status values (canonical, used everywhere):**
`uploading` → `stored` → `parsing` → `parsed` → `chunking` → `chunked` → `embedding` → `embedded` → `extracting_entities` → `entities_extracted` → `building_graph` → `ready` | `failed`

**Duplicate handling:** One canonical document per SHA-256 hash. Uploading a file whose hash already exists returns the existing document ID (HTTP 200, not 409). Reprocessing is explicit via `POST /documents/{id}/reprocess`. If the same content should appear in multiple collections, use collection membership — not duplicate rows.

**File type scope:** Accepted types for ingestion are `pdf`, `markdown`, `docx`, `xlsx`, `txt`, and common image formats (`png`, `jpg`, `tiff`). The viewer supports all of these. Plain text and images are simple enough that parsing is trivial; they are included from Phase 1.

```sql
-- Collections table (MUST be created before documents due to FK)
CREATE TABLE collections (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name            TEXT NOT NULL,
    description     TEXT,
    icon            TEXT,                    -- SF Symbol name
    parent_id       UUID REFERENCES collections(id),
    sort_order      INTEGER DEFAULT 0,

    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Documents table: stores document metadata and parsed content
CREATE TABLE documents (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    title           TEXT NOT NULL,
    original_filename TEXT NOT NULL,
    file_type       TEXT NOT NULL,           -- 'pdf', 'markdown', 'docx', 'xlsx', 'txt', 'png', etc.
    file_size_bytes BIGINT NOT NULL,
    file_hash       TEXT NOT NULL,           -- SHA-256 for deduplication
    mime_type       TEXT NOT NULL,

    -- Storage paths (relative to data root)
    original_path   TEXT NOT NULL,           -- path to original file
    thumbnail_path  TEXT,                    -- path to thumbnail image

    -- Parsed content
    parsed_content  JSONB,                   -- DoclingDocument JSON structure
    rendered_markdown TEXT,                  -- Markdown rendering of content
    rendered_html   TEXT,                    -- HTML rendering (structured view for DOCX/XLSX)

    -- Metadata
    page_count      INTEGER,
    word_count      INTEGER,
    language        TEXT DEFAULT 'en',
    author          TEXT,
    subject         TEXT,

    -- Processing status (canonical values — use these everywhere)
    status          TEXT NOT NULL DEFAULT 'uploading',
    -- Lifecycle: uploading → stored → parsing → parsed → chunking → chunked →
    --            embedding → embedded → extracting_entities → entities_extracted →
    --            building_graph → ready | failed
    error_message   TEXT,

    -- Timestamps
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    processed_at    TIMESTAMPTZ,

    -- User organization
    collection_id   UUID REFERENCES collections(id) ON DELETE SET NULL,
    tags            TEXT[] DEFAULT '{}',
    is_favorite     BOOLEAN DEFAULT FALSE,

    CONSTRAINT unique_file_hash UNIQUE (file_hash)
);

-- Chunks table: stores chunked text with embeddings
CREATE TABLE chunks (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id     UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,

    -- Chunk content
    chunk_text      TEXT NOT NULL,
    chunk_index     INTEGER NOT NULL,        -- sequential order within document
    start_char      INTEGER NOT NULL,        -- start character offset in original text
    end_char        INTEGER NOT NULL,        -- end character offset
    token_count     INTEGER NOT NULL,

    -- Structural context
    section_heading TEXT,                    -- nearest heading above this chunk
    section_level   INTEGER,                -- heading level (1-6)
    page_number     INTEGER,                -- source page (for PDFs)

    -- Embedding vector
    embedding       vector(1024),            -- Qwen3-Embedding-0.6B output

    -- Timestamps
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT unique_chunk_order UNIQUE (document_id, chunk_index)
);

-- Entities table: stores extracted named entities
CREATE TABLE entities (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name            TEXT NOT NULL,
    entity_type     TEXT NOT NULL,           -- 'person', 'organization', 'technology', etc.
    normalized_name TEXT NOT NULL,           -- lowercase, stripped for deduplication
    description     TEXT,

    -- Aggregate stats
    document_count  INTEGER DEFAULT 0,
    mention_count   INTEGER DEFAULT 0,

    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT unique_entity UNIQUE (normalized_name, entity_type)
);

-- Entity mentions: links entities to specific chunks
CREATE TABLE entity_mentions (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    entity_id       UUID NOT NULL REFERENCES entities(id) ON DELETE CASCADE,
    chunk_id        UUID NOT NULL REFERENCES chunks(id) ON DELETE CASCADE,
    document_id     UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,

    -- Mention details
    mention_text    TEXT NOT NULL,           -- exact text span
    start_char      INTEGER NOT NULL,        -- position within chunk
    end_char        INTEGER NOT NULL,
    confidence      FLOAT NOT NULL,          -- GLiNER confidence score

    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT unique_mention UNIQUE (entity_id, chunk_id, start_char)
);

-- (collections table defined above, before documents)

-- Extracted images from documents
CREATE TABLE document_images (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id     UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    image_path      TEXT NOT NULL,           -- filesystem path
    page_number     INTEGER,
    caption         TEXT,
    alt_text        TEXT,
    width           INTEGER,
    height          INTEGER,

    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

### 3.3 Indexes

```sql
-- pgvector HNSW index for semantic search
CREATE INDEX idx_chunks_embedding ON chunks
    USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 200);

-- pg_search BM25 index for full-text search
CALL paradedb.create_bm25(
    index_name => 'idx_chunks_bm25',
    table_name => 'chunks',
    key_field => 'id',
    text_fields => paradedb.field('chunk_text', tokenizer => paradedb.tokenizer('en_stem'))
);

-- Document-level BM25 index for document title/content search
CALL paradedb.create_bm25(
    index_name => 'idx_documents_bm25',
    table_name => 'documents',
    key_field => 'id',
    text_fields => paradedb.field('title', tokenizer => paradedb.tokenizer('en_stem'))
                   || paradedb.field('rendered_markdown', tokenizer => paradedb.tokenizer('en_stem'))
);

-- Standard B-tree indexes
CREATE INDEX idx_documents_status ON documents(status);
CREATE INDEX idx_documents_file_type ON documents(file_type);
CREATE INDEX idx_documents_created_at ON documents(created_at DESC);
CREATE INDEX idx_documents_collection ON documents(collection_id);
CREATE INDEX idx_documents_tags ON documents USING gin(tags);
CREATE INDEX idx_chunks_document ON chunks(document_id);
CREATE INDEX idx_entities_type ON entities(entity_type);
CREATE INDEX idx_entities_normalized ON entities(normalized_name);
CREATE INDEX idx_entity_mentions_entity ON entity_mentions(entity_id);
CREATE INDEX idx_entity_mentions_document ON entity_mentions(document_id);
```

### 3.4 Apache AGE Knowledge Graph Schema

```sql
-- Graph nodes (created dynamically during NER processing)

-- Entity node: {name, type, normalized_name, mention_count}
-- Document node: {doc_id, title, file_type}

-- Graph edges:
-- (Document)-[:MENTIONS {count, confidence_avg}]->(Entity)
-- (Entity)-[:CO_OCCURS {count, strength}]->(Entity)
-- (Entity)-[:RELATED_TO {relation_type}]->(Entity)  -- future: LLM-extracted
```

---

## 4. API Specification

### 4.1 Base URL
```
http://<workstation-ip>:8090/api/v1
```

### 4.2 Endpoints

#### Documents

| Method | Path | Description |
|--------|------|-------------|
| POST | /documents | Upload and ingest a document |
| GET | /documents | List all documents (paginated, filterable) |
| GET | /documents/{id} | Get document metadata |
| GET | /documents/{id}/content?view=structured\|fidelity | Get document content (structured HTML/JSON or original file URL) |
| GET | /documents/{id}/original | Download original file |
| GET | /documents/{id}/thumbnail | Get document thumbnail |
| GET | /documents/{id}/chunks | Get all chunks for a document |
| GET | /documents/{id}/entities | Get entities extracted from document |
| POST | /documents/{id}/reprocess | Re-run ingestion pipeline on existing document |
| DELETE | /documents/{id} | Delete document and all associated data |
| PATCH | /documents/{id} | Update document metadata (tags, collection, favorite) |

#### Search

| Method | Path | Description |
|--------|------|-------------|
| POST | /search | Semantic search across corpus |
| POST | /search/documents | Search for whole documents (not chunks) |
| GET | /search/suggestions | Get search suggestions/autocomplete (Phase 4) |

#### Entities

| Method | Path | Description |
|--------|------|-------------|
| GET | /entities | List all entities (paginated, filterable by type) |
| GET | /entities/{id} | Get entity details with related documents |
| GET | /entities/{id}/related | Get related entities from graph |
| GET | /graph/explore | Explore knowledge graph from a starting entity |

#### Collections

| Method | Path | Description |
|--------|------|-------------|
| POST | /collections | Create a collection |
| GET | /collections | List collections |
| PATCH | /collections/{id} | Update collection |
| DELETE | /collections/{id} | Delete collection |

#### System

| Method | Path | Description |
|--------|------|-------------|
| GET | /health | Health check |
| GET | /status/processing | Get processing queue status |
| WebSocket | /ws/events | Real-time event stream (processing updates) |

### 4.3 Key Request/Response Schemas

```python
# POST /documents (multipart form data)
# Request: file upload + optional metadata
# Response:
class DocumentUploadResponse(BaseModel):
    id: UUID
    status: str  # "uploading" (or existing doc ID if duplicate hash)
    message: str
    is_duplicate: bool = False  # True if hash matched existing document

# POST /search
class SearchRequest(BaseModel):
    query: str
    top_k: int = 10
    filters: Optional[SearchFilters] = None
    include_graph: bool = True
    rerank: bool = True

class SearchFilters(BaseModel):
    file_types: Optional[list[str]] = None
    collection_ids: Optional[list[UUID]] = None
    date_from: Optional[datetime] = None
    date_to: Optional[datetime] = None
    tags: Optional[list[str]] = None
    entity_types: Optional[list[str]] = None

class SearchResponse(BaseModel):
    query: str
    results: list[SearchResult]
    total_candidates: int
    search_time_ms: float

class SearchResult(BaseModel):
    chunk_id: UUID
    document_id: UUID
    document_title: str
    document_type: str
    chunk_text: str
    highlighted_snippet: str
    section_heading: Optional[str]
    page_number: Optional[int]
    score: float
    score_breakdown: ScoreBreakdown
    entities: list[EntityMention]

    # Anchor fields for "jump to hit" navigation
    chunk_start_char: int           # character offset in the full document text
    chunk_end_char: int             # end character offset
    anchor_id: Optional[str]       # HTML anchor ID for structured views (e.g., "chunk-7")
    # For PDFs: page_number is used to scroll PDFView to the right page
    # For Markdown/HTML: anchor_id is injected into rendered HTML as <span id="chunk-7">
    # For DOCX/XLSX: opens structured view scrolled to anchor_id

class ScoreBreakdown(BaseModel):
    vector_score: Optional[float]
    bm25_score: Optional[float]
    graph_score: Optional[float]
    rerank_score: Optional[float]

# GET /documents/{id}/content?view=structured|fidelity
class DocumentContent(BaseModel):
    id: UUID
    format: str  # "pdf_url", "html", "markdown", "spreadsheet_json", "image_url", "plain_text"
    content: str  # URL for PDF/image, HTML string, Markdown string, plain text, or JSON
    original_url: str  # always available — URL to download the original file
    metadata: DocumentMetadata

# WebSocket event types for /ws/events
class ProcessingEvent(BaseModel):
    event_type: str  # "status_changed", "processing_progress", "processing_complete", "processing_failed"
    document_id: UUID
    status: str           # canonical status value
    progress_pct: Optional[float]  # 0.0-1.0
    stage_label: Optional[str]     # human-readable: "Parsing document...", "Generating embeddings..."
    error_message: Optional[str]
```

---

## 5. macOS Frontend Specification

### 5.1 Main Window Layout

```
┌──────────────────────────────────────────────────────────────────┐
│ ◉ ◉ ◉  │  ← →  │  Cortex — Personal Knowledge Base     │ 🔍  │
├─────────┼────────────────────────┼───────────────────────────────┤
│         │                        │                               │
│ SIDEBAR │    DOCUMENT LIST       │      DOCUMENT VIEWER          │
│         │                        │                               │
│ 📚 All  │  ┌──────┐ ┌──────┐   │  ┌─────────────────────────┐  │
│ ⭐ Favs │  │ Doc  │ │ Doc  │   │  │                         │  │
│ 🏷 Tags │  │ thumb│ │ thumb│   │  │   [Rendered Document]    │  │
│         │  │      │ │      │   │  │                         │  │
│ ── Cols │  │ Title│ │ Title│   │  │   PDF via PDFKit        │  │
│ 📁 Work │  │ Date │ │ Date │   │  │   MD via WKWebView      │  │
│ 📁 Pers │  └──────┘ └──────┘   │  │   HTML via WKWebView    │  │
│         │                        │  │                         │  │
│ ── Types│  ┌──────┐ ┌──────┐   │  │                         │  │
│ 📄 PDFs │  │ Doc  │ │ Doc  │   │  │                         │  │
│ 📝 Notes│  │ thumb│ │ thumb│   │  └─────────────────────────┘  │
│ 📊 Excel│  │      │ │      │   │                               │
│         │  │ Title│ │ Title│   │  Entities: [person] [org]     │
│ ── Graph│  │ Date │ │ Date │   │  Tags: [tag1] [tag2]         │
│ 🔗 Ents │  └──────┘ └──────┘   │                               │
│         │                        │                               │
│ + New   │  Grid ☐ │ List ☰     │                               │
│ Import  │  Sort: Date Added ▼   │                               │
├─────────┴────────────────────────┴───────────────────────────────┤
│  Status: Ready │ 1,234 documents │ 45,678 chunks indexed        │
└──────────────────────────────────────────────────────────────────┘
```

### 5.2 Search Overlay (Cmd+K)

```
┌───────────────────────────────────────────────────┐
│  🔍  Search your knowledge base...               │
├───────────────────────────────────────────────────┤
│                                                   │
│  📄 Understanding Neural Networks                 │
│     "...backpropagation algorithm computes the    │
│     gradient of the loss function with respect    │
│     to each weight..."                            │
│     Chapter 3 • deep_learning.pdf • Score: 0.94   │
│                                                   │
│  📝 Meeting Notes - ML Architecture Review        │
│     "...decided to use transformer-based          │
│     architecture for the new recommendation       │
│     system..."                                    │
│     notes_2024_03.md • Score: 0.87                │
│                                                   │
│  📊 Model Performance Comparison                  │
│     "...BERT-large achieved 92.3% accuracy on     │
│     the validation set, compared to..."           │
│     Sheet: Results • models.xlsx • Score: 0.82    │
│                                                   │
│  ─── 7 more results ───                           │
│                                                   │
│  Filters: [All Types ▼] [All Collections ▼]      │
└───────────────────────────────────────────────────┘
```

### 5.3 Key UI Interactions

1. **Document Import**: Drag files onto drop zone OR File > Import (Cmd+I) OR toolbar button
2. **Search**: Cmd+K opens spotlight overlay; typing triggers debounced search
3. **Document Navigation**: Click search result → opens document viewer at the hit location:
   - **PDF**: Scrolls PDFView to `page_number` from the search result
   - **Markdown/HTML**: Opens rendered view scrolled to `anchor_id` (`<span id="chunk-N">`)
   - **DOCX/XLSX**: Opens structured view scrolled to `anchor_id`; user can switch to fidelity view (original file via QuickLook) — exact hit-jump in fidelity view is best-effort only
4. **View Modes**: Grid (thumbnails) / List (table) toggle in document list
5. **Collections**: Drag documents to sidebar collections; create smart collections with saved searches
6. **Keyboard Shortcuts**:
   - `Cmd+K` — Open search
   - `Cmd+I` — Import document
   - `Cmd+1/2/3` — Switch sidebar sections
   - `Cmd+D` — Toggle favorite
   - `Space` — Quick Look preview
   - `Enter` — Open selected document
   - `Cmd+F` — Find within document (client-side)

### 5.4 Document Viewer Behavior

**Dual-representation strategy for DOCX/XLSX:** These formats use two viewer modes because backend-converted HTML/JSON is a high-quality approximation but not pixel-identical to the original. The original file is always the source of truth for viewing; the parsed version is the source of truth for search, chunking, and entity extraction.

| File Type | Default Viewer | Fidelity Viewer | Features |
|-----------|---------------|-----------------|----------|
| PDF | PDFKit (PDFView) | _(same)_ | Scroll, zoom, page navigation, text search, outline/TOC. Search hits scroll to `page_number`. |
| Markdown | WKWebView (rendered HTML) | _(same)_ | Syntax highlighting, dark mode. Search hits scroll to `anchor_id`. |
| DOCX | WKWebView (structured HTML) | QuickLook (original file) | Structured view supports anchor navigation for search hits. Toggle to fidelity view for exact formatting. |
| XLSX | Custom SwiftUI Table (structured JSON) | QuickLook (original file) | Sheet tabs, cell formatting. Structured view supports search-hit anchoring. Toggle to fidelity view. |
| Plain Text | SwiftUI Text/ScrollView | _(same)_ | Monospace rendering. |
| Images | SwiftUI Image | _(same)_ | Zoom, pan. |

**Viewer mode toggle:** DOCX and XLSX show a segmented control in the toolbar: `Structured | Original`. Structured view is the default (supports search anchoring and entity chips). Original view renders via QuickLook/QLPreviewView for full formatting fidelity.

---

## 6. Backend Service Details

### 6.0 Domain Ports (`domain/ports.py`)

All services depend on abstract `typing.Protocol` interfaces — never on concrete infrastructure. This enables testing with protocol-based test doubles and swapping implementations without touching service code.

```python
# domain/ports.py
from typing import Protocol
from cortex.domain.document import Document, ParseResult
from cortex.domain.chunk import Chunk, ChunkResult

class ParserPort(Protocol):
    """Parses documents into structured content."""
    async def parse(self, file_path: Path, file_type: str) -> ParseResult: ...

class ChunkerPort(Protocol):
    """Chunks text into retrieval-sized pieces."""
    def chunk_document(self, text: str, structured_content: dict) -> list[ChunkResult]: ...

class EmbedderPort(Protocol):
    """Embeds text into dense vectors."""
    async def embed_texts(self, texts: list[str]) -> list[list[float]]: ...
    async def embed_query(self, query: str) -> list[float]: ...

class RerankerPort(Protocol):
    """Reranks search candidates by relevance."""
    async def rerank(self, query: str, documents: list[str], top_k: int) -> list[RerankResult]: ...

class NERPort(Protocol):
    """Extracts named entities from text."""
    def extract_entities(self, chunks: list[ChunkResult], threshold: float) -> list[EntityExtraction]: ...

class DocumentRepository(Protocol):
    """Persists and retrieves document records."""
    async def save(self, document: Document) -> None: ...
    async def get(self, document_id: UUID) -> Document | None: ...
    async def list_all(self, filters: dict | None = None) -> list[Document]: ...
    async def delete(self, document_id: UUID) -> None: ...

class ChunkRepository(Protocol):
    """Persists and retrieves chunks with vectors."""
    async def save_chunks(self, chunks: list[Chunk]) -> None: ...
    async def vector_search(self, query_vec: list[float], top_k: int) -> list[ScoredChunk]: ...
    async def bm25_search(self, query: str, top_k: int) -> list[ScoredChunk]: ...

class GraphPort(Protocol):
    """Knowledge graph operations."""
    async def add_document_entities(self, doc_id: UUID, entities: list[EntityExtraction]) -> None: ...
    async def get_related_entities(self, entity_id: UUID, hops: int) -> list[Entity]: ...

class FileStoragePort(Protocol):
    """Stores and retrieves files on disk."""
    async def save_original(self, file_data: bytes, document_id: UUID, filename: str) -> str: ...
    async def get_original_path(self, document_id: UUID) -> Path: ...
    async def delete_document_files(self, document_id: UUID) -> None: ...
```

### 6.0.1 Composition Root (`bootstrap.py`)

The single place where concrete implementations are wired to abstract ports. This is the **only** module that imports both application services and infrastructure adapters.

```python
# bootstrap.py
from cortex.settings import Settings
from cortex.application.ingestion_service import IngestionService
from cortex.application.search_service import SearchService
from cortex.application.document_service import DocumentService
from cortex.infrastructure.ml.docling_parser import DoclingParser
from cortex.infrastructure.ml.chonkie_chunker import ChonkieChunker
from cortex.infrastructure.ml.tei_embedder import TEIEmbedder
from cortex.infrastructure.ml.mxbai_reranker import MxbaiReranker
from cortex.infrastructure.ml.gliner_ner import GlinerNER
from cortex.infrastructure.persistence.document_repo import PGDocumentRepository
from cortex.infrastructure.persistence.chunk_repo import PGChunkRepository
from cortex.infrastructure.graph.age_repository import AGEGraphRepository
from cortex.infrastructure.file_storage import LocalFileStorage

class CompositionRoot:
    """Wires concrete infrastructure to abstract domain ports."""

    def __init__(self, settings: Settings, db_session_factory):
        # Infrastructure adapters
        parser = DoclingParser()
        chunker = ChonkieChunker(embedding_model=settings.embedding_model)
        embedder = TEIEmbedder(base_url=settings.embedder_url)
        reranker = MxbaiReranker()
        ner = GlinerNER()
        doc_repo = PGDocumentRepository(db_session_factory)
        chunk_repo = PGChunkRepository(db_session_factory)
        graph_repo = AGEGraphRepository(db_session_factory)
        file_storage = LocalFileStorage(data_dir=settings.data_dir)

        # Application services (depend on ports, not concrete types)
        self.ingestion_service = IngestionService(
            parser=parser,
            chunker=chunker,
            embedder=embedder,
            ner=ner,
            graph=graph_repo,
            doc_repo=doc_repo,
            chunk_repo=chunk_repo,
            file_storage=file_storage,
        )
        self.search_service = SearchService(
            embedder=embedder,
            reranker=reranker,
            chunk_repo=chunk_repo,
            graph=graph_repo,
        )
        self.document_service = DocumentService(
            doc_repo=doc_repo,
            file_storage=file_storage,
        )
```

### 6.1 Document Parser Service (`infrastructure/ml/docling_parser.py`)

```python
class DocumentParser:
    """Multi-format document parser using Docling as primary engine.

    Docling's ML models (layout detection via RT-DETR, TableFormer for tables,
    OCR via EasyOCR) are GPU-accelerated via PyTorch CUDA, delivering ~6.5x
    speedup over CPU (~0.48s/page vs ~3.1s/page on NVIDIA L4 benchmarks).

    GPU acceleration details:
    - Layout model: 14.4x speedup (633ms → 44ms/page)
    - TableFormer:  4.3x speedup (1.74s → 400ms/table)
    - OCR (EasyOCR): 8.1x speedup (13s → 1.6s/page)
    - VRAM usage: ~1-2 GB for model weights
    - Auto-detects CUDA; explicit config for optimal batch sizes

    Caveats:
    - TableFormer does not support GPU batching yet (processes tables sequentially)
    - Call torch.cuda.empty_cache() between documents to prevent VRAM leaks
    - For OCR: use EasyOCR, not RapidOCR with ONNX backend (ignores GPU)
    """

    def __init__(self):
        from docling.datamodel.accelerator_options import (
            AcceleratorDevice,
            AcceleratorOptions,
        )
        from docling.datamodel.pipeline_options import ThreadedPdfPipelineOptions

        # GPU acceleration: auto-detect CUDA, tune batch sizes for RTX 3090
        accelerator_options = AcceleratorOptions(
            device=AcceleratorDevice.AUTO,  # CUDA if available, else CPU
        )
        pipeline_options = ThreadedPdfPipelineOptions(
            layout_batch_size=32,    # default is 4; increase for GPU throughput
            ocr_batch_size=32,       # default is 4; increase for GPU throughput
            table_batch_size=4,      # GPU batching not yet supported for tables
        )

        self.docling_converter = DocumentConverter(
            pipeline_options=pipeline_options,
            accelerator_options=accelerator_options,
        )
        self.pymupdf_available = True  # for fast PDF operations

    async def parse(self, file_path: Path, file_type: str) -> ParseResult:
        """Parse a document and return structured content."""
        # Route to appropriate parser
        if file_type == 'pdf':
            return await self._parse_pdf(file_path)
        elif file_type == 'docx':
            return await self._parse_docx(file_path)
        elif file_type == 'xlsx':
            return await self._parse_xlsx(file_path)
        elif file_type == 'markdown':
            return await self._parse_markdown(file_path)
        else:
            raise UnsupportedFormatError(f"Unsupported: {file_type}")

    async def _parse_pdf(self, file_path: Path) -> ParseResult:
        """Parse PDF using Docling (GPU-accelerated), with PyMuPDF for thumbnails/images."""
        # 1. Docling for structural parsing (GPU-accelerated layout + table detection)
        result = self.docling_converter.convert(str(file_path))
        doc = result.document  # DoclingDocument

        # Prevent VRAM leaks between documents
        import torch
        if torch.cuda.is_available():
            torch.cuda.empty_cache()

        # 2. PyMuPDF for thumbnail and image extraction (CPU, very fast)
        pdf_doc = fitz.open(str(file_path))
        thumbnail = self._generate_thumbnail(pdf_doc)
        images = self._extract_images(pdf_doc)

        return ParseResult(
            text=doc.export_to_markdown(),
            structured=doc.export_to_dict(),
            rendered_html=doc.export_to_html(),
            metadata=self._extract_metadata(doc, pdf_doc),
            images=images,
            thumbnail=thumbnail,
            page_count=len(pdf_doc)
        )
```

### 6.2 Chunker Service (`infrastructure/ml/chonkie_chunker.py`)

```python
class ChunkerService:
    """Text chunking using Chonkie with semantic awareness."""

    def __init__(self, embedding_model: str = "Qwen/Qwen3-Embedding-0.6B"):
        self.semantic_chunker = SemanticChunker(
            embedding_model=embedding_model,
            chunk_size=512,
            chunk_overlap=64,
            similarity_threshold=0.5,
        )
        self.recursive_chunker = RecursiveChunker(
            tokenizer="Qwen/Qwen3-Embedding-0.6B",
            chunk_size=512,
            chunk_overlap=64,
            separators=["\n\n", "\n", ". ", " "],
        )

    def chunk_document(
        self,
        text: str,
        structured_content: dict,
        strategy: str = "semantic"
    ) -> list[ChunkResult]:
        """Chunk document text with section context preservation."""
        # Choose chunker
        chunker = self.semantic_chunker if strategy == "semantic" else self.recursive_chunker

        # Chunk the text
        chunks = chunker.chunk(text)

        # Enrich with section context from structured content
        section_map = self._build_section_map(structured_content)

        results = []
        for i, chunk in enumerate(chunks):
            section = self._find_section(chunk.start_index, section_map)
            results.append(ChunkResult(
                text=chunk.text,
                index=i,
                start_char=chunk.start_index,
                end_char=chunk.end_index,
                token_count=chunk.token_count,
                section_heading=section.heading if section else None,
                section_level=section.level if section else None,
            ))

        return results
```

### 6.3 Embedding Client (`infrastructure/ml/tei_embedder.py`)

```python
class EmbeddingClient:
    """Client for HuggingFace TEI embedding service."""

    def __init__(self, base_url: str = "http://embedder:80"):
        self.base_url = base_url
        self.session = httpx.AsyncClient(timeout=60.0)

    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """Batch embed texts via TEI API."""
        response = await self.session.post(
            f"{self.base_url}/embed",
            json={"inputs": texts, "normalize": True, "truncate": True}
        )
        response.raise_for_status()
        return response.json()

    async def embed_query(self, query: str) -> list[float]:
        """Embed a single query with instruction prefix."""
        # Qwen3-Embedding supports instruction-aware encoding
        prefixed = f"Instruct: Retrieve relevant passages\nQuery: {query}"
        embeddings = await self.embed_texts([prefixed])
        return embeddings[0]
```

### 6.4 Search Orchestrator (`application/search_service.py`)

```python
class SearchOrchestrator:
    """Orchestrates hybrid search: vector + BM25 + graph + rerank."""

    async def search(self, request: SearchRequest) -> SearchResponse:
        start = time.monotonic()

        # 1. Embed query
        query_embedding = await self.embedder.embed_query(request.query)

        # 2. Parallel retrieval
        vector_task = self._vector_search(query_embedding, top_k=50)
        bm25_task = self._bm25_search(request.query, top_k=50)
        tasks = [vector_task, bm25_task]

        if request.include_graph:
            graph_task = self._graph_enhanced_search(request.query)
            tasks.append(graph_task)

        results = await asyncio.gather(*tasks)

        # 3. Reciprocal Rank Fusion
        fused = self._reciprocal_rank_fusion(
            results,
            weights=[0.5, 0.3, 0.2] if request.include_graph else [0.6, 0.4],
            k=60,
            top_k=50,
        )

        # 4. Rerank
        if request.rerank and len(fused) > 0:
            reranked = await self.reranker.rerank(
                query=request.query,
                documents=[r.chunk_text for r in fused],
                top_k=request.top_k,
            )
            final = self._apply_rerank_scores(fused, reranked)
        else:
            final = fused[:request.top_k]

        # 5. Enrich with metadata
        enriched = await self._enrich_results(final)

        elapsed = (time.monotonic() - start) * 1000
        return SearchResponse(
            query=request.query,
            results=enriched,
            total_candidates=len(fused),
            search_time_ms=elapsed,
        )
```

### 6.5 NER Service (`infrastructure/ml/gliner_ner.py`)

```python
class NERService:
    """Named Entity Recognition using GLiNER."""

    ENTITY_LABELS = [
        "person", "organization", "location", "country", "city",
        "date", "monetary value",
        "programming language", "software framework", "database",
        "algorithm", "protocol", "API", "technology",
        "product", "company", "methodology",
        "scientific concept", "industry term",
        "book title", "publication", "conference",
    ]

    def __init__(self, model_name: str = "urchade/gliner_large_v2.5"):
        self.model = GLiNER.from_pretrained(model_name)
        if torch.cuda.is_available():
            self.model = self.model.to("cuda")

    def extract_entities(
        self,
        chunks: list[ChunkResult],
        threshold: float = 0.4
    ) -> list[EntityExtraction]:
        """Extract entities from all chunks."""
        all_entities = []

        for chunk in chunks:
            entities = self.model.predict_entities(
                chunk.text,
                self.ENTITY_LABELS,
                threshold=threshold
            )
            for e in entities:
                all_entities.append(EntityExtraction(
                    chunk_id=chunk.id,
                    text=e["text"],
                    label=e["label"],
                    confidence=e["score"],
                    start_char=e["start"],
                    end_char=e["end"],
                ))

        # Deduplicate and normalize
        return self._deduplicate_entities(all_entities)
```

### 6.6 Knowledge Graph Service (`infrastructure/graph/age_repository.py`)

```python
class GraphService:
    """Knowledge graph operations using Apache AGE."""

    async def add_document_entities(
        self,
        document_id: UUID,
        document_title: str,
        entities: list[EntityExtraction],
        chunks: list[ChunkResult],
    ):
        """Add document and its entities to the knowledge graph."""
        async with self.db.begin() as conn:
            # 1. Create/merge document node
            await conn.execute(text("""
                SELECT * FROM cypher('knowledge_graph', $$
                    MERGE (d:Document {doc_id: '%s'})
                    SET d.title = '%s'
                    RETURN d
                $$) as (v agtype)
            """ % (document_id, document_title)))

            # 2. Create/merge entity nodes and MENTIONS edges
            for entity in entities:
                await conn.execute(text("""
                    SELECT * FROM cypher('knowledge_graph', $$
                        MERGE (e:Entity {normalized_name: '%s', type: '%s'})
                        SET e.name = '%s'
                        WITH e
                        MATCH (d:Document {doc_id: '%s'})
                        MERGE (d)-[r:MENTIONS]->(e)
                        SET r.count = coalesce(r.count, 0) + 1,
                            r.confidence = %f
                        RETURN e
                    $$) as (v agtype)
                """ % (entity.normalized_name, entity.label,
                       entity.text, document_id, entity.confidence)))

            # 3. Create CO_OCCURS edges for entities in same chunk
            for chunk in chunks:
                chunk_entities = [e for e in entities if e.chunk_id == chunk.id]
                for i, e1 in enumerate(chunk_entities):
                    for e2 in chunk_entities[i+1:]:
                        await conn.execute(text("""
                            SELECT * FROM cypher('knowledge_graph', $$
                                MATCH (a:Entity {normalized_name: '%s'}),
                                      (b:Entity {normalized_name: '%s'})
                                MERGE (a)-[r:CO_OCCURS]->(b)
                                SET r.count = coalesce(r.count, 0) + 1
                                RETURN r
                            $$) as (v agtype)
                        """ % (e1.normalized_name, e2.normalized_name)))
```

---

## 7. Docker & Infrastructure Configuration

### 7.1 Custom PostgreSQL Dockerfile

```dockerfile
# infrastructure/postgres/Dockerfile
FROM paradedb/paradedb:latest-pg16

# Install Apache AGE build dependencies
USER root
RUN apt-get update && apt-get install -y \
    build-essential \
    libreadline-dev \
    zlib1g-dev \
    flex \
    bison \
    postgresql-server-dev-16 \
    git \
    && rm -rf /var/lib/apt/lists/*

# Build and install Apache AGE
RUN git clone --branch release/PG16/1.5.0 https://github.com/apache/age.git /tmp/age \
    && cd /tmp/age \
    && make install \
    && rm -rf /tmp/age

# Copy custom PostgreSQL configuration
COPY postgresql.conf /etc/postgresql/postgresql.conf
COPY init.sql /docker-entrypoint-initdb.d/

USER postgres
```

### 7.2 PostgreSQL Configuration (`postgresql.conf`)

```ini
# Memory (tuned for 128GB system)
shared_buffers = 16GB
effective_cache_size = 48GB
work_mem = 256MB
maintenance_work_mem = 4GB
wal_buffers = 64MB

# Parallelism
max_parallel_workers_per_gather = 4
max_parallel_workers = 8
max_parallel_maintenance_workers = 4

# WAL
wal_level = replica
max_wal_size = 4GB
checkpoint_completion_target = 0.9

# Planner
random_page_cost = 1.1  # SSD
effective_io_concurrency = 200  # SSD

# Extensions
shared_preload_libraries = 'age,pg_search'

# Logging
log_min_duration_statement = 1000  # log queries > 1s
```

### 7.3 Docker Compose

```yaml
# infrastructure/docker-compose.yml
version: '3.8'

services:
  postgres:
    build:
      context: ./postgres
      dockerfile: Dockerfile
    container_name: cortex-postgres
    environment:
      POSTGRES_DB: cortex
      POSTGRES_USER: cortex
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
    ports:
      - "5432:5432"
    volumes:
      - pgdata:/var/lib/postgresql/data
      - ./postgres/postgresql.conf:/etc/postgresql/postgresql.conf
    command: postgres -c config_file=/etc/postgresql/postgresql.conf
    shm_size: '4gb'
    restart: unless-stopped

  redis:
    image: redis:7-alpine
    container_name: cortex-redis
    ports:
      - "6379:6379"
    volumes:
      - redisdata:/data
    restart: unless-stopped

  embedder:
    image: ghcr.io/huggingface/text-embeddings-inference:1.7.2
    container_name: cortex-embedder
    environment:
      MODEL_ID: Qwen/Qwen3-Embedding-0.6B
      DTYPE: float16
      MAX_BATCH_TOKENS: 16384
      MAX_CONCURRENT_REQUESTS: 128
    ports:
      - "8081:80"
    volumes:
      - hf_cache:/data
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 1
              capabilities: [gpu]
    restart: unless-stopped

  api:
    build:
      context: ../backend
      dockerfile: Dockerfile
    container_name: cortex-api
    environment:
      DATABASE_URL: postgresql+asyncpg://cortex:${POSTGRES_PASSWORD}@postgres:5432/cortex
      REDIS_URL: redis://redis:6379/0
      EMBEDDER_URL: http://embedder:80
      DATA_DIR: /data
      NVIDIA_VISIBLE_DEVICES: all
    ports:
      - "8080:8080"
    volumes:
      - filedata:/data
      - hf_cache:/root/.cache/huggingface
    depends_on:
      - postgres
      - redis
      - embedder
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 1
              capabilities: [gpu]
    restart: unless-stopped

  worker:
    build:
      context: ../backend
      dockerfile: Dockerfile
    container_name: cortex-worker
    command: celery -A cortex.tasks.celery_app worker --loglevel=info --concurrency=2
    environment:
      DATABASE_URL: postgresql+asyncpg://cortex:${POSTGRES_PASSWORD}@postgres:5432/cortex
      REDIS_URL: redis://redis:6379/0
      EMBEDDER_URL: http://embedder:80
      DATA_DIR: /data
      NVIDIA_VISIBLE_DEVICES: all
    volumes:
      - filedata:/data
      - hf_cache:/root/.cache/huggingface
    depends_on:
      - postgres
      - redis
      - embedder
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 1
              capabilities: [gpu]
    restart: unless-stopped

volumes:
  pgdata:
  redisdata:
  filedata:
  hf_cache:
```

---

## 8. Python Backend Dependencies

```toml
# backend/pyproject.toml
[project]
name = "cortex"
version = "0.1.0"
requires-python = ">=3.11"

dependencies = [
    # API framework
    "fastapi>=0.115",
    "uvicorn[standard]>=0.32",
    "python-multipart>=0.0.9",
    "websockets>=13.0",

    # Database
    "sqlalchemy[asyncio]>=2.0",
    "asyncpg>=0.30",
    "alembic>=1.14",
    "pgvector>=0.3",

    # Task queue
    "celery[redis]>=5.4",

    # Document parsing
    "docling>=2.0",
    "pymupdf>=1.24",
    "openpyxl>=3.1",
    "markdown-it-py[plugins]>=3.0",
    "python-docx>=1.1",

    # ML / NLP
    "chonkie[semantic]>=0.3",
    "gliner>=0.2",
    "mxbai-rerank>=0.1",
    "sentence-transformers>=2.7",
    "torch>=2.4",

    # HTTP client
    "httpx>=0.27",

    # Configuration
    "pydantic-settings>=2.5",

    # Utilities
    "pillow>=10.4",
    "python-magic>=0.4",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "pytest-asyncio>=0.24",
    "pytest-cov>=5.0",
    "ruff>=0.7",
    "mypy>=1.12",
]
```

---

## 9. Swift/macOS Frontend Architecture

### 9.1 SPM Multi-Target Package Manifest

The frontend uses Swift Package Manager with **compiler-enforced dependency boundaries**. Each target is a separate module; the `dependencies` array prevents illegal imports at compile time.

```swift
// Package.swift
// swift-tools-version: 5.10
import PackageDescription

let package = Package(
    name: "Cortex",
    platforms: [.macOS(.v14)],
    products: [
        .executable(name: "Cortex", targets: ["CortexApp"]),
    ],
    dependencies: [
        .package(url: "https://github.com/apple/swift-markdown", from: "0.4.0"),
    ],
    targets: [
        // Domain: entities, value objects, port protocols. No external deps.
        .target(name: "Domain"),

        // AppCore: use-case orchestration. Depends only on Domain.
        .target(name: "AppCore", dependencies: ["Domain"]),

        // Infrastructure: API client, WebSocket, thumbnail loading. Depends only on Domain.
        .target(name: "Infrastructure", dependencies: [
            "Domain",
            .product(name: "Markdown", package: "swift-markdown"),
        ]),

        // Bootstrap: composition root + settings. Depends on all above.
        .target(name: "Bootstrap", dependencies: ["Domain", "AppCore", "Infrastructure"]),

        // CortexApp: SwiftUI views + @main entry point. Depends on Bootstrap.
        .executableTarget(name: "CortexApp", dependencies: ["Bootstrap"]),

        // Tests aligned with architecture
        .testTarget(name: "DomainTests", dependencies: ["Domain"]),
        .testTarget(name: "AppCoreTests", dependencies: ["Domain", "AppCore"]),
        .testTarget(name: "InfrastructureTests", dependencies: ["Domain", "Infrastructure"]),
    ]
)
```

### 9.2 Key Architectural Patterns

**Domain entities are value types (structs), Sendable, and Equatable:**
```swift
// Domain/Document.swift
import Foundation

package struct Document: Sendable, Equatable, Codable {
    package let id: UUID
    package let title: String
    package let fileType: FileType
    package let status: ProcessingStatus
    package let createdAt: Date
    // ...
}
```

**Port protocols use `package` visibility and `Sendable`:**
```swift
// Domain/Ports.swift
package protocol DocumentRepositoryPort: Sendable {
    func list(filters: DocumentFilters?) async throws -> [Document]
    func get(id: UUID) async throws -> Document
    func delete(id: UUID) async throws
}

package protocol SearchPort: Sendable {
    func search(query: String, filters: SearchFilters?) async throws -> SearchResponse
}
```

**Services depend on protocols, not concrete types:**
```swift
// AppCore/SearchService.swift
import Domain

package struct SearchService: Sendable {
    private let searchRepo: any SearchPort

    package init(searchRepo: any SearchPort) {
        self.searchRepo = searchRepo
    }

    package func search(query: String, filters: SearchFilters? = nil) async throws -> SearchResponse {
        try await searchRepo.search(query: query, filters: filters)
    }
}
```

**Composition root wires everything:**
```swift
// Bootstrap/CompositionRoot.swift
import Domain
import AppCore
import Infrastructure

package struct CompositionRoot: Sendable {
    package let documentService: DocumentService
    package let searchService: SearchService
    package let ingestionService: IngestionService

    package init(settings: Settings) {
        let apiClient = APIClient(baseURL: settings.backendURL)
        let docRepo = APIDocumentRepository(client: apiClient)
        let searchRepo = APISearchRepository(client: apiClient)

        self.documentService = DocumentService(docRepo: docRepo)
        self.searchService = SearchService(searchRepo: searchRepo)
        self.ingestionService = IngestionService(docRepo: docRepo, client: apiClient)
    }
}
```

**Tests use protocol test doubles — no mocking framework:**
```swift
// AppCoreTests/SearchServiceTests.swift
import Domain
import AppCore

final class MockSearchRepo: SearchPort {
    private(set) var lastQuery: String?

    func search(query: String, filters: SearchFilters?) async throws -> SearchResponse {
        lastQuery = query
        return SearchResponse(query: query, results: [], totalCandidates: 0, searchTimeMs: 0)
    }
}
```

### 9.3 System Frameworks
- SwiftUI, AppKit (via NSViewRepresentable)
- PDFKit, WebKit (WKWebView)
- QuickLookThumbnailing, UniformTypeIdentifiers
- CoreSpotlight (Phase 4)

---

## 10. Non-Functional Requirements

### 10.1 Performance Targets

| Operation | Target Latency | Notes |
|-----------|---------------|-------|
| Document upload (10MB) | < 5s | Stream to server |
| Document processing (10-page PDF) | < 15s | Full pipeline (GPU-accelerated Docling: ~5s parse, ~2s chunk, ~3s embed, ~3s NER) |
| Search query | < 500ms | End-to-end including rerank |
| Document list loading | < 200ms | Paginated, 50 items |
| Document viewer loading | < 1s | Fetch + render |
| Thumbnail generation | < 2s | Per document |

### 10.2 Storage Estimates

| 1,000 Documents | Estimated Storage |
|-----------------|-------------------|
| Original files | ~5-10 GB |
| PostgreSQL (all tables + indexes) | ~2-5 GB |
| Thumbnails + images | ~500 MB |
| Total | ~8-16 GB |

| 10,000 Documents | Estimated Storage |
|------------------|-------------------|
| Original files | ~50-100 GB |
| PostgreSQL | ~20-50 GB |
| Thumbnails + images | ~5 GB |
| Total | ~75-155 GB |

### 10.3 Reliability
- PostgreSQL WAL for crash recovery
- Document processing is idempotent (can retry safely)
- Original files are never modified
- Backup script exports PostgreSQL dump + file directory

### 10.4 Security
- Single-user system — no authentication required on localhost
- If exposed on LAN: optional API key in header
- All data stays local — no cloud services, no telemetry
- File uploads validated by type and size
