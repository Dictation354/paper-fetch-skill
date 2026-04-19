"""Shared section-aware HTML-to-Markdown helpers."""

from __future__ import annotations

import re
from typing import Any

from ..models import normalize_text
from ._html_citations import is_citation_link, is_citation_text
from .html_noise import HTML_BLOCK_TAGS, HTML_DROP_TAGS, should_drop_html_element

try:
    from bs4 import BeautifulSoup, NavigableString, Tag
except ImportError:  # pragma: no cover - exercised implicitly when dependency is absent
    BeautifulSoup = None
    NavigableString = None
    Tag = None

HEADING_TAG_PATTERN = re.compile(r"^h[1-6]$")
HTML_TIGHT_INLINE_TAGS = {"sub", "sup"}
HTML_NO_SPACE_AFTER_CHARS = set("([{/+-–—−")
HTML_NO_SPACE_BEFORE_CHARS = set(")]},.;:!?%/+-–—−")


def extract_section_title(section: Any) -> str:
    if BeautifulSoup is None or section is None:
        return ""
    heading = section.find(HEADING_TAG_PATTERN)
    if heading is None:
        return ""
    return normalize_text(heading.get_text(" ", strip=True))


def normalize_section_title(title: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", title.lower()).strip()


def _select_first(node: Any, selectors: tuple[str, ...]) -> Any:
    if BeautifulSoup is None or node is None:
        return None
    for selector in selectors:
        match = node.select_one(selector)
        if match is not None:
            return match
    return None


def render_section_markdown(
    section: Any,
    lines: list[str],
    *,
    level: int,
    force_heading: str | None = None,
    section_content_selectors: tuple[str, ...] = ("div.c-article-section__content",),
) -> None:
    heading = force_heading or extract_section_title(section)
    if heading:
        lines.extend([f"{'#' * max(2, min(level, 6))} {heading}", ""])
    content_root = _select_first(section, section_content_selectors) or section
    render_container_markdown(
        content_root,
        lines,
        level=level + 1,
        skip_first_heading=heading or None,
        section_content_selectors=section_content_selectors,
    )


def render_container_markdown(
    node: Any,
    lines: list[str],
    *,
    level: int,
    skip_first_heading: str | None = None,
    section_content_selectors: tuple[str, ...] = ("div.c-article-section__content",),
) -> None:
    if BeautifulSoup is None or node is None:
        return

    skipped_heading = False
    for child in node.children:
        if isinstance(child, NavigableString):
            text = normalize_text(str(child))
            if text:
                lines.extend([text, ""])
            continue
        if not isinstance(child, Tag):
            continue
        if child.name in {"header", "footer"}:
            continue
        if child.name in HTML_DROP_TAGS or should_drop_html_element(child):
            continue
        if child.name == "section":
            render_section_markdown(
                child,
                lines,
                level=level,
                section_content_selectors=section_content_selectors,
            )
            continue
        if child.name and HEADING_TAG_PATTERN.match(child.name):
            heading_text = render_clean_text_from_html(child)
            if (
                skip_first_heading
                and not skipped_heading
                and normalize_section_title(heading_text) == normalize_section_title(skip_first_heading)
            ):
                skipped_heading = True
                continue
            skipped_heading = True
            if heading_text:
                lines.extend([f"{'#' * max(2, min(level, 6))} {heading_text}", ""])
            continue
        if child.name in {"p", "blockquote", "pre"}:
            text = render_clean_text_from_html(child)
            if text:
                lines.extend([text, ""])
            continue
        if child.name in {"ul", "ol"}:
            for item in child.find_all("li", recursive=False):
                text = render_clean_text_from_html(item)
                if text:
                    lines.append(f"- {text}")
            if lines and lines[-1]:
                lines.append("")
            continue
        if child.name == "figure":
            continue
        if child.name == "table":
            text = render_clean_text_from_html(child)
            if text:
                lines.extend([text, ""])
            continue
        if child.name in {"div", "article", "main"}:
            next_skip = skip_first_heading if not skipped_heading else None
            render_container_markdown(
                child,
                lines,
                level=level,
                skip_first_heading=next_skip,
                section_content_selectors=section_content_selectors,
            )
            continue
        text = render_clean_text_from_html(child)
        if text:
            lines.extend([text, ""])


def render_clean_text_from_html(node: Any) -> str:
    rendered = render_clean_html_node(node)
    rendered = re.sub(r"[ \t\r\f\v]+", " ", rendered)
    rendered = re.sub(r" *\n *", "\n", rendered)
    rendered = re.sub(r"\n{3,}", "\n\n", rendered)
    return normalize_text(rendered)


def render_clean_html_node(node: Any) -> str:
    if node is None:
        return ""
    if isinstance(node, NavigableString):
        return str(node)
    if not isinstance(node, Tag):
        return ""
    if node.name in HTML_DROP_TAGS:
        return ""
    if node.name == "br":
        return "\n"
    if node.name == "a":
        text = render_clean_children(node)
        href = str(node.get("href") or "")
        if is_citation_link(href, text):
            return ""
        return text
    if node.name == "sup":
        text = render_clean_children(node)
        if is_citation_text(text):
            return ""
        return text
    if node.name == "sub":
        return render_clean_children(node)
    if node.name == "figure":
        caption = node.find("figcaption")
        return render_clean_html_node(caption)

    rendered = render_clean_children(node)
    if not rendered.strip():
        return ""
    if node.name in {"li"}:
        return f"\n\n{rendered}\n\n"
    if node.name in HTML_BLOCK_TAGS:
        return f"\n\n{rendered}\n\n"
    return rendered


def render_clean_children(node: Any) -> str:
    text = ""
    previous_child: Any = None
    for child in node.children:
        rendered = render_clean_html_node(child)
        if not rendered:
            continue
        if needs_space_between(text, rendered, previous_child, child):
            text += " "
        text += rendered
        previous_child = child
    return text


def needs_space_between(left: str, right: str, previous_child: Any, child: Any) -> bool:
    if not left or not right:
        return False
    if left[-1].isspace() or right[0].isspace():
        return False
    if is_tight_inline_node(previous_child) or is_tight_inline_node(child):
        return False

    left_char = last_significant_char(left)
    right_char = first_significant_char(right)
    if not left_char or not right_char:
        return False
    if left_char in HTML_NO_SPACE_AFTER_CHARS:
        return False
    if right_char in HTML_NO_SPACE_BEFORE_CHARS:
        return False
    return left_char.isalnum() and right_char.isalnum()


def is_tight_inline_node(node: Any) -> bool:
    return isinstance(node, Tag) and node.name in HTML_TIGHT_INLINE_TAGS


def last_significant_char(text: str) -> str:
    for char in reversed(text):
        if not char.isspace():
            return char
    return ""


def first_significant_char(text: str) -> str:
    for char in text:
        if not char.isspace():
            return char
    return ""
