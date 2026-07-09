"""Admin dashboard — serves the management web UI."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends
from fastapi.responses import HTMLResponse

from app.routers import require_role

router = APIRouter(prefix="/admin", tags=["admin"])

_HERE = Path(__file__).parent


@router.get("/dashboard", include_in_schema=False)
async def admin_dashboard(user: dict = Depends(require_role("operator"))):
    """Serve the admin dashboard HTML."""
    html_path = _HERE / "templates" / "dashboard.html"
    if not html_path.exists():
        return HTMLResponse("<h1>Dashboard template not found</h1>", status_code=404)
    return HTMLResponse(html_path.read_text())
