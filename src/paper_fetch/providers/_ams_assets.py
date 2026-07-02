"""AMS asset extraction helpers."""

from __future__ import annotations

import html
import re
import urllib.parse
from typing import Any

from ..common_patterns import TABLE_LABEL_PATTERN
from ..extraction.html.assets import extract_formula_assets
from ..extraction.html.parsing import choose_parser
from ..image_tools import source_image_format_from_payload
from ..utils import normalize_text
from ._ams_dom import (
    _ams_full_image_src,
    _ams_gallery_href,
    _ams_inline_image,
    _normalize_ams_dom,
    _render_ams_inline_text,
)
from ._ams_markdown import _normalize_ams_label_text

from bs4 import BeautifulSoup, Tag


AMS_SOURCE_FIGURE_FORMATS = {"eps", "tiff"}
AMS_SOURCE_FIGURE_KEY_PATTERN = re.compile(
    r"(?:^|[-_/])f0*([0-9]+[A-Za-z]?)(?=[._/?#-]|$)",
    flags=re.IGNORECASE,
)
AMS_SOURCE_FIGURE_DOM_ID_PATTERN = re.compile(
    r"^(?:fig|figure)0*([0-9]+[A-Za-z]?)$",
    flags=re.IGNORECASE,
)
AMS_SOURCE_FIGURE_LABEL_PATTERN = re.compile(
    r"\bfig(?:ure)?\.?\s*0*([0-9]+[A-Za-z]?)\b",
    flags=re.IGNORECASE,
)


def _normalize_ams_asset_html(html_text: str) -> str:
    soup = BeautifulSoup(html_text, choose_parser())
    _normalize_ams_dom(soup)
    return str(soup)


def _table_label_text(node: Any) -> str:
    if not isinstance(node, Tag):
        return "Table"
    for selector in (".tableWrapLabel", ".label"):
        candidate = node.select_one(selector)
        if isinstance(candidate, Tag):
            text = _normalize_ams_label_text(
                candidate.get_text(" ", strip=True), kind="table"
            )
            if text:
                return text
    title = _normalize_ams_label_text(str(node.get("title") or ""), kind="table")
    match = TABLE_LABEL_PATTERN.search(title)
    if match:
        return f"Table {match.group(1)}."
    text = _normalize_ams_label_text(node.get_text(" ", strip=True), kind="table")
    match = TABLE_LABEL_PATTERN.search(text)
    if match:
        return f"Table {match.group(1)}."
    return "Table"


def _table_caption_text(node: Any, label: str) -> str:
    if not isinstance(node, Tag):
        return ""
    candidates: list[str] = []
    for selector in (".tableWrapCaption", ".caption", "figcaption", "caption"):
        caption_node = node.select_one(selector)
        if isinstance(caption_node, Tag):
            text = _render_ams_inline_text(caption_node)
            if text:
                candidates.append(text)
    title = normalize_text(str(node.get("title") or ""))
    if title:
        candidates.append(title)
    label_text = normalize_text(label).rstrip(".")
    for text in candidates:
        if label_text:
            text = re.sub(
                rf"^{re.escape(label_text)}\.?\s*", "", text, flags=re.IGNORECASE
            )
        text = normalize_text(text).lstrip(".:;,-) ]")
        if text:
            return text
    return ""


def _absolute_url(source_url: str, value: str) -> str:
    return urllib.parse.urljoin(source_url, normalize_text(value))


def _ams_figure_key(value: str) -> str:
    normalized = normalize_text(value)
    if not normalized:
        return ""
    parsed_path = urllib.parse.urlparse(normalized).path or normalized
    for candidate in (parsed_path, normalized):
        match = AMS_SOURCE_FIGURE_KEY_PATTERN.search(candidate)
        if match:
            return f"f{match.group(1).lower()}"
    dom_match = AMS_SOURCE_FIGURE_DOM_ID_PATTERN.match(normalized)
    if dom_match:
        return f"f{dom_match.group(1).lower()}"
    label_match = AMS_SOURCE_FIGURE_LABEL_PATTERN.search(normalized)
    if label_match:
        return f"f{label_match.group(1).lower()}"
    return ""


