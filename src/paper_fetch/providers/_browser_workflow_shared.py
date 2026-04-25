"""Shared URL and signal helpers for browser-workflow providers."""

from __future__ import annotations

import urllib.parse

from ..quality import html_profiles as _html_profiles
from ..utils import normalize_text
from ._pdf_candidates import extract_pdf_url_from_crossref as extract_pdf_url_from_crossref

HTML_STRONG_FULLTEXT_MARKERS = _html_profiles.HTML_STRONG_FULLTEXT_MARKERS
HTML_STRUCTURE_MARKERS = _html_profiles.HTML_STRUCTURE_MARKERS
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


def _append_unique(candidates: list[str], candidate: str | None) -> None:
    normalized = normalize_text(candidate)
    if normalized and normalized not in candidates:
        candidates.append(normalized)


def build_browser_workflow_html_candidates(
    doi: str,
    landing_page_url: str | None,
    *,
    hosts: tuple[str, ...],
    base_hosts: tuple[str, ...],
    path_templates: tuple[str, ...],
) -> list[str]:
    candidates: list[str] = []
    preferred_candidate = preferred_html_candidate_from_landing_page(
        doi,
        landing_page_url,
        hosts=hosts,
    )
    _append_unique(candidates, preferred_candidate)
    for base in build_base_urls(hosts=hosts, base_hosts=base_hosts, landing_page_url=landing_page_url):
        for template in path_templates:
            _append_unique(candidates, f"{base}{template.format(doi=doi)}")
    return candidates


def build_browser_workflow_pdf_candidates(
    doi: str,
    crossref_pdf_url: str | None,
    *,
    hosts: tuple[str, ...],
    base_hosts: tuple[str, ...],
    path_templates: tuple[str, ...],
    crossref_pdf_position: int,
    base_seed_url: str | None = None,
) -> list[str]:
    generated_candidates: list[str] = []
    for base in build_base_urls(hosts=hosts, base_hosts=base_hosts, landing_page_url=base_seed_url):
        for template in path_templates:
            _append_unique(generated_candidates, f"{base}{template.format(doi=doi)}")

    crossref_candidate = normalize_text(crossref_pdf_url)
    if not crossref_candidate:
        return generated_candidates

    candidates: list[str] = []
    inserted = False
    insert_at = max(crossref_pdf_position, 0)
    for index, candidate in enumerate(generated_candidates):
        if index == insert_at:
            _append_unique(candidates, crossref_candidate)
            inserted = True
        _append_unique(candidates, candidate)
    if not inserted:
        _append_unique(candidates, crossref_candidate)
    return candidates
