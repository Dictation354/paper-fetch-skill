"""HTTP header helpers."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any


def header_value(headers: Mapping[str, Any] | None, key: str, default: str = "") -> str:
    """Case-insensitive header lookup."""
    if not headers:
        return default
    target = key.lower()
    for header_key, value in headers.items():
        if str(header_key).lower() == target:
            return str(value or "")
    return default


__all__ = ["header_value"]
