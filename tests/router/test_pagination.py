"""Tests for the pagination helper."""

from __future__ import annotations

from app.pagination import Page, PaginationParams, paginate


class TestPaginationParams:
    """PaginationParams dependency tests."""

    def test_default_params(self):
        p = PaginationParams(page=1, page_size=50)
        assert p.page == 1
        assert p.page_size == 50
        assert p.offset == 0

    def test_page_2(self):
        p = PaginationParams(page=2, page_size=20)
        assert p.page == 2
        assert p.offset == 20


class TestPage:
    """Page model tests."""

    def test_page_model_creation(self):
        page = Page(items=[1, 2, 3], total=100, page=1, page_size=10, total_pages=10)
        assert len(page.items) == 3
        assert page.total == 100
        assert page.total_pages == 10


class TestPaginate:
    """Paginate function tests."""

    def test_paginate_basic(self):
        params = PaginationParams(page=1, page_size=10)
        result = paginate(items=["a", "b"], total=2, params=params)
        assert result.total == 2
        assert result.total_pages == 1
        assert result.items == ["a", "b"]

    def test_paginate_multiple_pages(self):
        params = PaginationParams(page=2, page_size=10)
        result = paginate(items=[], total=25, params=params)
        assert result.total == 25
        assert result.total_pages == 3
        assert result.page == 2

    def test_paginate_empty(self):
        params = PaginationParams(page=1, page_size=10)
        result = paginate(items=[], total=0, params=params)
        assert result.total_pages == 1
