"""Shared provider reference DOI matching helpers."""

from __future__ import annotations

import html
import re
from urllib.parse import unquote

from ..publisher_identity import DOI_PATTERN, SICI_DOI_PATTERN, normalize_doi


def reference_doi_match(value: str) -> re.Match[str] | None:
    for pattern in (SICI_DOI_PATTERN, DOI_PATTERN):
        for match in pattern.finditer(value):
            if match.start() == 0 or not value[match.start() - 1].isalnum():
                return match
    return None


def reference_doi(value: str) -> str | None:
    """Validate a publisher-selected citation candidate before normalization.

    Selection belongs to the adapter; normalization alone also accepts opaque
    identifiers. Match the decoded SICI form before the ordinary DOI pattern.
    """
    value = unquote(html.unescape(value))
    match = reference_doi_match(value)
    return normalize_doi(match.group(0).rstrip(").,;")) if match else None


__all__ = ["reference_doi", "reference_doi_match"]
