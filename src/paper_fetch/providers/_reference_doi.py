"""Shared provider reference DOI matching helpers."""

from __future__ import annotations

import re

from ..publisher_identity import DOI_PATTERN, SICI_DOI_PATTERN


def reference_doi_match(value: str) -> re.Match[str] | None:
    for pattern in (SICI_DOI_PATTERN, DOI_PATTERN):
        for match in pattern.finditer(value):
            if match.start() == 0 or not value[match.start() - 1].isalnum():
                return match
    return None


__all__ = ["reference_doi_match"]
