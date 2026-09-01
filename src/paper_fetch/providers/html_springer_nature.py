"""Shared Springer Nature HTML extraction helpers."""

from __future__ import annotations

import re
import urllib.parse
from typing import Any

from ..common_patterns import EXTENDED_DATA_PREFIX_PATTERN
from ..extraction.html.ui_tokens import SPRINGER_NATURE_SOURCE_DATA_LABEL

from ..extraction.html.cleanup_policy import classify_dom_cleanup_node
from ..extraction.html.parsing import choose_parser
from ..extraction.html.provider_rules import (
    cleanup_policy_for_profile,
    normalize_provider_heading,
)
from ..extraction.html._runtime import clean_markdown, count_words
from ..models import normalize_text
from ..provider_catalog import matching_provider_domain, provider_domain_matches
from ..extraction.html.semantics import (
    ANCILLARY_HEADINGS,
    BACK_MATTER_HEADINGS,
    heading_category,
    identity_category,
    node_identity_text,
    normalize_section_title,
)
from ..markdown.citations import (
    COMMON_FIGURE_LINE_PATTERN,
    COMMON_LABEL_PATTERN,
    clean_citation_markers,
    normalize_inline_citation_markdown,
)
from ._html_section_markdown import (
    extract_section_title,
    render_heading_text_from_html,
    render_container_markdown,
    render_section_markdown,
    section_has_direct_renderable_content,
)

from bs4 import BeautifulSoup, Tag

SPRINGER_NATURE_ROOT_SELECTORS = (
    "article",
    "main article",
    "main",
    '[data-test="article-body"]',
    "div.c-article-body",
)
SPRINGER_NATURE_SECTION_CONTENT_SELECTORS = ("div.c-article-section__content",)
SPRINGER_NATURE_SCIENTIFIC_BACK_MATTER_TITLES = (
    (
        BACK_MATTER_HEADINGS
        & {
            "acknowledgements",
            "acknowledgments",
            "author contributions",
            "competing interests",
            "funding",
            "supplementary information",
        }
    )
    | (ANCILLARY_HEADINGS & {"additional information"})
    | {"ethics declarations"}
)
SPRINGER_NATURE_INLINE_ARTICLE_LINK_PATTERN = re.compile(
    r"\[([^\]]+)\]\((?:/(?:article|articles)/[^)]+|#[^)]+)\)"
)
SPRINGER_NATURE_INLINE_LINK_UNWRAP_PATTERNS = (
    SPRINGER_NATURE_INLINE_ARTICLE_LINK_PATTERN,
)
# Springer/Nature citation cleanup accepts abbreviated Extended Data figure and
# table labels, so it keeps a provider-owned regex derived from the shared prefix.
SPRINGER_NATURE_EXTENDED_DATA_LABEL_PATTERN = re.compile(
    rf"\b((?:{EXTENDED_DATA_PREFIX_PATTERN}\s+(?:Fig|Figs|Tab|Tabs)|{EXTENDED_DATA_PREFIX_PATTERN}))"
    r"\.?\s+(\d+[A-Za-z]?)\b",
    flags=re.IGNORECASE,
)
SPRINGER_NATURE_CITATION_LABEL_PATTERNS = (
    SPRINGER_NATURE_EXTENDED_DATA_LABEL_PATTERN,
    COMMON_LABEL_PATTERN,
)
SPRINGER_NATURE_EXTENDED_DATA_FIGURE_LINE_PATTERN = re.compile(
    rf"(?im)^{EXTENDED_DATA_PREFIX_PATTERN}\s+fig\.\s*[a-z0-9.-]+:.*$"
)
SPRINGER_NATURE_SOURCE_DATA_LINE_PATTERN = re.compile(
    rf"(?im)^\s*{re.escape(SPRINGER_NATURE_SOURCE_DATA_LABEL)}\s*$"
)
SPRINGER_NATURE_FIGURE_LINE_PATTERNS = (
    COMMON_FIGURE_LINE_PATTERN,
    SPRINGER_NATURE_EXTENDED_DATA_FIGURE_LINE_PATTERN,
    SPRINGER_NATURE_SOURCE_DATA_LINE_PATTERN,
)
SPRINGER_NATURE_CLEANUP_CONTEXT = "extraction"


def is_springer_nature_url(url: str) -> bool:
    hostname = urllib.parse.urlparse(url).hostname
    return provider_domain_matches("springer", hostname)


def is_nature_url(url: str) -> bool:
    hostname = urllib.parse.urlparse(url).hostname
    return matching_provider_domain("springer", hostname) == "nature.com"


def _candidate_score(node: Any) -> int:
    if node is None:
        return 0
    text = normalize_text(node.get_text(" ", strip=True))
    if not text:
        return 0
    score = count_words(text)
    if (
        isinstance(node, Tag)
        and node.select_one("div.c-article-body div.main-content") is not None
    ):
        score += 1000
    if isinstance(node, Tag) and node.find("h1") is not None:
        score += 100
    return score


def select_springer_nature_article_root(root: Any):

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
        current = (
            current.parent
            if isinstance(getattr(current, "parent", None), Tag)
            else None
        )
    return False


def _is_availability_section_title(title_key: str) -> bool:
    return heading_category("h2", title_key) in {
        "data_availability",
        "code_availability",
    }


def _is_scientific_back_matter_title(title_key: str) -> bool:
    return (
        title_key in SPRINGER_NATURE_SCIENTIFIC_BACK_MATTER_TITLES
        or _is_availability_section_title(title_key)
    )


