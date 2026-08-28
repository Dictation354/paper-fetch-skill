"""Helpers for extracting and constructing publisher PDF fallback candidates."""

from __future__ import annotations

import html
import re
import urllib.parse
from typing import Any
from collections.abc import Mapping

from ..extraction.html.parsing import choose_parser
from ..extraction.html._metadata import raw_html_meta_values
from ..extraction.html.ui_tokens import DOWNLOAD_PDF_LABEL
from ..http import is_pdf_content_type
from ..provider_catalog import (
    host_matches_domain,
    provider_base_domains,
    provider_domain_matches,
    provider_pdf_path_templates,
    provider_pdf_source_path_templates,
)
from ..utils import normalize_text

from bs4 import BeautifulSoup

PDF_LINK_TEXT_TOKENS = ("pdf", DOWNLOAD_PDF_LABEL, "full text pdf", "view pdf")
PDF_URL_COMMON_TOKENS = (".pdf", "download=true")
HTML_DISCOVERY_PDF_URL_TOKENS = ("/pdf", "/epdf", "/pdfdirect", "/pdfft")
BROWSER_WORKFLOW_PDF_URL_PREFIX_TOKENS = (
    "/doi/pdf/",
    "/doi/pdfdirect/",
    "/doi/epdf/",
    "/downloadpdf/",
    "/fullpdf",
)
# HTML discovery accepts broad href shapes because labels/content types can
# disambiguate; browser workflow Crossref links stay limited to known PDF lanes.
PDF_HREF_TOKENS = (*PDF_URL_COMMON_TOKENS, *HTML_DISCOVERY_PDF_URL_TOKENS)
BROWSER_WORKFLOW_PDF_URL_TOKENS = (
    *PDF_URL_COMMON_TOKENS,
    *BROWSER_WORKFLOW_PDF_URL_PREFIX_TOKENS,
)
PDF_JS_DEFAULT_URL_RE = re.compile(
    r"PDFViewerApplicationOptions\.set\(\s*['\"]defaultUrl['\"]\s*,\s*['\"]([^'\"]+)['\"]",
    flags=re.IGNORECASE,
)


def _append_candidate(
    candidates: list[str], candidate: str | None, *, source_url: str | None = None
) -> None:
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


def _append_query_param_pdf_candidates(
    candidates: list[str],
    candidate: str | None,
    *,
    source_url: str | None = None,
) -> None:
    normalized = normalize_text(candidate)
    if not normalized:
        return
    absolute = urllib.parse.urljoin(source_url or "", normalized)
    parsed = urllib.parse.urlparse(absolute)
    for key, values in urllib.parse.parse_qs(
        parsed.query, keep_blank_values=True
    ).items():
        if normalize_text(key).lower() not in {"file", "pdf", "src", "url"}:
            continue
        for value in values:
            lowered_value = normalize_text(value).lower()
            if any(token in lowered_value for token in PDF_HREF_TOKENS):
                _append_candidate(candidates, value, source_url=absolute)


def extract_pdf_url_from_metadata_links(metadata: Mapping[str, Any]) -> str | None:
    for item in metadata.get("fulltext_links") or []:
        if not isinstance(item, Mapping):
            continue
        url = normalize_text(str(item.get("url") or ""))
        if not url:
            continue
        content_type = normalize_text(str(item.get("content_type") or "")).lower()
        if any(
            token in url.lower() for token in PDF_HREF_TOKENS
        ) or is_pdf_content_type(content_type):
            return url
    return None


def build_direct_pdf_candidates(
    metadata: Mapping[str, Any],
    *,
    source_url: str,
    direct_pdf_url: str,
) -> list[str]:
    candidates: list[str] = []
    for value in raw_html_meta_values(metadata, "citation_pdf_url"):
        candidates.append(urllib.parse.urljoin(source_url, value))
    for item in metadata.get("fulltext_links") or ():
        if not isinstance(item, Mapping):
            continue
        url = normalize_text(str(item.get("url") or ""))
        content_type = normalize_text(str(item.get("content_type") or "")).lower()
        if url and ("pdf" in content_type or "pdf" in url.lower()):
            candidates.append(urllib.parse.urljoin(source_url, url))
    candidates.append(direct_pdf_url)
    return list(dict.fromkeys(candidate for candidate in candidates if candidate))


def looks_like_browser_workflow_pdf_url(url: str | None) -> bool:
    normalized = normalize_text(url).lower()
    return bool(normalized) and any(
        token in normalized for token in BROWSER_WORKFLOW_PDF_URL_TOKENS
    )


def extract_pdf_url_from_crossref(metadata: Mapping[str, Any]) -> str | None:
    for item in metadata.get("fulltext_links") or []:
        if not isinstance(item, Mapping):
            continue
        url = normalize_text(str(item.get("url") or ""))
        if not url:
            continue
        content_type = normalize_text(str(item.get("content_type") or "")).lower()
        if looks_like_browser_workflow_pdf_url(url) or is_pdf_content_type(
            content_type
        ):
            return url
    return None


