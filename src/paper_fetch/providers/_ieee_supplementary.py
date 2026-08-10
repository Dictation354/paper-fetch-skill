"""IEEE supplementary asset discovery and download helpers."""

from __future__ import annotations

import html as html_lib
import json
import re
import urllib.parse
from pathlib import Path
from typing import Any
from collections.abc import Mapping

from ..config import resolve_asset_download_concurrency
from ..extraction.html import decode_html
from ..extraction.html.assets import (
    FIGURE_KIND,
    SUPPLEMENTARY_KIND,
    download_assets,
    split_body_and_supplementary_assets,
)
from ..extraction.html.assets.supplementary import (
    GENERIC_SUPPLEMENTARY_TEXT_TOKENS,
    has_supplementary_file_suffix,
)
from ..extraction.html.parsing import choose_parser
from ..http import DEFAULT_FULLTEXT_TIMEOUT_SECONDS, RequestFailure
from ..http.headers import header_value
from ..models import AssetProfile
from ..publisher_identity import normalize_doi
from ..utils import empty_asset_results, normalize_text, strip_html_tags
from ..runtime import RuntimeContext
from ._ieee_asset_memo import (
    cache_ieee_multimedia_assets,
    cached_ieee_multimedia_assets,
    ieee_asset_key as _supplementary_asset_key,
)
from ._ieee_metadata import IeeeLandingAttempt, _landing_metadata_has_multimedia_scope
from ._ieee_url import (
    IEEE_BASE_URL,
    IEEE_DOCUMENT_URL_TEMPLATE,
    _absolute_ieee_asset_url,
    _absolute_ieee_url,
    _article_number_from_metadata,
    _article_number_from_url,
    _is_ignored_ieee_asset_url,
)
from .browser_runtime.types import BrowserRuntimeConfig

from bs4 import BeautifulSoup, Tag

IEEE_SUPPLEMENTARY_SEMANTIC_TOKENS = (
    *GENERIC_SUPPLEMENTARY_TEXT_TOKENS,
    "supporting-information",
    "supporting-material",
    "multimedia",
    "supplement file",
    "supplemental item",
)
IEEE_SUPPLEMENTARY_EXTRA_FILE_SUFFIXES = tuple(
    ".doc .docx .ps .eps .bmp .mp4 .mov .wmv .avi .mp3 .aiff .ra .wav .tar.gz".split()
)
IEEE_ASSET_URL_ATTRS = tuple(
    "href src data-src data-original data-full-src data-url".split()
)


def _small_html_dimension(value: Any, *, max_size: int = 32) -> bool:
    normalized = normalize_text(str(value or "")).lower().rstrip("px")
    if not normalized:
        return False
    try:
        return 0 < int(float(normalized)) <= max_size
    except (TypeError, ValueError):
        return False


def _ieee_support_icon_text(value: str) -> bool:
    normalized = normalize_text(value).lower()
    if not normalized:
        return False
    tokens = set(normalized.replace("-", " ").replace("_", " ").split())
    return "icon" in tokens and ("support" in tokens or "help" in tokens)


def _looks_like_ieee_support_icon_node(node: Tag) -> bool:
    attrs = getattr(node, "attrs", None) or {}
    text_parts = [
        normalize_text(str(attrs.get("alt") or "")),
        normalize_text(str(attrs.get("title") or "")),
        normalize_text(str(attrs.get("aria-label") or "")),
        normalize_text(str(attrs.get("id") or "")),
    ]
    class_values = attrs.get("class")
    if isinstance(class_values, (list, tuple, set)):
        text_parts.extend(normalize_text(str(item)) for item in class_values)
    else:
        text_parts.append(normalize_text(str(class_values or "")))
    if not _ieee_support_icon_text(" ".join(text_parts)):
        return False
    width_small = _small_html_dimension(attrs.get("width"))
    height_small = _small_html_dimension(attrs.get("height"))
    return (
        width_small
        or height_small
        or normalize_text(getattr(node, "name", "")).lower() == "img"
    )


def _ieee_tag_has_ignored_asset_url(node: Tag) -> bool:
    if _looks_like_ieee_support_icon_node(node):
        return True
    for attr_name in IEEE_ASSET_URL_ATTRS:
        value = normalize_text(str(node.get(attr_name) or ""))
        if value and _is_ignored_ieee_asset_url(
            _absolute_ieee_asset_url(value, IEEE_BASE_URL)
        ):
            return True
    return False


