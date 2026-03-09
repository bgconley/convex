-- Cortex: PostgreSQL extension initialization
-- Tables are managed by Alembic — do NOT create tables here.

-- pgvector: vector similarity search
CREATE EXTENSION IF NOT EXISTS vector;

-- pg_search (ParadeDB): BM25 full-text search via Tantivy
-- May already be created by ParadeDB base image; IF NOT EXISTS is safe.
CREATE EXTENSION IF NOT EXISTS pg_search;

-- Apache AGE: graph database
LOAD 'age';
SET search_path = ag_catalog, "$user", public;
SELECT create_graph('knowledge_graph');
