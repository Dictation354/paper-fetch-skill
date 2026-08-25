"""Container/profile helpers for Atypon browser-workflow extraction."""

from __future__ import annotations

import re

from ...common_patterns import HEADING_TAG_PATTERN
from ...extraction.html.container_selectors import ARTICLE_BODY_SELECTORS
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
from ...extraction.html.cleanup_policy import (
    classify_markdown_cleanup_block,
    extend_cleanup_policy,
)
from ...extraction.html.provider_rules import (
    cleanup_policy_for_profile,
    front_matter_contains_tokens_for_profile,
    front_matter_exact_texts_for_profile,
    front_matter_publication_keywords_for_profile,
    provider_html_rules,
)
from ...extraction.html._runtime import (
    FRONT_MATTER_PUBLICATION_KEYWORDS,
    _publication_watermark_label_tokens,
    body_metrics,
    clean_markdown,
    extract_article_markdown,
    has_sufficient_article_body,
)
from ...extraction.html.front_matter import COMMON_FRONT_MATTER_LINE_PATTERNS
from ...extraction.html.signals import contains_access_gate_text
from ...extraction.html.shared import (
    attr_text,
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
from .._html_authors import ATYPON_VIEW_ALL_ARTICLES_LABEL
from ...utils import normalize_text
from .._atypon_browser_workflow_postprocess import is_display_math_markdown_block
from .._atypon_browser_workflow_profiles import (
    noise_profile_for_publisher as _profile_noise_profile_for_publisher,
    publisher_profile as _publisher_profile,
)

from bs4 import BeautifulSoup, Tag
import contextlib

BODY_PARAGRAPH_MIN_CHARS = 80


SENTENCE_PATTERN = re.compile(r"[.!?。！？]+")


FRONT_MATTER_LINE_PATTERNS = (
    *COMMON_FRONT_MATTER_LINE_PATTERNS,
    re.compile(r"^[A-Z][a-z]{2,9}\s+\d{4}$"),
    re.compile(r"^[0-3]?\d\s+[A-Z][a-z]{2,9}\s+\d{4}$"),
)


POST_CONTENT_BREAK_PREFIXES = (
    "copyright",
    "license information",
    "submission history",
)


POST_CONTENT_BREAK_TEXTS = {
    "these authors contributed equally to this work.",
}


# SITE_UI_COPY_REGRESSION_MARKER: site-owned Atypon export/account chrome;
# rerun browser-workflow extraction tests when these labels change. These
# labels are registered through CleanupPolicy post-content classification.
POST_CONTENT_BREAK_TOKENS = (
    ATYPON_VIEW_ALL_ARTICLES_LABEL,
    "select the format you want to export the citation of this publication",
    "loading institution options",
    "account help",
)


CONTENT_ABSTRACT_SELECTORS = (
    "#abstracts",
    "section[role='doc-abstract']",
    "[property='abstract'][typeof='Text']",
    "[itemprop='description']",
    ".abstract",
    ".article-section__abstract",
)


CONTENT_BODY_SELECTORS = ARTICLE_BODY_SELECTORS


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


def _promo_block_tokens(publisher: str | None) -> tuple[str, ...]:
    return _cleanup_policy_for_publisher(publisher).markdown_contains_tokens


def _cleanup_policy_for_publisher(publisher: str | None):
    return cleanup_policy_for_profile(
        publisher or _noise_profile_for_publisher(publisher)
    )


def _front_matter_exact_texts(publisher: str | None) -> tuple[str, ...]:
    return front_matter_exact_texts_for_profile(
        publisher or _noise_profile_for_publisher(publisher)
    )


def _front_matter_contains_tokens(publisher: str | None) -> tuple[str, ...]:
    return front_matter_contains_tokens_for_profile(
        publisher or _noise_profile_for_publisher(publisher)
    )


def _front_matter_publication_keywords(publisher: str | None) -> set[str]:
    return {
        *FRONT_MATTER_PUBLICATION_KEYWORDS,
        *front_matter_publication_keywords_for_profile(
            publisher or _noise_profile_for_publisher(publisher)
        ),
    }


def _post_content_break_tokens(publisher: str | None) -> tuple[str, ...]:
    return (
        *POST_CONTENT_BREAK_TOKENS,
        *provider_html_rules(publisher).cleanup.post_content_break_tokens,
    )


def _post_content_cleanup_policy(publisher: str | None):
    return extend_cleanup_policy(
        _cleanup_policy_for_publisher(publisher),
        post_content_exact_texts=tuple(POST_CONTENT_BREAK_TEXTS),
        post_content_prefixes=POST_CONTENT_BREAK_PREFIXES,
        post_content_cutoff_tokens=_post_content_break_tokens(publisher),
    )


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
    return (
        len(normalized) >= BODY_PARAGRAPH_MIN_CHARS or _sentence_count(normalized) >= 2
    )


def _heading_category(node_name: str, text: str, *, title: str | None = None) -> str:
    return heading_category(node_name, text, title=title)


def _promotional_parent(node: Tag, *, promo_block_tokens: tuple[str, ...] = ()) -> Tag:
    current = node
    while isinstance(current.parent, Tag):
        parent = current.parent
        parent_text = _short_text(parent).lower()
        if not parent_text or len(parent_text) > 320:
            break
        if any(token in parent_text for token in promo_block_tokens):
            current = parent
            continue
        break
    return current


def _drop_promotional_blocks(
    container: Tag, *, promo_block_tokens: tuple[str, ...]
) -> None:
    if not promo_block_tokens:
        return
    for node in list(container.find_all(True)):
        if not isinstance(node, Tag) or node.parent is None:
            continue
        text = _short_text(node).lower()
        if not text or len(text) > 220:
            continue
        if any(token in text for token in promo_block_tokens):
            _promotional_parent(node, promo_block_tokens=promo_block_tokens).decompose()


def _structural_abstract_nodes(container: Tag) -> list[Tag]:
    abstract_roots: list[Tag] = []
    if (
        attr_text((getattr(container, "attrs", None) or {}).get("id")).lower()
        == "abstracts"
    ):
        abstract_roots.append(container)
    with contextlib.suppress(Exception):
        abstract_roots.extend(
            [node for node in container.select("#abstracts") if isinstance(node, Tag)]
        )

    sections: list[Tag] = []
    seen: set[int] = set()
    for root in abstract_roots:
        search_parents = [
            child
            for child in _direct_child_tags(root)
            if "core-container" in _class_tokens(child)
        ] or [root]
        for parent in search_parents:
            for child in _direct_child_tags(parent):
                if normalize_text(child.name or "").lower() != "section":
                    continue
                if attr_text(child.get("role")).lower() != "doc-abstract":
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


def _drop_abstract_sections_from_body_container(container: Tag) -> None:
    for node in _abstract_nodes(container):
        node.decompose()


def extract_page_title(soup: BeautifulSoup) -> str | None:
    from .normalization import _render_non_table_inline_text

    for selector in ["h1", "meta[property='og:title']", "title"]:
        node = soup.select_one(selector)
        if node is None:
            continue
        if node.name == "meta":
            title = normalize_text(
                (getattr(node, "attrs", None) or {}).get("content", "")
            )
        elif node.name == "h1":
            title = _render_non_table_inline_text(node)
        else:
            title = normalize_text(node.get_text(" ", strip=True))
        if title:
            return title
    return None


def _ancestor_identity_text(node: Tag | None) -> str:
    return ancestor_identity_text(node)


def _looks_like_front_matter_paragraph(
    text: str,
    *,
    title: str | None = None,
    publisher: str | None = None,
) -> bool:
    normalized = normalize_text(text)
    lowered = normalized.lower()
    if not normalized:
        return True
    if title and lowered == normalize_text(title).lower():
        return True
    if lowered in _front_matter_exact_texts(publisher):
        return True
    if any(token in lowered for token in _front_matter_contains_tokens(publisher)):
        return True
    if (
        len(normalized) <= 80
        and normalized.upper() == normalized
        and len(normalized.split()) <= 5
    ):
        return True
    if lowered.startswith("by ") and _sentence_count(normalized) <= 1:
        return True
    if any(pattern.match(normalized) for pattern in FRONT_MATTER_LINE_PATTERNS):
        return True
    return _looks_like_publication_watermark(normalized, publisher=publisher)


def _looks_like_publication_watermark(
    text: str,
    *,
    publisher: str | None = None,
) -> bool:
    normalized = normalize_text(text)
    tokens = _publication_watermark_label_tokens(normalized)
    if not tokens:
        return False
    publication_keywords = _front_matter_publication_keywords(publisher)
    return any(token.lower().strip("&") in publication_keywords for token in tokens)


def _looks_like_access_gate_text(text: str) -> bool:
    return contains_access_gate_text(text)


def _markdown_heading_info(block: str) -> tuple[int, str] | None:
    return parse_markdown_heading(block)


def _looks_like_post_content_noise_block(
    text: str, *, publisher: str | None = None
) -> bool:
    return (
        classify_markdown_cleanup_block(
            text,
            policy=_post_content_cleanup_policy(publisher),
        ).action
        != "keep"
    )


def _looks_like_markdown_auxiliary_block(text: str) -> bool:
    if is_display_math_markdown_block(text):
        return True
    lowered = normalize_text(text).lower()
    if not lowered:
        return False
    if lowered == "$$":
        return True
    return (
        lowered.startswith("**equation")
        or lowered.startswith("**figure")
        or lowered.startswith("**table")
    )


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
        deduped = [
            existing for existing in deduped if not _is_descendant(existing, node)
        ]
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
    node_id = normalize_text(
        str((getattr(node, "attrs", None) or {}).get("id") or "")
    ).lower()
    if node_id in {"data-availability", "code-availability", "software-availability"}:
        score += 120
    if normalize_text(node.name or "").lower() == "section":
        score += 10
    if any(token in identity for token in BODY_CONTAINER_TOKENS):
        score += 40
    if any(
        token in identity
        for token in DATA_AVAILABILITY_TOKENS + CODE_AVAILABILITY_TOKENS
    ):
        score += 20
    heading = node.find(HEADING_TAG_PATTERN)
    if isinstance(heading, Tag):
        heading_kind = _heading_category(
            normalize_text(heading.name or "").lower(),
            heading.get_text(" ", strip=True),
        )
        if heading_kind in {"data_availability", "code_availability"}:
            score += 40
    if any(token in identity for token in ANCILLARY_TOKENS):
        score -= 60
    if any(
        token in identity
        for token in (
            "collateral",
            "tabpanel",
            "tab-panel",
            "tab_panel",
            "info-panel",
            "info_panel",
        )
    ):
        score -= 120
    return score


def _select_availability_nodes(container: Tag, body_nodes: list[Tag]) -> list[Tag]:
    chosen_by_text: dict[str, tuple[int, int, Tag]] = {}
    for index, node in enumerate(
        _nodes_from_selectors(container, CONTENT_AVAILABILITY_SELECTORS)
    ):
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
        [
            entry[2]
            for entry in sorted(chosen_by_text.values(), key=lambda entry: entry[1])
        ]
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
    "BODY_PARAGRAPH_MIN_CHARS",
    "CONTENT_ABSTRACT_SELECTORS",
    "CONTENT_AVAILABILITY_SELECTORS",
    "CONTENT_BODY_SELECTORS",
    "FRONT_MATTER_LINE_PATTERNS",
    "FRONT_MATTER_PUBLICATION_KEYWORDS",
    "HEADING_TAG_PATTERN",
    "POST_CONTENT_BREAK_PREFIXES",
    "POST_CONTENT_BREAK_TEXTS",
    "POST_CONTENT_BREAK_TOKENS",
    "SENTENCE_PATTERN",
    "_abstract_nodes",
    "_ancestor_identity_text",
    "_availability_node_score",
    "_container_selection_policy",
    "_content_fragment_html",
    "_dedupe_top_level_nodes",
    "_drop_abstract_sections_from_body_container",
    "_drop_promotional_blocks",
    "_heading_category",
    "_is_descendant",
    "_is_substantial_prose",
    "_looks_like_access_gate_text",
    "_looks_like_front_matter_paragraph",
    "_looks_like_markdown_auxiliary_block",
    "_looks_like_post_content_noise_block",
    "_looks_like_publication_watermark",
    "_markdown_heading_info",
    "_node_language_hint",
    "_nodes_from_selectors",
    "_noise_profile_for_publisher",
    "_promotional_parent",
    "_select_availability_nodes",
    "_select_content_nodes",
    "_sentence_count",
    "_strip_heading_terminal_punctuation",
    "_structural_abstract_nodes",
    "body_metrics",
    "clean_markdown",
    "extract_article_markdown",
    "extract_page_title",
    "has_sufficient_article_body",
]
