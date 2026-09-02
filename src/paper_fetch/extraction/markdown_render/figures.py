"""Figure rendering helpers."""

from __future__ import annotations

from collections.abc import Callable, Mapping
import re
from typing import Any

from ...common_patterns import FIGURE_LABEL_CORE_PATTERN
from ...extraction.html.ui_tokens import (
    FIGURE_FULL_SIZE_IMAGE_LABEL,
    FIGURE_POWERPOINT_SLIDE_LABEL,
)
from ..html.shared import class_tokens as _html_class_tokens
from ...markdown.images import render_markdown_image
from ...utils import normalize_text
from ._ir import MarkdownFigure

from bs4 import Tag

FIGURE_LABEL_PATTERN = re.compile(
    rf"^\s*{FIGURE_LABEL_CORE_PATTERN}\s*[:.]?\s*(.*)$",
    flags=re.IGNORECASE,
)
FIGURE_ID_PATTERN = re.compile(
    r"(?:^|[-_ ])figure[-_ ]?(\d+[A-Za-z]?)$", flags=re.IGNORECASE
)
SILVERCHAIR_FIGURE_ID_PATTERN = re.compile(
    r"(?:^|[-_])f(\d+[A-Za-z]?)(?:$|[-_ ])",
    flags=re.IGNORECASE,
)
SILVERCHAIR_FIGURE_BASENAME_PATTERN = re.compile(
    r"(?:^|[-_/])(?:m_)?[A-Za-z0-9]+f(\d+[A-Za-z]?)\.(?:jpe?g|png|gif|webp|tiff?|svg)(?:[?#]|$)",
    flags=re.IGNORECASE,
)
FIGURE_ACTION_TRAILING_LINK_PATTERN = re.compile(
    rf"\b(?:{re.escape(FIGURE_POWERPOINT_SLIDE_LABEL)}|{re.escape(FIGURE_FULL_SIZE_IMAGE_LABEL)})\b.*$",
    flags=re.IGNORECASE,
)
FIGURE_DESCRIPTION_SELECTORS = (
    "figcaption",
    ".c-article-section__figure-description",
    ".figure__caption-text",
    ".fig-caption",
    ".caption",
)
INLINE_FIGURE_SRC_ATTR = "data-paper-fetch-inline-src"
INLINE_FIGURE_ALT_ATTR = "data-paper-fetch-inline-alt"
FIGURE_IMAGE_SRC_ATTRS = (
    INLINE_FIGURE_SRC_ATTR,
    "data-lg-src",
    "data-full-src",
    "data-src",
    "data-lazy-src",
    "src",
)
FIGURE_IMAGE_ALT_ATTRS = (
    INLINE_FIGURE_ALT_ATTR,
    "alt",
    "title",
    "aria-label",
)


def render_figure(figure: MarkdownFigure) -> list[str]:
    alt = normalize_text(figure.alt or figure.label or "Figure") or "Figure"
    lines = [render_markdown_image("figure", alt, figure.asset_url), ""]
    caption = normalize_text(figure.caption)
    if caption:
        lines.extend([caption, ""])
    return lines


def figure_from_entry(entry: Mapping[str, str]) -> MarkdownFigure:
    heading = normalize_text(str(entry.get("heading") or "Figure")) or "Figure"
    return MarkdownFigure(
        label=heading,
        caption=normalize_text(str(entry.get("caption") or "")),
        asset_url=normalize_text(str(entry.get("link") or "")),
        alt=heading,
    )


def render_figure_block(entry: Mapping[str, str]) -> list[str]:
    return render_figure(figure_from_entry(entry))


def add_figure_once(
    lines: list[str], entry: Mapping[str, str] | None, used_figure_keys: set[str]
) -> None:
    if not entry:
        return
    key = entry["key"]
    if key in used_figure_keys:
        return
    used_figure_keys.add(key)
    lines.extend(render_figure_block(entry))


