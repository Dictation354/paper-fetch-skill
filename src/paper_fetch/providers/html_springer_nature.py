"""Shared Springer Nature HTML extraction helpers."""

from __future__ import annotations

import re
import urllib.parse
from typing import Any

from ..extraction.html.parsing import choose_parser
from ..models import normalize_text
from ..extraction.html.semantics import (
    heading_category,
    identity_category,
    node_identity_text,
    normalize_section_title,
)
from ..markdown.citations import clean_citation_markers, normalize_inline_citation_markdown
from ._html_section_markdown import (
    extract_section_title,
    render_heading_text_from_html,
    render_container_markdown,
    render_section_markdown,
    section_has_direct_renderable_content,
)
from .html_noise import clean_markdown, count_words

try:
    from bs4 import BeautifulSoup, Tag
except ImportError:  # pragma: no cover - exercised implicitly when dependency is absent
    BeautifulSoup = None
    Tag = None

SPRINGER_NATURE_HOST_SUFFIXES = (
    "nature.com",
    "springer.com",
    "springernature.com",
    "biomedcentral.com",
)
SPRINGER_NATURE_ROOT_SELECTORS = (
    "article",
    "main article",
    "main",
    '[data-test="article-body"]',
    "div.c-article-body",
)
SPRINGER_NATURE_SECTION_CONTENT_SELECTORS = ("div.c-article-section__content",)
SPRINGER_NATURE_CHROME_TEXTS = {
    "aims and scope",
    "save article",
    "submit manuscript",
    "view saved research",
}
SPRINGER_NATURE_CHROME_SECTION_TITLES = {
    "about this article",
    "article information",
    "author information",
    "authors and affiliations",
    "cite this article",
    "open access",
    "permissions",
    "rights and permissions",
    "reprints and permissions",
}
SPRINGER_NATURE_SCIENTIFIC_BACK_MATTER_TITLES = {
    "acknowledgements",
    "acknowledgments",
    "additional information",
    "author contributions",
    "competing interests",
    "ethics declarations",
    "funding",
    "supplementary information",
}
SPRINGER_NATURE_LICENSE_TOKENS = (
    "creative commons",
    "this article is licensed under",
    "the images or other third party material in this article",
)
SPRINGER_NATURE_CHROME_ATTR_TOKENS = (
    "article-actions",
    "article-metrics",
    "saved-research",
    "save-article",
    "submit-manuscript",
)


def is_springer_nature_url(url: str) -> bool:
    hostname = urllib.parse.urlparse(url).netloc.lower()
    return any(hostname == suffix or hostname.endswith(f".{suffix}") for suffix in SPRINGER_NATURE_HOST_SUFFIXES)


def is_nature_url(url: str) -> bool:
    hostname = urllib.parse.urlparse(url).netloc.lower()
    return hostname == "nature.com" or hostname.endswith(".nature.com")


def _candidate_score(node: Any) -> int:
    if BeautifulSoup is None or node is None:
        return 0
    text = normalize_text(node.get_text(" ", strip=True))
    if not text:
        return 0
    score = count_words(text)
    if isinstance(node, Tag) and node.select_one("div.c-article-body div.main-content") is not None:
        score += 1000
    if isinstance(node, Tag) and node.find("h1") is not None:
        score += 100
    return score


def select_springer_nature_article_root(root: Any):
    if BeautifulSoup is None:
        return None

    best_candidate = None
    best_score = 0
    seen: set[int] = set()

    def consider(candidate: Any) -> None:
        nonlocal best_candidate, best_score
        if not isinstance(candidate, Tag):
            return
        candidate_id = id(candidate)
        if candidate_id in seen:
            return
        seen.add(candidate_id)
        score = _candidate_score(candidate)
        if score > best_score:
            best_candidate = candidate
            best_score = score

    if isinstance(root, Tag) and not isinstance(root, BeautifulSoup):
        consider(root)
    for selector in SPRINGER_NATURE_ROOT_SELECTORS:
        try:
            matches = root.select(selector)
        except Exception:
            continue
        for match in matches:
            consider(match)
    return best_candidate


def _section_title_key(node: Any) -> str:
    if not isinstance(node, Tag):
        return ""
    attrs = getattr(node, "attrs", None) or {}
    for key in ("data-title", "aria-label"):
        value = normalize_text(str(attrs.get(key) or ""))
        if value:
            return normalize_section_title(value)
    for child in node.find_all(re.compile(r"^h[1-6]$"), recursive=False):
        if isinstance(child, Tag):
            return normalize_section_title(render_heading_text_from_html(child))
    if normalize_text(node.name or "").lower() == "section":
        return normalize_section_title(extract_section_title(node))
    return ""