def _has_ieee_supplementary_file_suffix(url: str) -> bool:
    parsed = urllib.parse.urlparse(normalize_text(str(url or "")))
    path = urllib.parse.unquote(parsed.path).lower()
    query = urllib.parse.unquote(parsed.query).lower()
    return has_supplementary_file_suffix(
        path,
        extra_suffixes=IEEE_SUPPLEMENTARY_EXTRA_FILE_SUFFIXES,
    ) or has_supplementary_file_suffix(
        query,
        extra_suffixes=IEEE_SUPPLEMENTARY_EXTRA_FILE_SUFFIXES,
    )


def _supplementary_assets_from_ieee_multimedia_payload(
    payload: Mapping[str, Any],
    source_url: str,
) -> list[dict[str, str]]:
    raw_items = payload.get("multimedia")
    if not isinstance(raw_items, list):
        return []
    assets: list[dict[str, str]] = []
    seen: set[str] = set()
    for item in raw_items:
        if not isinstance(item, Mapping):
            continue
        url = _absolute_ieee_asset_url(
            str(
                item.get("filePath")
                or item.get("fileUrl")
                or item.get("downloadUrl")
                or item.get("url")
                or ""
            ),
            source_url,
        )
        if not url or _is_ignored_ieee_asset_url(url):
            continue
        key = url.lower()
        if key in seen:
            continue
        seen.add(key)
        filename = normalize_text(str(item.get("fileName") or ""))
        title = normalize_text(str(item.get("title") or ""))
        description = normalize_text(
            html_lib.unescape(strip_html_tags(str(item.get("description") or "")) or "")
        )
        asset: dict[str, str] = {
            "kind": "supplementary",
            "heading": title or filename or "Supplementary Material",
            "caption": description,
            "url": url,
            "section": "supplementary",
        }
        if filename:
            asset["filename_hint"] = filename
        media_type = normalize_text(str(item.get("mediaType") or ""))
        if media_type:
            asset["media_type"] = media_type
        media_doi = normalize_doi(str(item.get("doi") or ""))
        if media_doi:
            asset["doi"] = media_doi
        assets.append(asset)
    return assets


def fetch_ieee_multimedia_assets(
    transport: Any,
    landing_attempt: IeeeLandingAttempt,
    *,
    multimedia_url: str,
    headers: Mapping[str, str],
    timeout: float = DEFAULT_FULLTEXT_TIMEOUT_SECONDS,
    runtime_context: RuntimeContext | None = None,
) -> list[dict[str, str]]:
    if not landing_attempt.article_number or not _landing_metadata_has_multimedia_scope(
        landing_attempt.landing_metadata
    ):
        return []
    cached = cached_ieee_multimedia_assets(
        runtime_context,
        article_number=landing_attempt.article_number,
        multimedia_url=multimedia_url,
    )
    if cached is not None:
        return cached
    try:
        response = transport.request(
            "GET",
            multimedia_url,
            headers=headers,
            timeout=timeout,
            retry_on_transient=True,
        )
        payload = json.loads(
            decode_html(
                bytes(response.get("body") or b""),
                content_type=header_value(response.get("headers"), "content-type"),
            )
        )
    except (RequestFailure, TypeError, ValueError):
        return []
    if not isinstance(payload, Mapping):
        return []
    response_url = _absolute_ieee_url(
        str(response.get("url") or multimedia_url), multimedia_url
    )
    assets = _supplementary_assets_from_ieee_multimedia_payload(payload, response_url)
    cache_ieee_multimedia_assets(
        runtime_context,
        article_number=landing_attempt.article_number,
        multimedia_url=multimedia_url,
        assets=assets,
    )
    return assets


def _ieee_supplementary_token_match(text: str) -> bool:
    normalized = normalize_text(text).lower()
    compact = re.sub(r"[^a-z0-9]+", "", normalized)
    for token in IEEE_SUPPLEMENTARY_SEMANTIC_TOKENS:
        normalized_token = token.lower()
        if (
            normalized_token in normalized
            or re.sub(r"[^a-z0-9]+", "", normalized_token) in compact
        ):
            return True
    return False


def _ieee_node_identity_text(
    node: Tag, *, include_accessible_labels: bool = True
) -> str:
    values: list[str] = []
    for key, value in (getattr(node, "attrs", None) or {}).items():
        normalized_key = normalize_text(str(key)).lower()
        if normalized_key in {"href", "src", "srcset"}:
            continue
        if normalized_key in {"title", "aria-label"} and not include_accessible_labels:
            continue
        if normalized_key in {
            "id",
            "class",
            "role",
            "title",
            "aria-label",
        } or normalized_key.startswith("data-"):
            if isinstance(value, list):
                values.extend(normalize_text(str(item)) for item in value)
            else:
                values.append(normalize_text(str(value)))
    return " ".join(value for value in values if value)


