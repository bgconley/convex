# Cortex — Personal Knowledge Base

## Project Overview

Cortex is a personal knowledge base with a native macOS frontend (Swift/SwiftUI) and a GPU-accelerated Python backend. It ingests documents (PDF, Markdown, DOCX, XLSX, TXT, images), preserves formatting, and provides semantic search with hybrid retrieval (vector + BM25 + knowledge graph) and neural reranking.

**Planning docs (read before writing code):**
- `APP_SPEC.md` — Product contract: schemas, API endpoints, database design, UI spec
- `ARCHITECTURE_BRAINSTORM.md` — Component validation, GPU budgets, data flows, design decisions
- `IMPLEMENTATION_PLAN.md` — Phased step-by-step build plan with file lists and verification criteria

**Coding guidelines (follow strictly):**
- `python-instruct.md` — Python architecture: layered design, Protocol-based DI, composition root
- `swift-instruct.md` — Swift architecture: SPM multi-target, package access, Sendable, protocol DI

---

## Implementation Progress

### Phase 1: Foundation & Core Pipeline (complete)
- **Step 1.1** — Infrastructure: Docker Compose, custom PG16 (pgvector + pg_search + AGE), Redis
- **Step 1.2** — Backend scaffolding: layered architecture, domain entities/ports, ORM tables, FastAPI, Alembic
- **Step 1.3** — Document upload & CRUD: file storage, PG repository, duplicate detection (SHA-256)
- **Step 1.4** — Document parsing: Docling with GPU (CUDA layout + EasyOCR), PyMuPDF thumbnails
- **Step 1.5** — Chunking: Chonkie SemanticChunker (potion-base-32M, threshold=0.5, chunk_size=512)
- **Step 1.6** — Embedding: TEI client via existing gateway (:8080), 1024-dim vectors
- **Step 1.7** — Ingestion pipeline: Celery task (parse→chunk→embed→NER→graph→store)
- **Step 1.8** — Vector search: POST /search endpoint, pgvector HNSW, snippet highlighting
- **Step 1.9** — macOS app scaffolding: SPM multi-target, 5 targets, NavigationSplitView
- **Step 1.10** — Document Library & Import: grid/list view, Table, drag-drop, import progress with polling
- **Step 1.11** — Document Viewer: PDF (PDFKit), HTML (WKWebView), Markdown, XLSX (sheet tabs), image, QuickLook dual-view
- **Step 1.12** — Search UI: Cmd+K overlay, debounced search, keyboard nav, hit navigation (anchor/page)

### Phase 2: Enhanced Search (complete)
- **Step 2.1** — BM25 full-text search: pg_search indexes, `|||`/`&&&`/`###` operators, query parsing
- **Step 2.2** — Hybrid search: vector + BM25 with RRF (w_vec=0.6, w_bm25=0.4, k=60)
- **Step 2.3** — Reranker: mxbai-rerank-large-v2 via existing service (:9006), ~80ms overhead
- **Step 2.4** — Document-level search: POST /search/documents, chunk aggregation by document
- **Step 2.5** — Frontend search enhancements: filters (type, date, collection), Passages/Documents toggle, score breakdown tooltip, "More from this document" expansion

### Phase 3: Knowledge Graph & NER (complete)
- **Step 3.1** — NER: GLiNER HTTP client (:9002), 18 cross-domain entity labels, entity dedup, ingestion pipeline step
- **Step 3.2** — Knowledge graph: Apache AGE, Document/Entity nodes, MENTIONS/CO_OCCURS edges, graph cleanup on delete
- **Step 3.3** — Graph-enhanced search: query NER → entity expansion via CO_OCCURS (1-2 hops) → chunk lookup via entity_mentions → 3-way RRF (w_vec=0.5, w_bm25=0.3, w_graph=0.2), `include_graph` toggle, `graph_score` in response
- **Step 3.4** — Entity API: GET /entities (paginated, type-filterable), GET /entities/{id} (detail + docs + related), GET /entities/{id}/related, GET /graph/explore, GET /documents/{id}/entities (real data), EntityService, 8 tests
- **Step 3.5** — Frontend entity browsing: entity chips in document viewer (click → filter library by entity), entity browser sidebar (grouped by type, mention count badges), entity detail view (documents + related entities), entity search suggestions in Cmd+K overlay, EntityDetailView with FlowLayout

