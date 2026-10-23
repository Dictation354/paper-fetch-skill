"""Associate Oxford figure renditions by their owning DOM image."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from bs4 import Tag

from ..extraction.html.asset_fields import PREVIEW_IMAGE_ATTRS
from ..extraction.html.assets.figures import (
    SILVERCHAIR_FIGURE_CONTAINER_SELECTORS,
    _figure_assets_from_soup_node,
    _image_is_formula_asset,
    _is_silverchair_figure_node,
)


def extract_inline_figures(body: Tag, source_url: str) -> list[dict[str, Any]]:
    """Discover each image once across nested figure/graphic containers.

    Reuse the Silverchair URL and signature parser in every owning scope, so
    sibling download controls can supply an original without equating distinct
    URL renditions or different subpanels.
    """
    by_image: dict[int, dict[str, Any]] = {}
    caption_only: list[dict[str, Any]] = []
    for node in body.select(
        ", ".join(("figure", *SILVERCHAIR_FIGURE_CONTAINER_SELECTORS))
    ):
        if node.name != "figure" and not _is_silverchair_figure_node(node):
            continue
        images = [
            img for img in node.find_all("img") if not _image_is_formula_asset(img)
        ]
        # The shared single-image helper may inspect its parent. Enclosing
        # scopes are visited separately here; isolate this scope so one panel
        # cannot borrow a sibling panel's full-size attribute or link.
        for asset in _figure_assets_from_soup_node(deepcopy(node), body, source_url):
            if not images:
                if asset not in caption_only:
                    caption_only.append(asset)
                continue
            image = images[int(asset["asset_order"])]
            existing = by_image.get(id(image))
            if existing is None:
                by_image[id(image)] = asset
                continue
            # Outer scopes carry figure labels and controls; inner scopes can
            # add an image-specific original. Never replace one with a preview.
            for field, value in asset.items():
                if value and not existing.get(field):
                    existing[field] = value
            if len(asset.get("caption", "")) > len(existing.get("caption", "")):
                existing["caption"] = asset["caption"]
            existing["url"] = existing.get("full_size_url") or existing["url"]

    figures = []
    for image in body.find_all("img"):
        figure = by_image.get(id(image))
        if figure is None:
            continue
        target = figure.get("full_size_url") or figure["url"]
        if target:
            figure["original_url"] = target
            image["src"] = target
            for attr in PREVIEW_IMAGE_ATTRS:
                if image.has_attr(attr):
                    image[attr] = target
        figures.append(figure)
    return [*figures, *caption_only]
