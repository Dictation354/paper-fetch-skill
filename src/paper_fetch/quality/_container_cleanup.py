"""HTML container evidence, staged read-only selection, and destructive cleanup."""

from __future__ import annotations

import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any, Literal

from bs4 import BeautifulSoup, Tag

from ..common_patterns import HEADING_TAG_PATTERN
from ..extraction.html.cleanup_policy import classify_availability_node
from ..extraction.html.container_selectors import ARTICLE_BODY_SELECTORS
from ..extraction.html.formula_rules import is_formula_script_node
from ..extraction.html.provider_rules import availability_rules_for_provider
from ..extraction.html.semantics import (
    BACK_MATTER_TOKENS,
    looks_like_explicit_body_container,
    node_identity_text,
    node_source_selector,
)
from ..extraction.html.shared import (
    class_tokens as _class_tokens,
)
from ..extraction.html.shared import (
    direct_child_tags as _direct_child_tags,
)
from ..extraction.html.signals import CHALLENGE_PATTERNS
from ..utils import normalize_text
from .html_profiles import site_rule_for_publisher

HTML_CONTAINER_SCORE_AVAILABILITY = "availability"
HTML_CONTAINER_SCORE_BROWSER_WORKFLOW = "browser_workflow"
HTML_CONTAINER_DROP_AVAILABILITY = "availability"
HTML_CONTAINER_DROP_BROWSER_WORKFLOW = "browser_workflow"
HTML_CONTAINER_BROWSER_WORKFLOW_FALLBACK_TAGS = ("article", "main", "body")
HTML_CONTAINER_BODY_SELECTORS = ARTICLE_BODY_SELECTORS
HtmlContainerScope = Literal["explicit_body", "article", "page"]
HTML_CONTAINER_SCOPE_EXPLICIT_BODY: HtmlContainerScope = "explicit_body"
HTML_CONTAINER_SCOPE_ARTICLE: HtmlContainerScope = "article"
HTML_CONTAINER_SCOPE_PAGE: HtmlContainerScope = "page"

_ARTICLE_TOKEN_RE = re.compile(r"(?:^|[\s_-])article(?:$|[\s_-])")
_HEADING_RE = re.compile(r"^h[1-6]$")


@dataclass(frozen=True)
class HtmlContainerEvidence:
    """Origin evidence for a selected HTML container.

    Provider extractors sometimes normalize a selected node into a synthetic
    ``<article>`` before quality assessment. Keeping the original scope here
    prevents that normalization from upgrading a page-level shell into an
    article-level full-text signal.
    """

    tag: str | None
    selector: str | None
    scope: HtmlContainerScope
    synthetic: bool = False


@dataclass(frozen=True)
class HtmlContainerSelectionPolicy:
    score_profile: str = HTML_CONTAINER_SCORE_AVAILABILITY
    fallback_tags: tuple[str, ...] = ()
    prefer_complete_ancestor: bool = False
    avoid_page_level_container: bool = False
    body_selectors: tuple[str, ...] = HTML_CONTAINER_BODY_SELECTORS
    abstract_node_finder: Callable[[Tag], list[Tag]] | None = None
    refine_selected_container: Callable[..., Any] | None = None


@dataclass(frozen=True)
class ContainerCleanupMode:
    """Explicit node-removal configuration for one cleanup responsibility."""

    browser_workflow: bool
    preserve_figure_media: bool


AVAILABILITY_CLEANUP_MODE = ContainerCleanupMode(
    browser_workflow=False,
    preserve_figure_media=False,
)
BROWSER_WORKFLOW_CLEANUP_MODE = ContainerCleanupMode(
    browser_workflow=True,
    preserve_figure_media=True,
)
_CLEANUP_MODES: Mapping[str, ContainerCleanupMode] = {
    HTML_CONTAINER_DROP_AVAILABILITY: AVAILABILITY_CLEANUP_MODE,
    HTML_CONTAINER_DROP_BROWSER_WORKFLOW: BROWSER_WORKFLOW_CLEANUP_MODE,
}


def extract_page_title(soup: BeautifulSoup) -> str | None:
    for selector in ("h1", "meta[property='og:title']", "title"):
        node = soup.select_one(selector)
        if node is None:
            continue
        if node.name == "meta":
            title = normalize_text(
                (getattr(node, "attrs", None) or {}).get("content", "")
            )
        else:
            title = normalize_text(node.get_text(" ", strip=True))
        if title:
            return title
    return None


def _has_selector_descendant(node: Tag, selectors: tuple[str, ...]) -> bool:
    for selector in selectors:
        try:
            if node.select_one(selector) is not None:
                return True
        except Exception:
            continue
    return False


def _matches_selector(node: Tag, selector: str) -> bool:
    try:
        return bool(node.css.match(selector))
    except Exception:
        return False