def _is_descendant_of(node: Any, ancestor: Any) -> bool:
    current = node
    while isinstance(current, Tag):
        if current is ancestor:
            return True
        current = current.parent if isinstance(getattr(current, "parent", None), Tag) else None
    return False


def _is_availability_section_title(title_key: str) -> bool:
    return heading_category("h2", title_key) in {"data_availability", "code_availability"}


def _is_scientific_back_matter_title(title_key: str) -> bool:
    return title_key in SPRINGER_NATURE_SCIENTIFIC_BACK_MATTER_TITLES or _is_availability_section_title(title_key)


def _prune_springer_nature_chrome(root: Any) -> None:
    if BeautifulSoup is None or not isinstance(root, Tag):
        return
    for node in list(root.find_all(True)):
        if not isinstance(node, Tag):
            continue
        title_key = _section_title_key(node)
        if title_key in SPRINGER_NATURE_CHROME_SECTION_TITLES:
            node.decompose()
            continue
        text = normalize_text(node.get_text(" ", strip=True))
        lowered = text.lower()
        if lowered in SPRINGER_NATURE_CHROME_TEXTS:
            node.decompose()
            continue
        if normalize_section_title(extract_section_title(node)) == "open access":
            node.decompose()
            continue
        if any(token in lowered for token in SPRINGER_NATURE_LICENSE_TOKENS) and count_words(text) <= 180:
            node.decompose()
            continue
        attrs = getattr(node, "attrs", None) or {}
        attr_parts: list[str] = []
        for value in attrs.values():
            if isinstance(value, (list, tuple, set)):
                attr_parts.extend(normalize_text(str(item)).lower() for item in value)
            else:
                attr_parts.append(normalize_text(str(value)).lower())
        attr_blob = " ".join(part for part in attr_parts if part)
        if any(token in attr_blob for token in SPRINGER_NATURE_CHROME_ATTR_TOKENS) and count_words(text) <= 80:
            node.decompose()


def _render_scientific_back_matter_sections(
    article: Any,
    main: Any,
    lines: list[str],
    *,
    availability_only: bool = False,
) -> None:
    if not isinstance(article, Tag) or not isinstance(main, Tag) or article is main:
        return
    seen: set[int] = set()
    for section in article.find_all("section"):
        if not isinstance(section, Tag) or id(section) in seen or _is_descendant_of(section, main):
            continue
        seen.add(id(section))
        title_key = _section_title_key(section)
        if availability_only:
            if not _is_availability_section_title(title_key):
                continue
        elif not _is_scientific_back_matter_title(title_key):
            continue
        render_section_markdown(
            section,
            lines,
            level=2,
            force_heading=extract_section_title(section) or normalize_text(str(section.get("data-title") or "")) or None,
            section_content_selectors=SPRINGER_NATURE_SECTION_CONTENT_SELECTORS,
        )


def select_nature_abstract_section(body: Any):
    if BeautifulSoup is None or body is None:
        return None
    direct_children = [child for child in body.find_all(["section", "div"], recursive=False) if isinstance(child, Tag)]
    for section in direct_children:
        if identity_category(node_identity_text(section)) == "abstract":
            return section
    for section in direct_children:
        if any(section.select_one(selector) is not None for selector in SPRINGER_NATURE_SECTION_CONTENT_SELECTORS):
            if identity_category(node_identity_text(section)) == "abstract":
                return section
            label_text = normalize_text(
                str((getattr(section, "attrs", None) or {}).get("data-title") or (getattr(section, "attrs", None) or {}).get("aria-labelledby") or "")
            )
            if "abstract" in label_text.lower():
                return section
    for section in direct_children:
        if normalize_section_title(extract_section_title(section)) == "abstract":
            return section
    return None


def clean_springer_nature_text_fragment(text: str) -> str:
    cleaned = clean_citation_markers(normalize_text(text))
    return normalize_text(cleaned)


def _normalized_nature_section_heading(section: Any) -> str:
    title = extract_section_title(section)
    normalized = normalize_section_title(title)
    if normalized == "online methods":
        return "Methods"
    return title


def _is_renderable_nature_body_div(node: Any) -> bool:
    if not isinstance(node, Tag) or normalize_text(node.name or "").lower() != "div":
        return False
    classes = getattr(node, "attrs", {}).get("class") or []
    if isinstance(classes, str):
        class_values = classes.split()
    else:
        class_values = [str(value) for value in classes]
    if "c-article-section__content" in class_values:
        return True
    return section_has_direct_renderable_content(
        node,
        section_content_selectors=SPRINGER_NATURE_SECTION_CONTENT_SELECTORS,
    )


