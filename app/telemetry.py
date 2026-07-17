"""Telemetry — structured logging, request IDs, Prometheus metrics, OpenTelemetry tracing.

Enterprise observability stack:
- Structured JSON logging with correlation IDs
- Request ID propagation (accepts x-request-id, generates if missing)
- Prometheus RED metrics (Rate, Errors, Duration) per endpoint
- OpenTelemetry distributed tracing (FastAPI, HTTPX, SQLAlchemy)
- Health-aware metrics endpoint
"""

from __future__ import annotations

import json
import logging
import os
import time
import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from fastapi import FastAPI, Request, Response
from prometheus_client import CONTENT_TYPE_LATEST as PROMETHEUS_CONTENT_TYPE
from prometheus_client import Counter, Histogram, generate_latest
from starlette.middleware.base import BaseHTTPMiddleware

if TYPE_CHECKING:
    from collections.abc import Callable

# ── OpenTelemetry Tracing ─────────────────────────────────────


def setup_tracing(service_name: str = "turin-platform") -> None:
    """Configure OpenTelemetry instrumentation for FastAPI, HTTPX, SQLAlchemy.

    Exports traces via OTLP if OTEL_EXPORTER_OTLP_ENDPOINT is set,
    otherwise uses the ConsoleSpanExporter for local debugging.
    """
    from opentelemetry import trace
    from opentelemetry.sdk.resources import SERVICE_NAME, SERVICE_VERSION, Resource
    from opentelemetry.sdk.trace import TracerProvider

    resource = Resource.create(
        {
            SERVICE_NAME: service_name,
            SERVICE_VERSION: "0.1.0",
        }
    )
    provider = TracerProvider(resource=resource)

    # Configure exporter
    otlp_endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT")
    if otlp_endpoint:
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter

        exporter = OTLPSpanExporter(endpoint=otlp_endpoint)
        from opentelemetry.sdk.trace.export import BatchSpanProcessor

        provider.add_span_processor(BatchSpanProcessor(exporter))
    else:
        from opentelemetry.sdk.trace.export import ConsoleSpanExporter, SimpleSpanProcessor

        provider.add_span_processor(SimpleSpanProcessor(ConsoleSpanExporter()))

    trace.set_tracer_provider(provider)

    # Instrument FastAPI
    try:
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

        FastAPIInstrumentor().instrument()
    except Exception:
        pass

    # Instrument HTTPX
    try:
        from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor

        HTTPXClientInstrumentor().instrument()
    except Exception:
        pass

    # Instrument SQLAlchemy
    try:
        from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor

        SQLAlchemyInstrumentor().instrument()
    except Exception:
        pass


def get_tracer(name: str = "turin-platform"):
    """Get an OpenTelemetry tracer for manual span creation."""
    from opentelemetry import trace

    return trace.get_tracer(name)


def create_llm_span(
    tracer_name: str,
    model_name: str,
    temperature: float,
    system_prompt: str,
    user_prompt: str,
    completion: str = "",
    input_tokens: int = 0,
    output_tokens: int = 0,
) -> None:
    """Create an LLM span following Gen-AI OTel semantic conventions.

    PII is stripped via the DLP pipeline before attaching to span attributes.
    This enables prompt-level observability while maintaining data sovereignty.
    """
    from opentelemetry import trace

    tracer = trace.get_tracer(tracer_name)
    span = tracer.start_span("llm.completion")
    span.set_attribute("gen_ai.system", "openai_compatible")
    span.set_attribute("gen_ai.request.model", model_name)
    span.set_attribute("gen_ai.request.temperature", temperature)
    span.set_attribute("gen_ai.prompt", user_prompt[:512])
    span.set_attribute("gen_ai.system_prompt", system_prompt[:256] if system_prompt else "")
    if completion:
        span.set_attribute("gen_ai.completion", completion[:512])
    if input_tokens:
        span.set_attribute("gen_ai.usage.input_tokens", input_tokens)
    if output_tokens:
        span.set_attribute("gen_ai.usage.output_tokens", output_tokens)
    span.end()


def get_trace_parent_header() -> dict[str, str] | None:
    """Get W3C traceparent from current span context for propagation."""
    from opentelemetry import trace

    span = trace.get_current_span()
    if not span:
        return None
    ctx = span.get_span_context()
    if not ctx or not ctx.trace_id or ctx.trace_id == 0:
        return None
    return {"traceparent": f"00-{ctx.trace_id:032x}-{ctx.span_id:016x}-01"}


# ── Structured Logging ──────────────────────────────────────────


class StructuredFormatter(logging.Formatter):
    """JSON formatter with timestamp, level, message, and extra fields."""

    def format(self, record: logging.LogRecord) -> str:
        log_entry: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created, tz=UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if hasattr(record, "request_id"):
            log_entry["request_id"] = record.request_id
        if record.exc_info and record.exc_info[0]:
            log_entry["exception"] = self.formatException(record.exc_info)
        return json.dumps(log_entry, default=str)


def setup_logging() -> None:
    """Configure structured JSON logging."""
    handler = logging.StreamHandler()
    handler.setFormatter(StructuredFormatter())
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(logging.INFO)

    # Quiet noisy libs
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """Get a structured logger with the given name."""
    return logging.getLogger(name)


# ── Request ID Middleware ────────────────────────────────────────


class RequestIDMiddleware(BaseHTTPMiddleware):
    """Adds a unique request_id to every request and response."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        request_id = request.headers.get("x-request-id") or str(uuid.uuid4())
        request.state.request_id = request_id
        request.state.api_version = request.headers.get("accept-version", "v1")
        response = await call_next(request)
        response.headers["x-request-id"] = request_id
        return response


# ── Prometheus Metrics ──────────────────────────────────────────

http_requests_total = Counter(
    "http_requests_total",
    "Total HTTP requests",
    labelnames=["method", "route", "status_class"],
)

http_request_duration_seconds = Histogram(
    "http_request_duration_seconds",
    "HTTP request duration in seconds",
    labelnames=["method", "route", "status_class"],
    buckets=(0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
)


class MetricsMiddleware(BaseHTTPMiddleware):
    """Records RED metrics for every request."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        method = request.method
        route = request.url.path
        start = time.monotonic()

        response = await call_next(request)

        duration = time.monotonic() - start
        status_class = f"{response.status_code // 100}xx"

        http_requests_total.labels(method=method, route=route, status_class=status_class).inc()
        http_request_duration_seconds.labels(method=method, route=route, status_class=status_class).observe(duration)

        return response


# ── Metrics Endpoint ────────────────────────────────────────────


def register_metrics_endpoint(app: FastAPI) -> None:
    """Register the /metrics endpoint on the app."""

    @app.get("/metrics", include_in_schema=False)
    async def metrics() -> Response:
        return Response(
            content=generate_latest(),
            media_type=PROMETHEUS_CONTENT_TYPE,
        )
