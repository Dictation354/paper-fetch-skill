"""IEEE Xplore URL helpers."""

from __future__ import annotations

import re
import urllib.parse
from typing import Any
from collections.abc import Mapping

from ..utils import normalize_text

IEEE_BASE_URL = "https://ieeexplore.ieee.org"
IEEE_DOCUMENT_URL_TEMPLATE = IEEE_BASE_URL + "/document/{article_number}/"
IEEE_REST_URL_TEMPLATE = (
    IEEE_BASE_URL + "/rest/document/{article_number}/?logAccess=true"
)
IEEE_REFERENCES_URL_TEMPLATE = (
    IEEE_BASE_URL + "/rest/document/{article_number}/references"
)
IEEE_MULTIMEDIA_URL_TEMPLATE = (
    IEEE_BASE_URL + "/rest/document/{article_number}/multimedia"
)
IEEE_STAMP_URL_TEMPLATE = IEEE_BASE_URL + "/stamp/stamp.jsp?arnumber={article_number}"
IEEE_SUPPORT_ICON_PATH = "/assets/img/icon.support.gif"
IEEE_MEDIASTORE_PATH_PREFIX = "/mediastore/ieee/content/media/"

# IEEE Xplore article numbers are parsed only from the provider-owned
# `/document/{article_number}/` URL contract. Other IEEE URLs expose the same
# number in query params or REST paths, but those are handled by metadata fields
# or explicit route builders instead of this landing URL parser.
IEEE_ARTICLE_NUMBER_PATH_PATTERN = re.compile(
    r"^/document/(?P<article_number>\d+)(?:/|$)"
)


def _article_number_from_url(url: str | None) -> str:
    parsed = urllib.parse.urlparse(normalize_text(url or ""))
    match = IEEE_ARTICLE_NUMBER_PATH_PATTERN.match(parsed.path or "")
    return match.group("article_number") if match else ""


def _article_number_from_metadata(metadata: Mapping[str, Any] | None) -> str:
    for key in ("article_number", "articleNumber", "articleId", "arnumber"):
        value = normalize_text(str((metadata or {}).get(key) or ""))
        if value.isdigit():
            return value
    return ""


def _absolute_ieee_url(raw_url: str, fallback_url: str = "") -> str:
    url = normalize_text(str(raw_url or ""))
    if not url or url.startswith("#") or url.lower().startswith("javascript:"):
        return ""
    if url.startswith("/"):
        return urllib.parse.urljoin(IEEE_BASE_URL, url)
    base_url = normalize_text(str(fallback_url or "")) or IEEE_BASE_URL
    if not urllib.parse.urlparse(base_url).scheme:
        base_url = urllib.parse.urljoin(IEEE_BASE_URL, base_url)
    return urllib.parse.urljoin(base_url, url)


def _absolute_ieee_asset_url(raw_url: str, source_url: str) -> str:
    return _absolute_ieee_url(raw_url, source_url)


def _ieee_asset_url_path(url: str) -> str:
    return urllib.parse.urlparse(normalize_text(str(url or ""))).path.lower()


def _is_ignored_ieee_asset_url(url: str) -> bool:
    # Kept as a fallback contract for the historical Xplore support icon path;
    # DOM and asset heuristics in the HTML/supplementary modules cover newer markup.
    return _ieee_asset_url_path(url).endswith(IEEE_SUPPORT_ICON_PATH)


def _dedupe_urls(urls: list[str | None]) -> list[str]:
    deduped: list[str] = []
    for raw_url in urls:
        url = normalize_text(str(raw_url or ""))
        if url and url not in deduped:
            deduped.append(url)
    return deduped


def _is_ieee_rest_document_url(url: str, article_number: str) -> bool:
    parsed = urllib.parse.urlparse(normalize_text(url))
    host = normalize_text(parsed.netloc).lower()
    path = normalize_text(parsed.path).rstrip("/")
    return bool(
        article_number
        and host.endswith("ieeexplore.ieee.org")
        and path == f"/rest/document/{article_number}"
    )


def _pdf_candidates(landing_attempt: Any) -> list[str]:
    metadata = landing_attempt.merged_metadata
    candidates: list[str] = []
    for key in ("pdfUrl", "pdfPath"):
        value = normalize_text(
            str(metadata.get(key) or landing_attempt.landing_metadata.get(key) or "")
        )
        if value:
            candidates.append(urllib.parse.urljoin(IEEE_BASE_URL, value))
    if landing_attempt.article_number:
        candidates.append(
            IEEE_STAMP_URL_TEMPLATE.format(
                article_number=landing_attempt.article_number
            )
        )
    return _dedupe_urls(candidates)
