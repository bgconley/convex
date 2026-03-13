# Cortex: Personal Knowledge Base — Architecture Brainstorm & Component Analysis

## Table of Contents

1. [Component Validation Summary](#1-component-validation-summary)
2. [Architecture Brainstorm](#2-architecture-brainstorm)
3. [Data Flow Design](#3-data-flow-design)
4. [Hardware Utilization Strategy](#4-hardware-utilization-strategy)
5. [Code Architecture Principles](#5-code-architecture-principles)
6. [Key Design Decisions](#6-key-design-decisions)
7. [Risk Analysis](#7-risk-analysis)

---

## 1. Component Validation Summary

### 1.1 Chonkie (Text Chunker) — APPROVED ✅

**Verdict:** Excellent choice. Purpose-built, fast, feature-rich chunking library.

**Key findings:**
- Supports 8+ chunking strategies: Token, Word, Sentence, Semantic, SDPM (Semantic Double-Pass Merge), Recursive, Neural, Late Chunking
- Semantic chunking uses embedding models to detect topic boundaries — ideal for knowledge base quality
- SDPM performs double-pass: split semantically, then merge similar adjacent chunks — best chunk coherence
- Returns `Chunk` objects with `text`, `start_index`, `end_index`, `token_count` — critical for source attribution
- Text-only input — requires document parsers upstream (this is correct; separation of concerns)
- MIT license, actively maintained, thousands of GitHub stars
- Minimal dependencies; optional extras for semantic features

**Recommended strategy for this project:** Use `SemanticChunker` as the primary strategy with the Qwen3-Embedding model for boundary detection. Fall back to `RecursiveChunker` for documents where semantic chunking is too slow or produces poor results. Use `SentenceChunker` for short documents.

**Configuration guidance:**
- `chunk_size`: 512 tokens (balances retrieval precision with context)
- `chunk_overlap`: 64 tokens (maintains continuity at boundaries)
- `similarity_threshold`: 0.5 (tune based on domain; lower = fewer, larger chunks)

---

### 1.2 Qwen3-Embedding-0.6B — APPROVED ✅ (Confirmed: Dedicated Embedding Model)

**Verdict:** Outstanding choice. Best-in-class for its size. The user's instinct was correct — this IS a dedicated embedding model, not the language model repurposed.

**Key findings:**
- `Qwen/Qwen3-Embedding-0.6B` is a purpose-built embedding model (trained with contrastive learning + instruction tuning)
- 0.6B parameters, 28 transformer layers, max 1024 embedding dimensions, 32K token context
- **Matryoshka Representation Learning**: flexible output dimensions from 32 to 1024 — can trade accuracy for storage/speed
- **MTEB Multilingual**: 64.33 (vs BGE-M3's 59.56 at same size — a massive +4.77 point lead)
- **MTEB English v2**: 70.70 (outperforms NV-Embed-v2 at 7.8B params which scores 69.81)
- ~2-3 GB VRAM in BF16 — trivially fits on RTX 3090 alongside all other models
- First-class support: sentence-transformers (>=2.7.0), vLLM (>=0.8.5), HuggingFace TEI Docker
- GGUF/ONNX variants available for flexible deployment
- Apache 2.0 license, 4.45M monthly downloads

**Deployment recommendation:** Run via HuggingFace Text Embeddings Inference (TEI) Docker container for production stability and batching efficiency. Alternatively, use vLLM's embed endpoint for unified model serving.

**Dimension choice:** Use 1024 dimensions for maximum quality. With pgvector HNSW indexing, 1024-dim vectors at personal scale (< 1M chunks) will perform excellently on 128GB RAM.

---

### 1.3 PostgreSQL + pgvector + pg_search + Apache AGE — APPROVED ✅ (with caveats)

**Verdict:** Strong architectural choice. The "one database to rule them all" approach is ideal for a personal knowledge base. Operational simplicity is a massive win.

#### pgvector
- HNSW indexing for approximate nearest neighbor search — best recall/speed tradeoff
- Supports up to 2,000 indexed dimensions (our 1024-dim Qwen3 embeddings fit perfectly)
- `halfvec` (float16) type available for 50% memory savings if needed
- Sub-10ms queries at <1M vectors, well within personal KB scale
- Parallel HNSW index builds (v0.7.0+)

#### pg_search (ParadeDB)
- BM25 scoring via Tantivy (Rust-based Lucene equivalent) — 20x faster than PostgreSQL's native `tsvector`
- Native hybrid search with pgvector via Reciprocal Rank Fusion (RRF)
- Real-time indexing — transactionally consistent with PostgreSQL
- Tokenizers, stemmers, fuzzy search, phrase search, term boosting
- `paradedb.rank_hybrid()` function for built-in RRF — eliminates app-level score normalization

#### Apache AGE
- openCypher query language (Neo4j-compatible)
- Enables knowledge graph: entities as nodes, relationships as edges
- Good for entity relationship traversal (2-3 hops) at personal scale
- SQL/Cypher interoperability in same queries
- **Caveat:** Pin to PostgreSQL 16 for maximum compatibility across all three extensions
- **Caveat:** AGE Cypher coverage is incomplete (subset of openCypher)
- **Caveat:** No built-in graph algorithms (PageRank, community detection) — not needed for this use case

#### Integration
- All three extensions coexist in the same PostgreSQL instance without conflicts
- ParadeDB Docker image bundles pgvector + pg_search; add AGE via custom Dockerfile
- `shared_preload_libraries = 'age,pg_search'` in postgresql.conf
- Memory estimate for 1M chunks at 1024 dims: ~12-15 GB total (vectors + HNSW index + BM25 index + graph) — easily handled by 128GB RAM

---

### 1.4 GLiNER — APPROVED ✅

**Verdict:** Excellent choice for zero-shot NER. The killer feature is specifying ANY entity type at inference time without retraining.

**Key findings:**
- Zero-shot NER: define entity types as natural language labels at inference time
- DeBERTa-v3 backbone; available in small (50M), medium (110M), large (350M) variants
- v2.5 is latest and best — use `urchade/gliner_large_v2.5` for maximum accuracy
- ~2-3 GB VRAM for large model inference
- ~30-60ms per sentence on RTX 3090 (large model)
- Apache 2.0 license
- spaCy integration via `gliner-spacy`; ONNX export supported
- **Limitation:** Entities only — no relationship extraction. Need separate model/pipeline for relations
- **Limitation:** Max ~512 token input (DeBERTa context) — must process chunked text, not full documents
- Best with a small, stable cross-domain label set; too many granular labels degrade zero-shot quality

**Entity label strategy for knowledge base:**
```python
labels = [
    "person", "organization", "location", "date",
    "monetary value", "product", "event",
    "technology", "software",
    "medical condition", "medication", "medical procedure",
    "law", "regulation", "contract term",
    "financial instrument", "account number", "vehicle"
]
```

**Relationship extraction strategy:** Use a two-stage pipeline:
1. GLiNER extracts entities from each chunk (fast, cheap)
2. Co-occurring entities within the same chunk are linked with a "co_occurs_in" relationship
3. For richer relationships, optionally use an LLM (local or API) on high-value chunks

---

### 1.5 mxbai-rerank-large-v2 — APPROVED ✅

**Verdict:** Best open-source reranker available. Matches Cohere's commercial offering.

**Key findings:**
- Qwen2 backbone (~1.5B params), trained with ProRank (GRPO + Contrastive + Preference learning)
- BEIR Average: 57.49 — best open-source, competitive with Cohere Rerank v3.5
- ~3 GB VRAM in FP16
- 0.89s latency on A100 for ~100 docs; estimated ~1.2-1.6s on RTX 3090 for 100 docs
- For personal KB reranking 20 candidates: ~200-400ms on RTX 3090 — excellent for interactive use
- Long context: 8K-32K token pairs
- Apache 2.0 license
- Official package: `pip install mxbai-rerank`

**Pipeline position:** Retrieve top-50 candidates via hybrid search (vector + BM25), rerank to top-5/10 with mxbai-rerank-large-v2.

---

### 1.6 Document Parsers — RECOMMENDED STACK

**Primary parser: Docling (IBM)** — MIT license, multi-format, structured output, GPU-accelerated
- Handles PDF, DOCX, PPTX, XLSX, HTML, images through ONE API
- Produces `DoclingDocument` — hierarchical structure with sections, headings, paragraphs, tables, figures
- TableFormer model handles complex tables (merged cells, nested headers)
- Exports to Markdown, JSON, HTML
- **GPU acceleration (CUDA):** Docling's ML models (layout detection via RT-DETR, TableFormer, OCR) run on NVIDIA GPUs via PyTorch
  - Layout model: **14.4x speedup** over CPU (633ms → 44ms per page on NVIDIA L4)
  - TableFormer: **4.3x speedup** (1.74s → 400ms per table)
  - OCR (EasyOCR): **8.1x speedup** (13s → 1.6s per page)
  - Overall: **~6.5x speedup** (3.1s → 0.48s per page)
  - Auto-detects CUDA — no configuration required for basic usage
  - Optimal config: increase `layout_batch_size` and `ocr_batch_size` to 32-64 on RTX 3090
  - ~1-2 GB VRAM for model weights (layout + TableFormer)
  - **Caveats:** TableFormer does not support GPU batching yet; call `torch.cuda.empty_cache()` between documents to avoid VRAM leaks; for OCR, use EasyOCR (not RapidOCR with ONNX default) to get actual GPU acceleration

**PDF fallback: marker-pdf** — superior for math-heavy/academic PDFs
- GPL-3.0 license (note: more restrictive)
- ML-based PDF-to-Markdown with excellent heading, list, equation detection

**Excel: openpyxl** — full formatting preservation
- Cell values + formulas + fonts + fills + borders + conditional formatting

**Markdown: markdown-it-py** — CommonMark compliant with plugin architecture
- GFM tables, footnotes, task lists, math, front matter extensions

**Fast PDF operations: PyMuPDF** — image extraction, thumbnail generation, page counting

**Storage strategy:**
- Store original file binary (for full document retrieval/viewing)
- Store parsed DoclingDocument JSON (structured representation)
- Store rendered Markdown (for display and LLM consumption)
- Extract and store images as separate assets
- Generate and cache thumbnails

---

### 1.7 macOS Frontend — Swift/SwiftUI with AppKit Bridging

**Verdict:** Swift/SwiftUI is the right choice for a macOS-only personal knowledge base.

**Key arguments:**
- PDFKit provides superior PDF experience vs PDF.js (native scrolling, text selection, annotations)
- System integration: Spotlight indexing, QuickLook, Services menu, Share extensions, Shortcuts
- Lower memory footprint than web-based alternatives
- NavigationSplitView for three-column layout (sidebar / document list / document detail)
- WKWebView (wrapped in NSViewRepresentable) for Markdown/HTML rendering
- `.searchable` modifier + custom Command-K spotlight overlay for search
- Drag-and-drop via `.dropDestination()` for document ingestion
- `URLSession` + `async/await` for backend communication (no external deps needed)
- `QLThumbnailGenerator` for document thumbnails

**Key Swift packages:**
- `apple/swift-markdown` — Markdown to HTML conversion
- PDFKit, WebKit, QuickLookThumbnailing (system frameworks)

---

## 2. Architecture Brainstorm

### 2.1 High-Level Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    macOS Frontend                        │
│                 (Swift/SwiftUI + AppKit)                 │
│                                                         │
│  ┌──────────┐ ┌───────────┐ ┌──────────┐ ┌──────────┐ │
│  │ Document  │ │  Search   │ │ Document │ │ Library  │ │
│  │ Ingestion │ │ Interface │ │ Viewer   │ │ Browser  │ │
│  └────┬─────┘ └─────┬─────┘ └────┬─────┘ └────┬─────┘ │
│       │             │            │             │        │
└───────┼─────────────┼────────────┼─────────────┼────────┘
        │             │            │             │
        ▼             ▼            ▼             ▼
   ┌────────────────────────────────────────────────┐
   │              REST API Gateway                   │
   │            (FastAPI + Uvicorn)                   │
   │                                                 │
   │  /documents  /search  /documents/{id}  /status  │
   └────────────────────┬───────────────────────────┘
                        │
        ┌───────────────┼───────────────┐
        ▼               ▼               ▼
   ┌─────────┐   ┌───────────┐   ┌───────────────┐
   │ Ingest  │   │  Search   │   │  Retrieval    │
   │ Pipeline│   │  Pipeline │   │  Pipeline     │
   │         │   │           │   │               │
   │ Parse → │   │ Embed  →  │   │ Fetch doc  →  │
   │ Chunk → │   │ Hybrid →  │   │ Render     →  │
   │ Embed → │   │ Rerank →  │   │ Return        │
   │ NER  → │   │ Graph  →  │   │               │
   │ Store   │   │ Return    │   │               │
   └────┬────┘   └─────┬─────┘   └───────┬───────┘
        │              │                  │
        ▼              ▼                  ▼
   ┌──────────────────────────────────────────────┐
   │        PostgreSQL 16 (Unified Database)       │
   │                                               │
   │  ┌──────────┐ ┌──────────┐ ┌──────────────┐ │
   │  │ pgvector │ │ pg_search│ │  Apache AGE  │ │
   │  │ (vectors)│ │  (BM25)  │ │  (graph)     │ │
   │  └──────────┘ └──────────┘ └──────────────┘ │
   │                                               │
   │  ┌──────────────────────────────────────────┐ │
   │  │ Relational Tables (documents, chunks,    │ │
   │  │ entities, metadata, original files)      │ │
   │  └──────────────────────────────────────────┘ │
   └───────────────────────────────────────────────┘

   ┌──────────────────────────────────────────────┐
   │          ML Model Services (GPU)              │
   │                                               │
   │  ┌─────────────────┐  ┌──────────────────┐  │
   │  │ Qwen3-Embedding │  │ mxbai-rerank     │  │
   │  │ 0.6B (TEI)      │  │ large-v2         │  │
   │  │ ~2-3 GB VRAM    │  │ ~3 GB VRAM       │  │
   │  └─────────────────┘  └──────────────────┘  │
   │                                               │
   │  ┌─────────────────┐                         │
   │  │ GLiNER large    │                         │
   │  │ v2.5            │                         │
   │  │ ~2-3 GB VRAM    │                         │
   │  └─────────────────┘                         │
   │                                               │
   │  Total GPU: ~8-9 GB / 24 GB RTX 3090         │
   └──────────────────────────────────────────────┘

   ┌──────────────────────────────────────────────┐
   │        File Storage (Local Filesystem)        │
   │                                               │
   │  /data/originals/    — Original uploaded files│
   │  /data/thumbnails/   — Generated thumbnails   │
   │  /data/images/       — Extracted images       │
   │  /data/rendered/     — Rendered HTML/Markdown  │
   └──────────────────────────────────────────────┘
```

### 2.2 GPU Memory Budget (RTX 3090 — 24 GB VRAM)

| Model | VRAM (FP16) | VRAM (INT8) | Recommended |
|-------|------------|------------|-------------|
| Qwen3-Embedding-0.6B | ~2-3 GB | ~1.5 GB | FP16 (quality) |
| mxbai-rerank-large-v2 | ~3 GB | ~1.5 GB | FP16 (quality) |
| GLiNER large v2.5 | ~2-3 GB | ~1-1.5 GB | FP16 (quality) |
| Docling ML models (layout + TableFormer) | ~1-2 GB | N/A | FP16 (GPU-accelerated) |
| **Total** | **~8-11 GB** | **~5-6 GB** | **~8-11 GB** |
| **Remaining headroom** | **~13-16 GB** | | Batch processing buffers |

All models fit comfortably in FP16 with significant headroom for batch processing. Docling's ML models (layout detection via RT-DETR, TableFormer for tables) are GPU-accelerated via PyTorch CUDA, delivering ~6.5x speedup over CPU (0.48s/page vs 3.1s/page). With `layout_batch_size=32-64` on the RTX 3090, throughput approaches ~5-8 pages/sec for PDFs.

### 2.3 System Memory Budget (128 GB RAM)

| Component | Estimated RAM | Notes |
|-----------|--------------|-------|
| PostgreSQL shared_buffers | 16 GB | Generous for knowledge base scale |
| PostgreSQL effective_cache_size | 48 GB | OS page cache for index/data files |
| pgvector HNSW index (1M chunks, 1024 dims) | ~4-6 GB | Float32 vectors + graph structure |
| pg_search Tantivy index | ~1-2 GB | BM25 inverted index |
| AGE graph data | ~1-2 GB | Entity nodes + relationship edges |
| FastAPI + worker processes | ~2-4 GB | API server + background workers |
| ML model CPU overhead | ~4-8 GB | Model loading, tokenizers, batch buffers |
| Docling parsing | ~2-4 GB | Document processing buffers |
| OS + Docker overhead | ~4-8 GB | Container runtime, filesystem cache |
| **Total estimated** | **~42-98 GB** | |
| **Remaining headroom** | **~30-86 GB** | Plenty for growth |

---

## 3. Data Flow Design

### 3.1 Document Ingestion Flow

```
User drops file on macOS app
        │
        ▼
[1. Upload] — multipart POST /api/v1/documents
        │     Streams file to server, returns document_id
        │     Status: "uploading"
        ▼
[2. Store Original] — Save binary to /data/originals/{doc_id}/{filename}
        │     Store file hash for deduplication check
        │     Status: "stored"
        ▼
[3. Parse] — Docling (or format-specific parser)
        │     Status: "parsing" (on entry)
        │     Produces: DoclingDocument JSON
        │     Extracts: headings, paragraphs, tables, images, metadata
        │     Stores: parsed structure in documents table
        │     Stores: extracted images to /data/images/{doc_id}/
        │     Generates: thumbnail via PyMuPDF/QuickLook
        │     Status: "parsed" (on completion)
        ▼
[4. Chunk] — Chonkie SemanticChunker
        │     Status: "chunking" (on entry)
        │     Input: extracted text from DoclingDocument
        │     Output: chunks with text, start_index, end_index, token_count
        │     Stores: chunks in chunks table with document_id FK
        │     Preserves: section/heading context per chunk (from DoclingDocument hierarchy)
        │     Status: "chunked" (on completion)
        ▼
[5. Embed] — Qwen3-Embedding-0.6B (via TEI)
        │     Status: "embedding" (on entry)
        │     Batch embed all chunks
        │     Store 1024-dim vectors in chunks table (pgvector column)
        │     Status: "embedded" (on completion)
        ▼
[6. Index] — pg_search BM25 index auto-updates (transactional)
        │     (No separate status — BM25 indexes update transactionally with chunk inserts)
        ▼
[7. NER] — GLiNER large v2.5
        │     Status: "extracting_entities" (on entry)
        │     Process each chunk with entity labels
        │     Extract entities: persons, orgs, dates, concepts, etc.
        │     Deduplicate and normalize entities across document
        │     Status: "entities_extracted" (on completion)
        ▼
[8. Graph] — Apache AGE
        │     Create/update entity nodes in knowledge graph
        │     Create document→entity edges (MENTIONS relationship)
        │     Create entity→entity edges (CO_OCCURS relationship for entities in same chunk)
        │     Optionally: entity→entity semantic relationships via simple heuristics
        │     Status: "building_graph" → "ready"
        ▼
[9. Complete] — Status: "ready"
        │     Push ProcessingEvent via WebSocket (/ws/events)
        │     Document appears in library
        ▼
[macOS app shows document in library with thumbnail]
```

### 3.2 Semantic Search Flow

```
User types query in search bar (Cmd+K)
        │
        ▼
[1. Query] — POST /api/v1/search
        │     Body: { query: "...", filters: {...}, top_k: 20 }
        ▼
[2. Embed Query] — Qwen3-Embedding-0.6B
        │     Embed the query text → 1024-dim vector
        │     ~5-10ms
        ▼
[3. Hybrid Retrieval] — pgvector + pg_search (parallel)
        │
        ├── [3a. Vector Search] — pgvector HNSW
        │     SELECT chunk_id, 1 - (embedding <=> query_vec) as vec_score
        │     ORDER BY embedding <=> query_vec LIMIT 50
        │     ~5-15ms
        │
        ├── [3b. BM25 Search] — pg_search
        │     SELECT chunk_id, paradedb.score(chunk_id) as bm25_score
        │     WHERE chunks @@@ query_text LIMIT 50
        │     ~5-15ms
        │
        └── [3c. Graph Expansion] — Apache AGE (optional)
              Extract entities from query via GLiNER
              Find related entities in graph via 1-2 hop traversal
              Boost chunks that mention related entities
              ~10-30ms
        │
        ▼
[4. Fusion] — Reciprocal Rank Fusion (RRF)
        │     Combine vector + BM25 + graph scores
        │     Deduplicate by chunk_id
        │     Take top 50 candidates
        │     ~1ms
        ▼
[5. Rerank] — mxbai-rerank-large-v2
        │     Score each (query, chunk_text) pair
        │     Reorder by reranker score
        │     Take top 10
        │     ~200-400ms on RTX 3090
        ▼
[6. Enrich] — Join with document metadata
        │     Add: document title, type, date, thumbnail URL
        │     Add: highlighted snippet with query term bolding
        │     Add: section context (which heading/section the chunk belongs to)
        │     ~2-5ms
        ▼
[7. Return] — Response to macOS frontend
        │     Results with: chunk text, score, document info, snippet
        │     Total latency: ~230-475ms (excellent for interactive use)
        ▼
[macOS app displays results with highlighted snippets]
[User clicks result → navigates to full document viewer]
```

### 3.3 Full Document Retrieval Flow

```
User clicks document in library or search result
        │
        ▼
[1. Fetch Metadata] — GET /api/v1/documents/{id}
        │     Returns: title, type, dates, tags, entity summary
        ▼
[2. Fetch Content] — GET /api/v1/documents/{id}/content?format=rendered
        │     For PDF: returns original file URL (client renders via PDFKit)
        │     For Markdown: returns rendered HTML (client renders via WKWebView)
        │     For DOCX: returns rendered HTML from Docling conversion
        │     For Excel: returns structured table data as JSON
        ▼
[3. Fetch Original] — GET /api/v1/documents/{id}/original (optional)
        │     Returns original binary file for download/export
        ▼
[macOS app renders document in appropriate viewer]
```

---

## 4. Hardware Utilization Strategy

### Lenovo P620 Specs
- **CPU:** AMD Threadripper PRO 3945WX (12 cores / 24 threads, 4.0 GHz boost)
- **RAM:** 128 GB DDR4 ECC
- **GPU:** NVIDIA RTX 3090 (24 GB VRAM, Ampere)
- **Storage:** 2 TB NVMe M.2 SSD
- **OS:** Linux (Docker host)

### Optimization Strategy

**CPU (12C/24T):** Assign cores to workloads:
- PostgreSQL: 4-6 cores (parallel query execution, index builds)
- FastAPI workers: 4 Uvicorn workers (1 core each)
- Document parsing (Docling): 2-4 cores (CPU portions of pipeline — I/O, pre/post-processing)
- Background task processing: 2 cores (Celery/RQ workers)

**GPU:** Serve all four ML workloads simultaneously:
- TEI (Qwen3-Embedding): dedicated container, ~3 GB VRAM, handles batch embedding requests
- Reranker service: dedicated container or loaded on-demand, ~3 GB VRAM
- GLiNER: loaded in ingestion worker process, ~3 GB VRAM
- Docling ML models (layout RT-DETR + TableFormer): ~1-2 GB VRAM, GPU-accelerated via PyTorch CUDA
  - 14.4x layout speedup, 4.3x table speedup, ~6.5x overall vs CPU
  - Configure `layout_batch_size=32-64` and `ocr_batch_size=32-64` on RTX 3090
  - Use EasyOCR (not RapidOCR ONNX default) for GPU-accelerated OCR
  - Call `torch.cuda.empty_cache()` between documents to prevent VRAM leaks

**Storage (2 TB NVMe):**
- PostgreSQL data directory: 200 GB allocation (generous for years of personal use)
- Original documents: 500 GB allocation
- Thumbnails, images, rendered content: 100 GB allocation
- Docker images and layers: 100 GB allocation
- Remaining: ~1.1 TB headroom

**RAM (128 GB):**
- PostgreSQL: 64 GB (shared_buffers=16GB, effective_cache_size=48GB)
- Application services: 16 GB
- OS + Docker: 8 GB
- Headroom: 40 GB

---

## 5. Code Architecture Principles

Both the Python backend and Swift frontend follow the same core architectural principles: **separation by reason to change**, **dependency inversion**, and **composition at the edge**. The specific idioms differ by language, but the structural intent is identical.

### 5.1 Python Backend Architecture

**Layout:** `src/` layout with `pyproject.toml` (PyPA recommended). Prevents accidentally importing the in-development copy.

**Architectural layers (dependency direction: inward):**
- `domain/` — Entities, value objects, core business concepts, abstract ports (`typing.Protocol`)
- `application/` — Use-case orchestration (services). Depends on domain types and ports only.
- `infrastructure/` — Concrete adapters to external systems (PostgreSQL, TEI, GLiNER, Docling). Implements domain ports.
- `entrypoints/` — FastAPI routes, CLI. Depends on application services.
- `bootstrap.py` — Composition root. The **single place** where concrete implementations are wired to abstract interfaces. Only module that imports both application and infrastructure.

**Key principles:**
- **Dependency inversion via `typing.Protocol`:** Services depend on abstract ports, never on concrete infrastructure. Swap implementations without touching service code.
- **No ambiguous `models/` directory:** Split into `domain/` (entities), `schemas/` (Pydantic request/response), and let ORM/table definitions live in `infrastructure/`.
- **No `utils/` junk drawer:** Put logging in `observability/`, text processing in domain-specific modules. Graduate helpers out of utils aggressively.
- **Pydantic `BaseSettings`** for configuration: typed, validated, reads from env vars and `.env` files.
- **Pipeline composition:** Ingestion pipeline stages are individually testable callables composed in the application layer.
- **Testing aligned with architecture:** Unit-test domain and application in isolation; integration-test infrastructure against real deps; protocol-based test doubles require no mocking framework.

**Feature-based packaging option:** As the codebase grows, consider organizing by feature (`documents/`, `search/`, `ingestion/`) rather than purely by layer. Each feature module owns its service, repository port, and schemas. A shared `domain/` holds cross-cutting types. Both approaches work; feature-based often navigates better at scale.

### 5.2 Swift Frontend Architecture

**Layout:** SPM multi-target package with compiler-enforced dependency boundaries. Each target under `Sources/` is a separate module.

**Architectural layers (compiler-enforced via SPM `dependencies` array):**
- `Domain/` — Entities (structs), value objects, abstract ports (protocols). No external dependencies.
- `AppCore/` — Use-case orchestration (services). Depends only on `Domain`.
- `Infrastructure/` — API client, WebSocket client, thumbnail generation. Depends only on `Domain`.
- `Bootstrap/` — Composition root + settings. Depends on `Domain`, `AppCore`, and `Infrastructure`.
- `CortexApp/` — SwiftUI views and app entry point. Depends on `Bootstrap`.

**Key principles:**
- **`package` access level** for cross-target APIs that shouldn't be `public`. Protocols, services, and composition root types use `package` visibility.
- **Value types (structs) by default:** Domain models, services without mutable state. Reach for classes only for reference semantics (connection pools, caches) or actors for shared mutable state.
- **`Sendable` compliance:** Domain structs with value-type properties are `Sendable` automatically. Protocol ports marked `Sendable` ensure conforming types are safe across concurrency domains.
- **Protocol-based dependency injection:** `any GraphRepository` existentials for service-layer injection. Test doubles are plain structs/final classes conforming to protocols — no mocking framework.
- **One primary type per file**, named after the type.
- **No `Utilities/` or `Helpers/`**: Put markdown rendering in a specific module, thumbnail generation in `Infrastructure/`.
- **Typed pipeline composition with generics:** Compiler verifies stage input/output type contracts at build time.

### 5.3 Cross-Cutting Rules (Both Languages)

1. **Separation by reason to change:** If two pieces of code change for different reasons, they belong in different modules.
2. **Dependencies point inward:** Entrypoints → Application → Domain ← Infrastructure. Infrastructure implements domain ports; application consumes them.
3. **Composition root at the edge:** Wire concrete implementations to abstractions in exactly one place (`bootstrap.py` / `CompositionRoot.swift`).
4. **Keep domain models free of infrastructure:** Domain types may depend on stdlib, typing/validation, and small domain helpers — but never on databases, HTTP clients, or ML frameworks.
5. **Transport schemas ≠ domain models:** Pydantic request/response schemas (`schemas/`) and Codable DTOs are separate from domain entities unless they are truly identical.
6. **When to split a module:** Not by line count but by: multiple reasons to change, needing "and" to describe the file's purpose, internal function clusters that don't reference each other, or inability to test in isolation.
7. **Circular imports signal design problems:** Extract shared concepts into a third module or invert the dependency via a protocol.

---

## 6. Key Design Decisions

### 6.1 Monorepo vs Polyrepo
**Decision: Monorepo with service directories**
```
cortex/
  backend/          — Python backend (FastAPI + services)
  frontend/         — Swift/SwiftUI macOS app
  infrastructure/   — Docker Compose, configs, scripts
  docs/             — Documentation
```
Rationale: Single project, single developer — monorepo is simpler.

### 6.2 Task Queue for Async Processing
**Decision: Celery with Redis broker** (or simpler: Python `asyncio` + PostgreSQL-based queue)

For a personal KB, a lightweight approach works:
- Use PostgreSQL as the task queue (SKIP/NOTIFY + polling on a `tasks` table)
- Or use Redis + Celery if you want battle-tested task management
- Document ingestion is async — user uploads, gets back document_id, polls for status
- WebSocket/SSE pushes status updates to macOS frontend

### 6.3 API Design Philosophy
**Decision: RESTful with OpenAPI spec**
- FastAPI auto-generates OpenAPI docs
- Swift client can be auto-generated from OpenAPI spec
- Pragmatic REST: not strictly HATEOAS, but well-structured resource endpoints

### 6.4 Document Storage Strategy
**Decision: Dual storage — original files on filesystem, metadata/content in PostgreSQL**
- Original files stored at `/data/originals/{document_id}/{original_filename}`
- File hash (SHA-256) stored in DB for deduplication
- Parsed content (DoclingDocument JSON) stored in PostgreSQL JSONB column
- Rendered Markdown/HTML stored in PostgreSQL TEXT column
- Thumbnails cached on filesystem at `/data/thumbnails/{document_id}.png`
- Images extracted to `/data/images/{document_id}/`

### 6.5 Embedding Model Serving
**Decision: HuggingFace TEI (Text Embeddings Inference) via Docker**
- Production-grade serving with automatic batching
- HTTP API compatible with OpenAI embedding format
- Built-in health checks and metrics
- Easier to manage than raw PyTorch serving

### 6.6 Search Result Scoring
**Decision: Reciprocal Rank Fusion (RRF) with tunable weights**
```
RRF_score = w_vec / (k + rank_vec) + w_bm25 / (k + rank_bm25) + w_graph / (k + rank_graph)

Default weights: w_vec=0.5, w_bm25=0.3, w_graph=0.2
k = 60 (standard RRF constant)
```
Post-RRF, rerank top-50 with mxbai-rerank-large-v2 for final ordering.

---

## 7. Risk Analysis

### 7.1 Technical Risks

| Risk | Severity | Mitigation |
|------|----------|------------|
| Apache AGE PG version lag | Medium | Pin to PG 16; AGE is optional — can defer graph features |
| Docling parsing quality on edge cases | Low | Fall back to marker-pdf for complex PDFs, python-docx for DOCX |
| Docling GPU memory leak on batch processing | Medium | Call `torch.cuda.empty_cache()` between documents; monitor VRAM usage |
| Docling TableFormer no GPU batching | Low | Tables still get 4.3x GPU speedup per-table; batching may be added in future releases |
| Docling OCR backend misconfiguration | Medium | Use EasyOCR (not RapidOCR ONNX default) for GPU acceleration; set `use_gpu=True` |
| GLiNER accuracy on domain-specific entities | Medium | Start with broad labels, fine-tune on user corrections over time |
| VRAM contention during concurrent requests | Low | TEI handles batching; stagger model loading; 24GB provides ample headroom |
| pg_search AGPL license | Medium | ParadeDB extension is AGPL; evaluate if this matters for personal use (it doesn't for personal) |
| marker-pdf GPL license | Low | Only used as fallback; personal use is fine |

### 7.2 Complexity Risks

| Risk | Severity | Mitigation |
|------|----------|------------|
| Too many moving parts for V1 | High | Phase implementation — core first, graph/NER later |
| SwiftUI learning curve if unfamiliar | Medium | Start with proven patterns; NavigationSplitView template |
| Docker Compose orchestration complexity | Medium | Start simple — 4 containers (PG, TEI, API, Redis) |
| Data migration if schema changes | Low | Use Alembic for PostgreSQL migrations from day 1 |

### 7.3 Recommended Phasing

**Phase 1 (MVP):** Document ingestion + storage + basic search
- Docling parsing → Chonkie chunking → Qwen3 embedding → pgvector search
- Basic macOS app: upload, list, view, search

**Phase 2:** Enhanced search
- Add pg_search BM25 → hybrid search (RRF)
- Add mxbai reranker
- Search result highlighting and snippets

**Phase 3:** Knowledge graph
- Add GLiNER NER extraction
- Add Apache AGE graph storage
- Graph-enhanced search results
- Entity browser in macOS app

**Phase 4:** Polish
- Spotlight integration
- Share extensions
- Advanced filtering (by date, type, entity, tag)
- Collections/folders
- Keyboard shortcuts throughout
