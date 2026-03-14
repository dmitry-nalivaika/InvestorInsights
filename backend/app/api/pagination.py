# filepath: backend/app/api/pagination.py
"""Shared pagination utilities for list endpoints.

Provides ``PaginationQuery`` — a FastAPI-injectable dependency that
binds ``limit``, ``offset``, ``sort_by``, and ``sort_order`` from
query parameters.  Reuse across all list endpoints for consistent
pagination behaviour (FR-107).

Usage in a route handler::

    @router.get("/things")
    async def list_things(pagination: PaginationQuery = Depends()):
        items, total = await repo.list(
            limit=pagination.limit,
            offset=pagination.offset,
            sort_by=pagination.sort_by,
            sort_order=pagination.sort_order,
        )
        return pagination.paginate(items, total)
"""

from __future__ import annotations

from typing import Any

from fastapi import Query


class PaginationQuery:
    """Injectable query-parameter group for paginated endpoints.

    FastAPI resolves each ``Query()`` default from the request's
    query string automatically when this class is used as a
    dependency via ``Depends()``.
    """

    def __init__(
        self,
        limit: int = Query(50, ge=1, le=100, description="Items per page"),
        offset: int = Query(0, ge=0, description="Items to skip"),
        sort_by: str = Query("ticker", description="Column to sort by"),
        sort_order: str = Query("asc", pattern="^(asc|desc)$", description="Sort direction"),
    ) -> None:
        self.limit = limit
        self.offset = offset
        self.sort_by = sort_by
        self.sort_order = sort_order

    def paginate(self, items: list[Any], total: int) -> dict[str, Any]:
        """Build a pagination envelope dict.

        This returns a plain dict that FastAPI serialises through
        the ``response_model``.  Callers should set the route's
        ``response_model`` to the appropriate ``PaginatedResponse[T]``
        subclass so Pydantic validates the items.
        """
        return {
            "items": items,
            "total": total,
            "limit": self.limit,
            "offset": self.offset,
        }
