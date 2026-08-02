"""IEEE Xplore HTML extraction and asset normalization."""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any
from collections.abc import Mapping

from ..extraction.html.assets import extract_scoped_html_assets
from ..extraction.html.parsing import choose_parser
from ..extraction.html.provider_rules import IEEE_EXTRACTION_CLEANUP_SELECTORS
from ..extraction.html.renderer import clean_rendered_markdown
from ..extraction.html.semantics import collect_html_section_hints
from ..reason_codes import NO_RESULT
from ..runtime import RuntimeContext
from ..utils import normalize_text
from ._html_section_markdown import render_container_markdown
from ._ieee_asset_identity import (
    IEEE_ASSET_RETRY_POLICY as IEEE_ASSET_RETRY_POLICY,
    IEEE_ASSET_URL_FIELDS,
    IEEE_DOWNLOAD_MERGE_FIELDS as IEEE_DOWNLOAD_MERGE_FIELDS,
    _dedupe_ieee_assets_by_priority,
    reconcile_ieee_downloaded_assets as reconcile_ieee_downloaded_assets,
)
from ._ieee_block_page import _looks_like_ieee_block_page
from ._ieee_supplementary import (
    _extract_ieee_supplementary_assets,
    _ieee_support_icon_text,
    _ieee_tag_has_ignored_asset_url,
    _small_html_dimension,
)
from ._ieee_url import (
    IEEE_MEDIASTORE_PATH_PREFIX,
    _absolute_ieee_asset_url,
    _ieee_asset_url_path,
    _is_ignored_ieee_asset_url,
)
from .base import ProviderFailure

from bs4 import BeautifulSoup, Tag

IEEE_SECTION_MARKER_PATTERN = re.compile(
    r"^SECTION\s+(?:[IVXLCDM]+|\d+)\s*[.:]?$", flags=re.IGNORECASE
)


@dataclass(frozen=True)
class IeeeHtmlExtraction:
    html_text: str
    markdown_text: str
    section_hints: list[dict[str, Any]]
    abstract_sections: list[dict[str, Any]]
    extracted_assets: list[dict[str, Any]]
    marker_counts: dict[str, int]


def _find_ieee_article(html_text: str) -> Tag | None:
    html_for_parse = re.sub(r"^\s*<\?xml[^>]*>\s*", "", html_text)
    soup = BeautifulSoup(html_for_parse, choose_parser())
    article = soup.select_one("#article")
    return article if isinstance(article, Tag) else None


def _clean_ieee_article(article: Tag) -> None:
    for selector in IEEE_EXTRACTION_CLEANUP_SELECTORS:
        try:
            for node in list(article.select(selector)):
                if isinstance(node, Tag):
                    if (
                        "href^='javascript:'" in selector
                        and node.name == "a"
                        and _is_ieee_bibliography_anchor(node)
                    ):
                        continue
                    node.decompose()
        except Exception:
            continue
    for node in list(article.find_all(True)):
        if isinstance(node, Tag) and _ieee_tag_has_ignored_asset_url(node):
            node.decompose()
    for node in list(article.find_all(True)):
        if not isinstance(node, Tag):
            continue
        text = normalize_text(node.get_text(" ", strip=True))
        classes = {
            normalize_text(str(item)).lower() for item in (node.get("class") or [])
        }
        if "kicker" in classes and IEEE_SECTION_MARKER_PATTERN.fullmatch(text):
            node.decompose()
            continue
        if (
            node.name in {"span", "div"}
            and IEEE_SECTION_MARKER_PATTERN.fullmatch(text)
            and not node.find(True)
        ):
            node.decompose()
    for anchor in list(article.find_all("a")):
        if not isinstance(anchor, Tag):
            continue
        href = normalize_text(str(anchor.get("href") or ""))
        if href.lower().startswith("javascript:"):
            anchor.attrs.pop("href", None)
            if _is_ieee_bibliography_anchor(anchor):
                continue
            if normalize_text(anchor.get_text(" ", strip=True)):
                anchor.unwrap()
            else:
                anchor.decompose()
            continue
        for attr in ("onclick", "data-docId", "data-docid", "data-figure-id"):
            anchor.attrs.pop(attr, None)


def _is_ieee_bibliography_anchor(anchor: Tag) -> bool:
    attrs = getattr(anchor, "attrs", None) or {}
    if normalize_text(str(attrs.get("ref-type") or "")).lower() == "bibr":
        return True
    for key in ("anchor", "data-range"):
        value = normalize_text(str(attrs.get(key) or ""))
        if re.fullmatch(r"ref\d+[a-z]?", value, flags=re.IGNORECASE):
            return True
    return False


