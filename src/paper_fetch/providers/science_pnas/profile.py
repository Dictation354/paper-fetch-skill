"""Container/profile helpers for Science/PNAS browser-workflow extraction."""

from __future__ import annotations

import re

from ...extraction.html.language import html_node_language_hint
from ...extraction.html.semantics import (
    ANCILLARY_TOKENS,
    BODY_CONTAINER_TOKENS,
    CODE_AVAILABILITY_TOKENS,
    DATA_AVAILABILITY_TOKENS,
    ancestor_identity_text,
    heading_category,
    parse_markdown_heading,
)
from ...extraction.html.signals import PAYWALL_PATTERNS
from ...extraction.html.shared import (
    class_tokens as _class_tokens,
    direct_child_tags as _direct_child_tags,
    short_text as _short_text,
)
from ...quality.html_availability import (
    HTML_CONTAINER_BROWSER_WORKFLOW_FALLBACK_TAGS,
    HTML_CONTAINER_DROP_BROWSER_WORKFLOW,
    HTML_CONTAINER_SCORE_BROWSER_WORKFLOW,
    HtmlContainerSelectionPolicy,
)
from ...utils import normalize_text
from .._science_pnas_profiles import (
    noise_profile_for_publisher as _profile_noise_profile_for_publisher,
    publisher_profile as _publisher_profile,
)
from .. import html_noise as _html_noise

try:
    from bs4 import BeautifulSoup, Tag
except ImportError:  # pragma: no cover - dependency is declared in pyproject
    BeautifulSoup = None
    Tag = None

clean_markdown = _html_noise.clean_markdown


extract_article_markdown = _html_noise.extract_article_markdown


body_metrics = _html_noise.body_metrics


has_sufficient_article_body = _html_noise.has_sufficient_article_body


BODY_PARAGRAPH_MIN_CHARS = 80


HEADING_TAG_PATTERN = re.compile(r"^h[1-6]$")


SENTENCE_PATTERN = re.compile(r"[.!?。！？]+")


FRONT_MATTER_LINE_PATTERNS = (
    re.compile(r"^doi:\s*", flags=re.IGNORECASE),
    re.compile(r"^(vol\.?|volume)\b", flags=re.IGNORECASE),
    re.compile(r"^issue\b", flags=re.IGNORECASE),
    re.compile(r"^[A-Z][a-z]{2,9}\s+\d{4}$"),
    re.compile(r"^[0-3]?\d\s+[A-Z][a-z]{2,9}\s+\d{4}$"),
)


FRONT_MATTER_EXACT_TEXTS = {
    "full access",
    "open access",
    "free access",
    "research article",
    "perspective",
    "review",
    "editorial",
    "commentary",
}


POST_CONTENT_BREAK_PREFIXES = (
    "copyright",
    "license information",
    "submission history",
)


POST_CONTENT_BREAK_TEXTS = {
    "these authors contributed equally to this work.",
}


POST_CONTENT_BREAK_TOKENS = (
    "view all articles by this author",
    "purchase digital access to this article",
    "purchase access to other journals in the science family",
    "select the format you want to export the citation of this publication",
    "loading institution options",
    "become a aaas member",
    "activate your aaas id",
    "account help",
)


PROMO_BLOCK_TOKENS = (
    "sign up for pnas alerts",
    "get alerts for new articles, or get an alert when an article is cited",
)


CONTENT_ABSTRACT_SELECTORS = (
    "#abstracts",
    "section[role='doc-abstract']",
    "[property='abstract'][typeof='Text']",
    "[itemprop='description']",
    ".abstract",
    ".article-section__abstract",
)


CONTENT_BODY_SELECTORS = (
    "#bodymatter",
    "[data-extent='bodymatter']",
    "[property='articleBody']",
    "[itemprop='articleBody']",
    ".article__body",
    ".article-body",
    ".article__content",
    ".article-section__content",
    ".article__fulltext",
    ".epub-section",
)


CONTENT_AVAILABILITY_SELECTORS = (
    "#data-availability",
    "#code-availability",
    "#software-availability",
    "section[id*='data-availability']",
    "section[id*='code-availability']",
    "section[id*='software-availability']",
    "section[class*='data-availability']",
    "section[class*='code-availability']",
    "section[class*='software-availability']",
    "div[id*='data-availability']",
    "div[id*='code-availability']",
    "div[id*='software-availability']",
    "div[class*='data-availability']",
    "div[class*='code-availability']",
    "div[class*='software-availability']",
)


