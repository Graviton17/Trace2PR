"""Shared pagination helper for Supabase-backed list endpoints."""
import math
from typing import Any


def paginate_range(page: int, per_page: int) -> tuple[int, int]:
    """Convert a 1-indexed (page, per_page) pair into a 0-indexed
    inclusive [start, end] range for supabase-py's `.range()`."""
    start = (page - 1) * per_page
    end = start + per_page - 1
    return start, end


def build_paginated_response(
    items: list[Any], total: int, page: int, per_page: int
) -> dict[str, Any]:
    pages = math.ceil(total / per_page) if per_page else 0
    return {
        "items": items,
        "total": total,
        "page": page,
        "per_page": per_page,
        "pages": pages,
    }
