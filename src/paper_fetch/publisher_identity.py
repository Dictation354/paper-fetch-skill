"""Shared DOI and publisher identity helpers for the skill runtime."""

from __future__ import annotations

import re
import urllib.parse

from .normalize_journal_name import normalize_journal_name

PROVIDER_DISPLAY_NAMES = {
    "springer": "Springer",
    "elsevier": "Elsevier",
    "wiley": "Wiley",
    "science": "Science",
    "pnas": "PNAS",
    "crossref": "Crossref",
}
PUBLISHER_PROVIDER_MAP = {
    "springer": "springer",
    "springer nature": "springer",
    "springer science and business media llc": "springer",
    "elsevier": "elsevier",
    "elsevier bv": "elsevier",
    "elsevier ltd": "elsevier",
    "elsevier masson sas": "elsevier",
    "wiley": "wiley",
    "wiley blackwell": "wiley",
    "john wiley and sons": "wiley",
    "john wiley sons": "wiley",
    "american association for the advancement of science": "science",
    "aaas": "science",
    "proceedings of the national academy of sciences": "pnas",
    "proceedings of the national academy of sciences of the united states of america": "pnas",
}
DOI_PREFIX_PROVIDER_MAP = {
    "10.1038/": "springer",
    "10.1007/": "springer",
    "10.1186/": "springer",
    "10.1016/": "elsevier",
    "10.1002/": "wiley",
    "10.1111/": "wiley",
    "10.1126/": "science",
    "10.1073/": "pnas",
}
URL_PROVIDER_TOKENS = {
    "elsevier": ("sciencedirect.com", "elsevier.com"),
    "springer": ("springer.com", "springernature.com", "nature.com", "biomedcentral.com"),
    "wiley": ("wiley.com", "onlinelibrary.wiley.com"),
    "science": ("science.org",),
    "pnas": ("pnas.org",),
}
DOI_PATTERN = re.compile(r"10\.\d{4,9}/[^\s\"'<>]+", flags=re.IGNORECASE)


def normalize_doi(doi: str | None) -> str:
    if not doi:
        return ""
    value = doi.strip().lower()
    value = re.sub(r"^https?://(dx\.)?doi\.org/", "", value)
    value = re.sub(r"^doi:\s*", "", value)
    return value


def extract_doi(text: str | None) -> str | None:
    if not text:
        return None
    match = DOI_PATTERN.search(text)
    if not match:
        return None
    return normalize_doi(match.group(0).rstrip(").,;"))


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


def infer_provider_from_url(url: str | None) -> str | None:
    if not url:
        return None
    hostname = urllib.parse.urlparse(url).netloc.lower()
    for provider, tokens in URL_PROVIDER_TOKENS.items():
        if any(token in hostname for token in tokens):
            return provider
    return None


def ordered_provider_candidates(
    *,
    landing_urls: list[str | None] | None = None,
    publishers: list[str | None] | None = None,
    doi: str | None = None,
) -> list[tuple[str, str]]:
    candidates: list[tuple[str, str]] = []
    seen: set[str] = set()

    for url in landing_urls or []:
        provider = infer_provider_from_url(url)
        if provider and provider not in seen:
            seen.add(provider)
            candidates.append((provider, "domain"))

    for publisher in publishers or []:
        provider = infer_provider_from_publisher(publisher)
        if provider and provider not in seen:
            seen.add(provider)
            candidates.append((provider, "publisher"))

    provider = infer_provider_from_doi(doi)
    if provider and provider not in seen:
        candidates.append((provider, "doi"))
    return candidates


def infer_provider_from_signals(
    *,
    landing_urls: list[str | None] | None = None,
    publishers: list[str | None] | None = None,
    doi: str | None = None,
) -> str | None:
    candidates = ordered_provider_candidates(
        landing_urls=landing_urls,
        publishers=publishers,
        doi=doi,
    )
    return candidates[0][0] if candidates else None
