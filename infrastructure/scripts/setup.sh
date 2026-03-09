#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INFRA_DIR="$(dirname "$SCRIPT_DIR")"
ROOT_DIR="$(dirname "$INFRA_DIR")"

echo "=== Cortex Infrastructure Setup ==="
echo ""

# Check for .env
if [ ! -f "$INFRA_DIR/.env" ]; then
    echo "ERROR: $INFRA_DIR/.env not found."
    echo "  cp $INFRA_DIR/.env.example $INFRA_DIR/.env"
    echo "  Then edit .env and set POSTGRES_PASSWORD."
    exit 1
fi

# Check Docker
if ! command -v docker &> /dev/null; then
    echo "ERROR: docker is not installed or not in PATH."
    exit 1
fi

# Check NVIDIA runtime (warn, don't fail — postgres/redis don't need it)
if ! docker info 2>/dev/null | grep -q "nvidia"; then
    echo "WARNING: NVIDIA Docker runtime not detected."
    echo "  GPU containers (embedder, api, worker) may fail to start."
    echo "  Install nvidia-container-toolkit if running on the GPU server."
    echo ""
fi

cd "$INFRA_DIR"

echo "--- Building custom PostgreSQL image (pgvector + pg_search + AGE) ---"
docker compose build postgres

echo ""
echo "--- Starting infrastructure services ---"
docker compose up -d postgres redis

echo ""
echo "--- Waiting for PostgreSQL health check ---"
until docker compose exec -T postgres pg_isready -U cortex -d cortex 2>/dev/null; do
    echo "  Waiting for PostgreSQL..."
    sleep 2
done
echo "  PostgreSQL is ready."

echo ""
echo "--- Waiting for Redis health check ---"
until docker compose exec -T redis redis-cli ping 2>/dev/null | grep -q PONG; do
    echo "  Waiting for Redis..."
    sleep 2
done
echo "  Redis is ready."

echo ""
echo "--- Verifying PostgreSQL extensions ---"
docker compose exec -T postgres psql -U cortex -d cortex -c "
    SELECT extname, extversion FROM pg_extension
    WHERE extname IN ('vector', 'pg_search', 'age')
    ORDER BY extname;
"

echo ""
echo "--- Verifying knowledge graph ---"
docker compose exec -T postgres psql -U cortex -d cortex -c "
    LOAD 'age';
    SET search_path = ag_catalog, \"\\\$user\", public;
    SELECT * FROM ag_graph WHERE name = 'knowledge_graph';
"

echo ""
echo "--- Starting TEI embedder (GPU) ---"
docker compose up -d embedder

echo ""
echo "--- TEI may take 1-2 minutes to download and load the model. ---"
echo "    Check status: docker compose logs -f embedder"
echo ""

echo "=== Setup complete ==="
echo ""
echo "Next steps:"
echo "  1. Wait for TEI to be healthy: docker compose ps"
echo "  2. Set up the backend:  cd $ROOT_DIR/backend && uv sync && uv run alembic upgrade head"
echo "  3. Start the API:       uv run python -m cortex"
echo "  4. Build the frontend:  cd $ROOT_DIR/frontend && swift build"
