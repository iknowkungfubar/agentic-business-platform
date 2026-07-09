"""Tests for the structured error handling module."""

from __future__ import annotations

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

    def test_error_handler_runs_on_unauthenticated(self, api_client):
        """Verify the error handler returns structured errors on auth failures."""
        r = api_client.get("/api/v1/eval/criteria")
        assert r.status_code == 401
        data = r.json()
        assert "error" in data
        assert data["error"]["code"] == "HTTP_401"
