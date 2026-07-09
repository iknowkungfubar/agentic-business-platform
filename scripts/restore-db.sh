#!/bin/bash
# TurinTech Platform — PostgreSQL restore script
# Usage: ./scripts/restore-db.sh <backup-file>
set -euo pipefail

if [ $# -lt 1 ]; then
    echo "Usage: $0 <backup-file.sql.gz>"
    exit 1
fi

BACKUP_FILE="$1"
if [ ! -f "$BACKUP_FILE" ]; then
    echo "ERROR: Backup file not found: $BACKUP_FILE"
    exit 1
fi

# Extract connection info
DB_USER=$(echo "$DATABASE_URL" | sed 's|.*://||' | sed 's|:.*||')
DB_PASS=$(echo "$DATABASE_URL" | sed 's|.*://[^:]*:||' | sed 's|@.*||')
DB_HOST=$(echo "$DATABASE_URL" | sed 's|.*@||' | sed 's|:.*||')
DB_PORT=$(echo "$DATABASE_URL" | sed 's|.*@[^:]*:||' | sed 's|/.*||')
DB_NAME=$(echo "$DATABASE_URL" | sed 's|.*/||' | sed 's|?.*||')

export PGPASSWORD="$DB_PASS"

echo "[restore] Starting restore from: $BACKUP_FILE"
echo "[restore] Target: $DB_HOST:$DB_PORT/$DB_NAME"

# Drop and recreate connections
psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d postgres <<SQL
SELECT pg_terminate_backend(pg_stat_activity.pid)
FROM pg_stat_activity
WHERE pg_stat_activity.datname = '$DB_NAME'
  AND pid <> pg_backend_pid();
SQL

# Restore
gunzip -c "$BACKUP_FILE" | psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" "$DB_NAME"

echo "[restore] Complete"