def _noise_profile_for_publisher(publisher: str | None) -> str:
    return _profile_noise_profile_for_publisher(publisher)


def _container_selection_policy(publisher: str) -> HtmlContainerSelectionPolicy:
    profile = _publisher_profile(publisher)
    return HtmlContainerSelectionPolicy(
        score_profile=HTML_CONTAINER_SCORE_BROWSER_WORKFLOW,
        drop_profile=HTML_CONTAINER_DROP_BROWSER_WORKFLOW,
        fallback_tags=HTML_CONTAINER_BROWSER_WORKFLOW_FALLBACK_TAGS,
        prefer_complete_ancestor=True,
        avoid_page_level_container=True,
        body_selectors=CONTENT_BODY_SELECTORS,
        abstract_node_finder=_abstract_nodes,
        refine_selected_container=profile.refine_selected_container,
    )


def _sentence_count(text: str) -> int:
    normalized = normalize_text(text)
    if not normalized:
        return 0
    matches = SENTENCE_PATTERN.findall(normalized)
    if matches:
        return len(matches)
    return 1 if len(normalized) >= BODY_PARAGRAPH_MIN_CHARS else 0


def _is_substantial_prose(text: str) -> bool:
    normalized = normalize_text(text)
    return len(normalized) >= BODY_PARAGRAPH_MIN_CHARS or _sentence_count(normalized) >= 2


def _heading_category(node_name: str, text: str, *, title: str | None = None) -> str:
    return heading_category(node_name, text, title=title)


def _promotional_parent(node: Tag) -> Tag:
    current = node
    while isinstance(current.parent, Tag):
        parent = current.parent
        parent_text = _short_text(parent).lower()
        if not parent_text or len(parent_text) > 320:
            break
        if any(token in parent_text for token in PROMO_BLOCK_TOKENS) or parent_text == "learn more":
            current = parent
            continue
        break
    return current


def _drop_promotional_blocks(container: Tag, publisher: str) -> None:
    if publisher != "pnas":
        return
    for node in list(container.find_all(True)):
        if not isinstance(node, Tag) or node.parent is None:
            continue
        text = _short_text(node).lower()
        if not text or len(text) > 220:
            continue
        if any(token in text for token in PROMO_BLOCK_TOKENS) or text == "learn more":
            _promotional_parent(node).decompose()


def _structural_abstract_nodes(container: Tag) -> list[Tag]:
    abstract_roots: list[Tag] = []
    if normalize_text(((getattr(container, "attrs", None) or {}).get("id") or "")).lower() == "abstracts":
        abstract_roots.append(container)
    try:
        abstract_roots.extend([node for node in container.select("#abstracts") if isinstance(node, Tag)])
    except Exception:
        pass

    sections: list[Tag] = []
    seen: set[int] = set()
    for root in abstract_roots:
        search_parents = [child for child in _direct_child_tags(root) if "core-container" in _class_tokens(child)] or [root]
        for parent in search_parents:
            for child in _direct_child_tags(parent):
                if normalize_text(child.name or "").lower() != "section":
                    continue
                if normalize_text(child.get("role") or "").lower() != "doc-abstract":
                    continue
                if id(child) in seen:
                    continue
                seen.add(id(child))
                sections.append(child)
    return sections


def _abstract_nodes(container: Tag) -> list[Tag]:
    structural_nodes = _structural_abstract_nodes(container)
    if structural_nodes:
        return structural_nodes
    nodes: list[Tag] = []
    for selector in CONTENT_ABSTRACT_SELECTORS:
        try:
            matches = container.select(selector)
        except Exception:
            continue
        for match in matches:
            if isinstance(match, Tag):
                nodes.append(match)
    return _dedupe_top_level_nodes(nodes)


def _node_language_hint(node: Tag) -> str | None:
    return html_node_language_hint(node, allow_soft_hints=True)


def _drop_abstract_sections_from_body_container(container: Tag, publisher: str) -> None:
    if publisher != "wiley":
        return
    for node in _abstract_nodes(container):
        node.decompose()


def extract_page_title(soup: BeautifulSoup) -> str | None:
    from .normalization import _render_non_table_inline_text

    for selector in ["h1", "meta[property='og:title']", "title"]:
        node = soup.select_one(selector)
        if node is None:
            continue
        if node.name == "meta":
            title = normalize_text((getattr(node, "attrs", None) or {}).get("content", ""))
        elif node.name == "h1":
            title = _render_non_table_inline_text(node)
        else:
            title = normalize_text(node.get_text(" ", strip=True))
        if title:
            return title
    return None