def html_node_attr_text(node: Any) -> str:
    if not isinstance(node, Tag):
        return ""
    attrs = getattr(node, "attrs", None) or {}
    parts = [normalize_text(node.name or "")]
    for key in (
        "id",
        "class",
        "data-test",
        "data-container-section",
        "data-content-id",
        "data-id",
    ):
        value = attrs.get(key)
        if isinstance(value, (list, tuple, set)):
            parts.extend(normalize_text(str(item)) for item in value)
        else:
            parts.append(normalize_text(str(value or "")))
    return " ".join(part.lower() for part in parts if part)


def _is_silverchair_figure_section(node: Any) -> bool:
    classes = _html_class_tokens(node)
    return {"fig", "fig-section"} <= classes or "js-fig-section" in classes


def _has_silverchair_figure_content(node: Any) -> bool:
    return isinstance(node, Tag) and (
        node.find("img") is not None
        or node.select_one(".fig-label, .fig-caption, .caption") is not None
    )


def _has_silverchair_figure_section_ancestor(node: Any, *, max_depth: int = 4) -> bool:
    current = node.parent if isinstance(getattr(node, "parent", None), Tag) else None
    depth = 0
    while isinstance(current, Tag) and depth < max_depth:
        if _is_silverchair_figure_section(current):
            return True
        current = (
            current.parent
            if isinstance(getattr(current, "parent", None), Tag)
            else None
        )
        depth += 1
    return False


def _is_explicit_generic_figure_container(node: Any) -> bool:
    if not isinstance(node, Tag):
        return False
    classes = _html_class_tokens(node)
    return "figure" in classes and (
        node.find("img") is not None
        or node.find("picture") is not None
        or node.select_one("figcaption, .figcaption, .figure__caption-text") is not None
    )


def is_html_figure_container(node: Any) -> bool:
    if not isinstance(node, Tag):
        return False
    node_name = normalize_text(node.name or "").lower()
    if node_name == "figure":
        return True
    if _is_explicit_generic_figure_container(node):
        return True
    if _is_silverchair_figure_section(node):
        return _has_silverchair_figure_content(node)
    classes = _html_class_tokens(node)
    if "graphic-wrap" in classes and _has_silverchair_figure_section_ancestor(node):
        return node.find("img") is not None
    return False


def clean_html_figure_text_candidate(text: str) -> str:
    normalized = normalize_text(text.replace("\n", " "))
    if not normalized:
        return ""
    normalized = FIGURE_ACTION_TRAILING_LINK_PATTERN.sub("", normalized).strip()
    return normalize_text(normalized)


def html_figure_label_from_text(text: str) -> tuple[str, str]:
    normalized = clean_html_figure_text_candidate(text)
    match = FIGURE_LABEL_PATTERN.match(normalized)
    if match is None:
        return "", normalized
    return f"Figure {match.group(1)}.", normalize_text(match.group(2))


def html_figure_label_from_node(node: Any) -> str:
    if not isinstance(node, Tag):
        return ""
    label_node = node.select_one(".fig-label, .figcaption .title, .label.title-label")
    if isinstance(label_node, Tag):
        label = normalize_text(label_node.get_text(" ", strip=True))
        if label:
            return label
    current: Tag | None = node
    while isinstance(current, Tag):
        identity = html_node_attr_text(current)
        match = FIGURE_ID_PATTERN.search(identity)
        if match is not None:
            return f"Figure {match.group(1)}."
        match = SILVERCHAIR_FIGURE_ID_PATTERN.search(identity)
        if match is not None:
            return f"Figure {match.group(1)}."
        current = (
            current.parent
            if isinstance(getattr(current, "parent", None), Tag)
            else None
        )
    image = node.find("img")
    if isinstance(image, Tag):
        for attr in FIGURE_IMAGE_SRC_ATTRS:
            src = normalize_text(str(image.get(attr) or ""))
            match = SILVERCHAIR_FIGURE_BASENAME_PATTERN.search(src)
            if match is not None:
                return f"Figure {match.group(1)}."
    return ""


