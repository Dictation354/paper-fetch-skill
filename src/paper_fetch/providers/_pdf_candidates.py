"""Helpers for extracting and constructing publisher PDF fallback candidates."""

from __future__ import annotations

import urllib.parse
from typing import Any, Mapping

from ..utils import normalize_text

try:
    from bs4 import BeautifulSoup
except ImportError:  # pragma: no cover - dependency is declared in pyproject
    BeautifulSoup = None

PDF_LINK_TEXT_TOKENS = ("pdf", "download pdf", "full text pdf", "view pdf")
PDF_HREF_TOKENS = (".pdf", "/pdf", "/epdf", "/pdfdirect", "/pdfft", "download=true")
SPRINGER_HOST_TOKENS = ("springer.com", "springernature.com", "nature.com", "biomedcentral.com")


def _append_candidate(candidates: list[str], candidate: str | None, *, source_url: str | None = None) -> None:
    normalized = normalize_text(candidate)
    if not normalized:
        return
    if source_url:
        normalized = urllib.parse.urljoin(source_url, normalized)
    parsed = urllib.parse.urlparse(normalized)
    if parsed.scheme not in {"http", "https"} or not normalize_text(parsed.netloc):
        return
    if normalized not in candidates:
        candidates.append(normalized)


def extract_pdf_url_from_metadata_links(metadata: Mapping[str, Any]) -> str | None:
    for item in metadata.get("fulltext_links") or []:
        if not isinstance(item, Mapping):
            continue
        url = normalize_text(str(item.get("url") or ""))
        if not url:
            continue
        content_type = normalize_text(str(item.get("content_type") or "")).lower()
        if any(token in url.lower() for token in PDF_HREF_TOKENS) or content_type == "application/pdf":
            return url
    return None


def extract_pdf_candidate_urls_from_html(html_text: str, source_url: str) -> list[str]:
    candidates: list[str] = []
    if BeautifulSoup is None:
        return candidates

    soup = BeautifulSoup(html_text, "html.parser")

    for meta in soup.find_all("meta"):
        content = normalize_text(meta.get("content"))
        if not content:
            continue
        meta_key = normalize_text(meta.get("name") or meta.get("property") or meta.get("itemprop")).lower()
        if "citation_pdf_url" in meta_key or meta_key.endswith("pdf_url") or meta_key == "pdf_url":
            _append_candidate(candidates, content, source_url=source_url)

    for node in soup.find_all(["a", "link"]):
        href = normalize_text(node.get("href"))
        if not href:
            continue
        lowered_href = href.lower()
        label = normalize_text(" ".join(filter(None, [node.get_text(" ", strip=True), node.get("title"), node.get("aria-label")]))).lower()
        if any(token in lowered_href for token in PDF_HREF_TOKENS) or any(token in label for token in PDF_LINK_TEXT_TOKENS):
            _append_candidate(candidates, href, source_url=source_url)

    return candidates


def _nature_pdf_candidate(url: str | None) -> str | None:
    normalized = normalize_text(url)
    if not normalized:
        return None
    parsed = urllib.parse.urlparse(normalized)
    hostname = normalize_text(parsed.hostname).lower()
    if "nature.com" not in hostname:
        return None
    path = parsed.path.rstrip("/")
    if not path.startswith("/articles/") or path.endswith(".pdf"):
        return None
    return urllib.parse.urlunparse((parsed.scheme or "https", parsed.netloc, f"{path}.pdf", "", "", ""))


def _springer_link_pdf_candidate(doi: str) -> str | None:
    normalized_doi = normalize_text(doi)
    if not normalized_doi:
        return None
    encoded = urllib.parse.quote(normalized_doi, safe="")
    return f"https://link.springer.com/content/pdf/{encoded}.pdf"


def build_springer_pdf_candidates(
    doi: str,
    metadata: Mapping[str, Any],
    *,
    html_text: str | None = None,
    source_url: str | None = None,
) -> list[str]:
    candidates: list[str] = []
    _append_candidate(candidates, extract_pdf_url_from_metadata_links(metadata))
    if html_text and source_url:
        for candidate in extract_pdf_candidate_urls_from_html(html_text, source_url):
            _append_candidate(candidates, candidate)

    for url in (source_url, normalize_text(metadata.get("landing_page_url"))):
        _append_candidate(candidates, _nature_pdf_candidate(url))

    landing_url = normalize_text(source_url or metadata.get("landing_page_url"))
    if landing_url:
        hostname = normalize_text(urllib.parse.urlparse(landing_url).hostname).lower()
        if any(token in hostname for token in SPRINGER_HOST_TOKENS):
            _append_candidate(candidates, _springer_link_pdf_candidate(doi))
    else:
        _append_candidate(candidates, _springer_link_pdf_candidate(doi))

    return candidates