def html_container_evidence(
    node: Tag,
    *,
    policy: HtmlContainerSelectionPolicy | None = None,
    selector: str | None = None,
    scope: HtmlContainerScope | None = None,
    synthetic: bool = False,
) -> HtmlContainerEvidence:
    """Describe the original trust scope of a selected container."""
    active_policy = policy or HtmlContainerSelectionPolicy()
    node_name = normalize_text(node.name or "").lower() or None
    resolved_scope = scope
    if resolved_scope is None:
        if looks_like_explicit_body_container(node) or any(
            _matches_selector(node, candidate)
            for candidate in active_policy.body_selectors
        ):
            resolved_scope = HTML_CONTAINER_SCOPE_EXPLICIT_BODY
        elif node_name == "article" or _ARTICLE_TOKEN_RE.search(
            node_identity_text(node)
        ):
            resolved_scope = HTML_CONTAINER_SCOPE_ARTICLE
        else:
            resolved_scope = HTML_CONTAINER_SCOPE_PAGE
    return HtmlContainerEvidence(
        tag=node_name,
        selector=normalize_text(selector or node_source_selector(node)) or None,
        scope=resolved_scope,
        synthetic=synthetic,
    )


def score_browser_workflow_container(node: Tag) -> float:
    text = " ".join(node.stripped_strings)
    text_length = len(text)
    paragraph_count = len(node.find_all("p"))
    heading_count = len(node.find_all(HEADING_TAG_PATTERN))
    link_count = len(node.find_all("a"))
    score = text_length / 120.0
    score += paragraph_count * 6.0
    score += heading_count * 12.0
    score -= max(0, link_count - paragraph_count * 2) * 1.5
    lowered = text.lower()
    if any(pattern in lowered for pattern in CHALLENGE_PATTERNS):
        score -= 500
    if "abstract" in lowered:
        score += 20
    if "references" in lowered:
        score += 20
    return score


def score_availability_container(node: Tag) -> float:
    text_length = len(normalize_text(node.get_text(" ", strip=True)))
    heading_count = len(node.find_all(_HEADING_RE))
    paragraph_count = sum(
        1
        for child in node.find_all(["p", "div", "section", "article"])
        if normalize_text(child.get_text(" ", strip=True))
    )
    figure_count = len(node.find_all(["figure", "table"]))
    identity = node_identity_text(node)
    identity_bonus = 0.0
    if looks_like_explicit_body_container(node):
        identity_bonus += 400.0
    if normalize_text(node.name or "").lower() == "article" or _ARTICLE_TOKEN_RE.search(
        identity
    ):
        identity_bonus += 200.0
    if any(token in identity for token in BACK_MATTER_TOKENS):
        identity_bonus -= 120.0
    return float(
        text_length
        + heading_count * 200
        + paragraph_count * 40
        + figure_count * 20
        + identity_bonus
    )


_CONTAINER_SCORERS: Mapping[str, Callable[[Tag], float]] = {
    HTML_CONTAINER_SCORE_AVAILABILITY: score_availability_container,
    HTML_CONTAINER_SCORE_BROWSER_WORKFLOW: score_browser_workflow_container,
}


def score_container(
    node: Tag, *, score_profile: str = HTML_CONTAINER_SCORE_AVAILABILITY
) -> float:
    scorer = _CONTAINER_SCORERS.get(score_profile, score_availability_container)
    return scorer(node)


def container_completeness_score(
    node: Tag,
    *,
    abstract_node_finder: Callable[[Tag], list[Tag]] | None = None,
    body_selectors: tuple[str, ...] = HTML_CONTAINER_BODY_SELECTORS,
) -> int:
    score = 0
    node_name = normalize_text(node.name or "").lower()
    if isinstance(node.find("h1"), Tag) or node_name == "h1":
        score += 40
    if abstract_node_finder is not None:
        try:
            if abstract_node_finder(node):
                score += 40
        except Exception:
            pass
    if looks_like_explicit_body_container(node) or _has_selector_descendant(
        node, body_selectors
    ):
        score += 40
    if node_name == "article":
        score += 10
    elif node_name == "main":
        score += 5
    return score


def _prefer_complete_ancestor(
    node: Tag, score_key: Callable[[Tag], tuple[int, float]]
) -> Tag:
    best = node
    best_key = score_key(node)
    current = node.parent if isinstance(node.parent, Tag) else None
    depth = 0
    while isinstance(current, Tag) and depth < 8:
        if normalize_text(current.name or "").lower() == "html":
            break
        current_key = score_key(current)
        if current_key > best_key:
            best = current
            best_key = current_key
        current = current.parent if isinstance(current.parent, Tag) else None
        depth += 1
    return best