def _annotate_ieee_inline_media_blocks(article: Tag, source_url: str) -> None:
    for block in article.select("div.figure.figure-full"):
        if not isinstance(block, Tag):
            continue
        asset = _ieee_asset_from_figure_full_block(block, source_url)
        if asset is None:
            continue
        inline_url = normalize_text(
            str(
                asset.get("url")
                or asset.get("full_size_url")
                or asset.get("preview_url")
                or ""
            )
        )
        if inline_url:
            block["data-paper-fetch-inline-src"] = inline_url
            block["data-paper-fetch-inline-alt"] = normalize_text(
                str(asset.get("heading") or asset.get("caption") or "Figure")
            )
            # The block-level annotation is the canonical inline media node.
            # Removing nested preview images prevents large+preview duplicates
            # while retaining captions and links for extraction.
            for preview in list(block.find_all("img")):
                if isinstance(preview, Tag):
                    preview.decompose()


def _ieee_marker_counts(article: Tag) -> dict[str, int]:
    return {
        "sections": len(article.select("div.section, div.section_2, section")),
        "headings": len(article.select("h2, h3, h4")),
        "paragraphs": len(article.select("p")),
        "figures": len(article.select("figure, .figure, .fig, [id^='fig']")),
        "tables": len(article.select("table, .table, [id^='table']")),
        "formulas": len(
            article.select("tex-math, .tex-math, math, .formula, .disp-formula")
        ),
    }


def _is_ieee_mediastore_url(url: str) -> bool:
    return _ieee_asset_url_path(url).startswith(IEEE_MEDIASTORE_PATH_PREFIX)


def _looks_like_ieee_large_media_url(url: str) -> bool:
    return bool(re.search(r"-(?:large|full)\.[a-z0-9]+$", _ieee_asset_url_path(url)))


def _looks_like_ieee_small_media_url(url: str) -> bool:
    return bool(
        re.search(
            r"-(?:small|thumb|thumbnail|preview)\.[a-z0-9]+$", _ieee_asset_url_path(url)
        )
    )


def _first_ieee_text(node: Tag, selectors: tuple[str, ...]) -> str:
    for selector in selectors:
        candidate = node.select_one(selector)
        if isinstance(candidate, Tag):
            text = normalize_text(candidate.get_text(" ", strip=True))
            if text:
                return text
    return ""


def _dedupe_ieee_urls(urls: list[str]) -> list[str]:
    deduped: list[str] = []
    seen: set[str] = set()
    for raw_url in urls:
        url = normalize_text(raw_url)
        if url and url not in seen:
            seen.add(url)
            deduped.append(url)
    return deduped


def _ieee_media_urls_from_attrs(
    node: Tag, source_url: str, *, tag_name: str, attr_name: str
) -> list[str]:
    urls: list[str] = []
    for tag in node.find_all(tag_name):
        if not isinstance(tag, Tag):
            continue
        absolute_url = _absolute_ieee_asset_url(
            normalize_text(str(tag.get(attr_name) or "")), source_url
        )
        if (
            absolute_url
            and _is_ieee_mediastore_url(absolute_url)
            and not _is_ignored_ieee_asset_url(absolute_url)
        ):
            urls.append(absolute_url)
    return _dedupe_ieee_urls(urls)


def _preferred_ieee_url(urls: list[str], *, prefer_large: bool) -> str:
    if prefer_large:
        for url in urls:
            if _looks_like_ieee_large_media_url(url):
                return url
    else:
        for url in urls:
            if _looks_like_ieee_small_media_url(url):
                return url
    return urls[0] if urls else ""


def _ieee_asset_from_figure_full_block(
    block: Tag, source_url: str
) -> dict[str, str] | None:
    class_names = {
        normalize_text(str(item)).lower() for item in (block.get("class") or [])
    }
    kind = "table" if "table" in class_names else "figure"
    href_urls = _ieee_media_urls_from_attrs(
        block, source_url, tag_name="a", attr_name="href"
    )
    image_urls = _ieee_media_urls_from_attrs(
        block, source_url, tag_name="img", attr_name="src"
    )
    full_size_url = _preferred_ieee_url(
        href_urls, prefer_large=True
    ) or _preferred_ieee_url(image_urls, prefer_large=True)
    preview_url = _preferred_ieee_url(image_urls, prefer_large=False)
    url = full_size_url or preview_url
    if not url:
        return None
    title = _first_ieee_text(block, (".title",))
    caption = _first_ieee_text(block, (".figcaption", "figcaption"))
    image = block.find("img")
    alt_text = (
        normalize_text(str(image.get("alt") or "")) if isinstance(image, Tag) else ""
    )
    caption = caption or title or alt_text
    asset = {
        "kind": kind,
        "heading": title
        or caption[:80]
        or alt_text
        or ("Table" if kind == "table" else "Figure"),
        "caption": caption,
        "url": url,
        "section": "body",
        "render_state": "inline",
    }
    if preview_url:
        asset["preview_url"] = preview_url
    if full_size_url:
        asset["full_size_url"] = full_size_url
    return asset


