"""arXiv LaTeXML object and embedded-vector representation boundaries."""

from __future__ import annotations

import base64
import copy
from pathlib import Path
from typing import Any
from urllib.parse import urljoin

from bs4 import BeautifulSoup, Tag

from ..artifacts import ArtifactStore
from ..asset_budget import AssetBudget, AssetBudgetExceeded
from ..utils import sanitize_filename
from ._arxiv_parsing import ARXIV_HTML_PARSER

INLINE_SVG_PREFIX = "data:image/svg+xml;base64,"


def _standalone_svg(node: Tag) -> bytes:
    svg = copy.deepcopy(node)
    # HTML parsers lowercase SVG's case-sensitive XML names. Restore their
    # serialization spelling, without changing paths, text or layout values.
    names = {"foreignobject": "foreignObject", "clippath": "clipPath"}
    attributes = {
        "viewbox": "viewBox",
        "preserveaspectratio": "preserveAspectRatio",
        "clippathunits": "clipPathUnits",
    }
    for element in [svg, *svg.find_all(True)]:
        element.name = names.get(element.name, element.name)
        for old, new in attributes.items():
            if old in element.attrs:
                element[new] = element.attrs.pop(old)
        if element.name == "foreignObject":
            for child in element.find_all(recursive=False):
                child["xmlns"] = "http://www.w3.org/1999/xhtml"
        if element.name == "math":
            element["xmlns"] = "http://www.w3.org/1998/Math/MathML"
    svg["xmlns"] = "http://www.w3.org/2000/svg"
    svg["xmlns:xlink"] = "http://www.w3.org/1999/xlink"
    return str(svg).encode("utf-8")


def prepare_arxiv_graphics(article: Tag, source_url: str) -> None:
    """Expose the actual graph at its original DOM position before table capture."""
    factory = BeautifulSoup("", ARXIV_HTML_PARSER)
    for node in list(article.select("object[data], svg.ltx_picture")):
        # Frontmatter icons and inline mathematical glyphs are not figure assets.
        if node.find_parent(["figure", "section"]) is None:
            continue
        if node.name == "svg" and node.find_parent("figure") is None:
            continue
        if node.name == "object":
            if node.get("type") != "image/svg+xml" and not str(
                node.get("data", "")
            ).split("?", 1)[0].endswith(".svg"):
                continue
            target = urljoin(source_url, str(node["data"]))
            kind = "arxiv_html_object"
        else:
            target = INLINE_SVG_PREFIX + base64.b64encode(_standalone_svg(node)).decode(
                "ascii"
            )
            kind = "arxiv_inline_svg"
        image = factory.new_tag("img")
        image.attrs = {
            key: value
            for key, value in node.attrs.items()
            if key in {"id", "class", "width", "height", "style"}
        }
        image["src"] = target
        image["data-arxiv-graphic"] = kind
        node.replace_with(image)
    # Resolve both Markdown-rendered and table-rendered images in their source
    # context. Do not deduplicate separate legitimate occurrences.
    for image in article.find_all("img"):
        for attribute in ("src", "data-src", "data-lazy-src"):
            if image.get(attribute):
                image[attribute] = urljoin(source_url, str(image[attribute]))


def save_arxiv_inline_svgs(assets, *, output_dir, article_id, source_url, context):
    """Publish already acquired vector bytes through the usual store and budget."""
    result: dict[str, list[dict[str, Any]]] = {"assets": [], "asset_failures": []}
    budget = context.asset_budget or AssetBudget()
    store = context.artifact_store or ArtifactStore.from_download_dir(output_dir)
    folder = Path(output_dir) / f"{sanitize_filename(article_id)}_assets"
    folder.mkdir(parents=True, exist_ok=True)
    for asset in assets:
        context.raise_if_cancelled()
        origin = (
            source_url + "#" + str(asset.get("image_id") or asset.get("dom_id") or "")
        )
        try:
            body = base64.b64decode(
                asset["url"][len(INLINE_SVG_PREFIX) :], validate=True
            )
            with budget.reserve(declared_bytes=len(body)) as reservation:
                reservation.consume(len(body))
                filename = sanitize_filename(str(asset["image_id"])) + ".svg"
                with reservation.commit_critical_section():
                    path = store.write_bytes_file(
                        folder / filename, body, commit_guard=context.raise_if_cancelled
                    )
                    reservation.commit()
            result["assets"].append(
                {
                    **asset,
                    "path": str(path),
                    "source_url": origin,
                    "downloaded_bytes": len(body),
                    "download_tier": "full_size",
                    "content_type": "image/svg+xml",
                }
            )
        except (AssetBudgetExceeded, OSError, ValueError) as exc:
            result["asset_failures"].append(
                {
                    "kind": "figure",
                    "section": "body",
                    "heading": asset.get("heading"),
                    "source_url": origin,
                    "reason": getattr(
                        exc, "reason_code", "arxiv_inline_svg_save_failed"
                    ),
                    "message": str(exc),
                }
            )
    return result