def prefer_complete_ancestor(
    node: Tag,
    *,
    score_profile: str = HTML_CONTAINER_SCORE_BROWSER_WORKFLOW,
    abstract_node_finder: Callable[[Tag], list[Tag]] | None = None,
    body_selectors: tuple[str, ...] = HTML_CONTAINER_BODY_SELECTORS,
) -> Tag:
    return _prefer_complete_ancestor(
        node,
        lambda candidate: (
            container_completeness_score(
                candidate,
                abstract_node_finder=abstract_node_finder,
                body_selectors=body_selectors,
            ),
            score_container(candidate, score_profile=score_profile),
        ),
    )


class _ReadOnlyScoreSnapshot:
    """Single-phase memoized scores for an unmutated DOM tree."""

    def __init__(
        self,
        *,
        score_fn: Callable[[Tag], float],
        completeness_fn: Callable[[Tag], int],
        ancestor_fn: Callable[[Tag, Callable[[Tag], tuple[int, float]]], Tag],
    ) -> None:
        self._score_fn = score_fn
        self._completeness_fn = completeness_fn
        self._ancestor_fn = ancestor_fn
        self._scores: dict[int, float] = {}
        self._completeness: dict[int, int] = {}
        self._ancestors: dict[int, Tag] = {}

    def score(self, node: Tag) -> float:
        identity = id(node)
        if identity not in self._scores:
            self._scores[identity] = self._score_fn(node)
        return self._scores[identity]

    def key(self, node: Tag) -> tuple[int, float]:
        identity = id(node)
        if identity not in self._completeness:
            self._completeness[identity] = self._completeness_fn(node)
        return self._completeness[identity], self.score(node)

    def ancestor(self, node: Tag) -> Tag:
        identity = id(node)
        if identity not in self._ancestors:
            self._ancestors[identity] = self._ancestor_fn(node, self.key)
        return self._ancestors[identity]


def _is_page_level_container(node: Tag | None) -> bool:
    if not isinstance(node, Tag):
        return False
    return normalize_text(node.name or "").lower() in {"html", "body"}


def _collect_container_candidates(
    soup: BeautifulSoup,
    candidate_selectors: list[str] | tuple[str, ...],
    fallback_tags: tuple[str, ...],
) -> list[Tag]:
    candidates: list[Tag] = []
    seen: set[int] = set()
    for selector in candidate_selectors:
        try:
            matches = soup.select(selector)
        except Exception:
            continue
        for match in matches:
            if not isinstance(match, Tag) or id(match) in seen:
                continue
            seen.add(id(match))
            candidates.append(match)
    if not candidates and fallback_tags:
        for node in soup.find_all(fallback_tags):
            if not isinstance(node, Tag) or id(node) in seen:
                continue
            seen.add(id(node))
            candidates.append(node)
    return candidates


def select_container(
    soup: BeautifulSoup,
    publisher: str | None,
    *,
    policy: HtmlContainerSelectionPolicy | None = None,
    site_rule_lookup: Callable[[str | None], Mapping[str, Any]] = (
        site_rule_for_publisher
    ),
    score_fn: Callable[..., float] = score_container,
    completeness_fn: Callable[..., int] = container_completeness_score,
    ancestor_fn: Callable[
        [Tag, Callable[[Tag], tuple[int, float]]], Tag
    ] = _prefer_complete_ancestor,
) -> Tag | None:
    active_policy = policy or HtmlContainerSelectionPolicy()
    candidates = _collect_container_candidates(
        soup,
        site_rule_lookup(publisher)["candidate_selectors"],
        active_policy.fallback_tags,
    )
    if not candidates:
        body = soup.body
        return body if isinstance(body, Tag) else None

    def raw_score(candidate: Tag) -> float:
        return score_fn(candidate, score_profile=active_policy.score_profile)

    def raw_completeness(candidate: Tag) -> int:
        return completeness_fn(
            candidate,
            abstract_node_finder=active_policy.abstract_node_finder,
            body_selectors=active_policy.body_selectors,
        )

    def new_snapshot() -> _ReadOnlyScoreSnapshot:
        return _ReadOnlyScoreSnapshot(
            score_fn=raw_score,
            completeness_fn=raw_completeness,
            ancestor_fn=ancestor_fn,
        )

    snapshot = new_snapshot()
    candidates.sort(key=snapshot.score, reverse=True)

    # Pure read-only path: reuse one immutable snapshot across ranking,
    # ancestor promotion, and non-page fallback tie-breaking.
    if active_policy.refine_selected_container is None:
        preferred = (
            snapshot.ancestor(candidates[0])
            if active_policy.prefer_complete_ancestor
            else candidates[0]
        )
        if not active_policy.avoid_page_level_container or not _is_page_level_container(
            preferred
        ):
            return preferred
        alternatives = [
            promoted
            for node in candidates
            if not _is_page_level_container(
                promoted := (
                    snapshot.ancestor(node)
                    if active_policy.prefer_complete_ancestor
                    else node
                )
            )
        ]
        return max(alternatives, key=snapshot.key) if alternatives else preferred

    # Mutating refiner path (used by provider workflows such as T&F): pass
    # live uncached scoring callbacks into each refiner, then build a fresh
    # post-mutation snapshot only if tie-breaking across alternatives is needed.
    def refine_with_live_dom(node: Tag) -> Tag:
        base_node = (
            ancestor_fn(
                node,
                lambda candidate: (raw_completeness(candidate), raw_score(candidate)),
            )
            if active_policy.prefer_complete_ancestor
            else node
        )
        assert active_policy.refine_selected_container is not None
        refined = active_policy.refine_selected_container(
            base_node,
            direct_child_tags=_direct_child_tags,
            class_tokens=_class_tokens,
            container_completeness_score=raw_completeness,
            score_container=raw_score,
        )
        return refined if isinstance(refined, Tag) else base_node

    preferred = refine_with_live_dom(candidates[0])
    if not active_policy.avoid_page_level_container or not _is_page_level_container(
        preferred
    ):
        return preferred

    alternatives = [
        alternative
        for node in candidates
        if not _is_page_level_container(alternative := refine_with_live_dom(node))
    ]
    if not alternatives:
        return preferred
    final_snapshot = new_snapshot()
    return max(alternatives, key=final_snapshot.key)


