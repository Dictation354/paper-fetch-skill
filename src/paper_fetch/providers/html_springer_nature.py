"""Shared Springer Nature HTML extraction helpers."""

from __future__ import annotations

import re
import urllib.parse
from typing import Any

from ..models import normalize_text
from ._html_citations import clean_citation_markers
from ._html_section_markdown import (
    extract_section_title,
    normalize_section_title,
    render_clean_text_from_html,
    render_container_markdown,
    render_section_markdown,
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


def select_nature_abstract_section(body: Any):
    if BeautifulSoup is None or body is None:
        return None
    for section in body.find_all("section", recursive=False):
        if normalize_section_title(extract_section_title(section)) == "abstract":
            return section
    return None


def clean_springer_nature_text_fragment(text: str) -> str:
    cleaned = clean_citation_markers(normalize_text(text))
    return normalize_text(cleaned)


def extract_springer_nature_markdown(html_text: str, source_url: str) -> str:
    if BeautifulSoup is None or not is_springer_nature_url(source_url):
        return ""

    soup = BeautifulSoup(html_text, "html.parser")
    article = select_springer_nature_article_root(soup) or soup.select_one("article") or soup.select_one("main")
    if article is None:
        return ""

    lines: list[str] = []
    title_node = article.select_one("h1")
    title_text = render_clean_text_from_html(title_node)
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
        sections = main.find_all("section", recursive=False) if main is not None else []
        if sections:
            for section in sections:
                render_section_markdown(
                    section,
                    lines,
                    level=2,
                    section_content_selectors=SPRINGER_NATURE_SECTION_CONTENT_SELECTORS,
                )
        elif main is not None:
            render_container_markdown(
                main,
                lines,
                level=2,
                section_content_selectors=SPRINGER_NATURE_SECTION_CONTENT_SELECTORS,
            )
    else:
        render_container_markdown(
            article,
            lines,
            level=2,
            skip_first_heading=title_text or None,
            section_content_selectors=SPRINGER_NATURE_SECTION_CONTENT_SELECTORS,
        )

    rendered = clean_markdown("\n".join(lines), noise_profile="springer_nature")
    return postprocess_springer_nature_markdown(rendered)


def postprocess_springer_nature_markdown(markdown_text: str) -> str:
    if not markdown_text:
        return ""
    cleaned = clean_citation_markers(
        markdown_text,
        unwrap_inline_links=True,
        normalize_labels=True,
        drop_figure_lines=True,
    )
    cleaned = re.sub(r"(?m)^\s*[-*]\s*$", "", cleaned)
    return clean_markdown(cleaned, noise_profile="springer_nature")