def _ancestor_identity_text(node: Tag | None) -> str:
    return ancestor_identity_text(node)


def _looks_like_front_matter_paragraph(text: str, *, title: str | None = None) -> bool:
    normalized = normalize_text(text)
    lowered = normalized.lower()
    if not normalized:
        return True
    if title and lowered == normalize_text(title).lower():
        return True
    if lowered in FRONT_MATTER_EXACT_TEXTS:
        return True
    if "authors info" in lowered or "affiliations" in lowered:
        return True
    if len(normalized) <= 80 and normalized.upper() == normalized and len(normalized.split()) <= 5:
        return True
    if lowered.startswith("by ") and _sentence_count(normalized) <= 1:
        return True
    if any(pattern.match(normalized) for pattern in FRONT_MATTER_LINE_PATTERNS):
        return True
    return lowered in {"science", "pnas", "wiley interdisciplinary reviews"}


def _looks_like_access_gate_text(text: str) -> bool:
    lowered = normalize_text(text).lower()
    if not lowered:
        return False
    if any(pattern in lowered for pattern in PAYWALL_PATTERNS):
        return True
    return any(
        pattern in lowered
        for pattern in (
            "get access",
            "sign in to access",
            "view access options",
            "access provided by",
            "institutional login",
            "purchase article",
        )
    )


def _markdown_heading_info(block: str) -> tuple[int, str] | None:
    return parse_markdown_heading(block)


def _looks_like_post_content_noise_block(text: str) -> bool:
    lowered = normalize_text(text).lower()
    if not lowered:
        return False
    if any(token in lowered for token in PROMO_BLOCK_TOKENS) or lowered == "learn more":
        return True
    if lowered in POST_CONTENT_BREAK_TEXTS:
        return True
    if any(lowered.startswith(prefix) for prefix in POST_CONTENT_BREAK_PREFIXES):
        return True
    return any(token in lowered for token in POST_CONTENT_BREAK_TOKENS)


def _looks_like_markdown_auxiliary_block(text: str) -> bool:
    lowered = normalize_text(text).lower()
    if not lowered:
        return False
    if lowered == "$$":
        return True
    return lowered.startswith("**equation") or lowered.startswith("**figure") or lowered.startswith("**table")


def _is_descendant(node: Tag, candidate_ancestor: Tag) -> bool:
    current: Tag | None = node
    while current is not None:
        if current is candidate_ancestor:
            return True
        parent = current.parent
        current = parent if isinstance(parent, Tag) else None
    return False


def _dedupe_top_level_nodes(nodes: list[Tag]) -> list[Tag]:
    deduped: list[Tag] = []
    seen: set[int] = set()
    for node in nodes:
        if id(node) in seen:
            continue
        if any(_is_descendant(node, existing) for existing in deduped):
            continue
        deduped = [existing for existing in deduped if not _is_descendant(existing, node)]
        deduped.append(node)
        seen.add(id(node))
    return deduped


def _nodes_from_selectors(container: Tag, selectors: tuple[str, ...]) -> list[Tag]:
    nodes: list[Tag] = []
    for selector in selectors:
        try:
            matches = container.select(selector)
        except Exception:
            continue
        for match in matches:
            if isinstance(match, Tag):
                nodes.append(match)
    return _dedupe_top_level_nodes(nodes)


def _availability_node_score(node: Tag) -> int:
    score = 0
    identity = _ancestor_identity_text(node)
    node_id = normalize_text(str((getattr(node, "attrs", None) or {}).get("id") or "")).lower()
    if node_id in {"data-availability", "code-availability", "software-availability"}:
        score += 120
    if normalize_text(node.name or "").lower() == "section":
        score += 10
    if any(token in identity for token in BODY_CONTAINER_TOKENS):
        score += 40
    if any(token in identity for token in DATA_AVAILABILITY_TOKENS + CODE_AVAILABILITY_TOKENS):
        score += 20
    heading = node.find(HEADING_TAG_PATTERN)
    if isinstance(heading, Tag):
        heading_kind = _heading_category(normalize_text(heading.name or "").lower(), heading.get_text(" ", strip=True))
        if heading_kind in {"data_availability", "code_availability"}:
            score += 40
    if any(token in identity for token in ANCILLARY_TOKENS):
        score -= 60
    if any(token in identity for token in ("collateral", "tabpanel", "tab-panel", "tab_panel", "info-panel", "info_panel")):
        score -= 120
    return score


