"""Tests for the structured error handling module."""

from __future__ import annotations

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.errors import ErrorResponse


class TestErrorResponse:
    """ErrorResponse utility tests."""

    def test_make_basic_error(self):
        result = ErrorResponse.make(detail="Not found", status_code=404)
        assert "error" in result
        assert result["error"]["code"] == "HTTP_404"
        assert result["error"]["message"] == "Not found"
        assert result["error"]["status_code"] == 404

    def test_make_with_error_code(self):
        result = ErrorResponse.make(detail="Invalid input", status_code=400, error_code="VALIDATION_ERROR")
        assert result["error"]["code"] == "VALIDATION_ERROR"

    def test_make_with_request_id(self):
        result = ErrorResponse.make(detail="Internal error", status_code=500, request_id="abc-123")
        assert result["error"]["request_id"] == "abc-123"

    def test_error_handler_returns_structured_response(self, api_client):
        """Verify the global HTTPException handler returns structured errors."""
        # Test with an authenticated request to a non-existent resource
        from tests.helpers import auth_headers

        headers = auth_headers(api_client)
        r = api_client.get("/api/v1/agents/99999", headers=headers)
        assert r.status_code == 404
        data = r.json()
        assert "error" in data
        assert data["error"]["code"] == "HTTP_404"
