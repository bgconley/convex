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

### Completed (verified on GPU server)
- **Step 1.1** — Infrastructure: Docker Compose, custom PG16 (pgvector 0.8.1 + pg_search 0.21.13 + AGE 1.5.0), Redis
- **Step 1.2** — Backend scaffolding: layered architecture, domain entities/ports, ORM tables, FastAPI app, Alembic migration (6 tables), health endpoint
- **Step 1.3** — Document upload & CRUD: file storage, PG repository, duplicate detection (SHA-256), all 11 document endpoints
- **Step 1.4** — Document parsing: Docling with GPU (CUDA layout + EasyOCR), PyMuPDF thumbnails, plain text and image support (images convert to temp PDF for GPU OCR path)
- **Step 1.5** — Chunking: Chonkie SemanticChunker (potion-base-32M, threshold=0.5, chunk_size=512), section heading attribution, recursive fallback
- **Step 1.6** — Embedding: TEI client via existing gateway (:8080), OpenAI-compatible /v1/embeddings, 1024-dim vectors, pgvector storage verified
- **Step 1.7** — Ingestion pipeline: Celery task (parse→chunk→embed→store), status lifecycle transitions, idempotent reprocessing. Fresh CompositionRoot per task to avoid event loop bugs.
- **Step 1.8** — Vector search: POST /search endpoint, pgvector HNSW, snippet highlighting with `<mark>`, anchor_id for jump-to-hit, `<span id="chunk-N">` injection in structured content
- **Step 1.9** — macOS app scaffolding: SPM multi-target (Domain/AppCore/Infrastructure/Bootstrap/CortexApp), swift-tools-version 6.0, 4 tests passing, NavigationSplitView with health status

### Next Step
- **Step 1.10** — macOS App: Document Library & Import (grid/list view, drag-and-drop, thumbnails, file picker)
- Then: Step 1.11 (Document Viewer), Step 1.12 (Basic Search UI)
- Then: Phase 2 (BM25 hybrid search + reranking), Phase 3 (NER + knowledge graph), Phase 4 (polish)

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

### Search Hit Navigation
Search results include `page_number`, `chunk_start_char`, `chunk_end_char`, and `anchor_id`. Structured views inject `<span id="chunk-N">` anchors. PDFs scroll to page; HTML/structured views scroll to anchor.

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
cd backend && .venv/bin/python -m pytest tests/test_domain/

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

# 3. Run inspection scripts inside containers
docker compose exec -T api python /app/tests/test_ingestion_inspect.py
docker compose exec -T api python /app/tests/test_search_inspect.py
docker compose exec -T api python /app/tests/test_embedder_inspect.py
docker compose exec -T api python /app/tests/test_chunker_inspect.py
```

**Inspection scripts available in containers:**

| Script | Tests |
|--------|-------|
| `test_ingestion_inspect.py` | Full pipeline: upload → parse → chunk → embed → search → cleanup |
| `test_search_inspect.py` | 4-query search across 3 documents, ranking verification |
| `test_embedder_inspect.py` | Batch embed, query embed, cosine similarity, pgvector round-trip |
| `test_chunker_inspect.py` | Semantic chunking, section mapping, Docling structured dict inspection |

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