def _ieee_direct_heading_texts(node: Tag) -> list[str]:
    texts: list[str] = []
    for child in node.find_all(True, recursive=False):
        if not isinstance(child, Tag):
            continue
        child_name = normalize_text(getattr(child, "name", "")).lower()
        if re.fullmatch(r"h[1-6]", child_name):
            text = normalize_text(child.get_text(" ", strip=True))
            if text:
                texts.append(text)
            continue
        child_identity = _ieee_node_identity_text(child)
        if child_name != "header" and "header" not in child_identity.lower():
            continue
        for heading in child.find_all(re.compile(r"^h[1-6]$")):
            if isinstance(heading, Tag):
                text = normalize_text(heading.get_text(" ", strip=True))
                if text:
                    texts.append(text)
    return texts


def _is_ieee_supplementary_scope_node(node: Tag) -> bool:
    node_name = normalize_text(getattr(node, "name", "")).lower()
    if node_name not in {"section", "div", "aside", "ul", "ol"}:
        return False
    return _ieee_supplementary_token_match(_ieee_node_identity_text(node)) or any(
        _ieee_supplementary_token_match(text)
        for text in _ieee_direct_heading_texts(node)
    )


def _is_descendant_of_any(node: Tag, ancestors: list[Tag]) -> bool:
    parent = node.parent
    while isinstance(parent, Tag):
        if any(parent is ancestor for ancestor in ancestors):
            return True
        parent = parent.parent
    return False


def _ieee_supplementary_scope_nodes(soup: BeautifulSoup) -> list[Tag]:
    scopes: list[Tag] = []
    for node in soup.find_all(True):
        if not isinstance(node, Tag) or not _is_ieee_supplementary_scope_node(node):
            continue
        if not _is_descendant_of_any(node, scopes):
            scopes.append(node)
    return scopes


def _is_ieee_marked_supplementary_anchor(anchor: Tag) -> bool:
    return _ieee_supplementary_token_match(
        _ieee_node_identity_text(anchor, include_accessible_labels=False)
    )


def _ieee_anchor_semantic_text(anchor: Tag, href: str) -> str:
    values = [
        normalize_text(anchor.get_text(" ", strip=True)),
        href,
        normalize_text(str(anchor.get("title") or "")),
        normalize_text(str(anchor.get("aria-label") or "")),
    ]
    for key, value in anchor.attrs.items():
        if normalize_text(str(key)).lower().startswith("data-"):
            values.append(normalize_text(str(value or "")))
    return " ".join(value for value in values if value).lower()


def _is_ieee_supplementary_anchor(
    anchor: Tag, source_url: str, *, in_explicit_scope: bool
) -> bool:
    href = normalize_text(str(anchor.get("href") or ""))
    absolute_url = _absolute_ieee_asset_url(href, source_url)
    if not absolute_url or _is_ignored_ieee_asset_url(absolute_url):
        return False
    semantic_text = _ieee_anchor_semantic_text(anchor, href)
    if in_explicit_scope:
        return _ieee_supplementary_token_match(
            semantic_text
        ) or _has_ieee_supplementary_file_suffix(absolute_url)
    return _is_ieee_marked_supplementary_anchor(anchor) and (
        _ieee_supplementary_token_match(semantic_text)
        or _has_ieee_supplementary_file_suffix(absolute_url)
    )


def _ieee_supplementary_asset_from_anchor(
    anchor: Tag,
    source_url: str,
    *,
    in_explicit_scope: bool,
) -> dict[str, str] | None:
    if not _is_ieee_supplementary_anchor(
        anchor, source_url, in_explicit_scope=in_explicit_scope
    ):
        return None
    href = normalize_text(str(anchor.get("href") or ""))
    return {
        "kind": "supplementary",
        "heading": normalize_text(anchor.get_text(" ", strip=True))
        or normalize_text(str(anchor.get("title") or ""))
        or normalize_text(str(anchor.get("aria-label") or ""))
        or "Supplementary Material",
        "caption": "",
        "url": _absolute_ieee_asset_url(href, source_url),
        "section": "supplementary",
    }


def _extract_ieee_supplementary_assets(
    html_text: str, source_url: str
) -> list[dict[str, str]]:
    soup = BeautifulSoup(html_text, choose_parser())
    assets: list[dict[str, str]] = []
    seen: set[str] = set()
    scope_nodes = _ieee_supplementary_scope_nodes(soup)

    def add_anchor(anchor: Tag, *, in_explicit_scope: bool) -> None:
        asset = _ieee_supplementary_asset_from_anchor(
            anchor, source_url, in_explicit_scope=in_explicit_scope
        )
        if asset is None:
            return
        key = _supplementary_asset_key(asset)
        if key and key in seen:
            return
        if key:
            seen.add(key)
        assets.append(asset)

    for scope in scope_nodes:
        for anchor in scope.find_all("a", href=True):
            if isinstance(anchor, Tag):
                add_anchor(anchor, in_explicit_scope=True)
    for anchor in soup.find_all("a", href=True):
        if not isinstance(anchor, Tag) or _is_descendant_of_any(anchor, scope_nodes):
            continue
        add_anchor(anchor, in_explicit_scope=False)
    return assets


