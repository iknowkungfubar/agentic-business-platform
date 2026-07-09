# Multi-stage build for TurinTech Agentic Business Platform
FROM python:3.12-slim AS builder

WORKDIR /app
COPY pyproject.toml README.md ./
RUN pip install --no-cache-dir build && python -m build --wheel

# --- Runtime ---
FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY --from=builder /app/dist/*.whl /tmp/
RUN pip install --no-cache-dir /tmp/*.whl && rm /tmp/*.whl

COPY core/ ./core/
COPY app/ ./app/

RUN useradd -m -u 1000 turin && chown -R turin:turin /app
USER turin

HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
  CMD curl -f http://localhost:8000/health || exit 1

EXPOSE 8000
CMD ["uvicorn", "app.api:app", "--host", "0.0.0.0", "--port", "8000"]
