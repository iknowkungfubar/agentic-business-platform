# Multi-stage build for TurinTech Agentic Business Platform
FROM python:3.12-slim AS builder

WORKDIR /app
COPY pyproject.toml .
RUN pip install --no-cache-dir build && python -m build --wheel

# --- Runtime ---
FROM python:3.12-slim

WORKDIR /app

RUN pip install --no-cache-dir /tmp/*.whl && rm /tmp/*.whl
COPY core/ ./core/
COPY app/ ./app/
COPY --from=builder /app/dist/*.whl /tmp/

RUN useradd -m -u 1000 turin && chown -R turin:turin /app
USER turin

EXPOSE 8000
CMD ["uvicorn", "app.api:app", "--host", "0.0.0.0", "--port", "8000"]
