#!/bin/bash
# TurinTech Platform — PostgreSQL backup script
# Usage: ./scripts/backup-db.sh [output-dir]
# Cron: 0 2 * * * /app/scripts/backup-db.sh /backups
set -euo pipefail

OUTPUT_DIR="${1:-./backups}"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
mkdir -p "$OUTPUT_DIR"

# Extract connection info from DATABASE_URL
if [ -z "${DATABASE_URL:-}" ]; then
    echo "ERROR: DATABASE_URL not set"
    exit 1
fi

# Parse DATABASE_URL (postgresql://user:pass@host:port/dbname)
DB_USER=$(echo "$DATABASE_URL" | sed 's|.*://||' | sed 's|:.*||')
DB_PASS=$(echo "$DATABASE_URL" | sed 's|.*://[^:]*:||' | sed 's|@.*||')
DB_HOST=$(echo "$DATABASE_URL" | sed 's|.*@||' | sed 's|:.*||')
DB_PORT=$(echo "$DATABASE_URL" | sed 's|.*@[^:]*:||' | sed 's|/.*||')
DB_NAME=$(echo "$DATABASE_URL" | sed 's|.*/||' | sed 's|?.*||')

export PGPASSWORD="$DB_PASS"

echo "[backup] Starting PostgreSQL backup..."
echo "[backup] Host: $DB_HOST:$DB_PORT"
echo "[backup] Database: $DB_NAME"

# Dump with compression
DUMP_FILE="$OUTPUT_DIR/turin-platform-$TIMESTAMP.sql.gz"
pg_dump -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" "$DB_NAME" | gzip > "$DUMP_FILE"

# Create latest symlink
ln -sf "$DUMP_FILE" "$OUTPUT_DIR/turin-platform-latest.sql.gz"

echo "[backup] Complete: $DUMP_FILE"
echo "[backup] Size: $(du -h "$DUMP_FILE" | cut -f1)"

# Rotate: keep last 30 days
find "$OUTPUT_DIR" -name "turin-platform-*.sql.gz" -mtime +30 -delete
echo "[backup] Rotation: removed backups older than 30 days"
