"""Figure asset discovery helpers."""

from __future__ import annotations

import urllib.parse
from html.parser import HTMLParser
from typing import Any, Callable, Mapping

from ....http import DEFAULT_FULLTEXT_TIMEOUT_SECONDS, HttpTransport, RequestFailure
from ....models import normalize_text
from .._metadata import parse_html_metadata
from .._runtime import decode_html
from ..parsing import choose_parser
from .dom import (
    FIGURE_PAGE_HINTS,
    FULL_SIZE_IMAGE_ATTRS,
    PREVIEW_IMAGE_ATTRS,
    _collect_tag_attr_urls,
    _soup_attr_url,
    looks_like_full_size_asset_url,
)

try:
    from bs4 import BeautifulSoup, Tag
except ImportError:  # pragma: no cover - dependency is declared in pyproject
    BeautifulSoup = None
    Tag = None

FigurePageFetcher = Callable[[str], tuple[str, str] | None]


class _FigureParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.assets: list[dict[str, str]] = []
        self._in_figure = False
        self._in_figcaption = False
        self._current_src = ""
        self._caption_parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = {key.lower(): (value or "") for key, value in attrs}
        lowered_tag = tag.lower()
        if lowered_tag == "figure":
            self._in_figure = True
            self._current_src = ""
            self._caption_parts = []
        elif self._in_figure and lowered_tag == "img" and not self._current_src:
            self._current_src = attributes.get("src", "").strip()
        elif self._in_figure and lowered_tag == "figcaption":
            self._in_figcaption = True

    def handle_endtag(self, tag: str) -> None:
        lowered_tag = tag.lower()
        if lowered_tag == "figcaption":
            self._in_figcaption = False
        elif lowered_tag == "figure":
            caption = normalize_text(" ".join(self._caption_parts))
            if self._current_src or caption:
                self.assets.append(
                    {
                        "kind": "figure",
                        "heading": caption[:80] or "Figure",
                        "caption": caption,
                        "url": self._current_src,
                    }
                )
            self._in_figure = False
            self._in_figcaption = False
            self._current_src = ""
            self._caption_parts = []

    def handle_data(self, data: str) -> None:
        if self._in_figcaption and data.strip():
            self._caption_parts.append(data)


def _figure_caption_from_soup(node: Any, soup: Any) -> str:
    if Tag is None or not isinstance(node, Tag):
        return ""

    figcaption = node.find("figcaption")
    if isinstance(figcaption, Tag):
        caption = normalize_text(figcaption.get_text(" ", strip=True))
        if caption:
            return caption

    image = node.find("img")
    if isinstance(image, Tag):
        described_by = normalize_text(str(image.get("aria-describedby") or ""))
        if described_by:
            described_node = soup.find(id=described_by)
            if isinstance(described_node, Tag):
                caption = normalize_text(described_node.get_text(" ", strip=True))
                if caption:
                    return caption
    return ""


def _figure_page_url_from_soup(node: Any, source_url: str) -> str:
    if Tag is None or not isinstance(node, Tag):
        return ""

    contexts: list[Any] = [node]
    if isinstance(node.parent, Tag):
        contexts.append(node.parent)

    for context in contexts:
        for anchor in context.find_all("a", href=True):
            href = normalize_text(str(anchor.get("href") or ""))
            text = normalize_text(anchor.get_text(" ", strip=True)).lower()
            hint_blob = " ".join(
                [
                    text,
                    normalize_text(str(anchor.get("aria-label") or "")).lower(),
                    normalize_text(str(anchor.get("title") or "")).lower(),
                ]
            )
            if any(token in hint_blob for token in FIGURE_PAGE_HINTS) and href and not href.startswith("#"):
                return urllib.parse.urljoin(source_url, href)
    return ""


def _figure_full_size_url_from_soup(node: Any, source_url: str) -> str:
    if Tag is None or not isinstance(node, Tag):
        return ""

    contexts: list[Any] = [node]
    if isinstance(node.parent, Tag):
        contexts.append(node.parent)

    for context in contexts:
        for tag in [context, *context.find_all(True)]:
            for candidate in _collect_tag_attr_urls(tag, source_url, *FULL_SIZE_IMAGE_ATTRS):
                if looks_like_full_size_asset_url(candidate):
                    return candidate

    for context in contexts:
        for anchor in context.find_all("a", href=True):
            href = normalize_text(str(anchor.get("href") or ""))
            if href.startswith("#"):
                continue
            absolute_href = urllib.parse.urljoin(source_url, href)
            hint_blob = " ".join(
                [
                    normalize_text(anchor.get_text(" ", strip=True)).lower(),
                    normalize_text(str(anchor.get("aria-label") or "")).lower(),
                    normalize_text(str(anchor.get("title") or "")).lower(),
                ]
            )
            if looks_like_full_size_asset_url(absolute_href) or any(token in hint_blob for token in FIGURE_PAGE_HINTS):
                return absolute_href
    return ""