### Phase 4: Collections, Spotlight & Polish (complete)
- **Step 4.1** — Collections & Organization: CRUD API, nested collections (parent_id, hierarchical sidebar), drag-to-collection, smart collections (filter_json saved queries with server-side fileType+tags filtering), tag autocomplete
- **Step 4.2** — Spotlight Integration: CoreSpotlight indexing (CSSearchableItem per document with title, content_preview from rendered_markdown[:300], file type, tags + entity names as keywords), full-corpus background indexing on launch (paginated in batches of 100 + concurrent entity fetch via withTaskGroup), incremental indexing on document load (also fetches entities), deindex on delete, Spotlight tap handling (onContinueUserActivity → navigate to document)
- **Step 4.2.1** — Search Suggestions: `GET /search/suggestions?q=prefix&limit=5` returns 3 categories (recent searches, entity names, document titles). Backend: ILIKE prefix search on entities/documents repos, in-memory recent query tracking (deque, max 50). Frontend: `SearchSuggestionsView.swift` (3-category dropdown), replaced client-side 500-entity preload with server-side suggestions in Cmd+K overlay (shown when no search results yet).
- **Step 4.3** — Advanced UI Polish: Keyboard shortcuts (Cmd+1/2/3 sidebar sections, Cmd+D toggle favorite), Settings view (Cmd+, with General/Search/Storage tabs, backend URL config, search preferences, `GET /stats` corpus statistics), onboarding (first-launch backend URL config sheet with connection test), dark mode CSS optimization (added link colors, blockquote text, hr borders to both renderers' `@media (prefers-color-scheme: dark)`).
- **Step 4.4** — Backup & Restore: `backup.sh` (pg_dump custom format + file directory tar → compressed timestamped archive), `restore.sh` (drop/recreate DB, pg_restore, extract files, REINDEX BM25, restart services). Confirmation prompt on restore.
- **Step 4.5** — Monitoring & Observability: Structured JSON logging (`infrastructure/logging.py`, `JSONFormatter`, `request_id_var` context var), request correlation ID middleware (`RequestLoggingMiddleware` in `app.py` with try/finally for exception logging), `LOG_LEVEL`/`LOG_JSON` settings, Celery worker logging via `worker_process_init` signal. `MetricsPort` protocol in `domain/ports.py`, `MetricsCollector` in `infrastructure/metrics_collector.py` (Redis-backed ingestion metrics for cross-process visibility between API and Celery worker, in-memory search metrics for API process). Per-step ingestion timing (parse/chunk/embed/ner/graph) recorded in `IngestionService`. Per-search timing breakdown (retrieval/rerank) recorded in `SearchService`. `GET /dashboard` endpoint aggregates health checks, corpus stats, processing metrics (avg duration, error rate, stage breakdown), and search analytics (p50/p95/p99 latency, avg result count, recent queries). 18 new tests (12 metrics incl. cross-process test + 6 logging), 84 total backend tests pass.

### All Phases Complete
All implementation plan steps (1.1–4.5) are code-complete and deployed to the GPU server. Verified operational: health checks green, dashboard endpoint live, JSON structured logging active, search analytics recording, collections API working (Alembic migration applied).

---

## Architecture Rules

### Python Backend (`backend/`)

**Layered architecture with dependency inversion:**
```
entrypoints/ → application/ → domain/ ← infrastructure/
                                  ↑
                            bootstrap.py
```

- `domain/` — Entities, value objects, `typing.Protocol` ports. Depends on nothing.
- `application/` — Use-case services. Depends on `domain/` ports only.
- `infrastructure/` — Concrete adapters (DB, ML models, file storage). Implements `domain/` ports.
- `entrypoints/` — FastAPI routes. Depends on `application/` services.
- `schemas/` — Pydantic request/response types. Separate from domain entities.
- `bootstrap.py` — Composition root. The ONLY module that imports both `application/` and `infrastructure/`.

**Strict rules:**
- Services MUST depend on `typing.Protocol` interfaces from `domain/ports.py`, never on concrete infrastructure classes.
- Domain types MUST NOT import from `infrastructure/`, `entrypoints/`, or `schemas/`.
- No `utils/` or `helpers/` directories. Put helpers in their relevant domain module.
- No ambiguous `models/` directory. Use `domain/` for entities, `schemas/` for transport types, `infrastructure/persistence/tables.py` for ORM.
- Use `pydantic_settings.BaseSettings` with `model_config = SettingsConfigDict(env_file=".env")` for configuration.
- Entry point is `__main__.py` (run via `python -m cortex`).
- Alembic is the single source of truth for database schema. `init.sql` handles extensions only.

### Swift Frontend (`frontend/`)

**SPM multi-target with compiler-enforced dependencies (swift-tools-version 6.0):**
```
Domain:         []
AppCore:        ["Domain"]
Infrastructure: ["Domain", swift-markdown]
Bootstrap:      ["Domain", "AppCore", "Infrastructure"]
CortexApp:      ["Bootstrap"]
```

**Strict rules:**
- Domain entities are `struct` (value types), `Sendable`, `Equatable`.
- Port protocols use `package` access level and `Sendable` conformance.
- Services use `any ProtocolName` existentials for DI. Services are `actor` types.
- `CompositionRoot` in `Bootstrap/` is the only place that wires concrete to abstract.
- One primary type per file, named after the type.
- No `Utilities/` or `Helpers/` directories.
- Tests use protocol test doubles (`final class` with `@unchecked Sendable`), no mocking frameworks.
- Tests require Xcode SDK: `DEVELOPER_DIR=/Applications/Xcode.app/Contents/Developer swift test`

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | Swift/SwiftUI + AppKit bridging (PDFKit, WKWebView, QuickLook) |
| API | Python FastAPI + Uvicorn |
| Tasks | Celery + Redis |
| Database | PostgreSQL 16 + pgvector + pg_search (ParadeDB) + Apache AGE |
| Embedding | Qwen3-Embedding-0.6B via existing TEI gateway |
| Reranker | mxbai-rerank-large-v2 via existing service |
| NER | GLiNER medium v2.1 via existing service |
| Parser | Docling (GPU-accelerated: CUDA layout + EasyOCR) |
| Chunker | Chonkie SemanticChunker (potion-base-32M) |

## Hardware Target

Lenovo P620: AMD Threadripper PRO 3945WX (12C/24T), 128 GB RAM, RTX 3090 (24 GB VRAM), 2 TB NVMe SSD.

## GPU Server Services

**Cortex-owned containers** (managed by `infrastructure/docker-compose.yml`):

| Service | Host Port | Container Port | Notes |
|---------|-----------|---------------|-------|
| postgres | 5433 | 5432 | Cortex DB (existing weka PG on 5432) |
| redis | 6380 | 6379 | Cortex queue (existing weka-redis on 6379) |
| api | 8090 | 8080 | Cortex API (has GPU passthrough for Docling) |
| worker | — | — | Celery worker (has GPU passthrough for Docling) |

**Existing ML services** (shared with weka stack — do NOT duplicate):

| Service | Host Port | Endpoint | Model |
|---------|-----------|----------|-------|
| tei_gateway | 8080 | `/v1/embeddings` (OpenAI-compatible) | Routes to qwen3-embedder |
| mxbai-reranker | 9006 | `/v1/rerank` | mxbai-rerank-large-v2 |
| tei_gliner | 9002 | `/v1/extract` | gliner_medium-v2.1 |

Cortex containers reach ML services via `host.docker.internal` (mapped to host gateway via `extra_hosts`). Settings use `EMBEDDER_URL`, `RERANKER_URL`, `NER_URL` environment variables.

---

## Key Contracts

### Status Lifecycle (canonical — use everywhere)
`uploading` → `stored` → `parsing` → `parsed` → `chunking` → `chunked` → `embedding` → `embedded` → `extracting_entities` → `entities_extracted` → `building_graph` → `ready` | `failed`

### Duplicate Handling
One canonical document per SHA-256 hash. Duplicate upload returns existing document ID with `is_duplicate=True`. Reprocessing is explicit via `POST /documents/{id}/reprocess`.

### Document Viewing (Dual Representation)
- **PDF/Markdown/TXT/Images**: Single viewer (PDFKit, WKWebView, Text, Image).
- **DOCX/XLSX**: Structured view (HTML/JSON with search anchors) + Fidelity view (original via QuickLook). Toolbar toggle: `Structured | Original`.
- Backend returns `format: "html"` for all Docling-processed docs. Frontend routes by `format` for md/txt, by `fileType` for pdf/images and docx/xlsx (dual toggle).

### Search Pipeline
1. Vector search (pgvector HNSW) + BM25 search (pg_search `|||`/`&&&`/`###`) + Graph search (NER → entity expansion → chunk lookup) run in parallel
2. Reciprocal Rank Fusion merges results:
   - With graph: w_vec=0.5, w_bm25=0.3, w_graph=0.2, k=60
   - Without graph (`include_graph=false`): w_vec=0.6, w_bm25=0.4, k=60
3. Neural reranking via mxbai-rerank-large-v2 (optional, `rerank=true` default)
4. Score breakdown: `vector_score`, `bm25_score`, `graph_score`, `rerank_score` in response
5. Document-level search: `POST /search/documents` aggregates by document
6. Search suggestions: `GET /search/suggestions?q=prefix&limit=5` returns recent queries (in-memory), entity names (ILIKE), document titles (ILIKE) — 3 categories, up to `limit` per category

### Entity API
- `GET /entities` — paginated list, filterable by `entity_type`, sorted by mention_count desc
- `GET /entities/{id}` — entity detail + documents (from graph MENTIONS) + related entities (from graph CO_OCCURS)
- `GET /entities/{id}/related` — related entities via CO_OCCURS traversal, configurable `hops` (1-4, default 2)
- `GET /graph/explore` — graph exploration from a starting entity (center + related + documents)
- `GET /documents/{id}/entities` — entities extracted from a specific document (from relational entity_mentions)
- Entity `document_count` comes from relational store (entity_mentions); document list in detail/explore comes from graph MENTIONS edges. These can drift — see Knowledge Graph caveat below.

### Search Hit Navigation
Search results include `page_number`, `chunk_start_char`, `chunk_end_char`, and `anchor_id`. Structured views inject `<span id="chunk-N">` anchors. PDFs scroll to page; HTML/structured views scroll to anchor.

### Knowledge Graph (Apache AGE)
- Graph: `knowledge_graph` created by `init.sql`
- Nodes: `Document` (doc_id, title), `Entity` (normalized_name, type, name)
- Edges: `MENTIONS` (Document→Entity, count, confidence), `CO_OCCURS` (Entity→Entity, count)
- Document deletion cleans up graph nodes (orphans removed) and entity mention counts
- **Data consistency caveat**: Entity `document_count` (relational, from `entity_mentions` table) and graph `MENTIONS` edges can drift. Steps 3.1 (NER/relational) and 3.2 (graph) were deployed incrementally — documents ingested between steps have relational mentions but no graph edges. Reprocessing affected documents would re-sync.

### Collections & Smart Collections
- Manual collections: CRUD via `POST/GET/PATCH/DELETE /collections`, documents assigned via `collection_id` FK on documents table
- Nested collections: `parent_id` self-reference on collections table, frontend renders hierarchically with `DisclosureGroup`
- Smart collections: `filter_json` JSONB column stores `{query?, file_type?, tags?}`. `is_smart` is computed (`filter_json IS NOT NULL`)
- Smart collection document population: backend filters `fileType`/`tags` server-side via `GET /documents`; query-based smart collections then intersect those results with `searchDocuments(topK: 200)` IDs client-side
- Drag-to-collection: documents are `.draggable(id.uuidString)`, collection sidebar rows use `.dropDestination(for: String.self)`
- Smart collections are excluded from drag-drop targets and "Move to Collection" context menus
- Tag autocomplete: `GET /documents/tags/all` returns distinct tags, `DocumentDetailView` shows dropdown with prefix filtering and keyboard navigation
- Alembic migration `b2c3d4e5f6a7` adds `filter_json` column

### NER Entity Labels
18 cross-domain zero-shot labels for GLiNER: person, organization, location, date, monetary value, product, event, technology, software, medical condition, medication, medical procedure, law, regulation, contract term, financial instrument, account number, vehicle.

### Celery Task Pattern
Each Celery task creates a **fresh CompositionRoot** inside `asyncio.run()`. Do NOT cache the root or any async resources (SQLAlchemy engine, httpx client) across task invocations — they are event-loop-bound and will fail with "Future attached to a different loop" on the second task.

---

## Build & Run

```bash
# Infrastructure (GPU server)
cd infrastructure && docker compose up -d

# Backend (GPU server — containers)
cd infrastructure && docker compose build api worker && docker compose up -d api worker

# Backend (GPU server — host venv for testing)
cd backend && uv venv .venv && uv pip install -e ".[dev]" --python .venv/bin/python

# Frontend (Mac)
cd frontend && swift build && open Package.swift  # opens in Xcode
```

## Testing

### Unit Tests (Mac, local)
```bash
# Backend domain + application tests (no GPU, no DB needed)
cd backend && .venv/bin/python -m pytest tests/test_domain/ tests/test_application/

# Frontend (requires Xcode SDK)
cd frontend && DEVELOPER_DIR=/Applications/Xcode.app/Contents/Developer swift test
```

### Integration / Inspection Tests (GPU server)

Integration tests and inspection scripts run on the GPU server inside the containers.

**GPU Server:**
- Host: `10.25.0.50`
- User: `bgconley`
- SSH key: `/Users/brennanconley/vibecode/infx/ubuntu24_ed25519`
- Repo location: `~/convex`
- Repo remote: `https://github.com/bgconley/convex.git`

**SSH shorthand:**
```bash
ssh -i /Users/brennanconley/vibecode/infx/ubuntu24_ed25519 bgconley@10.25.0.50
```

**Deploy + test workflow:**
```bash
# 1. From Mac: commit and push
git push origin main

# 2. SSH to GPU server and deploy
ssh -i /Users/brennanconley/vibecode/infx/ubuntu24_ed25519 bgconley@10.25.0.50
cd ~/convex && git pull origin main
cd infrastructure && docker compose build api worker && docker compose up -d api worker

# 3. Run inspection scripts inside containers (pipe via stdin)
docker compose exec -T api python - < ../backend/tests/test_ingestion_inspect.py
```

**Inspection scripts available:**

| Script | Tests |
|--------|-------|
| `test_ingestion_inspect.py` | Full pipeline: upload → parse → chunk → embed → search → cleanup |
| `test_search_inspect.py` | 4-query search across 3 documents, ranking verification |
| `test_embedder_inspect.py` | Batch embed, query embed, cosine similarity, pgvector round-trip |
| `test_chunker_inspect.py` | Semantic chunking, section mapping, Docling structured dict |
| `test_bm25_inspect.py` | BM25 keyword, phrase, conjunction, non-matching searches |
| `test_hybrid_inspect.py` | Hybrid search via public endpoint, score breakdown |
| `test_reranker_inspect.py` | Reranker wiring, score propagation, latency |
| `test_reranker_full_inspect.py` | Multi-doc relevance, concurrent GPU stability |
| `test_docsearch_inspect.py` | Document-level search aggregation |
| `test_ner_inspect.py` | NER extraction, entity dedup, mention persistence |
| `test_graph_inspect.py` | Knowledge graph population, CO_OCCURS, cross-doc traversal |
| `test_graph_search_inspect.py` | Graph-enhanced search: graph_score in results, include_graph toggle, entity expansion |
| `test_entity_api_inspect.py` | Entity API: list, filter, detail, related, graph explore, per-document entities |

**What runs where:**

| Test Layer | Where | Why |
|------------|-------|-----|
| `test_domain/` | Mac (local) | Pure logic, no deps |
| `test_application/` | Mac (local) | Protocol test doubles, no GPU/DB |
| Inspection scripts | GPU server (in container) | Need PostgreSQL, TEI, GPU models |
| Frontend tests | Mac (local, needs Xcode SDK) | SwiftUI, no backend needed |

## Known Issues / Caveats

- **Docling VRAM**: Call `torch.cuda.empty_cache()` after every parse (in `finally` block). Known Docling memory leak on repeated conversions.
- **Image OCR path**: Images (.png/.jpg/.tiff) are converted to temp PDF first so they go through the GPU-configured PDF pipeline (EasyOCR) rather than Docling's IMAGE pipeline which falls back to RapidOCR/ONNX on CPU.
- **Chunker section mapping**: Uses the heading the chunk starts under (nearest preceding heading). Not the heading inside the chunk span.
- **Celery event loop**: Fresh CompositionRoot per task. See "Celery Task Pattern" above.
- **Swift tests**: Require `DEVELOPER_DIR=/Applications/Xcode.app/Contents/Developer` because default CommandLineTools SDK lacks XCTest.
- **WebSocket events**: `/ws/events` is implemented with a Redis pub/sub bridge. The frontend feeds those events into `IngestionService`, and import progress still keeps HTTP polling as a fallback path.
- **AGE + asyncpg**: asyncpg rejects multiple statements per execute. Split `LOAD 'age'` and `SET search_path` into separate calls via `_load_age()`. SQLAlchemy `text()` interprets Cypher `:LABEL` as bind params — use `exec_driver_sql()` via `_cypher()` helper.
- **AGE Cypher limitations**: Apache AGE doesn't support `WHERE NOT EXISTS { MATCH ... }` subquery syntax. Use count-based orphan detection instead.
- **APIClient URL construction**: `URL.appendingPathComponent` percent-encodes `?` and `=`. Use `buildURL()` with string concatenation for paths with query strings.
- **HTML wrapping**: Backend returns full HTML documents from Docling; detect via presence of `</head>` and inject CSS rather than re-wrapping.
- **pg_search operators**: ParadeDB 0.21.13 uses `|||` (OR), `&&&` (AND), `###` (phrase). Legacy `@@@` still supported. `pdb.score(id)` for BM25 scoring.
- **nvidia-persistenced**: GPU containers need this daemon running. If missing: `sudo systemctl start nvidia-persistenced && sudo nvidia-smi -pm 1`. Cannot `enable` (no Install section) — must `start`.
- **Inspection scripts in container**: Inspection tests piped via stdin (`docker compose exec -T api python - < ../backend/tests/foo.py`) always run the host's current copy. Running directly inside the container (`docker exec cortex-api python /app/tests/foo.py`) runs the copy baked at build time, which may be stale if no rebuild was done after a test-only commit.
- **Graph search query NER**: Uses a dummy `Chunk` wrapper to call `NERPort.extract_entities()` with query text. Threshold is 0.3 (lower than ingestion's 0.4) to catch more entity mentions in short queries. If NER or graph expansion fails, graph signal is silently skipped (returns empty list).
- **Entity count drift (relational vs graph)**: Entity `document_count` (relational, from `entity_mentions`) and graph `MENTIONS` edges can disagree. Steps 3.1 and 3.2 were deployed incrementally — documents ingested between them have relational mentions but no graph edges. In entity detail, `document_count` may exceed the length of the `documents` list. Fix: reprocess affected documents via `POST /documents/{id}/reprocess`.
- **Entity filter library reset**: Clicking an entity chip resets the library to "All Documents", clears any selected collection, and then applies the entity filter. ContentView owns filter lifecycle — `sidebarSelectionBinding` clears the filter on user sidebar clicks, while `filterLibraryByEntity` applies it directly.
- **Search suggestions in-memory**: Recent search queries are tracked in-memory in `SearchService` (max 50, deque). Lost on API restart — acceptable for personal KB. Entity and document prefix suggestions are server-side via ILIKE queries.
- **Smart collection filter_json**: Smart collections store a `filter_json` JSONB column on the `collections` table (`query`, `file_type`, `tags`). `fileType` and `tags` filtering is server-side (`GET /documents` supports `tags` query param via PostgreSQL ARRAY overlap). Only `query`-based smart collections do client-side ID intersection with search results. Non-query smart collections use default server-side pagination (no arbitrary cap). Query-based smart collections use server-side `fileType`+`tags` with `limit: 500`, then intersect with `searchDocuments(topK: 200)` result IDs. A collection with non-null `filter_json` is "smart" (`is_smart=true`). Smart collections reject drag-drop and are excluded from "Move to Collection" context menus.
- **Recursive sidebar DisclosureGroup**: `collectionRow()` returns `AnyView` because SwiftUI can't infer opaque return types for self-referencing `@ViewBuilder` functions. This is a compiler limitation — not a design choice.
- **PATCH encoding**: `APIDocumentRepository` uses custom `encode(to:)` logic so fields are only sent when intentionally set. Clearing `collection_id` is supported by explicitly encoding JSON `null` when `setCollection` is true.
- **Spotlight content_preview source**: `content_preview` in `DocumentMetadataResponse` is populated from `rendered_markdown[:300]`, not `parsed_content` (which is `dict | None`). Documents that have no `rendered_markdown` (e.g., still processing, or images with no OCR text) will have `content_preview: null` and Spotlight falls back to a metadata summary (file type, page/word count).
- **Spotlight indexing concurrency**: Both the full-corpus launch pass (`ContentView.indexAllDocumentsInSpotlight`) and incremental library pass (`DocumentLibraryView.loadDocuments`) fetch entity names per document via unbounded `withTaskGroup`. For very large corpora this could spike concurrent API calls. Acceptable for a personal KB (<1000 docs).
- **SwiftUI.Settings vs Bootstrap.Settings**: Both SwiftUI and Bootstrap define `Settings`. In CortexApp target, use `Bootstrap.Settings` for the config struct and `SwiftUI.Settings` for the Settings scene. SettingsView.swift takes `Bootstrap.Settings` explicitly.
- **Settings save requires restart**: Changing the backend URL in Settings saves to UserDefaults but doesn't reinitialize the CompositionRoot. The user must restart the app for URL changes to take effect. Search preferences (topK, rerank, includeGraph) are read from `root.settings` at overlay construction time — changes take effect after app restart.
- **Onboarding skippable**: First-launch onboarding shows if `backendURL` hasn't been explicitly set in UserDefaults. "Use Default" saves the default URL to UserDefaults and dismisses. Once any URL is saved (including via Settings or skip), onboarding won't show again.
- **Hidden keyboard shortcut buttons**: Cmd+1/2/3 and Cmd+D are implemented as hidden zero-size `Button` views in a `.background` overlay. This pattern avoids conflicts with macOS native tab switching.
- **Metrics cross-process architecture**: Ingestion metrics use Redis (`cortex:metrics:ingestion` list, lpush/ltrim) so both API and Celery worker processes can read/write. Search metrics are in-memory (API process only — search only runs in the API). The `GET /dashboard` endpoint reads ingestion from Redis and search from local memory. Redis writes are fire-and-forget with warning-level logging on failure (metrics are not critical path).
- **Request logging exception path**: `RequestLoggingMiddleware` uses try/finally so the log line is emitted even if an unhandled exception propagates. Status code defaults to 500 for exception cases. The `X-Request-ID` response header is only set on successful responses (can't modify headers after exception).