def iter_html_figure_text_candidates(
    node: Any, *, render_clean_text: Callable[[Any], str]
) -> list[str]:
    if not isinstance(node, Tag):
        return []
    caption_candidates: list[str] = []
    description_candidates: list[str] = []
    for selector in FIGURE_DESCRIPTION_SELECTORS:
        for match in node.select(selector):
            if not isinstance(match, Tag):
                continue
            text = render_clean_text(match)
            if not text:
                continue
            if selector == ".c-article-section__figure-description":
                if text not in description_candidates:
                    description_candidates.append(text)
                continue
            if text not in caption_candidates:
                caption_candidates.append(text)
    if caption_candidates:
        return caption_candidates + [
            text for text in description_candidates if text not in caption_candidates
        ]
    if description_candidates:
        return description_candidates

    candidates: list[str] = []
    data_title = normalize_text(str(node.get("data-title") or ""))
    if data_title and data_title not in candidates:
        candidates.append(data_title)
    if candidates:
        return candidates
    image = node.find("img")
    if isinstance(image, Tag):
        alt_text = normalize_text(str(image.get("alt") or ""))
        if alt_text and alt_text not in candidates:
            candidates.append(alt_text)
    return candidates


def iter_inline_html_figure_images(node: Any) -> list[tuple[str, str]]:
    if not isinstance(node, Tag):
        return []

    images: list[tuple[str, str]] = []
    seen: set[tuple[str, str]] = set()

    def add_image(candidate: Any) -> None:
        if not isinstance(candidate, Tag):
            return
        src = ""
        for attr in FIGURE_IMAGE_SRC_ATTRS:
            src = normalize_text(str(candidate.get(attr) or ""))
            if src:
                break
        if not src:
            return
        alt = ""
        for attr in FIGURE_IMAGE_ALT_ATTRS:
            alt = normalize_text(str(candidate.get(attr) or ""))
            if alt:
                break
        alt = alt or "Figure"
        item = (src, alt)
        if item in seen:
            return
        seen.add(item)
        images.append(item)

    add_image(node)
    for image in node.find_all("img"):
        add_image(image)
    return images


def append_inline_html_figure_image(lines: list[str], src: str, alt: str) -> None:
    lines.extend([render_markdown_image("figure", alt or "Figure", src), ""])


def render_html_figure_markdown(
    node: Any, lines: list[str], *, render_clean_text: Callable[[Any], str]
) -> None:
    if not isinstance(node, Tag):
        return

    inline_images = iter_inline_html_figure_images(node)
    figure_items: list[tuple[str, str]] = []
    for text in iter_html_figure_text_candidates(
        node, render_clean_text=render_clean_text
    ):
        label, remainder = html_figure_label_from_text(text)
        candidate = clean_html_figure_text_candidate(remainder if label else text)
        item = (label, candidate)
        if (label or candidate) and item not in figure_items:
            figure_items.append(item)

    fallback_label = html_figure_label_from_node(node)
    if not figure_items and fallback_label:
        figure_items.append((fallback_label, ""))
    if not figure_items:
        for src, alt in inline_images:
            append_inline_html_figure_image(lines, src, alt)
        return

    if (
        inline_images
        and len(inline_images) == len(figure_items)
        and len(inline_images) > 1
    ):
        for index, (label, caption) in enumerate(figure_items):
            src, alt = inline_images[index]
            active_label = label or (fallback_label if index == 0 else "")
            append_inline_html_figure_image(lines, src, active_label or alt)
            line = f"**{active_label}** {caption}".strip() if active_label else caption
            if line:
                lines.extend([line, ""])
        return

    for index, (src, alt) in enumerate(inline_images):
        figure_item_label = figure_items[index][0] if index < len(figure_items) else ""
        append_inline_html_figure_image(
            lines, src, figure_item_label or fallback_label or alt
        )

    for index, (label, caption) in enumerate(figure_items):
        active_label = label or (fallback_label if index == 0 else "")
        line = f"**{active_label}** {caption}".strip() if active_label else caption
        if line:
            lines.extend([line, ""])