def _figure_asset_from_soup_node(node: Any, soup: Any, source_url: str) -> dict[str, str] | None:
    if Tag is None or not isinstance(node, Tag):
        return None

    image = node.find("img")
    source = node.find("source")
    preview_url = _soup_attr_url(image, *PREVIEW_IMAGE_ATTRS) if image else ""
    if not preview_url:
        preview_url = _soup_attr_url(source, "srcset", "data-srcset") if source else ""
    full_size_url = _figure_full_size_url_from_soup(node, source_url)
    if not full_size_url and image is not None:
        full_size_url = _soup_attr_url(image, *FULL_SIZE_IMAGE_ATTRS)
    if not full_size_url and source is not None:
        full_size_url = _soup_attr_url(source, *FULL_SIZE_IMAGE_ATTRS)
    if not full_size_url and looks_like_full_size_asset_url(preview_url):
        full_size_url = preview_url
    absolute_preview_url = urllib.parse.urljoin(source_url, preview_url) if preview_url else ""
    absolute_full_size_url = urllib.parse.urljoin(source_url, full_size_url) if full_size_url else ""
    figure_page_url = _figure_page_url_from_soup(node, source_url)
    if (
        absolute_full_size_url
        and figure_page_url
        and absolute_full_size_url == figure_page_url
        and not looks_like_full_size_asset_url(absolute_full_size_url)
    ):
        absolute_full_size_url = ""

    caption = _figure_caption_from_soup(node, soup)
    alt_text = normalize_text(str(image.get("alt") or "")) if isinstance(image, Tag) else ""
    heading = caption[:80] or alt_text or "Figure"
    if not caption and alt_text:
        caption = alt_text

    if not preview_url and not full_size_url and not caption:
        return None

    asset: dict[str, str] = {
        "kind": "figure",
        "heading": heading,
        "caption": caption,
        "url": absolute_full_size_url or absolute_preview_url,
        "section": "body",
    }
    if absolute_preview_url:
        asset["preview_url"] = absolute_preview_url
    if absolute_full_size_url:
        asset["full_size_url"] = absolute_full_size_url
    if figure_page_url:
        asset["figure_page_url"] = figure_page_url
    return asset


def _extract_figure_assets_with_soup(html_text: str, source_url: str) -> list[dict[str, str]]:
    if BeautifulSoup is None:
        return []

    soup = BeautifulSoup(html_text, choose_parser())
    candidates: list[Any] = []
    seen_nodes: set[int] = set()

    for node in soup.find_all("figure"):
        node_id = id(node)
        if node_id not in seen_nodes:
            seen_nodes.add(node_id)
            candidates.append(node)

    assets_by_key: dict[tuple[str, str, str], dict[str, str]] = {}
    for node in candidates:
        asset = _figure_asset_from_soup_node(node, soup, source_url)
        if asset is None:
            continue
        figure_page_url = normalize_text(asset.get("figure_page_url") or "")
        preview_url = normalize_text(asset.get("url") or "")
        caption = normalize_text(asset.get("caption") or "")
        heading = normalize_text(asset.get("heading") or "")
        key = (figure_page_url or preview_url, preview_url, "figure")
        existing = assets_by_key.get(key)
        if existing is None:
            assets_by_key[key] = asset
            continue

        existing_caption = normalize_text(existing.get("caption") or "")
        existing_heading = normalize_text(existing.get("heading") or "")
        if len(caption) > len(existing_caption):
            existing["caption"] = caption
        if len(heading) > len(existing_heading):
            existing["heading"] = heading
        if figure_page_url and not normalize_text(existing.get("figure_page_url") or ""):
            existing["figure_page_url"] = figure_page_url
        if preview_url and not normalize_text(existing.get("url") or ""):
            existing["url"] = preview_url

    return list(assets_by_key.values())


