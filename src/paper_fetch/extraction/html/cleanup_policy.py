"""Shared ownership and classification helpers for HTML cleanup rules."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Literal

from ...models import normalize_text
from .availability_policy import AvailabilityContainerRules
from .html_tags import HTML_DROP_TAGS
from .semantics import (
    MARKDOWN_AUXILIARY_HEADINGS,
    looks_like_reference_anchor,
    node_identity_text,
)
from .signals import (
    MARKDOWN_ACCESS_NOISE_LABELS,
    MARKDOWN_SHORT_ACCESS_GATE_TOKENS,
    contains_access_gate_text,
)
from .ui_tokens import DOWNLOAD_PDF_LABEL

HTML_DROP_SELECTORS = (
    "nav",
    "aside",
    "form",
    "button",
    "input",
    "select",
    "textarea",
    "dialog",
    '[aria-hidden="true"]',
    "[hidden]",
)
HTML_EXACT_NOISE_TEXTS = frozenset(
    {
        "advertisement",
        "aims and scope",
        DOWNLOAD_PDF_LABEL,
        "rights and permissions",
        "save article",
        "submit manuscript",
        "view all journals",
        "view author publications",
        "view saved research",
        "search author on:",
        "search author on: pubmed google scholar",
        "get shareable link",
        "copy shareable link to clipboard",
    }
)
HTML_PREFIX_NOISE_TEXTS = ("skip to main content",)
HTML_NOISE_ATTR_TOKENS = (
    "advert",
    "cookie",
    "newsletter",
    "share",
    "toolbar",
    "related",
    "recommend",
    "metrics",
    "banner",
    "promo",
)
HTML_SEMANTIC_ATTRS = frozenset(
    {
        "alt",
        "aria-describedby",
        "aria-label",
        "aria-labelledby",
        "data-title",
        "title",
    }
)
MARKDOWN_EXACT_NOISE_TEXTS = frozenset(
    {
        *HTML_EXACT_NOISE_TEXTS,
        "menu",
        "home",
        "similar content being viewed by others",
    }
)
MARKDOWN_PREFIX_NOISE_TEXTS = HTML_PREFIX_NOISE_TEXTS + (
    "subscribe",
    *MARKDOWN_ACCESS_NOISE_LABELS,
)
MARKDOWN_SHORT_NOISE_TOKENS = MARKDOWN_SHORT_ACCESS_GATE_TOKENS
MARKDOWN_CHROME_SECTION_HEADINGS = MARKDOWN_AUXILIARY_HEADINGS - {"abbreviations"}
MARKDOWN_PROMO_MAX_WORDS = 16
MARKDOWN_PROMO_INTRO_PREFIXES = ("to ",)
MARKDOWN_PROMO_TERMINAL_CHARS = ",.:;!?([{)]}"
AVAILABILITY_DROP_TAGS = ("script", "style", "noscript", "iframe", "svg")
BROWSER_WORKFLOW_DROP_TAGS = (
    "script",
    "style",
    "noscript",
    "svg",
    "iframe",
    "button",
    "input",
    "form",
)
BROWSER_WORKFLOW_SHORT_TEXT_PATTERNS = (
    "share this",
    "view metrics",
    "article metrics",
)

_HEADING_TAG_RE = re.compile(r"^h[1-6]$")

CleanupAction = Literal["keep", "drop", "cutoff"]


@dataclass(frozen=True)
class CleanupDecision:
    action: CleanupAction
    reason: str = ""


KEEP_CLEANUP_DECISION = CleanupDecision("keep", "")


@dataclass(frozen=True)
class CleanupPolicy:
    name: str
    dom_drop_tags: tuple[str, ...] = HTML_DROP_TAGS
    dom_drop_selectors: tuple[str, ...] = HTML_DROP_SELECTORS
    dom_exact_texts: frozenset[str] = HTML_EXACT_NOISE_TEXTS
    dom_prefix_texts: tuple[str, ...] = HTML_PREFIX_NOISE_TEXTS
    dom_attr_tokens: tuple[str, ...] = HTML_NOISE_ATTR_TOKENS
    extraction_cleanup_selectors: tuple[str, ...] = ()
    dom_postprocess_cleanup_selectors: tuple[str, ...] = ()
    chrome_section_headings: frozenset[str] = frozenset()
    chrome_attr_tokens: tuple[str, ...] = ()
    license_link_hosts: tuple[str, ...] = ()
    license_link_path_prefixes: tuple[str, ...] = ()
    license_word_limit: int = 0
    extraction_drop_keywords: tuple[str, ...] = ()
    markdown_exact_texts: frozenset[str] = MARKDOWN_EXACT_NOISE_TEXTS
    markdown_prefix_texts: tuple[str, ...] = MARKDOWN_PREFIX_NOISE_TEXTS
    markdown_short_tokens: tuple[str, ...] = MARKDOWN_SHORT_NOISE_TOKENS
    markdown_contains_tokens: tuple[str, ...] = ()
    provider_markdown_promo_tokens: tuple[str, ...] = ()
    front_matter_exact_texts: tuple[str, ...] = ()
    front_matter_contains_tokens: tuple[str, ...] = ()
    front_matter_publication_keywords: tuple[str, ...] = ()
    post_content_exact_texts: frozenset[str] = frozenset()
    post_content_prefixes: tuple[str, ...] = ()
    post_content_cutoff_tokens: tuple[str, ...] = ()


def build_cleanup_policy(
    name: str,
    *,
    markdown_contains_tokens: tuple[str, ...] = (),
    provider_markdown_promo_tokens: tuple[str, ...] = (),
    extraction_cleanup_selectors: tuple[str, ...] = (),
    dom_postprocess_cleanup_selectors: tuple[str, ...] = (),
    chrome_section_headings: tuple[str, ...] = (),
    chrome_attr_tokens: tuple[str, ...] = (),
    license_link_hosts: tuple[str, ...] = (),
    license_link_path_prefixes: tuple[str, ...] = (),
    license_word_limit: int = 0,
    extraction_drop_keywords: tuple[str, ...] = (),
    front_matter_exact_texts: tuple[str, ...] = (),
    front_matter_contains_tokens: tuple[str, ...] = (),
    front_matter_publication_keywords: tuple[str, ...] = (),
    post_content_exact_texts: tuple[str, ...] = (),
    post_content_prefixes: tuple[str, ...] = (),
    post_content_cutoff_tokens: tuple[str, ...] = (),
) -> CleanupPolicy:
    return CleanupPolicy(
        name=name,
        dom_attr_tokens=(
            *HTML_NOISE_ATTR_TOKENS,
            *extraction_drop_keywords,
        ),
        extraction_cleanup_selectors=extraction_cleanup_selectors,
        dom_postprocess_cleanup_selectors=dom_postprocess_cleanup_selectors,
        chrome_section_headings=frozenset(chrome_section_headings),
        chrome_attr_tokens=chrome_attr_tokens,
        license_link_hosts=license_link_hosts,
        license_link_path_prefixes=license_link_path_prefixes,
        license_word_limit=license_word_limit,
        extraction_drop_keywords=extraction_drop_keywords,
        markdown_contains_tokens=markdown_contains_tokens,
        provider_markdown_promo_tokens=provider_markdown_promo_tokens,
        front_matter_exact_texts=front_matter_exact_texts,
        front_matter_contains_tokens=front_matter_contains_tokens,
        front_matter_publication_keywords=front_matter_publication_keywords,
        post_content_exact_texts=frozenset(post_content_exact_texts),
        post_content_prefixes=post_content_prefixes,
        post_content_cutoff_tokens=post_content_cutoff_tokens,
    )


def extend_cleanup_policy(
    policy: CleanupPolicy,
    *,
    post_content_exact_texts: tuple[str, ...] = (),
    post_content_prefixes: tuple[str, ...] = (),
    post_content_cutoff_tokens: tuple[str, ...] = (),
) -> CleanupPolicy:
    return CleanupPolicy(
        name=policy.name,
        dom_drop_tags=policy.dom_drop_tags,
        dom_drop_selectors=policy.dom_drop_selectors,
        dom_exact_texts=policy.dom_exact_texts,
        dom_prefix_texts=policy.dom_prefix_texts,
        dom_attr_tokens=policy.dom_attr_tokens,
        extraction_cleanup_selectors=policy.extraction_cleanup_selectors,
        dom_postprocess_cleanup_selectors=policy.dom_postprocess_cleanup_selectors,
        chrome_section_headings=policy.chrome_section_headings,
        chrome_attr_tokens=policy.chrome_attr_tokens,
        license_link_hosts=policy.license_link_hosts,
        license_link_path_prefixes=policy.license_link_path_prefixes,
        license_word_limit=policy.license_word_limit,
        extraction_drop_keywords=policy.extraction_drop_keywords,
        markdown_exact_texts=policy.markdown_exact_texts,
        markdown_prefix_texts=policy.markdown_prefix_texts,
        markdown_short_tokens=policy.markdown_short_tokens,
        markdown_contains_tokens=policy.markdown_contains_tokens,
        provider_markdown_promo_tokens=policy.provider_markdown_promo_tokens,
        front_matter_exact_texts=policy.front_matter_exact_texts,
        front_matter_contains_tokens=policy.front_matter_contains_tokens,
        front_matter_publication_keywords=policy.front_matter_publication_keywords,
        post_content_exact_texts=frozenset(
            (*policy.post_content_exact_texts, *post_content_exact_texts)
        ),
        post_content_prefixes=(
            *policy.post_content_prefixes,
            *post_content_prefixes,
        ),
        post_content_cutoff_tokens=(
            *policy.post_content_cutoff_tokens,
            *post_content_cutoff_tokens,
        ),
    )


def count_words(text: str) -> int:
    return len(re.findall(r"\b\w+\b", text, flags=re.UNICODE))


def _count_sentences(text: str) -> int:
    return len(re.findall(r"[.!?]+(?:\s|$)", text))


def _strip_terminal_punctuation(text: str) -> str:
    return text.strip().strip(MARKDOWN_PROMO_TERMINAL_CHARS).strip()


def _has_terminal_promo_boundary(text: str, prefix_length: int) -> bool:
    remainder = text[prefix_length:].strip()
    if not remainder:
        return True
    return remainder[0] in MARKDOWN_PROMO_TERMINAL_CHARS


def looks_like_markdown_promo_line(line: str, *, policy: CleanupPolicy) -> bool:
    normalized = normalize_text(re.sub(r"^#+\s*", "", line)).lower()
    if not normalized or count_words(normalized) > MARKDOWN_PROMO_MAX_WORDS:
        return False
    if _count_sentences(normalized) > 1:
        return False
    stripped = _strip_terminal_punctuation(normalized)
    for token in policy.markdown_contains_tokens:
        if stripped == token:
            return True
        if normalized.startswith(token) and _has_terminal_promo_boundary(
            normalized,
            len(token),
        ):
            return True
        for intro_prefix in MARKDOWN_PROMO_INTRO_PREFIXES:
            introduced_token = f"{intro_prefix}{token}"
            if normalized.startswith(introduced_token) and _has_terminal_promo_boundary(
                normalized,
                len(introduced_token),
            ):
                return True
    return False


def _element_text(element: Any) -> str:
    return normalize_text(element.get_text(separator=" ", strip=True))


def _element_name(element: Any) -> str:
    return normalize_text(getattr(element, "name", "")).lower()


def _attr_tokens(element: Any) -> list[str]:
    tokens: list[str] = []
    for key, value in (getattr(element, "attrs", None) or {}).items():
        key_name = str(key).lower()
        if key_name in {"href", "src", "srcset"} or key_name in HTML_SEMANTIC_ATTRS:
            continue
        if isinstance(value, str):
            tokens.append(value.lower())
        elif isinstance(value, list):
            tokens.extend(str(item).lower() for item in value)
    return tokens


def classify_availability_node(
    element: Any,
    rules: AvailabilityContainerRules,
    *,
    browser_workflow: bool = False,
    identity: str | None = None,
    text: str | None = None,
    matched_selector: str | None = None,
    is_mathml_script: bool = False,
) -> CleanupDecision:
    if is_mathml_script:
        return KEEP_CLEANUP_DECISION
    if matched_selector:
        return CleanupDecision("drop", "availability_selector")

    element_name = _element_name(element)
    normalized_text = normalize_text(
        text if text is not None else _element_text(element)
    )
    node_identity = normalize_text(
        identity if identity is not None else node_identity_text(element)
    ).lower()

    if browser_workflow:
        if element_name in rules.drop_tags_for(browser_workflow=True):
            return CleanupDecision("drop", "dom_drop_tag")
        if contains_access_gate_text(normalized_text):
            return KEEP_CLEANUP_DECISION
        short_text = len(normalized_text) <= 200
        if short_text and any(token in node_identity for token in rules.drop_keywords):
            return CleanupDecision("drop", "availability_identity_token")
        if short_text and normalized_text in rules.drop_texts:
            return CleanupDecision("drop", "availability_drop_text")
        lowered = normalized_text.lower()
        if short_text and any(
            pattern in lowered
            for pattern in rules.short_text_patterns_for(browser_workflow=True)
        ):
            return CleanupDecision("drop", "browser_workflow_short_ui_text")
        return KEEP_CLEANUP_DECISION

    if any(token in node_identity for token in rules.drop_keywords):
        return CleanupDecision("drop", "availability_identity_token")
    if normalized_text in rules.drop_texts:
        return CleanupDecision("drop", "availability_drop_text")
    if element_name in rules.drop_tags_for():
        return CleanupDecision("drop", "dom_drop_tag")
    return KEEP_CLEANUP_DECISION


def classify_dom_cleanup_node(
    element: Any,
    *,
    policy: CleanupPolicy,
    stage: str,
    identity: str | None = None,
    text: str | None = None,
    matched_selector: str | None = None,
    is_mathml_script: bool = False,
) -> CleanupDecision:
    if is_mathml_script:
        return KEEP_CLEANUP_DECISION
    if matched_selector:
        return CleanupDecision("drop", f"{stage}_selector")

    element_name = _element_name(element)
    normalized_text = normalize_text(
        text if text is not None else _element_text(element)
    )

    if not normalized_text:
        return KEEP_CLEANUP_DECISION
    if _HEADING_TAG_RE.match(element_name):
        return KEEP_CLEANUP_DECISION
    if looks_like_reference_anchor(element):
        return KEEP_CLEANUP_DECISION

    has_heading_descendant = bool(element.find(_HEADING_TAG_RE))
    lowered = normalized_text.lower()
    if lowered in policy.dom_exact_texts:
        return CleanupDecision("drop", "dom_exact_text")
    if any(lowered.startswith(prefix) for prefix in policy.dom_prefix_texts):
        if has_heading_descendant:
            return KEEP_CLEANUP_DECISION
        if count_words(normalized_text) <= 40:
            return CleanupDecision("drop", "dom_prefix_text")
    attr_tokens = _attr_tokens(element)
    if attr_tokens:
        joined = " ".join(attr_tokens)
        if any(token in joined for token in policy.dom_attr_tokens):
            if count_words(normalized_text) <= 80:
                return CleanupDecision("drop", "dom_attr_token")
    return KEEP_CLEANUP_DECISION


def classify_markdown_cleanup_line(
    line: str,
    *,
    policy: CleanupPolicy,
) -> CleanupDecision:
    normalized = normalize_text(re.sub(r"^#+\s*", "", line)).lower()
    if not normalized:
        return KEEP_CLEANUP_DECISION
    if normalized in policy.markdown_exact_texts:
        return CleanupDecision("drop", "markdown_exact_text")
    if any(normalized.startswith(prefix) for prefix in policy.markdown_prefix_texts):
        return CleanupDecision("drop", "markdown_prefix_text")
    if looks_like_markdown_promo_line(normalized, policy=policy):
        return CleanupDecision("drop", "markdown_short_contains_token")
    if (
        any(token in normalized for token in policy.markdown_short_tokens)
        and count_words(normalized) <= 16
    ):
        return CleanupDecision("drop", "markdown_short_access_token")
    return KEEP_CLEANUP_DECISION


def classify_markdown_cleanup_block(
    block: str,
    *,
    policy: CleanupPolicy,
    started_content: bool = False,
) -> CleanupDecision:
    normalized = normalize_text(block).lower()
    if not normalized:
        return KEEP_CLEANUP_DECISION
    line_decision = classify_markdown_cleanup_line(normalized, policy=policy)
    if line_decision.action != "keep":
        return line_decision
    if normalized in policy.post_content_exact_texts:
        return CleanupDecision(
            "cutoff" if started_content else "drop",
            "post_content_exact_text",
        )
    if any(normalized.startswith(prefix) for prefix in policy.post_content_prefixes):
        return CleanupDecision(
            "cutoff" if started_content else "drop",
            "post_content_prefix",
        )
    if any(token in normalized for token in policy.post_content_cutoff_tokens):
        return CleanupDecision(
            "cutoff" if started_content else "drop",
            "post_content_token",
        )
    return KEEP_CLEANUP_DECISION
