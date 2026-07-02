"""Shared citation/reference anchor URL semantics."""

from __future__ import annotations

import re

from ..common_patterns import REFERENCE_TOKEN_VOCABULARY
from ..utils import normalize_text

_REFERENCE_HREF_TOKEN_PATTERN = "|".join(
    re.escape(token) for token in REFERENCE_TOKEN_VOCABULARY
)
REFERENCE_HREF_FRAGMENT_PATTERN = re.compile(
    r"(?:"
    rf"(?:^|[-_/])(?:{_REFERENCE_HREF_TOKEN_PATTERN})\b[-_\w]*"
    r"|(?:^core-collateral-r\d+[a-z0-9-]*$)"
    r"|(?:^(?:r|ref|bibr|bib|cr)\d+[a-z0-9-]*$)"
    r")",
    flags=re.IGNORECASE,
)


def looks_like_reference_href(href: str | None) -> bool:
    normalized = normalize_text(str(href or ""))
    if not normalized:
        return False
    fragment = (
        normalized.split("#", 1)[1]
        if "#" in normalized
        else normalized[1:]
        if normalized.startswith("#")
        else ""
    )
    if not fragment:
        return False
    return bool(REFERENCE_HREF_FRAGMENT_PATTERN.search(fragment))
