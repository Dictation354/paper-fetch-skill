"""Shared HTML formula discovery rules."""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from typing import Any

from .asset_fields import (
    FULL_SIZE_IMAGE_ATTRS,
    PREVIEW_IMAGE_ATTRS,
    best_url_from_srcset,
)
from ...utils import normalize_text
from ...xml_security import XmlParseFailure, parse_mathml_fragment
from .provider_rules import (
    provider_display_formula_selectors,
    provider_formula_container_tokens,
)

from bs4 import Tag

FORMULA_IMAGE_URL_PATTERN = re.compile(
    r"(?:^|[-_/])(?:math|ieq|equ)[-_]?\d|_(?:IEq|Equ)\d|math-\d|equation",
    flags=re.IGNORECASE,
)
EXPLICIT_FORMULA_IMAGE_URL_PATTERN = re.compile(
    r"(?:^|[-_/])(?:math|ieq|equ)[-_]?\d|_(?:IEq|Equ)\d|math-\d",
    flags=re.IGNORECASE,
)
GENERIC_FORMULA_CONTAINER_TOKENS = (
    "inline-equation",
    "inline-eqn",
    "display-equation",
    "display-eqn",
    "disp-formula",
    "display-formula",
)
FORMULA_IMAGE_ATTRS = (
    "data-altimg",
    "data-alt-image",
    *FULL_SIZE_IMAGE_ATTRS,
    *PREVIEW_IMAGE_ATTRS,
    "location",
)
FORMULA_IMAGE_SRCSET_ATTRS = ("srcset", "data-srcset")
GENERIC_DISPLAY_FORMULA_SELECTORS = (
    *(
        f".{token}"
        for token in GENERIC_FORMULA_CONTAINER_TOKENS
        if token != "inline-eqn"
    ),
    "math[display='block']",
    "div[role='math']",
)
GENERIC_DISPLAY_FORMULA_IDENTITY_TOKENS = tuple(
    token for token in GENERIC_FORMULA_CONTAINER_TOKENS if token != "inline-eqn"
)
MATHML_SCRIPT_TYPES = frozenset(
    {
        "math/mml",
        "application/mathml+xml",
        "text/mml",
    }
)
TEX_SCRIPT_TYPES = frozenset(
    {
        "math/tex",
        "math/tex; mode=display",
        "text/tex",
        "application/x-tex",
    }
)
FORMULA_SCRIPT_TYPES = MATHML_SCRIPT_TYPES | TEX_SCRIPT_TYPES
SILVERCHAIR_FIGURE_CLASS_TOKENS = frozenset(
    {
        "fig",
        "fig-section",
        "js-fig-section",
        "graphic-wrap",
    }
)


def display_formula_identity_tokens_for_profile(
    noise_profile: str | None,
) -> tuple[str, ...]:
    return (
        *GENERIC_DISPLAY_FORMULA_IDENTITY_TOKENS,
        *(provider_formula_container_tokens(noise_profile) if noise_profile else ()),
    )


def formula_container_tokens_for_profile(noise_profile: str | None) -> tuple[str, ...]:
    return (
        *GENERIC_FORMULA_CONTAINER_TOKENS,
        *(provider_formula_container_tokens(noise_profile) if noise_profile else ()),
    )


def display_formula_selectors_for_profile(noise_profile: str | None) -> tuple[str, ...]:
    return (
        *GENERIC_DISPLAY_FORMULA_SELECTORS,
        *(provider_display_formula_selectors(noise_profile) if noise_profile else ()),
    )


def normalize_formula_script_type(value: Any) -> str:
    normalized = normalize_text(str(value or "")).lower()
    return re.sub(r"\s*;\s*", "; ", normalized)


def is_formula_script_node(node: Any) -> bool:
    return (
        isinstance(node, Tag)
        and normalize_text(node.name or "").lower() == "script"
        and normalize_formula_script_type(node.get("type")) in FORMULA_SCRIPT_TYPES
    )


