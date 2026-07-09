#!/bin/bash
# TurinTech Platform — Docker entrypoint
# Handles: signal forwarding, migration automation, server start
set -euo pipefail

# ── Signal handling ──────────────────────────────────────────────
# Forward SIGTERM to the uvicorn process for graceful shutdown
pid=0

cleanup() {
    echo "[entrypoint] Received SIGTERM, shutting down gracefully..."
    if [ "$pid" -ne 0 ]; then
        kill -SIGTERM "$pid" 2>/dev/null || true
        wait "$pid" 2>/dev/null || true
    fi
    echo "[entrypoint] Shutdown complete"
    exit 0
}
trap cleanup SIGTERM SIGINT

# ── Logging ──────────────────────────────────────────────────────
echo "[entrypoint] TurinTech Platform v0.1.0"
echo "[entrypoint] Database: ${DATABASE_URL:-sqlite:///./turin.db}"

# ── Wait for database ────────────────────────────────────────────
# PostgreSQL needs time to start; retry with backoff
if echo "${DATABASE_URL:-}" | grep -q "postgresql"; then
    echo "[entrypoint] Waiting for PostgreSQL..."
    for i in $(seq 1 30); do
        if python -c "
import os, sqlalchemy as sa
try:
    e = sa.create_engine(os.environ['DATABASE_URL'])
    c = e.connect()
    c.execute(sa.text('SELECT 1'))
    c.close()
    print('ready')
except Exception:
    pass
" 2>/dev/null | grep -q ready; then
            echo "[entrypoint] PostgreSQL ready (attempt $i)"
            break
        fi
        echo "[entrypoint] Waiting for PostgreSQL (attempt $i)..."
        sleep 2
    done
fi

# ── Run Alembic migrations ───────────────────────────────────────
echo "[entrypoint] Running Alembic migrations..."
python -m alembic upgrade head 2>&1 || {
    echo "[entrypoint] Alembic migration failed, using init_db fallback"
    python -c "from app.db import init_db; init_db()"
}
echo "[entrypoint] Migrations applied"

# ── Start server ─────────────────────────────────────────────────
echo "[entrypoint] Starting uvicorn..."
exec uvicorn app.api:app \
    --host 0.0.0.0 \
    --port "${PORT:-8000}" \
    --workers "${UVICORN_WORKERS:-4}" \
    --log-level "${LOG_LEVEL:-info}" \
    --no-access-log \
    "$@" &
pid=$!
wait "$pid"
