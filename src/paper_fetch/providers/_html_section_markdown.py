"""Shared section-aware HTML-to-Markdown helpers."""

from __future__ import annotations

import re
from typing import Any

from ..models import normalize_text
from ._html_citations import is_citation_link, make_numeric_citation_sentinel, numeric_citation_payload
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
FIGURE_LABEL_PATTERN = re.compile(r"^\s*(?:fig(?:ure)?\.?)\s*(\d+[A-Za-z]?)\s*[:.]?\s*(.*)$", flags=re.IGNORECASE)
FIGURE_ID_PATTERN = re.compile(r"(?:^|[-_ ])figure[-_ ]?(\d+[A-Za-z]?)$", flags=re.IGNORECASE)
FIGURE_TRAILING_LINK_PATTERN = re.compile(r"\b(?:PowerPoint slide|Full size image)\b.*$", flags=re.IGNORECASE)
FIGURE_DESCRIPTION_SELECTORS = (
    "figcaption",
    ".c-article-section__figure-description",
    ".figure__caption-text",
)


def _normalize_inline_text(text: str) -> str:
    normalized = text.replace("\xa0", " ")
    normalized = re.sub(r"[ \t\r\f\v]+", " ", normalized)
    normalized = re.sub(r"\s*\n\s*", " ", normalized)
    normalized = re.sub(r"\s*(<br>)\s*", r"\1", normalized)
    normalized = re.sub(r"<(sub|sup)>\s+", r"<\1>", normalized)
    normalized = re.sub(r"\s+</(sub|sup)>", r"</\1>", normalized)
    normalized = re.sub(r"\s+(<(?:sub|sup)>)", r"\1", normalized)
    normalized = re.sub(r"(</sub>)\s+\(", r"\1(", normalized)
    normalized = re.sub(r"(</(?:sub|sup)>)\s+([,.;:%\]\}\+\)])", r"\1\2", normalized)
    return normalized.strip()


def _wrap_inline_text_fragment(text: str, marker: str | None = None) -> str:
    value = text.replace("\xa0", " ")
    has_leading_space = bool(value[:1].isspace())
    has_trailing_space = bool(value[-1:].isspace())
    normalized = re.sub(r"\s+", " ", value).strip()
    if not normalized:
        return ""
    if marker:
        normalized = f"{marker}{normalized}{marker}"
    if has_leading_space:
        normalized = f" {normalized}"
    if has_trailing_space:
        normalized = f"{normalized} "
    return normalized


def _render_heading_inline_fragment(node: Any, *, text_style: str | None = None) -> str:
    if NavigableString is not None and isinstance(node, NavigableString):
        return _wrap_inline_text_fragment(str(node), text_style)
    if not isinstance(node, Tag):
        return ""

    name = normalize_text(node.name or "").lower()
    if name in {"i", "em"}:
        return _render_heading_inline_node(node, text_style="*")
    if name in {"b", "strong"}:
        return _render_heading_inline_node(node, text_style="**")
    if name == "sub":
        text = _render_heading_inline_node(node)
        return f"<sub>{text}</sub>" if text else ""
    if name == "sup":
        text = _render_heading_inline_node(node)
        return f"<sup>{text}</sup>" if text else ""
    if name == "br":
        return "<br>"
    return _render_heading_inline_node(node, text_style=text_style)


def _render_heading_inline_node(node: Any, *, text_style: str | None = None) -> str:
    if node is None:
        return ""
    if NavigableString is not None and isinstance(node, NavigableString):
        return _wrap_inline_text_fragment(str(node), text_style)
    if not isinstance(node, Tag):
        return ""

    parts: list[str] = []
    for child in node.children:
        rendered = _render_heading_inline_fragment(child, text_style=text_style)
        if rendered:
            parts.append(rendered)
    return _normalize_inline_text("".join(parts))


def render_heading_text_from_html(node: Any) -> str:
    return _render_heading_inline_node(node)


def extract_section_title(section: Any) -> str:
    if BeautifulSoup is None or section is None:
        return ""
    heading = section.find(HEADING_TAG_PATTERN)
    if heading is None:
        return ""
    return render_heading_text_from_html(heading)


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


def section_has_direct_renderable_content(
    section: Any,
    *,
    section_content_selectors: tuple[str, ...] = ("div.c-article-section__content",),
) -> bool:
    if BeautifulSoup is None or section is None:
        return False
    content_root = _select_first(section, section_content_selectors) or section
    for child in content_root.children:
        if isinstance(child, NavigableString):
            if normalize_text(str(child)):
                return True
            continue
        if not isinstance(child, Tag):
            continue
        if child.name in {"header", "footer"}:
            continue
        if child.name in HTML_DROP_TAGS or should_drop_html_element(child):
            continue
        if child.name in {"p", "blockquote", "pre", "ul", "ol", "figure", "table"}:
            return True
        if _is_figure_container(child):
            return True
        if child.name in {"div", "article", "main"}:
            if child.find("section", recursive=False) is None and render_clean_text_from_html(child):
                return True
    return False


