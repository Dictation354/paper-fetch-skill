"""Shared URL and signal helpers for browser-workflow providers."""

from __future__ import annotations

import urllib.parse
from typing import Any, Mapping

from ..utils import normalize_text

HTML_STRONG_FULLTEXT_MARKERS = (
    'property="articleBody"',
    "property='articleBody'",
    'itemprop="articleBody"',
    "itemprop='articleBody'",
)
HTML_STRUCTURE_MARKERS = (
    'data-article-access="full"',
    "data-article-access='full'",
    'data-article-access-type="full"',
    "data-article-access-type='full'",
    'id="bodymatter"',
    "id='bodymatter'",
)
PDF_URL_TOKENS = ("/doi/pdf/", "/doi/pdfdirect/", "/doi/epdf/", "/fullpdf", ".pdf", "download=true")


def dedupe_signals(values: list[str]) -> list[str]:
    return list(dict.fromkeys(value for value in values if value))


def default_positive_signals(html_text: str) -> tuple[list[str], list[str], list[str]]:
    strong: list[str] = []
    soft: list[str] = []
    lowered = html_text.lower()
    if any(marker in lowered for marker in HTML_STRONG_FULLTEXT_MARKERS):
        strong.append("article_body_marker")
    if any(marker in lowered for marker in HTML_STRUCTURE_MARKERS):
        soft.append("article_body_structure_marker")
    if "<article" in lowered:
        soft.append("article_tag_present")
    return dedupe_signals(strong), dedupe_signals(soft), []


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


def looks_like_abstract_redirect(requested_url: str, final_url: str | None) -> bool:
    if not final_url:
        return False
    requested = requested_url.lower()
    final = final_url.lower()
    return "/doi/full/" in requested and "/doi/abs/" in final and requested != final
