"""MDPI asset extraction helpers."""

from __future__ import annotations

import copy
import re
import urllib.parse
from typing import Any

from bs4 import BeautifulSoup, Tag

from ..extraction.html.assets import (
    extract_scoped_html_assets as extract_provider_neutral_scoped_assets,
)
from ..extraction.html.parsing import choose_parser
from ..extraction.html.signals import HtmlExtractionFailure
from ..models.markdown import (
    image_reference_candidates,
    image_references_match,
    iter_markdown_images,
)
from ..utils import extend_unique, normalize_text
from ._mdpi_dom import (
    MDPI_NOISE_PROFILE,
    MDPI_SUPPLEMENTARY_TEXT_TOKENS,
    _normalize_mdpi_dom,
    _select_article_container,
)

_SUPPLEMENTARY_SELECTORS = (
    "section[id*='supplement']",
    "div[id*='supplement']",
    "section[id^='app']",
)


def mark_inline_assets(markdown_text: str, assets: list[Any], source: str) -> None:
    if source != "mdpi_html" or not markdown_text or not assets:
        return
    inline_candidates = [
        image_reference_candidates(image.url)
        for image in iter_markdown_images(markdown_text)
        if image_reference_candidates(image.url)
    ]
    if not inline_candidates:
        return

    for asset in assets:
        kind = normalize_text(getattr(asset, "kind", None)).lower()
        if kind not in {"figure", "table", "formula", "equation"}:
            continue
        if normalize_text(getattr(asset, "section", None)).lower() in {
            "appendix",
            "supplementary",
        }:
            continue
        asset_candidates: set[str] = set()
        for field in (
            "path",
            "url",
            "original_url",
            "download_url",
            "source_url",
            "source_path",
            "source_href",
        ):
            asset_candidates |= image_reference_candidates(getattr(asset, field, None))
        if asset_candidates and any(
            image_references_match(asset_candidates, inline_candidate)
            for inline_candidate in inline_candidates
        ):
            asset.render_state = "inline"


def extract_pdf_urls(html_text: str, source_url: str | None = None) -> list[str]:
    soup = BeautifulSoup(html_text, choose_parser())
    urls: list[str] = []
    for selector, attr in (
        ("meta[name='citation_pdf_url']", "content"),
        ("link[type='application/pdf']", "href"),
        ("a[href$='/pdf']", "href"),
        ("a[href*='/pdf?']", "href"),
    ):
        for node in soup.select(selector):
            value = normalize_text(str(node.get(attr) or ""))
            if value:
                extend_unique(urls, [urllib.parse.urljoin(source_url or "", value)])
    return urls


def mdpi_pdf_url_from_landing_url(url: str | None) -> str | None:
    candidate = normalize_text(url)
    if not candidate:
        return None
    parsed = urllib.parse.urlparse(candidate)
    host = normalize_text(parsed.hostname or "").lower()
    if host not in {"www.mdpi.com", "mdpi.com"}:
        return None
    path = parsed.path.rstrip("/")
    if not path:
        return None
    if path.endswith("/pdf") or "/pdf/" in path:
        return candidate
    if re.fullmatch(r"/[0-9]{4}-[0-9Xx]{3,4}/[0-9]+/[0-9]+/[0-9]+", path):
        return urllib.parse.urlunparse(parsed._replace(path=f"{path}/pdf", query=""))
    return None


def extract_asset_html_scopes(html_text: str, source_url: str) -> tuple[str, str]:
    del source_url
    soup = BeautifulSoup(html_text, choose_parser())
    container = _select_article_container(soup)
    if container is None:
        raise HtmlExtractionFailure(
            "article_container_not_found",
            "Could not identify the MDPI article container for assets.",
        )
    body_container = copy.deepcopy(container)
    supplementary_container = copy.deepcopy(container)
    _normalize_mdpi_dom(body_container)
    _normalize_mdpi_dom(supplementary_container)

    for node in list(body_container.select(", ".join(_SUPPLEMENTARY_SELECTORS))):
        if (
            isinstance(node, Tag)
            and "supplement" in normalize_text(node.get_text(" ", strip=True)).lower()
        ):
            node.decompose()

    supplementary_nodes: list[Tag] = []
    for selector in _SUPPLEMENTARY_SELECTORS:
        for node in supplementary_container.select(selector):
            if not isinstance(node, Tag):
                continue
            text = normalize_text(node.get_text(" ", strip=True)).lower()
            if "supplement" in text or any(
                token in text for token in MDPI_SUPPLEMENTARY_TEXT_TOKENS
            ):
                supplementary_nodes.append(node)
    supplementary_html = "\n".join(str(node) for node in supplementary_nodes)
    return str(body_container), supplementary_html


def extract_scoped_html_assets(
    html_text: str,
    source_url: str,
    *,
    asset_profile,
) -> list[dict[str, str]]:
    body_html, supplementary_html = extract_asset_html_scopes(html_text, source_url)
    assets = extract_provider_neutral_scoped_assets(
        body_html,
        source_url,
        asset_profile=asset_profile,
        supplementary_html_text=supplementary_html,
        noise_profile=MDPI_NOISE_PROFILE,
    )
    if asset_profile == "all":
        assets.extend(
            _extract_mdpi_supplementary_assets(supplementary_html, source_url)
        )
    return _dedupe_assets(assets)


def _extract_mdpi_supplementary_assets(
    supplementary_html: str,
    source_url: str,
) -> list[dict[str, str]]:
    soup = BeautifulSoup(supplementary_html, choose_parser())
    assets: list[dict[str, str]] = []
    for anchor in soup.find_all("a", href=True):
        href = normalize_text(str(anchor.get("href") or ""))
        if not href or href.startswith("#"):
            continue
        text = normalize_text(anchor.get_text(" ", strip=True))
        context = normalize_text(
            anchor.find_parent(["section", "div"]).get_text(" ", strip=True)
            if isinstance(anchor.find_parent(["section", "div"]), Tag)
            else ""
        )
        lowered = " ".join([href, text, context]).lower()
        if not any(
            token in lowered for token in ("supplement", "/s1", "table s", "figure s")
        ):
            continue
        assets.append(
            {
                "kind": "supplementary",
                "heading": text or "Supplementary Material",
                "caption": context,
                "section": "supplementary",
                "url": urllib.parse.urljoin(source_url, href),
            }
        )
    return assets


def _dedupe_assets(assets: list[dict[str, str]]) -> list[dict[str, str]]:
    deduped: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for asset in assets:
        key = (
            normalize_text(str(asset.get("kind") or "")),
            normalize_text(str(asset.get("url") or asset.get("heading") or "")),
        )
        if key in seen:
            continue
        seen.add(key)
        deduped.append(asset)
    return deduped


__all__ = [
    "extract_asset_html_scopes",
    "extract_pdf_urls",
    "extract_scoped_html_assets",
    "mark_inline_assets",
    "mdpi_pdf_url_from_landing_url",
]
