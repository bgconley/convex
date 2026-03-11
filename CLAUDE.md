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

### Phase 3: Knowledge Graph & NER (in progress)
- **Step 3.1** — NER: GLiNER HTTP client (:9002), 18 cross-domain entity labels, entity dedup, ingestion pipeline step
- **Step 3.2** — Knowledge graph: Apache AGE, Document/Entity nodes, MENTIONS/CO_OCCURS edges, graph cleanup on delete
- **Step 3.3** — Graph-enhanced search: query NER → entity expansion via CO_OCCURS (1-2 hops) → chunk lookup via entity_mentions → 3-way RRF (w_vec=0.5, w_bm25=0.3, w_graph=0.2), `include_graph` toggle, `graph_score` in response

### Next Step
- **Step 3.4** — Entity API endpoints (GET /entities, GET /entities/{id}/related, etc.)
- Then: Step 3.5 (Frontend entities)
- Then: Phase 4 (Collections, Spotlight, polish)

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

### Search Hit Navigation
Search results include `page_number`, `chunk_start_char`, `chunk_end_char`, and `anchor_id`. Structured views inject `<span id="chunk-N">` anchors. PDFs scroll to page; HTML/structured views scroll to anchor.

### Knowledge Graph (Apache AGE)
- Graph: `knowledge_graph` created by `init.sql`
- Nodes: `Document` (doc_id, title), `Entity` (normalized_name, type, name)
- Edges: `MENTIONS` (Document→Entity, count, confidence), `CO_OCCURS` (Entity→Entity, count)
- Document deletion cleans up graph nodes (orphans removed) and entity mention counts

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
- **WebSocket events**: `/ws/events` endpoint and Redis pub/sub bridge are specified in the plan but not yet implemented. Status updates currently require polling.
- **AGE + asyncpg**: asyncpg rejects multiple statements per execute. Split `LOAD 'age'` and `SET search_path` into separate calls via `_load_age()`. SQLAlchemy `text()` interprets Cypher `:LABEL` as bind params — use `exec_driver_sql()` via `_cypher()` helper.
- **AGE Cypher limitations**: Apache AGE doesn't support `WHERE NOT EXISTS { MATCH ... }` subquery syntax. Use count-based orphan detection instead.
- **APIClient URL construction**: `URL.appendingPathComponent` percent-encodes `?` and `=`. Use `buildURL()` with string concatenation for paths with query strings.
- **HTML wrapping**: Backend returns full HTML documents from Docling; detect via presence of `</head>` and inject CSS rather than re-wrapping.
- **pg_search operators**: ParadeDB 0.21.13 uses `|||` (OR), `&&&` (AND), `###` (phrase). Legacy `@@@` still supported. `pdb.score(id)` for BM25 scoring.
- **nvidia-persistenced**: GPU containers need this daemon running. If missing: `sudo systemctl start nvidia-persistenced && sudo nvidia-smi -pm 1`. Cannot `enable` (no Install section) — must `start`.
