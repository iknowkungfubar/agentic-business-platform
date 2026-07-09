"""Shared utilities — pagination helpers for list endpoints."""

from __future__ import annotations

from math import ceil
from typing import Any

from fastapi import Query
from pydantic import BaseModel


class PaginationParams:
    """FastAPI dependency for pagination query parameters."""

    def __init__(
        self,
        page: int = Query(1, ge=1, description="Page number (1-based)"),
        page_size: int = Query(50, ge=1, le=200, description="Items per page"),
    ):
        self.page = page
        self.page_size = page_size
        self.offset = (page - 1) * page_size


class Page(BaseModel):
    """Standard paginated response wrapper."""

    items: list[Any]
    total: int
    page: int
    page_size: int
    total_pages: int


def paginate(items: list[Any], total: int, params: PaginationParams) -> Page:
    """Wrap a list of items into a paginated response."""
    return Page(
        items=items,
        total=total,
        page=params.page,
        page_size=params.page_size,
        total_pages=max(1, ceil(total / params.page_size)),
    )
