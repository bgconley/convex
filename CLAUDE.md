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

**SPM multi-target with compiler-enforced dependencies:**
```
Domain:         []
AppCore:        ["Domain"]
Infrastructure: ["Domain"]
Bootstrap:      ["Domain", "AppCore", "Infrastructure"]
CortexApp:      ["Bootstrap"]
```

**Strict rules:**
- Domain entities are `struct` (value types), `Sendable`, `Equatable`.
- Port protocols use `package` access level and `Sendable` conformance.
- Services use `any ProtocolName` existentials for DI.
- `CompositionRoot` in `Bootstrap/` is the only place that wires concrete to abstract.
- One primary type per file, named after the type.
- No `Utilities/` or `Helpers/` directories.
- Tests use protocol test doubles (`final class`), no mocking frameworks.

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | Swift/SwiftUI + AppKit bridging (PDFKit, WKWebView, QuickLook) |
| API | Python FastAPI + Uvicorn |
| Tasks | Celery + Redis |
| Database | PostgreSQL 16 + pgvector + pg_search (ParadeDB) + Apache AGE |
| Embedding | Qwen3-Embedding-0.6B via HuggingFace TEI (Docker, GPU) |
| Reranker | mxbai-rerank-large-v2 (GPU) |
| NER | GLiNER large v2.5 (GPU) |
| Parser | Docling (primary, GPU-accelerated) + marker-pdf fallback |
| Chunker | Chonkie (SemanticChunker) |

## Hardware Target

Lenovo P620: AMD Threadripper PRO 3945WX (12C/24T), 128 GB RAM, RTX 3090 (24 GB VRAM), 2 TB NVMe SSD.

GPU budget: ~8-11 GB of 24 GB used (Qwen3 ~3GB + mxbai ~3GB + GLiNER ~3GB + Docling ~1-2GB).

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

---

## Build & Run

```bash
# Infrastructure
cd infrastructure && docker compose up -d

# Backend (dev)
cd backend && uv sync && uv run alembic upgrade head && uv run python -m cortex

# Frontend
cd frontend && swift build && open Package.swift  # opens in Xcode
```

## Testing

### Unit Tests (local)
```bash
# Backend unit + application tests (no GPU, no DB needed)
cd backend && uv run pytest tests/test_domain/ tests/test_application/

# Frontend
cd frontend && swift test
```

### Integration Tests (GPU server)

Integration tests run on the GPU server (Lenovo P620) where the Docker infrastructure, ML models, and database are running. They cannot run locally on the Mac.

**GPU Server:**
- Host: `10.25.0.50`
- User: `bgconley`
- SSH key: `/Users/brennanconley/vibecode/infx/ubuntu24_ed25519`
- Existing TEI container already running on this server
- Repo remote: `https://github.com/bgconley/convex.git`

**SSH shorthand:**
```bash
ssh -i /Users/brennanconley/vibecode/infx/ubuntu24_ed25519 bgconley@10.25.0.50
```

**Integration test workflow:**
1. Commit and push changes from the Mac
2. SSH to GPU server
3. Pull latest, rebuild affected containers, restart
4. Run integration tests on the server

```bash
# 1. From Mac: commit and push
git add -A && git commit -m "..." && git push origin main

# 2. SSH to GPU server and deploy
ssh -i /Users/brennanconley/vibecode/infx/ubuntu24_ed25519 bgconley@10.25.0.50 << 'EOF'
  cd ~/convex                           # or wherever the repo lives on the server
  git pull origin main
  cd infrastructure
  docker compose build api worker       # rebuild only changed services
  docker compose up -d api worker       # restart changed services
  cd ../backend
  uv run pytest tests/test_infrastructure/ tests/test_entrypoints/  # integration tests
EOF
```

**What runs where:**

| Test Layer | Where | Why |
|------------|-------|-----|
| `test_domain/` | Mac (local) | Pure logic, no deps |
| `test_application/` | Mac (local) | Protocol test doubles, no GPU/DB |
| `test_infrastructure/` | GPU server | Needs PostgreSQL, TEI, GPU models |
| `test_entrypoints/` | GPU server | Needs running API + DB |
| `test_e2e/` | GPU server | Full pipeline: upload → process → search |
