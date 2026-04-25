"""Shared URL and signal helpers for browser-workflow providers."""

from __future__ import annotations

import urllib.parse
from typing import Any, Mapping

from ..quality import html_profiles as _html_profiles
from ..utils import normalize_text

HTML_STRONG_FULLTEXT_MARKERS = _html_profiles.HTML_STRONG_FULLTEXT_MARKERS
HTML_STRUCTURE_MARKERS = _html_profiles.HTML_STRUCTURE_MARKERS
PDF_URL_TOKENS = ("/doi/pdf/", "/doi/pdfdirect/", "/doi/epdf/", "/fullpdf", ".pdf", "download=true")
dedupe_signals = _html_profiles.dedupe_signals
default_positive_signals = _html_profiles.default_positive_signals
looks_like_abstract_redirect = _html_profiles.looks_like_abstract_redirect


def preferred_html_candidate_from_landing_page(
    doi: str,
    landing_page_url: str | None,
    *,
    hosts: tuple[str, ...],
) -> str | None:
    candidate = normalize_text(landing_page_url)
    if not candidate:
        return None
    parsed = urllib.parse.urlparse(candidate)
    hostname = normalize_text(parsed.hostname or "").lower()
    if parsed.scheme not in {"http", "https"} or not any(
        hostname == token or hostname.endswith(f".{token}")
        for token in hosts
    ):
        return None
    if normalize_text(urllib.parse.unquote(candidate)).lower().find(doi.lower()) == -1:
        return None
    return candidate


def build_base_urls(
    *,
    hosts: tuple[str, ...],
    base_hosts: tuple[str, ...],
    landing_page_url: str | None = None,
) -> list[str]:
    preferred = normalize_text(landing_page_url)
    base_urls: list[str] = []
    if preferred:
        parsed = urllib.parse.urlparse(preferred)
        hostname = normalize_text(parsed.hostname or "").lower()
        if parsed.scheme in {"http", "https"} and hostname:
            if any(hostname == token or hostname.endswith(f".{token}") for token in hosts):
                base_urls.append(f"{parsed.scheme}://{hostname}")
    for host in base_hosts or hosts:
        candidate = f"https://{host}"
        if candidate not in base_urls:
            base_urls.append(candidate)
    return base_urls


def extract_pdf_url_from_crossref(metadata: Mapping[str, Any]) -> str | None:
    for item in metadata.get("fulltext_links") or []:
        if not isinstance(item, Mapping):
            continue
        url = normalize_text(str(item.get("url") or ""))
        if not url:
            continue
        lowered_url = url.lower()
        if any(token in lowered_url for token in PDF_URL_TOKENS) or normalize_text(
            str(item.get("content_type") or "")
        ).lower() == "application/pdf":
            return url
    return None