def is_tex_formula_script_node(node: Any) -> bool:
    return (
        isinstance(node, Tag)
        and normalize_text(node.name or "").lower() == "script"
        and normalize_formula_script_type(node.get("type")) in TEX_SCRIPT_TYPES
    )


def formula_node_identity_text(node: Any) -> str:
    if not isinstance(node, Tag):
        return ""
    attrs = getattr(node, "attrs", None) or {}
    parts = [normalize_text(str(node.name or ""))]
    for key in (
        "id",
        "class",
        "role",
        "data-test",
        "data-type",
        "data-container-section",
    ):
        value = attrs.get(key)
        if isinstance(value, (list, tuple, set)):
            parts.extend(normalize_text(str(item)) for item in value)
        else:
            parts.append(normalize_text(str(value or "")))
    return " ".join(part.lower() for part in parts if part)


def formula_ancestor_identity_text(node: Any, *, max_depth: int = 6) -> str:
    parts: list[str] = []
    current: Any = node
    depth = 0
    while isinstance(current, Tag) and depth < max_depth:
        parts.append(formula_node_identity_text(current))
        current = (
            current.parent
            if isinstance(getattr(current, "parent", None), Tag)
            else None
        )
        depth += 1
    return " ".join(part for part in parts if part)


def _class_tokens(node: Any) -> set[str]:
    if not isinstance(node, Tag):
        return set()
    raw_classes = (getattr(node, "attrs", None) or {}).get("class") or []
    if isinstance(raw_classes, str):
        return {
            normalize_text(value).lower()
            for value in raw_classes.split()
            if normalize_text(value)
        }
    return {
        normalize_text(str(value)).lower()
        for value in raw_classes
        if normalize_text(str(value))
    }


def _has_formula_container_identity(
    node: Any, *, noise_profile: str | None = None, max_depth: int = 6
) -> bool:
    identity = formula_ancestor_identity_text(node, max_depth=max_depth)
    return any(
        token in identity
        for token in formula_container_tokens_for_profile(noise_profile)
    )


def _silverchair_content_id_looks_like_figure(node: Any) -> bool:
    if not isinstance(node, Tag):
        return False
    for key in ("data-content-id", "data-id", "content-id", "id"):
        value = normalize_text(str(node.get(key) or "")).lower()
        if "-f" in value:
            return True
    return False


def html_node_is_figure_asset_context(
    node: Any,
    *,
    noise_profile: str | None = None,
    max_depth: int = 8,
) -> bool:
    if not isinstance(node, Tag):
        return False
    if _has_formula_container_identity(
        node, noise_profile=noise_profile, max_depth=max_depth
    ):
        return False

    current: Any = node
    depth = 0
    while isinstance(current, Tag) and depth < max_depth:
        if normalize_text(current.name or "").lower() == "figure":
            return True
        classes = _class_tokens(current)
        if {"fig", "fig-section"} <= classes or "js-fig-section" in classes:
            return True
        if _silverchair_content_id_looks_like_figure(current):
            return True
        if "graphic-wrap" in classes and (
            current.select_one(".fig-label, .fig-caption, .caption") is not None
            or _silverchair_content_id_looks_like_figure(current.parent)
        ):
            return True
        current = (
            current.parent
            if isinstance(getattr(current, "parent", None), Tag)
            else None
        )
        depth += 1
    return False


def is_formula_container(node: Any, *, noise_profile: str | None = None) -> bool:
    if not isinstance(node, Tag):
        return False
    identity = formula_node_identity_text(node)
    role = normalize_text(
        str((getattr(node, "attrs", None) or {}).get("role") or "")
    ).lower()
    return role == "math" or any(
        token in identity
        for token in formula_container_tokens_for_profile(noise_profile)
    )


def is_display_formula_node(node: Any, *, noise_profile: str | None = None) -> bool:
    if not isinstance(node, Tag):
        return False
    attrs = getattr(node, "attrs", None) or {}
    if normalize_text(str(attrs.get("display") or "")).lower() == "block":
        return True
    identity = formula_ancestor_identity_text(node)
    return (
        any(
            token in identity
            for token in display_formula_identity_tokens_for_profile(noise_profile)
        )
        or normalize_text(str(attrs.get("role") or "")).lower() == "math"
    )