def _has_policy_license_link(node: Any, cleanup_policy: Any) -> bool:
    if not isinstance(node, Tag):
        return False
    hosts = tuple(host.lower() for host in cleanup_policy.license_link_hosts)
    path_prefixes = tuple(
        prefix.lower() for prefix in cleanup_policy.license_link_path_prefixes
    )
    if not hosts or not path_prefixes:
        return False
    for anchor in node.find_all("a", href=True, recursive=False):
        if not isinstance(anchor, Tag):
            continue
        href = normalize_text(str(anchor.get("href") or ""))
        parsed = urllib.parse.urlparse(href)
        hostname = (parsed.hostname or parsed.netloc).lower()
        path = parsed.path.lower()
        if any(
            hostname == host or hostname.endswith(f".{host}") for host in hosts
        ) and any(path.startswith(prefix) for prefix in path_prefixes):
            return True
    return False


def _prune_springer_nature_chrome(root: Any) -> None:
    if not isinstance(root, Tag):
        return
    cleanup_policy = cleanup_policy_for_profile("springer_nature")
    for node in list(root.find_all(True)):
        if not isinstance(node, Tag):
            continue
        title_key = _section_title_key(node)
        if title_key in cleanup_policy.chrome_section_headings:
            node.decompose()
            continue
        text = normalize_text(node.get_text(" ", strip=True))
        if (
            classify_dom_cleanup_node(
                node,
                policy=cleanup_policy,
                stage=SPRINGER_NATURE_CLEANUP_CONTEXT,
                text=text,
            ).action
            == "drop"
        ):
            node.decompose()
            continue
        if (
            "open access" in cleanup_policy.chrome_section_headings
            and normalize_section_title(extract_section_title(node)) == "open access"
        ):
            node.decompose()
            continue
        node_name = normalize_text(getattr(node, "name", "") or "").lower()
        if (
            node_name not in {"html", "body", "main", "article"}
            and cleanup_policy.license_word_limit > 0
            and _has_policy_license_link(node, cleanup_policy)
            and count_words(text) <= cleanup_policy.license_word_limit
        ):
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
        if (
            any(token in attr_blob for token in cleanup_policy.chrome_attr_tokens)
            and count_words(text) <= 80
        ):
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
        if (
            not isinstance(section, Tag)
            or id(section) in seen
            or _is_descendant_of(section, main)
        ):
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
            force_heading=extract_section_title(section)
            or normalize_text(str(section.get("data-title") or ""))
            or None,
            section_content_selectors=SPRINGER_NATURE_SECTION_CONTENT_SELECTORS,
        )


def select_nature_abstract_section(body: Any):
    if body is None:
        return None
    direct_children = [
        child
        for child in body.find_all(["section", "div"], recursive=False)
        if isinstance(child, Tag)
    ]
    for section in direct_children:
        if identity_category(node_identity_text(section)) == "abstract":
            return section
    for section in direct_children:
        if any(
            section.select_one(selector) is not None
            for selector in SPRINGER_NATURE_SECTION_CONTENT_SELECTORS
        ):
            if identity_category(node_identity_text(section)) == "abstract":
                return section
            label_text = normalize_text(
                str(
                    (getattr(section, "attrs", None) or {}).get("data-title")
                    or (getattr(section, "attrs", None) or {}).get("aria-labelledby")
                    or ""
                )
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
    return normalize_provider_heading("springer_nature", title)


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
        if normalize_section_title(
            heading
        ) == "main" and not section_has_direct_renderable_content(
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


def _normalize_springer_nature_inline_mathjax(root: Any) -> None:
    if not isinstance(root, Tag):
        return
    for node in root.select(".mathjax-tex"):
        if not isinstance(node, Tag):
            continue
        value = node.get_text("", strip=False).strip()
        if value.startswith(r"\(") and value.endswith(r"\)") and len(value) > 4:
            node.string = f"${value[2:-2]}$"


def extract_springer_nature_markdown(html_text: str, source_url: str) -> str:
    if not is_springer_nature_url(source_url):
        return ""

    soup = BeautifulSoup(html_text, choose_parser())
    article = (
        select_springer_nature_article_root(soup)
        or soup.select_one("article")
        or soup.select_one("main")
    )
    if article is None:
        return ""
    _prune_springer_nature_chrome(article)
    _normalize_springer_nature_inline_mathjax(article)

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
        _render_scientific_back_matter_sections(
            article, main, lines, availability_only=True
        )
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

    rendered = clean_markdown(
        _remove_duplicate_title_headings("\n".join(lines), title_text),
        noise_profile="springer_nature",
    )
    return postprocess_springer_nature_markdown(rendered)


def postprocess_springer_nature_markdown(markdown_text: str) -> str:
    if not markdown_text:
        return ""
    cleaned = clean_citation_markers(
        markdown_text,
        unwrap_inline_links=True,
        inline_link_patterns=SPRINGER_NATURE_INLINE_LINK_UNWRAP_PATTERNS,
        normalize_labels=True,
        label_patterns=SPRINGER_NATURE_CITATION_LABEL_PATTERNS,
        drop_figure_lines=False,
    )
    cleaned = re.sub(r"(?m)^\s*[-*]\s*$", "", cleaned)
    cleaned = normalize_inline_citation_markdown(cleaned)
    return clean_markdown(cleaned, noise_profile="springer_nature")