def _select_availability_nodes(container: Tag, body_nodes: list[Tag]) -> list[Tag]:
    chosen_by_text: dict[str, tuple[int, int, Tag]] = {}
    for index, node in enumerate(_nodes_from_selectors(container, CONTENT_AVAILABILITY_SELECTORS)):
        if any(_is_descendant(node, body_node) for body_node in body_nodes):
            continue
        text_key = normalize_text(node.get_text(" ", strip=True)).lower()
        if not text_key:
            continue
        candidate = (_availability_node_score(node), index, node)
        current = chosen_by_text.get(text_key)
        if current is None or candidate[0] > current[0]:
            chosen_by_text[text_key] = candidate
    return _dedupe_top_level_nodes(
        [entry[2] for entry in sorted(chosen_by_text.values(), key=lambda entry: entry[1])]
    )


def _select_content_nodes(container: Tag, *, publisher: str | None = None) -> list[Tag]:
    profile = _publisher_profile(publisher)
    if profile.select_content_nodes is not None:
        provider_nodes = profile.select_content_nodes(
            container,
            structural_abstract_nodes=_structural_abstract_nodes,
            nodes_from_selectors=_nodes_from_selectors,
            content_abstract_selectors=CONTENT_ABSTRACT_SELECTORS,
            content_body_selectors=CONTENT_BODY_SELECTORS,
            select_availability_nodes=_select_availability_nodes,
            dedupe_top_level_nodes=_dedupe_top_level_nodes,
            is_tag=lambda node: isinstance(node, Tag),
        )
        if provider_nodes:
            return provider_nodes

    selected: list[Tag] = []
    abstract_nodes = _nodes_from_selectors(container, CONTENT_ABSTRACT_SELECTORS)
    body_nodes = _nodes_from_selectors(container, CONTENT_BODY_SELECTORS)
    availability_nodes = _select_availability_nodes(container, body_nodes)
    selected.extend(abstract_nodes)
    selected.extend(body_nodes)
    selected.extend(availability_nodes)

    return _dedupe_top_level_nodes(selected)


def _content_fragment_html(container: Tag, *, publisher: str | None = None) -> str:
    content_nodes = _select_content_nodes(container, publisher=publisher)
    if not content_nodes:
        return str(container)
    return "<div>" + "".join(str(node) for node in content_nodes) + "</div>"


def _strip_heading_terminal_punctuation(heading_text: str) -> str:
    normalized = normalize_text(heading_text)
    if normalized.endswith("."):
        return normalized[:-1].rstrip()
    return normalized


__all__ = [
    "clean_markdown",
    "extract_article_markdown",
    "body_metrics",
    "has_sufficient_article_body",
    "BODY_PARAGRAPH_MIN_CHARS",
    "HEADING_TAG_PATTERN",
    "SENTENCE_PATTERN",
    "FRONT_MATTER_LINE_PATTERNS",
    "FRONT_MATTER_EXACT_TEXTS",
    "POST_CONTENT_BREAK_PREFIXES",
    "POST_CONTENT_BREAK_TEXTS",
    "POST_CONTENT_BREAK_TOKENS",
    "PROMO_BLOCK_TOKENS",
    "CONTENT_ABSTRACT_SELECTORS",
    "CONTENT_BODY_SELECTORS",
    "CONTENT_AVAILABILITY_SELECTORS",
    "_noise_profile_for_publisher",
    "_container_selection_policy",
    "_sentence_count",
    "_is_substantial_prose",
    "_heading_category",
    "_promotional_parent",
    "_drop_promotional_blocks",
    "_structural_abstract_nodes",
    "_abstract_nodes",
    "_node_language_hint",
    "_drop_abstract_sections_from_body_container",
    "extract_page_title",
    "_ancestor_identity_text",
    "_looks_like_front_matter_paragraph",
    "_looks_like_access_gate_text",
    "_markdown_heading_info",
    "_looks_like_post_content_noise_block",
    "_looks_like_markdown_auxiliary_block",
    "_is_descendant",
    "_dedupe_top_level_nodes",
    "_nodes_from_selectors",
    "_availability_node_score",
    "_select_availability_nodes",
    "_select_content_nodes",
    "_content_fragment_html",
    "_strip_heading_terminal_punctuation",
]
