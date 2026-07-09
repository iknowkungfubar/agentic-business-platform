#!/bin/bash
# Wait for API health endpoint
set -euo pipefail

URL="${1:-http://localhost:8000/health}"
TIMEOUT="${2:-60}"
INTERVAL="${3:-2}"

for i in $(seq 1 $((TIMEOUT / INTERVAL))); do
  if curl -sf "$URL" > /dev/null 2>&1; then
    echo "API ready after $((i * INTERVAL))s"
    exit 0
  fi
  sleep "$INTERVAL"
done

echo "TIMEOUT: API not healthy after ${TIMEOUT}s"
exit 1
