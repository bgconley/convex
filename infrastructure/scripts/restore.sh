#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INFRA_DIR="$(dirname "$SCRIPT_DIR")"

if [ $# -ne 1 ]; then
    echo "Usage: $0 <backup_archive.tar.gz>"
    echo "  Example: $0 ../backups/cortex_backup_20260312_143000.tar.gz"
    exit 1
fi

ARCHIVE="$1"

if [ ! -f "$ARCHIVE" ]; then
    echo "ERROR: Backup archive not found: $ARCHIVE"
    exit 1
fi

echo "=== Cortex Restore ==="
echo ""
echo "WARNING: This will REPLACE all current data with the backup."
echo "  Archive: $ARCHIVE"
echo ""
read -r -p "Continue? [y/N] " confirm
if [[ ! "$confirm" =~ ^[Yy]$ ]]; then
    echo "Aborted."
    exit 0
fi

# Check for .env
if [ ! -f "$INFRA_DIR/.env" ]; then
    echo "ERROR: $INFRA_DIR/.env not found."
    echo "  Cannot determine database credentials."
    exit 1
fi

# Load env vars
set -a
source "$INFRA_DIR/.env"
set +a

cd "$INFRA_DIR"

# Extract archive to temp directory
TEMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TEMP_DIR"' EXIT

echo "--- Extracting backup archive ---"
tar xzf "$ARCHIVE" -C "$TEMP_DIR"

# Find the extracted backup directory (single child of TEMP_DIR)
BACKUP_DIR="$(find "$TEMP_DIR" -mindepth 1 -maxdepth 1 -type d | head -1)"
if [ -z "$BACKUP_DIR" ]; then
    echo "ERROR: Archive does not contain a backup directory."
    exit 1
fi

if [ ! -f "$BACKUP_DIR/cortex.pgdump" ] || [ ! -f "$BACKUP_DIR/filedata.tar" ]; then
    echo "ERROR: Archive is missing required files (cortex.pgdump, filedata.tar)."
    exit 1
fi

echo ""

# 1. Stop API and worker (keep postgres running for restore)
echo "--- Stopping API and worker ---"
docker compose stop api worker 2>/dev/null || true

# 2. Restore PostgreSQL
echo ""
echo "--- Restoring PostgreSQL database ---"
# Drop and recreate the database for a clean restore
docker compose exec -T postgres psql -U cortex -d postgres -c "
    SELECT pg_terminate_backend(pid) FROM pg_stat_activity
    WHERE datname = 'cortex' AND pid <> pg_backend_pid();
" > /dev/null 2>&1 || true

docker compose exec -T postgres psql -U cortex -d postgres -c "DROP DATABASE IF EXISTS cortex;"
docker compose exec -T postgres psql -U cortex -d postgres -c "CREATE DATABASE cortex OWNER cortex;"

# Restore from custom-format dump
# pg_restore exits non-zero for warnings (e.g., "extension already exists") so we capture
# the exit code and check for actual failures via table count validation below.
RESTORE_EXIT=0
docker compose exec -T postgres pg_restore \
    -U cortex \
    -d cortex \
    --no-owner \
    --verbose \
    < "$BACKUP_DIR/cortex.pgdump" 2>"$TEMP_DIR/pgrestore.log" || RESTORE_EXIT=$?

# Validate the restore produced data — check that core tables exist
TABLE_COUNT=$(docker compose exec -T postgres psql -U cortex -d cortex -tA -c "
    SELECT count(*) FROM information_schema.tables
    WHERE table_schema = 'public' AND table_name IN ('documents', 'chunks', 'entities', 'collections');
")

if [ "$TABLE_COUNT" -lt 4 ]; then
    echo "  ERROR: Database restore failed — expected core tables not found."
    echo "  pg_restore exit code: $RESTORE_EXIT"
    echo "  Restore log: $TEMP_DIR/pgrestore.log"
    # Don't clean up temp dir so user can inspect the log
    trap - EXIT
    exit 1
fi

echo "  Database restored (pg_restore exit code: $RESTORE_EXIT, core tables verified)."
if [ "$RESTORE_EXIT" -ne 0 ]; then
    echo "  Note: pg_restore reported warnings — see $TEMP_DIR/pgrestore.log"
    # Keep temp dir for log inspection
    trap - EXIT
fi

# 3. Restore file storage via a temporary container mounting the same volume
echo ""
echo "--- Restoring file storage ---"
# Use a lightweight container with the filedata volume — api is stopped
docker run --rm -i \
    -v "$(docker volume ls -q | grep -E '(^|_)filedata$' | head -1)":/data \
    alpine:3 sh -c "rm -rf /data/* && tar xf - -C /data" \
    < "$BACKUP_DIR/filedata.tar"
echo "  Files restored."

# 4. Rebuild search indexes
echo ""
echo "--- Rebuilding BM25 search index ---"
docker compose exec -T postgres psql -U cortex -d cortex -c "REINDEX INDEX CONCURRENTLY idx_chunks_bm25;" 2>/dev/null || true
echo "  Indexes rebuilt."

# 5. Restart services
echo ""
echo "--- Restarting API and worker ---"
docker compose up -d api worker

echo ""
echo "=== Restore complete ==="
echo "  Database and files restored from: $ARCHIVE"
echo "  Services restarted. Verify: docker compose ps"
