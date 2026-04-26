"""Shared HTML formula discovery rules."""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from typing import Any

from ...utils import normalize_text

try:
    from bs4 import Tag
except ImportError:  # pragma: no cover - dependency is declared in pyproject
    Tag = None

FORMULA_IMAGE_URL_PATTERN = re.compile(
    r"(?:^|[-_/])(?:math|ieq)[-_]?\d|_IEq\d|math-\d|equation",
    flags=re.IGNORECASE,
)
FORMULA_CONTAINER_TOKENS = (
    "inline-equation",
    "display-equation",
    "disp-formula",
    "display-formula",
    "fallback__mathequation",
)
FORMULA_IMAGE_ATTRS = (
    "data-altimg",
    "data-alt-image",
    "data-original",
    "data-full-size",
    "data-fullsize",
    "data-zoom-src",
    "data-zoom-image",
    "data-lg-src",
    "data-hi-res-src",
    "data-hires",
    "data-large-src",
    "data-image-full",
    "data-download-url",
    "data-src",
    "src",
    "data-lazy-src",
    "location",
)
FORMULA_IMAGE_SRCSET_ATTRS = ("srcset", "data-srcset")
DISPLAY_FORMULA_SELECTORS = (
    ".display-formula",
    ".disp-formula",
    ".display-equation",
    ".inline-equation",
    "math[display='block']",
    "div[role='math']",
)


def first_url_from_srcset(value: str | None) -> str:
    srcset = normalize_text(value)
    if not srcset:
        return ""
    best_url = ""
    best_score = -1.0
    for raw_part in srcset.split(","):
        part = raw_part.strip()
        if not part:
            continue
        pieces = part.split()
        url = pieces[0].strip()
        score = 0.0
        for descriptor in pieces[1:]:
            match = re.match(r"^([0-9]+(?:\.[0-9]+)?)(w|x)$", descriptor.strip().lower())
            if not match:
                continue
            multiplier = 1000.0 if match.group(2) == "x" else 1.0
            score = max(score, float(match.group(1)) * multiplier)
        if score >= best_score:
            best_url = url
            best_score = score
    return best_url


def formula_node_identity_text(node: Any) -> str:
    if Tag is None or not isinstance(node, Tag):
        return ""
    attrs = getattr(node, "attrs", None) or {}
    parts = [normalize_text(str(node.name or ""))]
    for key in ("id", "class", "role", "data-test", "data-type", "data-container-section"):
        value = attrs.get(key)
        if isinstance(value, (list, tuple, set)):
            parts.extend(normalize_text(str(item)) for item in value)
        else:
            parts.append(normalize_text(str(value or "")))
    return " ".join(part.lower() for part in parts if part)


def formula_ancestor_identity_text(node: Any, *, max_depth: int = 6) -> str:
    parts: list[str] = []
    current = node
    depth = 0
    while Tag is not None and isinstance(current, Tag) and depth < max_depth:
        parts.append(formula_node_identity_text(current))
        current = current.parent if isinstance(getattr(current, "parent", None), Tag) else None
        depth += 1
    return " ".join(part for part in parts if part)


def is_formula_container(node: Any) -> bool:
    if Tag is None or not isinstance(node, Tag):
        return False
    identity = formula_node_identity_text(node)
    role = normalize_text(str((getattr(node, "attrs", None) or {}).get("role") or "")).lower()
    return role == "math" or any(token in identity for token in FORMULA_CONTAINER_TOKENS)


def is_display_formula_node(node: Any) -> bool:
    if Tag is None or not isinstance(node, Tag):
        return False
    attrs = getattr(node, "attrs", None) or {}
    if normalize_text(str(attrs.get("display") or "")).lower() == "block":
        return True
    identity = formula_ancestor_identity_text(node)
    return any(token in identity for token in ("display-equation", "disp-formula", "display-formula")) or normalize_text(
        str(attrs.get("role") or "")
    ).lower() == "math"


def _candidate_urls(tag: Any) -> list[str]:
    if Tag is None or not isinstance(tag, Tag):
        return []
    urls: list[str] = []
    for attr in FORMULA_IMAGE_ATTRS:
        candidate = normalize_text(str(tag.get(attr) or ""))
        if candidate and not candidate.lower().startswith("urn:"):
            urls.append(candidate)
    for attr in FORMULA_IMAGE_SRCSET_ATTRS:
        raw_srcset = normalize_text(str(tag.get(attr) or ""))
        if raw_srcset:
            candidate = first_url_from_srcset(raw_srcset)
            if candidate:
                urls.append(candidate)
    return urls


def formula_image_url_from_node(node: Any, *, include_adjacent: bool = False) -> str:
    if Tag is None or not isinstance(node, Tag):
        return ""
    tags_to_check: list[Tag] = [node]
    tags_to_check.extend(tag for tag in node.find_all(True) if isinstance(tag, Tag))

    if include_adjacent:
        previous = node.previous_sibling
        while previous is not None:
            if isinstance(previous, Tag):
                tags_to_check.append(previous)
                break
            previous = previous.previous_sibling

        following = node.next_sibling
        while following is not None:
            if isinstance(following, Tag):
                tags_to_check.append(following)
                break
            following = following.next_sibling

    for tag in tags_to_check:
        for candidate in _candidate_urls(tag):
            return candidate
    return ""


def looks_like_formula_image(node: Any, url: str | None = None) -> bool:
    if Tag is None or not isinstance(node, Tag):
        return False
    if normalize_text(node.name or "").lower() != "img":
        return False
    candidate_url = normalize_text(url or formula_image_url_from_node(node))
    if not candidate_url:
        return False
    identity = formula_ancestor_identity_text(node)
    alt_blob = " ".join(
        normalize_text(str(node.get(attr) or "")).lower()
        for attr in ("alt", "title", "aria-label")
    )
    return (
        bool(FORMULA_IMAGE_URL_PATTERN.search(candidate_url))
        or bool(FORMULA_IMAGE_URL_PATTERN.search(alt_blob))
        or any(token in identity for token in FORMULA_CONTAINER_TOKENS)
    )


def formula_heading_for_image(node: Any, index: int) -> str:
    if Tag is None or not isinstance(node, Tag):
        return f"Formula {index}"
    current = node
    depth = 0
    while isinstance(current, Tag) and depth < 6:
        identity = formula_node_identity_text(current)
        candidate_id = normalize_text(str((getattr(current, "attrs", None) or {}).get("id") or ""))
        if candidate_id and any(token in identity for token in FORMULA_CONTAINER_TOKENS):
            return candidate_id
        current = current.parent if isinstance(getattr(current, "parent", None), Tag) else None
        depth += 1
    return f"Formula {index}"


def mathml_element_from_html_node(node: Any) -> ET.Element | None:
    if Tag is None or not isinstance(node, Tag):
        return None
    math_node = node if normalize_text(node.name or "").lower() == "math" else node.find("math")
    if not isinstance(math_node, Tag):
        return None
    raw_mathml = str(math_node)
    try:
        return ET.fromstring(raw_mathml)
    except ET.ParseError:
        try:
            return ET.fromstring(raw_mathml.replace("&nbsp;", " "))
        except ET.ParseError:
            return None


def display_formula_nodes(container: Any) -> list[Any]:
    if Tag is None or not isinstance(container, Tag):
        return []
    nodes: list[Any] = []
    for selector in DISPLAY_FORMULA_SELECTORS:
        try:
            matches = container.select(selector)
        except Exception:
            continue
        nodes.extend(match for match in matches if isinstance(match, Tag))
    return nodes