def _render_nature_main_child_markdown(child: Any, lines: list[str]) -> bool:
    if not isinstance(child, Tag):
        return False
    if child.name == "section":
        heading = _normalized_nature_section_heading(child)
        if normalize_section_title(heading) == "main" and not section_has_direct_renderable_content(
            child,
            section_content_selectors=SPRINGER_NATURE_SECTION_CONTENT_SELECTORS,
        ):
            content_root = child.select_one("div.c-article-section__content") or child
            render_container_markdown(
                content_root,
                lines,
                level=2,
                skip_first_heading=extract_section_title(child) or None,
                section_content_selectors=SPRINGER_NATURE_SECTION_CONTENT_SELECTORS,
            )
            return True
        render_section_markdown(
            child,
            lines,
            level=2,
            force_heading=heading or None,
            section_content_selectors=SPRINGER_NATURE_SECTION_CONTENT_SELECTORS,
        )
        return True
    if _is_renderable_nature_body_div(child):
        render_container_markdown(
            child,
            lines,
            level=2,
            section_content_selectors=SPRINGER_NATURE_SECTION_CONTENT_SELECTORS,
        )
        return True
    return False


def _remove_duplicate_title_headings(markdown_text: str, title_text: str) -> str:
    title = normalize_text(title_text)
    if not markdown_text or not title:
        return markdown_text
    lines: list[str] = []
    title_key = normalize_section_title(title)
    for line in markdown_text.splitlines():
        match = re.match(r"^(#{2,6})\s+(.+?)\s*$", line)
        if match and normalize_section_title(match.group(2)) == title_key:
            continue
        lines.append(line)
    return "\n".join(lines)


def extract_springer_nature_markdown(html_text: str, source_url: str) -> str:
    if BeautifulSoup is None or not is_springer_nature_url(source_url):
        return ""

    soup = BeautifulSoup(html_text, choose_parser())
    article = select_springer_nature_article_root(soup) or soup.select_one("article") or soup.select_one("main")
    if article is None:
        return ""
    _prune_springer_nature_chrome(article)

    lines: list[str] = []
    title_node = article.select_one("h1")
    title_text = render_heading_text_from_html(title_node)
    if title_text:
        lines.extend([f"# {title_text}", ""])

    if is_nature_url(source_url):
        body = article.select_one("div.c-article-body") or article
        main = body.select_one("div.main-content") or body
        abstract_section = select_nature_abstract_section(body)
        if abstract_section is not None:
            render_section_markdown(
                abstract_section,
                lines,
                level=2,
                force_heading="Abstract",
                section_content_selectors=SPRINGER_NATURE_SECTION_CONTENT_SELECTORS,
            )
        rendered_main_children = 0
        if main is not None:
            for child in main.children:
                if abstract_section is not None and child is abstract_section:
                    continue
                if _render_nature_main_child_markdown(child, lines):
                    rendered_main_children += 1
        if main is not None and rendered_main_children == 0:
            render_container_markdown(
                main,
                lines,
                level=2,
                section_content_selectors=SPRINGER_NATURE_SECTION_CONTENT_SELECTORS,
            )
        _render_scientific_back_matter_sections(article, main, lines, availability_only=True)
    else:
        body = article.select_one("div.c-article-body") or article
        main = body.select_one("div.main-content") or body
        render_container_markdown(
            main,
            lines,
            level=2,
            skip_first_heading=title_text or None,
            section_content_selectors=SPRINGER_NATURE_SECTION_CONTENT_SELECTORS,
        )
        _render_scientific_back_matter_sections(article, main, lines)

    rendered = clean_markdown(_remove_duplicate_title_headings("\n".join(lines), title_text), noise_profile="springer_nature")
    return postprocess_springer_nature_markdown(rendered)


def postprocess_springer_nature_markdown(markdown_text: str) -> str:
    if not markdown_text:
        return ""
    cleaned = clean_citation_markers(
        markdown_text,
        unwrap_inline_links=True,
        normalize_labels=True,
        drop_figure_lines=False,
    )
    cleaned = re.sub(r"(?m)^\s*[-*]\s*$", "", cleaned)
    cleaned = normalize_inline_citation_markdown(cleaned)
    return clean_markdown(cleaned, noise_profile="springer_nature")
