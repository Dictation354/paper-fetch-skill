"""Leaf text helpers shared by HTML extraction modules."""

from __future__ import annotations

from ..publisher_identity import extract_doi


def extract_doi_from_text(value: str | None) -> str | None:
    return extract_doi(value)