def _extract_ieee_body_media_assets(
    article_html: str, source_url: str
) -> list[dict[str, str]]:
    soup = BeautifulSoup(article_html, choose_parser())
    assets: list[dict[str, str]] = []
    for block in soup.select("div.figure.figure-full"):
        if isinstance(block, Tag):
            asset = _ieee_asset_from_figure_full_block(block, source_url)
            if asset is not None:
                assets.append(asset)
    return assets


def _ieee_asset_has_ignored_url(asset: Mapping[str, Any]) -> bool:
    semantic_text = " ".join(
        normalize_text(str(asset.get(field) or ""))
        for field in (
            "heading",
            "caption",
            "alt",
            "title",
            "aria_label",
            "filename_hint",
        )
    )
    if _ieee_support_icon_text(semantic_text) and (
        _small_html_dimension(asset.get("width"))
        or _small_html_dimension(asset.get("height"))
    ):
        return True
    for field in (
        "url",
        "full_size_url",
        "preview_url",
        "original_url",
        "download_url",
        "source_url",
        "figure_page_url",
    ):
        value = normalize_text(str(asset.get(field) or ""))
        if value and _is_ignored_ieee_asset_url(value):
            return True
    return False


def _absolute_ieee_html_asset_fields(
    asset: dict[str, Any], source_url: str
) -> dict[str, Any]:
    for field in IEEE_ASSET_URL_FIELDS:
        value = normalize_text(str(asset.get(field) or ""))
        if value:
            asset[field] = _absolute_ieee_asset_url(value, source_url)
    return asset


def _normalize_ieee_html_assets(
    extracted_assets: list[dict[str, Any]],
    body_media_assets: list[dict[str, str]],
    source_url: str,
) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    for item in [*body_media_assets, *extracted_assets]:
        asset = _absolute_ieee_html_asset_fields(dict(item), source_url)
        if not _ieee_asset_has_ignored_url(asset):
            candidates.append(asset)
    return _dedupe_ieee_assets_by_priority(
        candidates, merge_fields=IEEE_ASSET_URL_FIELDS
    )


def _extract_ieee_html(
    html_text: str,
    source_url: str,
    *,
    metadata: Mapping[str, Any],
    context: RuntimeContext | None = None,
) -> IeeeHtmlExtraction:
    if _looks_like_ieee_block_page(html_text, context=context, source_url=source_url):
        raise ProviderFailure(
            NO_RESULT,
            "IEEE dynamic HTML endpoint returned an access, challenge, or unable page.",
        )

    article = _find_ieee_article(html_text)
    if article is None:
        raise ProviderFailure(
            NO_RESULT, "IEEE dynamic HTML endpoint did not include #article."
        )
    asset_html = str(article)
    _clean_ieee_article(article)
    _annotate_ieee_inline_media_blocks(article, source_url)
    marker_counts = _ieee_marker_counts(article)
    article_text = normalize_text(article.get_text(" ", strip=True))
    if not article_text and not any(marker_counts.values()):
        raise ProviderFailure(
            NO_RESULT, "IEEE dynamic HTML endpoint returned an empty #article shell."
        )
    if marker_counts["paragraphs"] <= 0 and marker_counts["sections"] <= 0:
        raise ProviderFailure(
            NO_RESULT,
            "IEEE dynamic HTML endpoint did not include article body sections or paragraphs.",
        )

    section_hints = collect_html_section_hints(
        article, title=str(metadata.get("title") or "") or None
    )
    lines: list[str] = []
    render_container_markdown(article, lines, level=2)
    markdown_text = clean_rendered_markdown("\n".join(lines), noise_profile="ieee")
    if not normalize_text(markdown_text):
        raise ProviderFailure(
            NO_RESULT, "IEEE dynamic HTML endpoint did not produce usable Markdown."
        )
    cleaned_html = str(article)
    extracted_assets = extract_scoped_html_assets(
        cleaned_html, source_url, asset_profile="body"
    )
    extracted_assets.extend(
        _extract_ieee_supplementary_assets(cleaned_html, source_url)
    )
    extracted_assets = _normalize_ieee_html_assets(
        [dict(item) for item in extracted_assets],
        _extract_ieee_body_media_assets(asset_html, source_url),
        source_url,
    )
    return IeeeHtmlExtraction(
        html_text=cleaned_html,
        markdown_text=markdown_text,
        section_hints=list(section_hints),
        abstract_sections=[],
        extracted_assets=[dict(item) for item in extracted_assets],
        marker_counts=marker_counts,
    )
