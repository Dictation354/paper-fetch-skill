"""Formula image asset discovery helpers."""

from __future__ import annotations

import urllib.parse
from typing import Any

from ..formula_rules import (
    FORMULA_IMAGE_ATTRS,
    FORMULA_IMAGE_SRCSET_ATTRS,
    formula_heading_for_image,
    formula_image_url_from_node,
    looks_like_formula_image,
)
from ..parsing import choose_parser
from .dom import _soup_attr_url

try:
    from bs4 import BeautifulSoup, Tag
except ImportError:  # pragma: no cover - dependency is declared in pyproject
    BeautifulSoup = None
    Tag = None

def _looks_like_formula_image(tag: Any, url: str) -> bool:
    return looks_like_formula_image(tag, url)


def _formula_heading_for_image(tag: Any, index: int) -> str:
    return formula_heading_for_image(tag, index)


def extract_formula_assets(html_text: str, source_url: str) -> list[dict[str, str]]:
    if BeautifulSoup is None:
        return []

    soup = BeautifulSoup(html_text, choose_parser())
    assets: list[dict[str, str]] = []
    seen: set[str] = set()
    for image in soup.find_all("img"):
        if not isinstance(image, Tag):
            continue
        url = formula_image_url_from_node(image) or _soup_attr_url(
            image,
            *FORMULA_IMAGE_ATTRS,
            *FORMULA_IMAGE_SRCSET_ATTRS,
        )
        if not url or not _looks_like_formula_image(image, url):
            continue
        absolute_url = urllib.parse.urljoin(source_url, url)
        if not absolute_url or absolute_url in seen:
            continue
        seen.add(absolute_url)
        heading = _formula_heading_for_image(image, len(assets) + 1)
        assets.append(
            {
                "kind": "formula",
                "heading": heading,
                "caption": "",
                "url": absolute_url,
                "preview_url": absolute_url,
                "section": "body",
            }
        )
    return assets


__all__ = [
    "extract_formula_assets",
]