def _ams_tag_class_blob(node: Any) -> str:
    if not isinstance(node, Tag):
        return ""
    classes = node.get("class") or []
    if isinstance(classes, str):
        return classes.lower()
    return " ".join(str(item) for item in classes).lower()


def _ams_download_link_is_powerpoint(anchor: Any) -> bool:
    if not isinstance(anchor, Tag):
        return True
    class_blob = _ams_tag_class_blob(anchor)
    text = normalize_text(anchor.get_text(" ", strip=True)).lower()
    href = normalize_text(str(anchor.get("href") or ""))
    return "export-figure-ppt" in class_blob or "powerpoint" in text or href == "#"


def _ams_download_link_source_format(anchor: Any, href: str) -> str:
    if not isinstance(anchor, Tag):
        return ""
    for value in (href, str(anchor.get("download") or "")):
        detected = source_image_format_from_payload(b"", source_url=value)
        if detected in AMS_SOURCE_FIGURE_FORMATS:
            return detected
    return ""


def _ams_source_figure_keys(node: Any, anchor: Any) -> set[str]:
    keys: set[str] = set()
    if isinstance(anchor, Tag):
        for value in (anchor.get("href"), anchor.get("download")):
            key = _ams_figure_key(str(value or ""))
            if key:
                keys.add(key)
    if not isinstance(node, Tag):
        return keys

    for candidate in (node, *getattr(node, "parents", ())):
        if not isinstance(candidate, Tag):
            continue
        for attr_name in ("id", "data-id", "data-content-id"):
            key = _ams_figure_key(str(candidate.get(attr_name) or ""))
            if key:
                keys.add(key)
        if candidate.name in {"article", "body", "html"}:
            break

    for image in node.find_all("img"):
        if not isinstance(image, Tag):
            continue
        for attr_name in ("data-image-src", "data-src", "data-full-size", "src"):
            key = _ams_figure_key(str(image.get(attr_name) or ""))
            if key:
                keys.add(key)

    for ppt_anchor in node.select("a.export-figure-ppt"):
        if not isinstance(ppt_anchor, Tag):
            continue
        key = _ams_figure_key(str(ppt_anchor.get("data-image-uris") or ""))
        if key:
            keys.add(key)

    caption = node.find("figcaption")
    if isinstance(caption, Tag):
        key = _ams_figure_key(caption.get_text(" ", strip=True))
        if key:
            keys.add(key)
    return keys


def _extract_ams_download_figure_sources(
    html_text: str,
    source_url: str,
) -> dict[str, dict[str, str]]:
    soup = BeautifulSoup(html_text, choose_parser())
    sources_by_key: dict[str, dict[str, str]] = {}
    for node in soup.find_all("figure"):
        if not isinstance(node, Tag):
            continue
        for anchor in node.select("li.download-figure a[href], a[download][href]"):
            if not isinstance(anchor, Tag) or _ams_download_link_is_powerpoint(anchor):
                continue
            href = normalize_text(str(anchor.get("href") or ""))
            source_format = _ams_download_link_source_format(anchor, href)
            if source_format not in AMS_SOURCE_FIGURE_FORMATS:
                continue
            download_url = _absolute_url(source_url, href)
            if not download_url:
                continue
            info = {
                "download_url": download_url,
                "source_asset_format": source_format,
            }
            filename = normalize_text(str(anchor.get("download") or ""))
            if filename:
                info["source_filename"] = filename
            for key in _ams_source_figure_keys(node, anchor):
                sources_by_key.setdefault(key, info)
    return sources_by_key


