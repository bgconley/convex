#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INFRA_DIR="$(dirname "$SCRIPT_DIR")"

# Default backup directory (override with BACKUP_DIR env var)
BACKUP_DIR="${BACKUP_DIR:-$INFRA_DIR/backups}"
TIMESTAMP="$(date +%Y%m%d_%H%M%S)"
BACKUP_NAME="cortex_backup_${TIMESTAMP}"
WORK_DIR="$BACKUP_DIR/$BACKUP_NAME"

echo "=== Cortex Backup ==="
echo ""

# Check for .env (needed for POSTGRES_PASSWORD)
if [ ! -f "$INFRA_DIR/.env" ]; then
    echo "ERROR: $INFRA_DIR/.env not found."
    echo "  Cannot determine database credentials."
    exit 1
fi

# Load env vars
set -a
source "$INFRA_DIR/.env"
set +a

# Verify required containers are running
cd "$INFRA_DIR"
if ! docker compose ps --format json postgres 2>/dev/null | grep -q "running"; then
    echo "ERROR: cortex-postgres container is not running."
    echo "  Start it first: cd $INFRA_DIR && docker compose up -d postgres"
    exit 1
fi

if ! docker compose ps --format json api 2>/dev/null | grep -q "running"; then
    echo "ERROR: cortex-api container is not running."
    echo "  File backup requires the api container (mounts filedata volume)."
    echo "  Start it first: cd $INFRA_DIR && docker compose up -d api"
    exit 1
fi

# Create working directory
mkdir -p "$WORK_DIR"
echo "Backup directory: $WORK_DIR"
echo ""

# 1. PostgreSQL dump
echo "--- Dumping PostgreSQL database ---"
docker compose exec -T postgres pg_dump \
    -U cortex \
    -d cortex \
    --format=custom \
    --compress=6 \
    --verbose \
    > "$WORK_DIR/cortex.pgdump" 2>"$WORK_DIR/pgdump.log"

DUMP_SIZE=$(du -h "$WORK_DIR/cortex.pgdump" | cut -f1)
echo "  Database dump: $DUMP_SIZE"

# 2. File directory tar (originals, thumbnails, images)
echo ""
echo "--- Backing up file storage ---"
docker compose exec -T api tar cf - -C /data . \
    > "$WORK_DIR/filedata.tar"

FILE_SIZE=$(du -h "$WORK_DIR/filedata.tar" | cut -f1)
echo "  File archive: $FILE_SIZE"

# 3. Compress into a single archive
echo ""
echo "--- Creating compressed backup archive ---"
tar czf "$BACKUP_DIR/${BACKUP_NAME}.tar.gz" -C "$BACKUP_DIR" "$BACKUP_NAME"

ARCHIVE_SIZE=$(du -h "$BACKUP_DIR/${BACKUP_NAME}.tar.gz" | cut -f1)

# Clean up working directory
rm -rf "$WORK_DIR"

echo ""
echo "=== Backup complete ==="
echo "  Archive: $BACKUP_DIR/${BACKUP_NAME}.tar.gz ($ARCHIVE_SIZE)"
echo "  Restore: ./restore.sh $BACKUP_DIR/${BACKUP_NAME}.tar.gz"
