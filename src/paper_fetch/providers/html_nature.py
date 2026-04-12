"""Nature-specific HTML extraction helpers."""

from __future__ import annotations

import re
import urllib.parse
from typing import Any

from ..models import normalize_text
from .html_noise import HTML_BLOCK_TAGS, HTML_DROP_TAGS, clean_markdown, count_words, should_drop_html_element

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
NATURE_FIGURE_LINE_PATTERN = re.compile(r"(?im)^(?:extended data\s+)?fig\.\s*[a-z0-9.-]+:.*$")
NATURE_REFERENCE_RANGE_PATTERN = re.compile(r"(?<=[A-Za-z)])\^?\s*\d+\s*[–-]\s*\d+(?=[.,;:]?(?:\s|$))")
NATURE_REFERENCE_LIST_PATTERN = re.compile(r"(?<=[A-Za-z)])\^?\s*\d+(?:\s*,\s*\d+){1,}(?=[.,;:]?(?:\s|$))")


def select_nature_article_root(root: Any):
    if BeautifulSoup is None:
        return None

    best_article = None
    best_words = 0
    candidates = []
    if isinstance(root, Tag) and getattr(root, "name", None) == "article":
        candidates.append(root)
    candidates.extend(root.select("article"))
    for article in candidates:
        main = article.select_one("div.c-article-body div.main-content")
        if main is None:
            continue
        words = count_words(normalize_text(main.get_text(" ", strip=True)))
        if words > best_words:
            best_article = article
            best_words = words
    return best_article


def is_nature_like_url(url: str) -> bool:
    hostname = urllib.parse.urlparse(url).netloc.lower()
    return hostname.endswith("nature.com") or hostname.endswith(".nature.com")


def select_nature_abstract_section(body: Any):
    if BeautifulSoup is None or body is None:
        return None
    for section in body.find_all("section", recursive=False):
        if normalize_section_title(extract_section_title(section)) == "abstract":
            return section
    return None


def extract_section_title(section: Any) -> str:
    if BeautifulSoup is None or section is None:
        return ""
    heading = section.find(HEADING_TAG_PATTERN)
    if heading is None:
        return ""
    return normalize_text(heading.get_text(" ", strip=True))


def normalize_section_title(title: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", title.lower()).strip()


def clean_nature_text_fragment(text: str) -> str:
    cleaned = normalize_text(text)
    if not cleaned:
        return ""
    cleaned = NATURE_REFERENCE_RANGE_PATTERN.sub("", cleaned)
    cleaned = NATURE_REFERENCE_LIST_PATTERN.sub("", cleaned)
    cleaned = re.sub(r"\((?:ref|refs)\.\)", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s+([,.;:!?])", r"\1", cleaned)
    cleaned = re.sub(r"([(\[])\s+", r"\1", cleaned)
    cleaned = re.sub(r"\s+([)\]])", r"\1", cleaned)
    return normalize_text(cleaned)


def extract_nature_markdown(html_text: str, source_url: str) -> str:
    if BeautifulSoup is None:
        return ""

    soup = BeautifulSoup(html_text, "html.parser")
    article = select_nature_article_root(soup) or soup.select_one("article")
    if article is None:
        return ""

    body = article.select_one("div.c-article-body") or article
    main = body.select_one("div.main-content") or body
    lines: list[str] = []

    title_node = article.select_one("h1")
    title_text = render_clean_text_from_html(title_node)
    if title_text:
        lines.extend([f"# {title_text}", ""])

    abstract_section = select_nature_abstract_section(body)
    if abstract_section is not None:
        render_nature_section_markdown(
            abstract_section,
            lines,
            level=2,
            force_heading="Abstract",
        )

    sections = main.find_all("section", recursive=False) if main is not None else []
    if sections:
        for section in sections:
            render_nature_section_markdown(section, lines, level=2)
    elif main is not None:
        render_nature_container_markdown(main, lines, level=2)

    rendered = clean_markdown("\n".join(lines))
    return postprocess_nature_markdown(rendered, source_url)


def render_nature_section_markdown(
    section: Any,
    lines: list[str],
    *,
    level: int,
    force_heading: str | None = None,
) -> None:
    heading = force_heading or extract_section_title(section)
    if heading:
        lines.extend([f"{'#' * max(2, min(level, 6))} {heading}", ""])
    content_root = section.select_one("div.c-article-section__content") or section
    render_nature_container_markdown(content_root, lines, level=level + 1, skip_first_heading=heading or None)


def render_nature_container_markdown(
    node: Any,
    lines: list[str],
    *,
    level: int,
    skip_first_heading: str | None = None,
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
        if child.name in HTML_DROP_TAGS or should_drop_html_element(child):
            continue
        if child.name == "section":
            render_nature_section_markdown(child, lines, level=level)
            continue
        if child.name and HEADING_TAG_PATTERN.match(child.name):
            heading_text = render_clean_text_from_html(child)
            if skip_first_heading and not skipped_heading and normalize_section_title(heading_text) == normalize_section_title(skip_first_heading):
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
            render_nature_container_markdown(child, lines, level=level, skip_first_heading=skip_first_heading if not skipped_heading else None)
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


def is_citation_text(text: str) -> bool:
    normalized = normalize_text(text)
    if not normalized:
        return False
    return bool(re.fullmatch(r"[\d,\-\u2013\u2014\s]+", normalized))


def is_citation_link(href: str, text: str) -> bool:
    normalized_href = href.strip().lower()
    normalized_text = normalize_text(text)
    if "#ref-" in normalized_href or "#bib" in normalized_href or "#cite" in normalized_href:
        return True
    if is_citation_text(normalized_text) and normalized_href.startswith("#"):
        return True
    return False


def postprocess_nature_markdown(markdown_text: str, source_url: str) -> str:
    if not markdown_text:
        return ""
    cleaned = markdown_text
    cleaned = NATURE_FIGURE_LINE_PATTERN.sub("", cleaned)
    cleaned = re.sub(r"(?im)^\s*source data\s*$", "", cleaned)
    cleaned = re.sub(r"\((?:ref|refs)\.\)", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\[([^\]]+)\]\((?:/articles/[^)]+|#[^)]+)\)", r"\1", cleaned)
    cleaned = re.sub(r"\s+([,.;:!?])", r"\1", cleaned)
    cleaned = re.sub(r"([(\[])\s+", r"\1", cleaned)
    cleaned = re.sub(r"\s+([)\]])", r"\1", cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    cleaned = re.sub(r"\b([A-Z]{1,4})\s+(\d+)\b", r"\1\2", cleaned)
    cleaned = re.sub(r"(?m)^\s*[-*]\s*$", "", cleaned)
    cleaned = re.sub(r"[ \t]+\n", "\n", cleaned)
    return clean_markdown(cleaned)