def _is_figure_media_node(node: Tag) -> bool:
    node_name = normalize_text(getattr(node, "name", "")).lower()
    if (
        node_name not in {"a", "img", "picture", "source"}
        and node.find(["img", "picture", "source"]) is None
    ):
        return False
    current: Any = node
    while isinstance(current, Tag):
        if normalize_text(getattr(current, "name", "")).lower() == "figure":
            return True
        current = current.parent
    return False


def _should_drop_node_for_mode(
    node: Tag,
    rules: Any,
    mode: ContainerCleanupMode,
    *,
    matched_selector: str | None = None,
) -> bool:
    if (
        matched_selector is None
        and mode.preserve_figure_media
        and _is_figure_media_node(node)
    ):
        return False
    decision = classify_availability_node(
        node,
        rules,
        browser_workflow=mode.browser_workflow,
        identity=node_identity_text(node),
        text=normalize_text(node.get_text(" ", strip=True)),
        matched_selector=matched_selector,
        is_mathml_script=is_formula_script_node(node),
    )
    return decision.action == "drop"


def should_drop_availability_node(node: Tag, publisher: str | None) -> bool:
    rules = availability_rules_for_provider(publisher).container_rules
    return _should_drop_node_for_mode(node, rules, AVAILABILITY_CLEANUP_MODE)


def should_drop_browser_workflow_node(node: Tag, publisher: str | None) -> bool:
    rules = availability_rules_for_provider(publisher).container_rules
    return _should_drop_node_for_mode(node, rules, BROWSER_WORKFLOW_CLEANUP_MODE)


def should_drop_node(
    node: Tag,
    publisher: str | None,
    *,
    drop_profile: str = HTML_CONTAINER_DROP_AVAILABILITY,
) -> bool:
    mode = _CLEANUP_MODES.get(drop_profile, AVAILABILITY_CLEANUP_MODE)
    rules = availability_rules_for_provider(publisher).container_rules
    return _should_drop_node_for_mode(node, rules, mode)


def _clean_container_with_mode(
    container: Tag, publisher: str | None, mode: ContainerCleanupMode
) -> Tag:
    rules = availability_rules_for_provider(publisher).container_rules
    for selector in rules.remove_selectors:
        try:
            matched_nodes = list(container.select(selector))
        except Exception:
            continue
        for node in matched_nodes:
            if isinstance(node, Tag) and _should_drop_node_for_mode(
                node, rules, mode, matched_selector=selector
            ):
                node.decompose()
    for node in list(container.find_all(True)):
        if _should_drop_node_for_mode(node, rules, mode):
            node.decompose()
    return container


def clean_availability_container(container: Tag, publisher: str | None) -> Tag:
    return _clean_container_with_mode(container, publisher, AVAILABILITY_CLEANUP_MODE)


def clean_browser_workflow_container(container: Tag, publisher: str | None) -> Tag:
    return _clean_container_with_mode(
        container, publisher, BROWSER_WORKFLOW_CLEANUP_MODE
    )


def clean_container(
    container: Tag,
    publisher: str | None,
    *,
    drop_profile: str = HTML_CONTAINER_DROP_AVAILABILITY,
) -> Tag:
    mode = _CLEANUP_MODES.get(drop_profile, AVAILABILITY_CLEANUP_MODE)
    return _clean_container_with_mode(container, publisher, mode)