def _ams_asset_figure_keys(asset: dict[str, str]) -> set[str]:
    keys: set[str] = set()
    for field in (
        "download_url",
        "url",
        "full_size_url",
        "preview_url",
        "source_url",
        "original_url",
        "figure_page_url",
        "dom_id",
        "image_id",
        "heading",
        "caption",
    ):
        key = _ams_figure_key(str(asset.get(field) or ""))
        if key:
            keys.add(key)
    return keys


def _merge_ams_download_figure_sources(
    assets: list[dict[str, str]],
    sources_by_key: dict[str, dict[str, str]],
) -> list[dict[str, str]]:
    if not sources_by_key:
        return assets
    merged: list[dict[str, str]] = []
    for asset in assets:
        item = dict(asset)
        if normalize_text(str(item.get("kind") or "")).lower() == "figure":
            for key in _ams_asset_figure_keys(item):
                source = sources_by_key.get(key)
                if not source:
                    continue
                item["download_url"] = source["download_url"]
                item["source_asset_format"] = source["source_asset_format"]
                if source.get("source_filename"):
                    item["source_filename"] = source["source_filename"]
                break
        merged.append(item)
    return merged


def _ams_download_figure_source_sidecar(
    sources_by_key: dict[str, dict[str, str]],
) -> str:
    if not sources_by_key:
        return ""
    figures: list[str] = []
    for key, source in sorted(sources_by_key.items()):
        download_url = normalize_text(source.get("download_url"))
        if not download_url:
            continue
        filename = normalize_text(source.get("source_filename"))
        figure_id = f"fig{key[1:]}" if key.startswith("f") else key
        download_attr = (
            f' download="{html.escape(filename, quote=True)}"' if filename else ""
        )
        figures.append(
            "<figure"
            f' id="{html.escape(figure_id, quote=True)}"'
            ' data-paper-fetch-ams-source-figure="true">'
            "<ul>"
            '<li class="download-figure">'
            f'<a href="{html.escape(download_url, quote=True)}"{download_attr}>'
            "Download Figure"
            "</a>"
            "</li>"
            "</ul>"
            "</figure>"
        )
    if not figures:
        return ""
    return (
        '<div hidden data-paper-fetch-ams-download-figure-sources="true">'
        + "".join(figures)
        + "</div>"
    )


def _append_ams_download_figure_source_sidecar(
    body_container: Any,
    raw_body_container: Any,
    source_url: str,
) -> None:
    if not isinstance(body_container, Tag) or not isinstance(raw_body_container, Tag):
        return
    sources_by_key = _extract_ams_download_figure_sources(
        str(raw_body_container),
        source_url,
    )
    sidecar_html = _ams_download_figure_source_sidecar(sources_by_key)
    if not sidecar_html:
        return
    fragment = BeautifulSoup(sidecar_html, choose_parser())
    sidecar = fragment.find(
        attrs={"data-paper-fetch-ams-download-figure-sources": "true"}
    )
    if isinstance(sidecar, Tag):
        target = body_container.select_one(
            "#articleBody, #contentRoot, #bodymatter, [property='articleBody'], "
            "[itemprop='articleBody'], .NLM_body, .component-content-html, "
            ".container-fulltext-display"
        )
        if not isinstance(target, Tag):
            target = body_container
        target.append(sidecar)


def _ams_asset_url_keys(asset: dict[str, str]) -> set[str]:
    return {
        normalize_text(str(asset.get(field) or ""))
        for field in (
            "url",
            "full_size_url",
            "preview_url",
            "source_url",
            "original_url",
            "path",
        )
        if normalize_text(str(asset.get(field) or ""))
    }


