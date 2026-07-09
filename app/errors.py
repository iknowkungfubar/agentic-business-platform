"""Enterprise error handling — structured error responses, exception handlers."""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse


class ErrorResponse:
    """Standardized error response builder."""

    @staticmethod
    def make(
        detail: str,
        status_code: int = 400,
        error_code: str | None = None,
        request_id: str | None = None,
    ) -> dict[str, Any]:
        """Build a structured error response body."""
        body: dict[str, Any] = {
            "error": {
                "code": error_code or f"HTTP_{status_code}",
                "message": detail,
                "status_code": status_code,
            }
        }
        if request_id:
            body["error"]["request_id"] = request_id
        return body


def register_error_handlers(app: FastAPI) -> None:
    """Register global exception handlers for structured error responses."""

    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
        request_id = getattr(request.state, "request_id", None)
        return JSONResponse(
            status_code=exc.status_code,
            content=ErrorResponse.make(
                detail=exc.detail,
                status_code=exc.status_code,
                error_code=f"HTTP_{exc.status_code}",
                request_id=request_id,
            ),
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        request_id = getattr(request.state, "request_id", None)
        return JSONResponse(
            status_code=500,
            content=ErrorResponse.make(
                detail="An internal error occurred",
                status_code=500,
                error_code="INTERNAL_ERROR",
                request_id=request_id,
            ),
        )