def extract_pdf_candidate_urls_from_html(html_text: str, source_url: str) -> list[str]:
    candidates: list[str] = []

    soup = BeautifulSoup(html_text, choose_parser())

    for meta in soup.find_all("meta"):
        content = normalize_text(meta.get("content"))
        if not content:
            continue
        meta_key = normalize_text(
            meta.get("name") or meta.get("property") or meta.get("itemprop")
        ).lower()
        if (
            "citation_pdf_url" in meta_key
            or meta_key.endswith("pdf_url")
            or meta_key == "pdf_url"
        ):
            _append_candidate(candidates, content, source_url=source_url)
            _append_query_param_pdf_candidates(
                candidates, content, source_url=source_url
            )

    for node in soup.find_all(["a", "link", "iframe", "embed", "object"]):
        target = normalize_text(node.get("href") or node.get("src") or node.get("data"))
        if not target:
            continue
        lowered_href = target.lower()
        content_type = normalize_text(node.get("type")).lower()
        label = normalize_text(
            " ".join(
                filter(
                    None,
                    [
                        node.get_text(" ", strip=True),
                        node.get("title"),
                        node.get("aria-label"),
                    ],
                )
            )
        ).lower()
        if (
            any(token in lowered_href for token in PDF_HREF_TOKENS)
            or any(token in label for token in PDF_LINK_TEXT_TOKENS)
            or "pdf" in content_type
        ):
            _append_candidate(candidates, target, source_url=source_url)
            _append_query_param_pdf_candidates(
                candidates, target, source_url=source_url
            )

    for script in soup.find_all("script"):
        script_text = (
            script.string
            if script.string is not None
            else script.get_text(" ", strip=False)
        )
        for match in PDF_JS_DEFAULT_URL_RE.finditer(str(script_text or "")):
            target = html.unescape(match.group(1))
            lowered_target = normalize_text(target).lower()
            if any(token in lowered_target for token in PDF_HREF_TOKENS):
                _append_candidate(candidates, target, source_url=source_url)
                _append_query_param_pdf_candidates(
                    candidates, target, source_url=source_url
                )

    return candidates


def _format_pdf_path_template(
    template: str,
    *,
    doi: str,
    source_path: str = "",
) -> str | None:
    normalized_template = normalize_text(template)
    if not normalized_template:
        return None
    try:
        return normalized_template.format(
            doi=doi,
            doi_quoted=urllib.parse.quote(doi, safe=""),
            source_path=source_path,
            source_path_quoted=urllib.parse.quote(source_path, safe="/"),
        )
    except (KeyError, ValueError):
        return None


def _provider_pdf_template_host_matches(
    provider_name: str, hostname: str | None
) -> bool:
    if provider_domain_matches(provider_name, hostname):
        return True
    return any(
        host_matches_domain(hostname, domain)
        for domain in provider_base_domains(provider_name)
    )


def _append_provider_source_path_pdf_candidates(
    candidates: list[str],
    provider_name: str,
    source_url: str | None,
    *,
    doi: str,
) -> None:
    normalized = normalize_text(source_url)
    if not normalized:
        return
    parsed = urllib.parse.urlparse(normalized)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return
    hostname = normalize_text(parsed.hostname).lower()
    source_path = parsed.path.rstrip("/")
    if not source_path or source_path.lower().endswith(".pdf"):
        return

    for template in provider_pdf_source_path_templates(provider_name):
        if not host_matches_domain(hostname, template.domain):
            continue
        path_prefix = normalize_text(template.path_prefix)
        if path_prefix and not source_path.startswith(path_prefix):
            continue
        candidate_path = _format_pdf_path_template(
            template.path_template,
            doi=doi,
            source_path=source_path,
        )
        if not candidate_path:
            continue
        parsed_candidate = urllib.parse.urlparse(candidate_path)
        if parsed_candidate.scheme in {"http", "https"}:
            _append_candidate(candidates, candidate_path)
            continue
        if not candidate_path.startswith("/"):
            candidate_path = f"/{candidate_path}"
        _append_candidate(
            candidates,
            urllib.parse.urlunparse(
                (parsed.scheme or "https", parsed.netloc, candidate_path, "", "", "")
            ),
        )


def _append_provider_doi_pdf_candidates(
    candidates: list[str],
    provider_name: str,
    doi: str,
) -> None:
    normalized_doi = normalize_text(doi)
    if not normalized_doi:
        return
    for domain in provider_base_domains(provider_name):
        base_url = f"https://{domain}"
        for template in provider_pdf_path_templates(provider_name):
            candidate_path = _format_pdf_path_template(template, doi=normalized_doi)
            if candidate_path:
                _append_candidate(
                    candidates, urllib.parse.urljoin(base_url, candidate_path)
                )


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
        _append_provider_source_path_pdf_candidates(
            candidates, "springer", url, doi=doi
        )

    landing_url = normalize_text(source_url or metadata.get("landing_page_url"))
    if landing_url:
        hostname = normalize_text(urllib.parse.urlparse(landing_url).hostname).lower()
        if _provider_pdf_template_host_matches("springer", hostname):
            _append_provider_doi_pdf_candidates(candidates, "springer", doi)
    else:
        _append_provider_doi_pdf_candidates(candidates, "springer", doi)

    return candidates