def download_ieee_related_assets(
    transport: Any,
    doi: str,
    metadata: Mapping[str, Any],
    raw_payload: Any,
    output_dir: Path | None,
    *,
    user_agent: str,
    env: Mapping[str, str],
    asset_profile: AssetProfile = "all",
    browser_runtime_config: BrowserRuntimeConfig | None = None,
    runtime_context: RuntimeContext | None = None,
) -> dict[str, list[dict[str, Any]]]:
    if output_dir is None or asset_profile == "none":
        return empty_asset_results()
    content = raw_payload.content
    if (
        normalize_text(content.route_kind if content is not None else "").lower()
        != "html"
    ):
        return empty_asset_results()
    extracted_assets = [
        dict(item) for item in (content.extracted_assets if content is not None else [])
    ]
    body_assets, supplementary_assets = split_body_and_supplementary_assets(
        extracted_assets
    )
    body_assets = [
        dict(item)
        for item in body_assets
        if normalize_text(str(item.get("kind") or "")).lower()
        in {"figure", "table", "formula"}
        and normalize_text(str(item.get("section") or "")).lower() != "supplementary"
    ]
    merged_metadata = (
        content.merged_metadata if content is not None else raw_payload.merged_metadata
    )
    article_id = (
        normalize_doi(str((merged_metadata or {}).get("doi") or doi or ""))
        or normalize_doi(doi)
        or normalize_text(str(metadata.get("title") or ""))
        or raw_payload.source_url
    )
    landing_or_source_url = normalize_text(
        str(
            (merged_metadata or {}).get("landing_page_url")
            or raw_payload.source_url
            or ""
        )
    )
    article_number = (
        _article_number_from_metadata(merged_metadata)
        or _article_number_from_metadata(metadata)
        or _article_number_from_url(raw_payload.source_url)
        or _article_number_from_url(landing_or_source_url)
    )
    canonical_landing_url = (
        IEEE_DOCUMENT_URL_TEMPLATE.format(article_number=article_number)
        if article_number
        else landing_or_source_url
    )
    seed_urls = [canonical_landing_url] if canonical_landing_url else []
    concurrency = resolve_asset_download_concurrency(env)
    if browser_runtime_config is not None:
        from ._ieee_asset_recovery import download_ieee_assets_with_browser

        return download_ieee_assets_with_browser(
            transport=transport,
            article_id=article_id,
            output_dir=output_dir,
            asset_profile=asset_profile,
            body_assets=body_assets,
            supplementary_assets=supplementary_assets,
            merged_metadata=dict(merged_metadata or {}),
            article_number=article_number,
            canonical_landing_url=canonical_landing_url,
            seed_urls=seed_urls,
            concurrency=concurrency,
            user_agent=user_agent,
            content=content,
            browser_runtime_config=browser_runtime_config,
            runtime_context=runtime_context,
            download_assets_fn=download_assets,
            split_assets_fn=split_body_and_supplementary_assets,
        )
    if not body_assets and not supplementary_assets:
        return empty_asset_results()
    body_result = (
        download_assets(
            FIGURE_KIND,
            transport,
            article_id=article_id,
            assets=body_assets,
            output_dir=output_dir,
            user_agent=user_agent,
            asset_profile=asset_profile,
            headers={"User-Agent": user_agent, "Referer": canonical_landing_url},
            seed_urls=seed_urls,
            asset_download_concurrency=concurrency,
        )
        if body_assets
        else empty_asset_results()
    )
    supplementary_result = (
        download_assets(
            SUPPLEMENTARY_KIND,
            transport,
            article_id=article_id,
            assets=supplementary_assets,
            output_dir=output_dir,
            user_agent=user_agent,
            asset_profile=asset_profile,
            headers={"User-Agent": user_agent, "Referer": canonical_landing_url},
            seed_urls=seed_urls,
            asset_download_concurrency=concurrency,
        )
        if supplementary_assets and asset_profile == "all"
        else empty_asset_results()
    )
    return {
        "assets": [
            *list(body_result.get("assets") or []),
            *list(supplementary_result.get("assets") or []),
        ],
        "asset_failures": [
            *list(body_result.get("asset_failures") or []),
            *list(supplementary_result.get("asset_failures") or []),
        ],
    }