def _extract_ams_table_assets(html_text: str, source_url: str) -> list[dict[str, str]]:
    soup = BeautifulSoup(_normalize_ams_asset_html(html_text), choose_parser())
    assets: list[dict[str, str]] = []
    seen: set[str] = set()
    for node in soup.select(".tableWrap"):
        if not isinstance(node, Tag):
            continue
        image = _ams_inline_image(node)
        full_size_url = _ams_gallery_href(node) or _ams_full_image_src(node)
        preview_url = ""
        if isinstance(image, Tag):
            preview_url = normalize_text(
                str(
                    image.get("data-src")
                    or image.get("data-image-src")
                    or image.get("src")
                    or ""
                )
            )
            full_size_url = (
                normalize_text(str(image.get("data-full-size") or "")) or full_size_url
            )
        url = full_size_url or preview_url
        if not url:
            continue
        absolute = _absolute_url(source_url, url)
        if absolute in seen:
            continue
        seen.add(absolute)
        label = _table_label_text(node)
        caption = _table_caption_text(node, label)
        asset: dict[str, str] = {
            "kind": "table",
            "heading": label or "Table",
            "caption": caption,
            "url": absolute,
            "section": "body",
        }
        dom_id = normalize_text(str(node.get("id") or ""))
        if dom_id:
            asset["dom_id"] = dom_id
        if preview_url:
            asset["preview_url"] = _absolute_url(source_url, preview_url)
        if full_size_url:
            asset["full_size_url"] = _absolute_url(source_url, full_size_url)
        assets.append(asset)
    return assets


def _extract_ams_formula_assets(
    html_text: str, source_url: str
) -> list[dict[str, str]]:
    return extract_formula_assets(html_text, source_url, noise_profile="ams")


def extract_asset_html_scopes(
    body_container: Any,
    supplementary_container: Any,
    *,
    publisher: str,
    source_url: str,
    raw_body_container: Any | None = None,
    content_fragment_html,
    atypon_browser_workflow_supplementary_sections,
) -> tuple[str, str]:
    for node in list(atypon_browser_workflow_supplementary_sections(body_container)):
        node.decompose()

    supplementary_html = "\n".join(
        str(node)
        for node in atypon_browser_workflow_supplementary_sections(
            supplementary_container
        )
        if normalize_text(node.get_text(" ", strip=True))
    )
    if raw_body_container is not None:
        _append_ams_download_figure_source_sidecar(
            body_container,
            raw_body_container,
            source_url,
        )
    return content_fragment_html(
        body_container, publisher=publisher
    ), supplementary_html


def scoped_asset_extractor(
    body_html_text: str,
    source_url: str,
    *,
    asset_profile,
    supplementary_html_text: str | None = None,
) -> list[dict[str, str]]:
    from ._html_asset_engine import (
        HtmlAssetExtractionPolicy,
        extract_scoped_assets_with_policy,
    )
    from .atypon_browser_workflow.asset_scopes import extract_supplementary_assets

    download_figure_sources = _extract_ams_download_figure_sources(
        body_html_text,
        source_url,
    )
    normalized_body_html = _normalize_ams_asset_html(body_html_text)
    # The Atypon shared extractor owns figures, formulas, and supplementary assets.
    # AMS adds image-only tableWrap screenshots here because they are table surrogates.
    assets = extract_scoped_assets_with_policy(
        normalized_body_html,
        source_url,
        asset_profile=asset_profile,
        supplementary_html_text=(
            _normalize_ams_asset_html(supplementary_html_text)
            if supplementary_html_text is not None
            else None
        ),
        policy=HtmlAssetExtractionPolicy(
            formula_extractor=_extract_ams_formula_assets,
            supplementary_extractor=extract_supplementary_assets,
        ),
    )
    table_assets = _extract_ams_table_assets(normalized_body_html, source_url)
    table_urls = {url for asset in table_assets for url in _ams_asset_url_keys(asset)}
    if table_urls:
        assets = [
            asset for asset in assets if not (_ams_asset_url_keys(asset) & table_urls)
        ]
    assets.extend(table_assets)
    assets = _merge_ams_download_figure_sources(assets, download_figure_sources)
    return assets


__all__ = [
    "extract_asset_html_scopes",
    "scoped_asset_extractor",
]
