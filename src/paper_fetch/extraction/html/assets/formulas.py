"""Formula image asset discovery helpers."""

from __future__ import annotations

import urllib.parse
from typing import Any

from ..formula_rules import (
    FORMULA_IMAGE_ATTRS,
    FORMULA_IMAGE_URL_PATTERN,
    FORMULA_IMAGE_SRCSET_ATTRS,
    display_formula_nodes,
    formula_ancestor_identity_text,
    formula_container_tokens_for_profile,
    formula_heading_for_image,
    formula_image_url_from_node,
    html_node_is_figure_asset_context,
    looks_like_formula_image,
)
from ..parsing import choose_parser
from .dom import _soup_attr_url

from bs4 import BeautifulSoup, Tag


def _looks_like_formula_image(
    tag: Any,
    url: str,
    *,
    noise_profile: str | None = None,
) -> bool:
    if looks_like_formula_image(tag, url, noise_profile=noise_profile):
        return True
    if html_node_is_figure_asset_context(tag, noise_profile=noise_profile):
        return False
    if FORMULA_IMAGE_URL_PATTERN.search(url):
        return True
    if not isinstance(tag, Tag):
        return False
    identity = formula_ancestor_identity_text(tag)
    return any(
        token in identity
        for token in formula_container_tokens_for_profile(noise_profile)
    )


def _formula_heading_for_image(
    tag: Any,
    index: int,
    *,
    noise_profile: str | None = None,
) -> str:
    return formula_heading_for_image(tag, index, noise_profile=noise_profile)


def _formula_asset_seen_key(absolute_url: str) -> str:
    parsed_path = urllib.parse.unquote(urllib.parse.urlparse(absolute_url).path or "")
    basename = parsed_path.rstrip("/").rsplit("/", 1)[-1].lower()
    return basename or absolute_url


def _formula_asset_candidate_nodes(
    soup: Any,
    *,
    noise_profile: str | None = None,
) -> list[Any]:
    candidates: list[Any] = []
    seen_nodes: set[int] = set()

    def add(node: Any) -> None:
        if not isinstance(node, Tag):
            return
        node_id = id(node)
        if node_id in seen_nodes:
            return
        seen_nodes.add(node_id)
        candidates.append(node)

    for image in soup.find_all("img"):
        add(image)
    for node in display_formula_nodes(soup, noise_profile=noise_profile):
        add(node)
    for node in soup.find_all(True):
        if not isinstance(node, Tag):
            continue
        if any(
            node.has_attr(attr)
            for attr in (*FORMULA_IMAGE_ATTRS, *FORMULA_IMAGE_SRCSET_ATTRS)
        ):
            add(node)
    return candidates


def extract_formula_assets(
    html_text: str,
    source_url: str,
    *,
    noise_profile: str | None = None,
) -> list[dict[str, str]]:

    soup = BeautifulSoup(html_text, choose_parser())
    assets: list[dict[str, str]] = []
    seen: set[str] = set()
    seen_keys: set[str] = set()
    for node in _formula_asset_candidate_nodes(soup, noise_profile=noise_profile):
        if not isinstance(node, Tag):
            continue
        url = formula_image_url_from_node(
            node, include_adjacent=True
        ) or _soup_attr_url(
            node,
            *FORMULA_IMAGE_ATTRS,
            *FORMULA_IMAGE_SRCSET_ATTRS,
        )
        if not url or not _looks_like_formula_image(
            node,
            url,
            noise_profile=noise_profile,
        ):
            continue
        absolute_url = urllib.parse.urljoin(source_url, url)
        seen_key = _formula_asset_seen_key(absolute_url)
        if not absolute_url or absolute_url in seen or seen_key in seen_keys:
            continue
        seen.add(absolute_url)
        seen_keys.add(seen_key)
        heading = _formula_heading_for_image(
            node,
            len(assets) + 1,
            noise_profile=noise_profile,
        )
        assets.append(
            {
                "kind": "formula",
                "heading": heading,
                "caption": "",
                "url": absolute_url,
                "preview_url": absolute_url,
                "preview_accepted": "true",
                "section": "body",
            }
        )
    return assets


__all__ = [
    "extract_formula_assets",
]
