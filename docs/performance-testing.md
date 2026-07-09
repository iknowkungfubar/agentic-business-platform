# Performance Testing — TurinTech Platform

## Quick Start

```bash
# Install locust
pip install locust

# Start the platform (local dev)
uv run uvicorn app.api:app --reload

# In another terminal, run load tests
locust -f locustfile.py --host=http://localhost:8000
# Open http://localhost:8089 in your browser

# Headless mode (CI)
locust -f locustfile.py --host=http://localhost:8000 \
  --headless -u 10 -r 2 --run-time 30s --csv=results
```

## Test Scenarios

The `locustfile.py` simulates a platform user with 7 task types:

| Task | Weight | Description |
|------|--------|-------------|
| `check_health` | 3 | GET /health — most frequent call |
| `classify` | 2 | POST /api/v1/classify |
| `list_agents` | 2 | GET /api/v1/agents — paginated |
| `evaluate_policy` | 1 | POST /api/v1/policies/test |
| `eval_criteria` | 1 | GET /api/v1/eval/criteria |
| `list_policies` | 1 | GET /api/v1/policies |

## Docker Compose Load Test

```bash
# Start the full stack with PostgreSQL
docker compose up -d

# Install locust
pip install locust

# Run load test against the containerized API
locust -f locustfile.py --host=http://localhost:8000 \
  --headless -u 20 -r 5 --run-time 60s
```

## Interpreting Results

After a test run, check `results_stats.csv` for:
- **Request count** per endpoint
- **Failure rate** — should be < 1% under normal load
- **Average response time** — should be < 200ms for health, < 500ms for API calls
- **95th percentile** — p95 should be < 2x average

## Prometheus Metrics

While running, also check:
```bash
curl http://localhost:8000/metrics | grep http_requests
```

Key metrics:
- `http_requests_total` — count by method, route, status class
- `http_request_duration_seconds` — latency histogram