def extract_figure_assets(html_text: str, source_url: str) -> list[dict[str, str]]:
    if BeautifulSoup is not None:
        assets = _extract_figure_assets_with_soup(html_text, source_url)
        if assets:
            return assets

    parser = _FigureParser()
    parser.feed(html_text)
    parser.close()
    assets: list[dict[str, str]] = []
    for item in parser.assets:
        url = item.get("url", "").strip()
        assets.append(
            {
                "kind": "figure",
                "heading": item.get("heading", "Figure"),
                "caption": item.get("caption", ""),
                "url": urllib.parse.urljoin(source_url, url) if url else "",
                "section": "body",
            }
        )
    return assets


def extract_full_size_figure_image_url(html_text: str, source_url: str) -> str | None:
    metadata = parse_html_metadata(html_text, source_url)
    raw_meta = metadata.get("raw_meta") if isinstance(metadata, Mapping) else {}
    if isinstance(raw_meta, Mapping):
        for key in ("twitter:image", "twitter:image:src", "og:image"):
            for value in raw_meta.get(key, []):
                candidate = urllib.parse.urljoin(source_url, normalize_text(str(value or "")))
                if candidate:
                    return candidate

    if BeautifulSoup is None:
        return None

    soup = BeautifulSoup(html_text, choose_parser())
    fallback_candidate = None
    seen: set[str] = set()
    for tag in soup.find_all(["img", "source"]):
        candidate = _soup_attr_url(
            tag,
            *FULL_SIZE_IMAGE_ATTRS,
            "data-src",
            "src",
            "data-lazy-src",
            "srcset",
            "data-srcset",
        )
        if not candidate:
            continue
        absolute_candidate = urllib.parse.urljoin(source_url, candidate)
        if not absolute_candidate or absolute_candidate in seen:
            continue
        seen.add(absolute_candidate)
        if looks_like_full_size_asset_url(absolute_candidate.lower()):
            return absolute_candidate
        if fallback_candidate is None:
            fallback_candidate = absolute_candidate
    return fallback_candidate


def figure_download_candidates(
    transport: HttpTransport,
    *,
    asset: Mapping[str, Any],
    user_agent: str,
    figure_page_fetcher: FigurePageFetcher | None = None,
) -> list[str]:
    direct_full_size_url = normalize_text(str(asset.get("full_size_url") or ""))
    primary_url = normalize_text(str(asset.get("url") or ""))
    preview_url = normalize_text(str(asset.get("preview_url") or "")) or primary_url
    candidates: list[str] = []

    if direct_full_size_url:
        candidates.append(direct_full_size_url)
    if primary_url and looks_like_full_size_asset_url(primary_url):
        candidates.append(primary_url)

    figure_page_url = normalize_text(str(asset.get("figure_page_url") or ""))
    if figure_page_url:
        try:
            if figure_page_fetcher is not None:
                page_result = figure_page_fetcher(figure_page_url)
                if page_result is None:
                    raise RequestFailure(None, f"Missing figure-page HTML for {figure_page_url}", url=figure_page_url)
                page_html, page_url = page_result
            else:
                response = transport.request(
                    "GET",
                    figure_page_url,
                    headers={"User-Agent": user_agent, "Accept": "text/html,application/xhtml+xml"},
                    timeout=DEFAULT_FULLTEXT_TIMEOUT_SECONDS,
                    retry_on_rate_limit=True,
                    retry_on_transient=True,
                )
                page_html = decode_html(response["body"])
                page_url = str(response["url"] or figure_page_url)
            full_size_url = extract_full_size_figure_image_url(page_html, page_url)
            if full_size_url:
                candidates.append(full_size_url)
        except RequestFailure:
            pass

    if preview_url:
        candidates.append(preview_url)

    deduped: list[str] = []
    seen: set[str] = set()
    for candidate in candidates:
        if candidate and candidate not in seen:
            seen.add(candidate)
            deduped.append(candidate)
    return deduped


def resolve_figure_download_url(
    transport: HttpTransport,
    *,
    asset: Mapping[str, Any],
    user_agent: str,
) -> str:
    candidates = figure_download_candidates(transport, asset=asset, user_agent=user_agent)
    return candidates[0] if candidates else normalize_text(str(asset.get("url") or ""))


__all__ = [
    "FigurePageFetcher",
    "extract_figure_assets",
    "extract_full_size_figure_image_url",
    "figure_download_candidates",
    "resolve_figure_download_url",
]
