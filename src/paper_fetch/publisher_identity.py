"""Shared DOI and publisher identity helpers for the skill runtime."""

from __future__ import annotations

import re

from .normalize_journal_name import normalize_journal_name

PROVIDER_DISPLAY_NAMES = {
    "springer": "Springer",
    "elsevier": "Elsevier",
    "wiley": "Wiley",
    "crossref": "Crossref",
}
PUBLISHER_PROVIDER_MAP = {
    "springer": "springer",
    "springer nature": "springer",
    "springer science and business media llc": "springer",
    "elsevier": "elsevier",
    "wiley": "wiley",
    "wiley blackwell": "wiley",
    "john wiley and sons": "wiley",
    "john wiley sons": "wiley",
}
DOI_PREFIX_PROVIDER_MAP = {
    "10.1038/": "springer",
    "10.1007/": "springer",
    "10.1186/": "springer",
    "10.1016/": "elsevier",
    "10.1002/": "wiley",
    "10.1111/": "wiley",
}


def normalize_doi(doi: str | None) -> str:
    if not doi:
        return ""
    value = doi.strip().lower()
    value = re.sub(r"^https?://(dx\.)?doi\.org/", "", value)
    value = re.sub(r"^doi:\s*", "", value)
    return value


def infer_provider_from_doi(doi: str | None) -> str | None:
    normalized = normalize_doi(doi)
    for prefix, provider in DOI_PREFIX_PROVIDER_MAP.items():
        if normalized.startswith(prefix):
            return provider
    return None


def infer_provider_from_publisher(publisher: str | None) -> str | None:
    if not publisher:
        return None
    normalized = normalize_journal_name(publisher)
    return PUBLISHER_PROVIDER_MAP.get(normalized)
