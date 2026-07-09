#!/bin/bash
# TurinTech Platform — Data Retention Cleanup
# Deletes stale records beyond configurable TTLs
# Cron: 0 3 * * 0 /app/scripts/retention-cleanup.sh
set -euo pipefail

TTL_DAYS="${RETENTION_TTL_DAYS:-90}"
DB_URL="${DATABASE_URL:-sqlite:///./turin.db}"

echo "[retention] Starting cleanup for records older than ${TTL_DAYS} days"
echo "[retention] Database: ${DB_URL}"

python -c "
import os
import sys
from datetime import datetime, timedelta, timezone

os.environ['DATABASE_URL'] = '$DB_URL'
from app.database import _get_engine, reset_engine
from sqlalchemy import text

reset_engine()
engine = _get_engine()
cutoff = datetime.now(timezone.utc) - timedelta(days=${TTL_DAYS})
cutoff_str = cutoff.isoformat()

results = {}

with engine.connect() as conn:
    # Old audit events
    r = conn.execute(
        text(\"DELETE FROM audit_events WHERE timestamp < :cutoff\"),
        {\"cutoff\": cutoff_str}
    )
    results['audit_events'] = r.rowcount

    # Old conversations (cascade deletes messages)
    r = conn.execute(
        text(\"DELETE FROM conversations WHERE updated_at < :cutoff\"),
        {\"cutoff\": cutoff_str}
    )
    results['conversations'] = r.rowcount

    # Old scan results
    r = conn.execute(
        text(\"DELETE FROM mcp_scan_results WHERE created_at < :cutoff\"),
        {\"cutoff\": cutoff_str}
    )
    results['mcp_scan_results'] = r.rowcount

    conn.commit()

for table, count in results.items():
    if count:
        print(f'[retention] Purged {count} records from {table}')
print('[retention] Cleanup complete')
"