def _candidate_urls(tag: Any) -> list[str]:
    if not isinstance(tag, Tag):
        return []
    urls: list[str] = []
    for attr in FORMULA_IMAGE_ATTRS:
        candidate = normalize_text(str(tag.get(attr) or ""))
        if candidate and not candidate.lower().startswith("urn:"):
            urls.append(candidate)
    for attr in FORMULA_IMAGE_SRCSET_ATTRS:
        raw_srcset = normalize_text(str(tag.get(attr) or ""))
        if raw_srcset:
            candidate = best_url_from_srcset(raw_srcset)
            if candidate:
                urls.append(candidate)
    return urls


def formula_image_url_from_node(node: Any, *, include_adjacent: bool = False) -> str:
    if not isinstance(node, Tag):
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


def looks_like_formula_image(
    node: Any, url: str | None = None, *, noise_profile: str | None = None
) -> bool:
    if not isinstance(node, Tag):
        return False
    if normalize_text(node.name or "").lower() != "img":
        return False
    candidate_url = normalize_text(url or formula_image_url_from_node(node))
    if not candidate_url:
        return False
    if html_node_is_figure_asset_context(node, noise_profile=noise_profile):
        return bool(EXPLICIT_FORMULA_IMAGE_URL_PATTERN.search(candidate_url))
    if FORMULA_IMAGE_URL_PATTERN.search(candidate_url):
        return True
    identity = formula_ancestor_identity_text(node)
    alt_blob = " ".join(
        normalize_text(str(node.get(attr) or "")).lower()
        for attr in ("alt", "title", "aria-label")
    )
    return bool(FORMULA_IMAGE_URL_PATTERN.search(alt_blob)) or any(
        token in identity
        for token in formula_container_tokens_for_profile(noise_profile)
    )


def formula_heading_for_image(
    node: Any, index: int, *, noise_profile: str | None = None
) -> str:
    if not isinstance(node, Tag):
        return f"Formula {index}"
    current: Any = node
    depth = 0
    while isinstance(current, Tag) and depth < 6:
        identity = formula_node_identity_text(current)
        candidate_id = normalize_text(
            str((getattr(current, "attrs", None) or {}).get("id") or "")
        )
        if candidate_id and any(
            token in identity
            for token in formula_container_tokens_for_profile(noise_profile)
        ):
            return candidate_id
        current = (
            current.parent
            if isinstance(getattr(current, "parent", None), Tag)
            else None
        )
        depth += 1
    return f"Formula {index}"


def mathml_element_from_html_node(node: Any) -> ET.Element | None:
    if not isinstance(node, Tag):
        return None
    math_node = (
        node if normalize_text(node.name or "").lower() == "math" else node.find("math")
    )
    if isinstance(math_node, Tag):
        parsed = _parse_mathml(str(math_node))
        if parsed is not None:
            return parsed
    for script in node.find_all("script"):
        if not isinstance(script, Tag):
            continue
        script_type = normalize_formula_script_type(script.get("type"))
        if script_type not in MATHML_SCRIPT_TYPES:
            continue
        raw_mathml = (
            script.string if script.string is not None else script.decode_contents()
        )
        parsed = _parse_mathml(str(raw_mathml or ""))
        if parsed is not None:
            return parsed
    return None


def _parse_mathml(raw_mathml: str) -> ET.Element | None:
    raw_mathml = raw_mathml.strip()
    if not raw_mathml:
        return None
    for candidate in (raw_mathml, raw_mathml.replace("&nbsp;", " ")):
        try:
            return parse_mathml_fragment(candidate)
        except XmlParseFailure:
            continue
    return None


def display_formula_nodes(
    container: Any, *, noise_profile: str | None = None
) -> list[Any]:
    if not isinstance(container, Tag):
        return []
    nodes: list[Any] = []
    for selector in display_formula_selectors_for_profile(noise_profile):
        try:
            matches = container.select(selector)
        except Exception:
            continue
        nodes.extend(match for match in matches if isinstance(match, Tag))
    return nodes
