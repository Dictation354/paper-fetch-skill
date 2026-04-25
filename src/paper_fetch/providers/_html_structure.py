"""Leaf HTML structure helpers re-exported from the shared semantics module."""

from __future__ import annotations

from ..extraction.html.semantics import (
    BACK_MATTER_TOKENS,
    heading_category,
    node_identity_text,
    normalize_heading,
)

__all__ = [
    "BACK_MATTER_TOKENS",
    "heading_category",
    "node_identity_text",
    "normalize_heading",
]