def render_section_markdown(
    section: Any,
    lines: list[str],
    *,
    level: int,
    force_heading: str | None = None,
    section_content_selectors: tuple[str, ...] = ("div.c-article-section__content",),
) -> None:
    heading = force_heading or extract_section_title(section)
    content_root = _select_first(section, section_content_selectors) or section
    rendered_content: list[str] = []
    render_container_markdown(
        content_root,
        rendered_content,
        level=level + 1,
        skip_first_heading=heading or None,
        section_content_selectors=section_content_selectors,
    )
    if not rendered_content:
        return
    if heading:
        lines.extend([f"{'#' * max(2, min(level, 6))} {heading}", ""])
    lines.extend(rendered_content)


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
            heading_text = render_heading_text_from_html(child)
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
        if _is_figure_container(child):
            render_figure_markdown(child, lines)
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


def _node_attr_text(node: Any) -> str:
    if not isinstance(node, Tag):
        return ""
    attrs = getattr(node, "attrs", None) or {}
    parts = [normalize_text(node.name or "")]
    for key in ("id", "class", "data-test", "data-container-section"):
        value = attrs.get(key)
        if isinstance(value, (list, tuple, set)):
            parts.extend(normalize_text(str(item)) for item in value)
        else:
            parts.append(normalize_text(str(value or "")))
    return " ".join(part.lower() for part in parts if part)


def _is_figure_container(node: Any) -> bool:
    if not isinstance(node, Tag):
        return False
    if node.name == "figure":
        return True
    identity = _node_attr_text(node)
    if "figure" not in identity:
        return False
    return node.find("figure") is not None or node.find("img") is not None or node.find("figcaption") is not None


def _clean_figure_text_candidate(text: str) -> str:
    normalized = normalize_text(text.replace("\n", " "))
    if not normalized:
        return ""
    normalized = FIGURE_TRAILING_LINK_PATTERN.sub("", normalized).strip()
    return normalize_text(normalized)


def _figure_label_from_text(text: str) -> tuple[str, str]:
    normalized = _clean_figure_text_candidate(text)
    match = FIGURE_LABEL_PATTERN.match(normalized)
    if match is None:
        return "", normalized
    return f"Figure {match.group(1)}.", normalize_text(match.group(2))


def _figure_label_from_node(node: Any) -> str:
    current = node
    while isinstance(current, Tag):
        identity = _node_attr_text(current)
        match = FIGURE_ID_PATTERN.search(identity)
        if match is not None:
            return f"Figure {match.group(1)}."
        current = current.parent if isinstance(getattr(current, "parent", None), Tag) else None
    return ""


def _iter_figure_text_candidates(node: Any) -> list[str]:
    if not isinstance(node, Tag):
        return []
    caption_candidates: list[str] = []
    description_candidates: list[str] = []
    for selector in FIGURE_DESCRIPTION_SELECTORS:
        for match in node.select(selector):
            if not isinstance(match, Tag):
                continue
            text = render_clean_text_from_html(match)
            if not text:
                continue
            if selector == ".c-article-section__figure-description":
                if text not in description_candidates:
                    description_candidates.append(text)
                continue
            if text not in caption_candidates:
                caption_candidates.append(text)
    if caption_candidates:
        return caption_candidates + [text for text in description_candidates if text not in caption_candidates]
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


def render_figure_markdown(node: Any, lines: list[str]) -> None:
    if not isinstance(node, Tag):
        return

    figure_label = ""
    figure_parts: list[str] = []
    for text in _iter_figure_text_candidates(node):
        label, remainder = _figure_label_from_text(text)
        if label and not figure_label:
            figure_label = label
        candidate = _clean_figure_text_candidate(remainder if label else text)
        if candidate and candidate not in figure_parts:
            figure_parts.append(candidate)
    if not figure_label:
        figure_label = _figure_label_from_node(node)
    if not figure_label and not figure_parts:
        return

    if figure_label:
        line = f"**{figure_label}**"
        if figure_parts:
            line = f"{line} {' '.join(figure_parts)}"
    else:
        line = " ".join(figure_parts)
    lines.extend([line, ""])


def _has_explicit_citation_marker(node: Any) -> bool:
    if not isinstance(node, Tag):
        return False
    attrs = getattr(node, "attrs", None) or {}
    if "citation-ref" in attrs:
        return True
    if normalize_text(str(attrs.get("data-test") or "")).lower() == "citation-ref":
        return True
    if normalize_text(str(attrs.get("role") or "")).lower() == "doc-biblioref":
        return True
    if normalize_text(str(attrs.get("data-xml-rid") or "")):
        return True
    return False


def _numeric_citation_payload_from_html(node: Any) -> str | None:
    if not isinstance(node, Tag):
        return None
    text = normalize_text(node.get_text("", strip=True))
    payload = numeric_citation_payload(text)
    if payload is None:
        return None
    href = normalize_text(str(node.get("href") or ""))
    if node.name == "a" and (_has_explicit_citation_marker(node) or is_citation_link(href, text)):
        return payload
    if node.name == "sup":
        anchors = [match for match in node.find_all("a") if isinstance(match, Tag)]
        if anchors and all(_numeric_citation_payload_from_html(anchor) for anchor in anchors):
            return payload
    return None


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
        payload = _numeric_citation_payload_from_html(node)
        if payload is not None:
            return make_numeric_citation_sentinel(payload) or ""
        text = render_clean_children(node)
        return text
    if node.name == "sup":
        payload = _numeric_citation_payload_from_html(node)
        if payload is not None:
            return make_numeric_citation_sentinel(payload) or ""
        text = render_clean_children(node)
        return f"<sup>{text}</sup>" if text else ""
    if node.name == "sub":
        text = render_clean_children(node)
        return f"<sub>{text}</sub>" if text else ""
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
