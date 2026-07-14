"""Shared HTML full-text availability diagnostics and structure analysis."""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from typing import Any, Literal
from collections.abc import Callable, Mapping

from ..common_patterns import HEADING_TAG_PATTERN
from ..extraction.html.container_selectors import ARTICLE_BODY_SELECTORS
from ..extraction.html.cleanup_policy import classify_availability_node
from ..extraction.html._runtime import body_metrics, has_sufficient_article_body
from ..extraction.html.front_matter import ARTICLE_TYPE_FRONT_MATTER_PREFIXES
from ..extraction.html.formula_rules import is_formula_script_node
from ..extraction.html.provider_rules import (
    availability_rules_for_provider,
    front_matter_footer_prefixes,
)
from ..extraction.html.section_scan import SectionScanState
from ..extraction.html.signals import (
    CHALLENGE_PATTERNS,
    contains_access_gate_text,
    detect_html_access_signals,
    html_failure_message,
    matched_access_gate_patterns,
)
from ..extraction.html.parsing import choose_parser
from ..extraction.html.semantics import (
    BACK_MATTER_TOKENS,
    category_for_section_hint_kind,
    classify_html_paragraph,
    coerce_html_section_hints,
    container_has_explicit_body_container,
    heading_category,
    iter_html_blocks,
    looks_like_explicit_body_container,
    match_next_html_section_hint,
    node_identity_text,
    node_source_selector,
    normalize_heading,
)
from ..extraction.html.shared import (
    class_tokens as _class_tokens,
    direct_child_tags as _direct_child_tags,
)
from ..models import classify_article_content, filtered_body_sections
from ..utils import normalize_text
from .html_profiles import (
    looks_like_abstract_redirect,
    site_rule_for_publisher,
)
from .html_signals import (
    AvailabilityOverrideState,
    AvailabilityOverrides,
    apply_availability_overrides,
    default_positive_signals,
    evaluate_datalayer_blocking_signals,
    evaluate_datalayer_positive_signals,
    evaluate_text_marker_blocking_signals,
    evaluate_text_marker_positive_signals,
)
from .reason_codes import (
    ABSTRACT_ONLY,
    ACCESS_PAGE_URL,
    BODY_SUFFICIENT,
    CITATION_ABSTRACT_HTML_URL,
    CLOUDFLARE_CHALLENGE,
    DATA_ARTICLE_ACCESS_ABSTRACT,
    DATA_ARTICLE_ACCESS_NO,
    FINAL_URL_MATCHES_CITATION_ABSTRACT_HTML_URL,
    FULLTEXT,
    INSUFFICIENT_BODY,
    METADATA_ONLY,
    PUBLISHER_PAYWALL,
    STRUCTURED_ARTICLE_NOT_FULLTEXT,
    STRUCTURED_MISSING_BODY_SECTIONS,
    WT_ABSTRACT_PAGE_TYPE,
)

from bs4 import BeautifulSoup, Tag

# Narrative labels relax structural availability thresholds for short
# commentary/news-style content. They are not front-matter cleanup tokens; the
# provider cleanup layer keeps its own article-type chrome vocabulary.
NARRATIVE_ARTICLE_TYPES = {
    "review",
    "perspective",
    "commentary",
    "analysis",
    "news",
    "research briefing",
    "editorial",
}
NARRATIVE_BODY_RUN_MIN_CHARS = 400
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


@dataclass(frozen=True)
class HtmlContainerEvidence:
    """Origin evidence for a selected HTML container.

    Provider extractors sometimes normalize a selected node into a synthetic
    ``<article>`` before quality assessment.  Keeping the original scope here
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
    drop_profile: str = HTML_CONTAINER_DROP_AVAILABILITY
    fallback_tags: tuple[str, ...] = ()
    prefer_complete_ancestor: bool = False
    avoid_page_level_container: bool = False
    body_selectors: tuple[str, ...] = HTML_CONTAINER_BODY_SELECTORS
    abstract_node_finder: Callable[[Tag], list[Tag]] | None = None
    refine_selected_container: Callable[..., Any] | None = None


@dataclass
class StructuredBodyAnalysis:
    body_marker_present: bool = False
    substantive_article_container: bool = False
    explicit_body_container: bool = False
    substantive_body_container: bool = False
    post_abstract_body_run: bool = False
    narrative_article_type: bool = False
    paywall_text_outside_body_ignored: bool = False
    body_run_paragraph_count: int = 0
    body_run_char_count: int = 0
    body_paragraph_count: int = 0
    body_candidate_text: str = ""
    paywall_gate_detected: bool = False
    page_has_paywall_text: bool = False
    container_has_paywall_text: bool = False
    access_gate_markers: list[str] = field(default_factory=list)
    provider_hard_negative_signals: list[str] = field(default_factory=list)
    provider_abstract_only_hints: list[str] = field(default_factory=list)
    provider_blocking_fallback_signals: list[str] = field(default_factory=list)


@dataclass
class FulltextAvailabilityDiagnostics:
    accepted: bool
    reason: str
    content_kind: str
    blocking_fallback_signals: list[str] = field(default_factory=list)
    hard_negative_signals: list[str] = field(default_factory=list)
    strong_positive_signals: list[str] = field(default_factory=list)
    soft_positive_signals: list[str] = field(default_factory=list)
    body_metrics: dict[str, Any] = field(default_factory=dict)
    figure_count: int = 0
    title: str | None = None
    container_tag: str | None = None
    container_text_length: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def extract_page_title(soup: BeautifulSoup) -> str | None:
    for selector in ["h1", "meta[property='og:title']", "title"]:
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


def _sentence_count(text: str) -> int:
    return len(
        [
            item
            for item in re.split(r"(?<=[.!?])\s+", normalize_text(text))
            if normalize_text(item)
        ]
    )


def _is_substantial_prose(text: str) -> bool:
    normalized = normalize_text(text)
    return len(normalized) >= 80 or _sentence_count(normalized) >= 2


def _is_mathml_script(node: Tag) -> bool:
    return is_formula_script_node(node)


def _normalized_page_text(html_text: str) -> str:
    soup = BeautifulSoup(html_text, choose_parser())
    return normalize_text(" ".join(soup.stripped_strings))


def _extract_article_type(
    metadata: Mapping[str, Any] | None,
    *,
    provider: str | None = None,
    html_text: str | None = None,
) -> str | None:
    del provider
    metadata_map = dict(metadata or {})
    for key in ("article_type", "type", "subtype"):
        value = normalize_text(metadata_map.get(key))
        if value:
            return value
    if not html_text:
        return None
    soup = BeautifulSoup(html_text, choose_parser())
    for selector in (
        "meta[name='citation_article_type']",
        "meta[property='article:section']",
        "[data-article-type]",
    ):
        node = soup.select_one(selector)
        if node is None:
            continue
        if node.name == "meta":
            value = normalize_text(
                (getattr(node, "attrs", None) or {}).get("content", "")
            )
        else:
            attrs = getattr(node, "attrs", None) or {}
            value = normalize_text(
                str(attrs.get("data-article-type") or node.get_text(" ", strip=True))
            )
        if value:
            return value
    return None


def _is_narrative_article_type(article_type: str | None) -> bool:
    normalized = normalize_heading(article_type or "")
    return normalized in NARRATIVE_ARTICLE_TYPES


def _final_url_looks_like_access_page(final_url: str | None) -> bool:
    normalized = normalize_text(final_url or "").lower()
    if not normalized:
        return False
    return any(
        token in normalized
        for token in (
            "/abstract",
            "/summary",
            "/doi/abs/",
            "/article/access",
            "/access",
            "/article-abstract",
        )
    )


def _detect_html_hard_negative_signals_impl(
    title: str,
    text: str,
    response_status: int | None,
    *,
    requested_url: str | None = None,
    final_url: str | None = None,
    include_paywall_text: bool = True,
    provider_metadata: Mapping[str, Any] | None = None,
) -> list[str]:
    redirected_to_abstract = bool(
        requested_url and looks_like_abstract_redirect(requested_url, final_url)
    )
    return detect_html_access_signals(
        title,
        text,
        response_status,
        redirected_to_abstract=redirected_to_abstract,
        include_paywall_text=include_paywall_text,
        explicit_no_access=bool(
            provider_metadata and provider_metadata.get("explicit_no_access")
        ),
    )


def detect_html_hard_negative_signals(
    title: str,
    text: str,
    response_status: int | None,
    *,
    requested_url: str | None = None,
    final_url: str | None = None,
) -> list[str]:
    return _detect_html_hard_negative_signals_impl(
        title,
        text,
        response_status,
        requested_url=requested_url,
        final_url=final_url,
        include_paywall_text=True,
    )


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
        elif node_name == "article" or re.search(
            r"(?:^|[\s_-])article(?:$|[\s_-])", node_identity_text(node)
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


def _browser_workflow_score_container(node: Tag) -> float:
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


def score_container(
    node: Tag, *, score_profile: str = HTML_CONTAINER_SCORE_AVAILABILITY
) -> float:
    if score_profile == HTML_CONTAINER_SCORE_BROWSER_WORKFLOW:
        return _browser_workflow_score_container(node)
    text_length = len(normalize_text(node.get_text(" ", strip=True)))
    heading_count = len(node.find_all(re.compile(r"^h[1-6]$")))
    paragraph_count = len(
        [
            child
            for child in node.find_all(["p", "div", "section", "article"])
            if normalize_text(child.get_text(" ", strip=True))
        ]
    )
    figure_count = len(node.find_all(["figure", "table"]))
    identity = node_identity_text(node)
    identity_bonus = 0.0
    if looks_like_explicit_body_container(node):
        identity_bonus += 400.0
    if normalize_text(node.name or "").lower() == "article" or re.search(
        r"(?:^|[\s_-])article(?:$|[\s_-])", identity
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


def container_completeness_score(
    node: Tag,
    *,
    abstract_node_finder: Callable[[Tag], list[Tag]] | None = None,
    body_selectors: tuple[str, ...] = HTML_CONTAINER_BODY_SELECTORS,
) -> int:
    score = 0
    if (
        isinstance(node.find("h1"), Tag)
        or normalize_text(node.name or "").lower() == "h1"
    ):
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
    if normalize_text(node.name or "").lower() == "article":
        score += 10
    if normalize_text(node.name or "").lower() == "main":
        score += 5
    return score


def prefer_complete_ancestor(
    node: Tag,
    *,
    score_profile: str = HTML_CONTAINER_SCORE_BROWSER_WORKFLOW,
    abstract_node_finder: Callable[[Tag], list[Tag]] | None = None,
    body_selectors: tuple[str, ...] = HTML_CONTAINER_BODY_SELECTORS,
) -> Tag:
    best = node
    best_key = (
        container_completeness_score(
            node,
            abstract_node_finder=abstract_node_finder,
            body_selectors=body_selectors,
        ),
        score_container(node, score_profile=score_profile),
    )
    current = node.parent if isinstance(node.parent, Tag) else None
    depth = 0
    while isinstance(current, Tag) and depth < 8:
        if normalize_text(current.name or "").lower() == "html":
            break
        current_key = (
            container_completeness_score(
                current,
                abstract_node_finder=abstract_node_finder,
                body_selectors=body_selectors,
            ),
            score_container(current, score_profile=score_profile),
        )
        if current_key > best_key:
            best = current
            best_key = current_key
        current = current.parent if isinstance(current.parent, Tag) else None
        depth += 1
    return best


def _is_page_level_container(node: Tag | None) -> bool:
    if not isinstance(node, Tag):
        return False
    return normalize_text(node.name or "").lower() in {"html", "body"}


def _refine_selected_container(node: Tag, policy: HtmlContainerSelectionPolicy) -> Tag:
    refined_node = (
        prefer_complete_ancestor(
            node,
            score_profile=policy.score_profile,
            abstract_node_finder=policy.abstract_node_finder,
            body_selectors=policy.body_selectors,
        )
        if policy.prefer_complete_ancestor
        else node
    )
    if policy.refine_selected_container is None:
        return refined_node
    refined = policy.refine_selected_container(
        refined_node,
        direct_child_tags=_direct_child_tags,
        class_tokens=_class_tokens,
        container_completeness_score=lambda candidate: container_completeness_score(
            candidate,
            abstract_node_finder=policy.abstract_node_finder,
            body_selectors=policy.body_selectors,
        ),
        score_container=lambda candidate: score_container(
            candidate, score_profile=policy.score_profile
        ),
    )
    if isinstance(refined, Tag):
        return refined
    return refined_node


def select_best_container(
    soup: BeautifulSoup,
    publisher: str | None,
    *,
    policy: HtmlContainerSelectionPolicy | None = None,
):
    active_policy = policy or HtmlContainerSelectionPolicy()
    selectors = site_rule_for_publisher(publisher)["candidate_selectors"]
    candidates: list[Tag] = []
    seen: set[int] = set()
    for selector in selectors:
        try:
            matches = soup.select(selector)
        except Exception:
            continue
        for match in matches:
            if not isinstance(match, Tag) or id(match) in seen:
                continue
            seen.add(id(match))
            candidates.append(match)
    if not candidates:
        for node in soup.find_all(active_policy.fallback_tags):
            if not isinstance(node, Tag) or id(node) in seen:
                continue
            seen.add(id(node))
            candidates.append(node)
    if not candidates:
        body = soup.body
        return body if isinstance(body, Tag) else None

    candidates.sort(
        key=lambda node: score_container(
            node, score_profile=active_policy.score_profile
        ),
        reverse=True,
    )
    preferred = _refine_selected_container(candidates[0], active_policy)
    if not active_policy.avoid_page_level_container or not _is_page_level_container(
        preferred
    ):
        return preferred

    alternative_nodes: list[Tag] = []
    for node in candidates:
        alternative = _refine_selected_container(node, active_policy)
        if _is_page_level_container(alternative):
            continue
        alternative_nodes.append(alternative)
    if not alternative_nodes:
        return preferred
    return max(
        alternative_nodes,
        key=lambda node: (
            container_completeness_score(
                node,
                abstract_node_finder=active_policy.abstract_node_finder,
                body_selectors=active_policy.body_selectors,
            ),
            score_container(node, score_profile=active_policy.score_profile),
        ),
    )


def _should_drop_browser_workflow_node(node: Tag, publisher: str | None) -> bool:
    rules = availability_rules_for_provider(publisher).container_rules
    decision = classify_availability_node(
        node,
        rules,
        browser_workflow=True,
        identity=node_identity_text(node),
        text=normalize_text(node.get_text(" ", strip=True)),
        is_mathml_script=_is_mathml_script(node),
    )
    return decision.action == "drop"


def should_drop_node(
    node: Tag,
    publisher: str | None,
    *,
    drop_profile: str = HTML_CONTAINER_DROP_AVAILABILITY,
) -> bool:
    if drop_profile == HTML_CONTAINER_DROP_BROWSER_WORKFLOW and _is_figure_media_node(
        node
    ):
        return False
    if drop_profile == HTML_CONTAINER_DROP_BROWSER_WORKFLOW:
        return _should_drop_browser_workflow_node(node, publisher)
    rules = availability_rules_for_provider(publisher).container_rules
    identity = node_identity_text(node)
    text = normalize_text(node.get_text(" ", strip=True))
    decision = classify_availability_node(
        node,
        rules,
        identity=identity,
        text=text,
        is_mathml_script=_is_mathml_script(node),
    )
    if decision.action == "drop":
        return True
    try:
        return any(
            classify_availability_node(
                node,
                rules,
                identity=identity,
                text=text,
                matched_selector=selector,
                is_mathml_script=_is_mathml_script(node),
            ).action
            == "drop"
            for selector in rules.remove_selectors
            if node.select_one(selector) is node
        )
    except Exception:
        return False


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


def clean_container(
    container: Tag,
    publisher: str | None,
    *,
    drop_profile: str = HTML_CONTAINER_DROP_AVAILABILITY,
) -> Tag:
    rules = availability_rules_for_provider(publisher).container_rules
    browser_workflow = drop_profile == HTML_CONTAINER_DROP_BROWSER_WORKFLOW
    for selector in rules.remove_selectors:
        try:
            for node in list(container.select(selector)):
                if isinstance(node, Tag):
                    decision = classify_availability_node(
                        node,
                        rules,
                        browser_workflow=browser_workflow,
                        identity=node_identity_text(node),
                        text=normalize_text(node.get_text(" ", strip=True)),
                        matched_selector=selector,
                        is_mathml_script=_is_mathml_script(node),
                    )
                    if decision.action == "drop":
                        node.decompose()
        except Exception:
            continue
    for node in list(container.find_all(True)):
        if should_drop_node(node, publisher, drop_profile=drop_profile):
            node.decompose()
    return container


def _looks_like_front_matter_paragraph(text: str, *, title: str | None = None) -> bool:
    normalized = normalize_text(text)
    lowered = normalized.lower()
    if not lowered:
        return False
    if title and lowered == normalize_text(title).lower():
        return True
    if title:
        compact_text = re.sub(r"\s+", "", lowered)
        compact_title = re.sub(r"\s+", "", normalize_text(title).lower())
        if compact_title and compact_text.endswith(compact_title):
            for prefix in ARTICLE_TYPE_FRONT_MATTER_PREFIXES:
                if compact_text.startswith(re.sub(r"\s+", "", prefix)):
                    return True
    if any(lowered.startswith(prefix) for prefix in front_matter_footer_prefixes()):
        return True
    return any(
        token in lowered
        for token in (
            "published",
            "accepted",
            "received",
            "author information",
            "authors info",
            "citation",
            "view options",
            "metrics & citations",
        )
    )


def _looks_like_access_gate_text(text: str) -> bool:
    return contains_access_gate_text(text)


def _run_candidate_barrier(kind: str) -> bool:
    return kind in {
        "front_matter",
        "abstract",
        "references_or_back_matter",
        "ancillary",
        "data_availability",
        "code_availability",
    }


def _availability_section_scan_state() -> SectionScanState:
    return SectionScanState(
        enabled_states=frozenset(
            {
                "body",
                "abstract",
                "back_matter",
                "front_matter",
                "data_availability",
                "auxiliary",
            }
        )
    )


def _substantive_explicit_body_container(container: Tag) -> bool:
    candidates = [
        node
        for node in (container, *container.find_all(True))
        if isinstance(node, Tag) and looks_like_explicit_body_container(node)
    ]
    for candidate in candidates:
        paragraphs = [
            normalize_text(node.get_text(" ", strip=True))
            for node in candidate.find_all("p")
            if isinstance(node, Tag)
        ]
        if any(_is_substantial_prose(text) for text in paragraphs):
            return True
        if not paragraphs and _is_substantial_prose(
            normalize_text(candidate.get_text(" ", strip=True))
        ):
            return True
    return False


def _substantive_article_container(container: Tag) -> bool:
    candidates = (
        [container]
        if normalize_text(str(container.name or "")).lower() == "article"
        else []
    )
    candidates.extend(
        node for node in container.find_all("article") if isinstance(node, Tag)
    )
    return any(
        _is_substantial_prose(normalize_text(node.get_text(" ", strip=True)))
        for node in candidates
    )


def _apply_availability_override_policy(
    *,
    provider: str | None,
    soup: BeautifulSoup,
    analysis: StructuredBodyAnalysis,
    final_url: str | None,
    metadata: Mapping[str, Any] | None,
) -> None:
    policy = availability_rules_for_provider(provider)
    if policy.overrides is None:
        return
    state = AvailabilityOverrideState(
        final_url=final_url,
        metadata=metadata,
        soup=soup,
        structure=analysis,
    )
    apply_availability_overrides(state, policy.overrides)
    analysis.provider_hard_negative_signals = _dedupe_signals(
        state.hard_negative_signals or []
    )
    analysis.provider_abstract_only_hints = _dedupe_signals(
        state.abstract_only_hints or []
    )
    analysis.provider_blocking_fallback_signals = _dedupe_signals(
        state.blocking_fallback_signals or []
    )


def _evaluate_provider_positive_policy_signals(
    provider: str | None, html_text: str
) -> tuple[list[str], list[str], list[str]]:
    policy = availability_rules_for_provider(provider)
    strong, soft, abstract_only = default_positive_signals(html_text)
    if policy.datalayer_signal_set is not None:
        d_strong, d_soft, d_abstract = evaluate_datalayer_positive_signals(
            html_text, policy.datalayer_signal_set
        )
        strong.extend(d_strong)
        soft.extend(d_soft)
        abstract_only.extend(d_abstract)
    if policy.text_marker_signal_set is not None:
        t_strong, t_soft, t_abstract = evaluate_text_marker_positive_signals(
            html_text, policy.text_marker_signal_set
        )
        strong.extend(t_strong)
        soft.extend(t_soft)
        abstract_only.extend(t_abstract)
    return (
        _dedupe_signals(strong),
        _dedupe_signals(soft),
        _dedupe_signals(abstract_only),
    )


def _evaluate_provider_blocking_policy_signals(
    provider: str | None, html_text: str
) -> list[str]:
    policy = availability_rules_for_provider(provider)
    signals: list[str] = []
    if policy.datalayer_signal_set is not None:
        signals.extend(
            evaluate_datalayer_blocking_signals(html_text, policy.datalayer_signal_set)
        )
    if policy.text_marker_signal_set is not None:
        signals.extend(
            evaluate_text_marker_blocking_signals(
                html_text, policy.text_marker_signal_set
            )
        )
    if policy.overrides is not None and policy.overrides.empty_shell_rules:
        state = AvailabilityOverrideState(
            soup=BeautifulSoup(html_text, choose_parser()),
            structure=StructuredBodyAnalysis(),
        )
        apply_availability_overrides(
            state,
            AvailabilityOverrides(empty_shell_rules=policy.overrides.empty_shell_rules),
        )
        signals.extend(state.blocking_fallback_signals or [])
    return _dedupe_signals(signals)


def _analyze_html_structure(
    html_text: str,
    *,
    provider: str | None,
    title: str | None,
    metadata: Mapping[str, Any] | None,
    final_url: str | None,
) -> tuple[StructuredBodyAnalysis, HtmlContainerEvidence | None, int | None]:
    analysis = StructuredBodyAnalysis(
        narrative_article_type=_is_narrative_article_type(
            _extract_article_type(metadata, provider=provider, html_text=html_text)
        )
    )

    soup = BeautifulSoup(html_text, choose_parser())
    container = select_best_container(soup, provider)
    if container is None:
        _apply_availability_override_policy(
            provider=provider,
            soup=soup,
            analysis=analysis,
            final_url=final_url,
            metadata=metadata,
        )
        return analysis, None, None

    clean_container(container, provider)
    container_evidence = html_container_evidence(container)
    analysis.body_marker_present = container_has_explicit_body_container(container)
    analysis.substantive_article_container = _substantive_article_container(container)
    analysis.substantive_body_container = _substantive_explicit_body_container(
        container
    )
    analysis.explicit_body_container = analysis.substantive_body_container
    container_text = normalize_text(container.get_text(" ", strip=True))
    page_text = _normalized_page_text(html_text)
    analysis.page_has_paywall_text = contains_access_gate_text(page_text)
    analysis.container_has_paywall_text = contains_access_gate_text(container_text)

    blocks = iter_html_blocks(container)
    body_chunks: list[str] = []
    normalized_title_heading = normalize_heading(title or "")
    state = _availability_section_scan_state()

    for block in blocks:
        if block["kind"] == "marker":
            analysis.body_marker_present = True
            continue

        node = block["node"]
        text = block["text"]
        access_gate_markers = matched_access_gate_patterns(text)
        if block["kind"] == "heading":
            if (
                normalized_title_heading
                and normalize_heading(text) == normalized_title_heading
            ):
                state.transition("front_matter", is_heading=False)
                state.reset_body_run()
                continue
            category = heading_category(
                normalize_text(node.name or "").lower(), text, title=title
            )
        elif block["kind"] == "figure_or_table":
            category = "figure_or_table"
        else:
            category = classify_html_paragraph(
                node,
                text,
                title=title,
                in_back_matter=state.in_back_matter,
                in_front_matter=state.in_front_matter,
                in_abstract=state.in_abstract,
                in_data_availability=state.in_data_availability,
                in_auxiliary=state.in_auxiliary,
                looks_like_front_matter_paragraph=lambda value: (
                    _looks_like_front_matter_paragraph(value, title=title)
                ),
                is_substantial_prose=_is_substantial_prose,
                looks_like_access_gate_text=_looks_like_access_gate_text,
            )
        if access_gate_markers:
            analysis.access_gate_markers.extend(access_gate_markers)

        if category == "abstract":
            state.transition(category, is_heading=block["kind"] == "heading")
            state.reset_body_run()
            continue
        if category == "references_or_back_matter":
            state.transition(category, is_heading=block["kind"] == "heading")
            state.reset_body_run()
            continue
        if category in {"data_availability", "code_availability"}:
            state.transition(category, is_heading=block["kind"] == "heading")
            state.reset_body_run()
            continue
        if category == "front_matter":
            state.transition(category, is_heading=block["kind"] == "heading")
            state.reset_body_run()
            continue
        if category == "ancillary":
            state.transition(category, is_heading=block["kind"] == "heading")
            state.reset_body_run()
            continue
        if category == "body_heading":
            state.transition(category, is_heading=block["kind"] == "heading")
            continue
        if category == "figure_or_table":
            continue
        if category != "body_paragraph":
            if _run_candidate_barrier(category):
                state.reset_body_run()
            continue

        body_chunks.append(text)
        state.record_body_paragraph(text_len=len(normalize_text(text)))
        analysis.body_paragraph_count = state.body_paragraph_count
        analysis.body_run_paragraph_count = state.body_run_paragraph_count
        analysis.body_run_char_count = state.body_run_char_count
        if state.abstract_seen and state.body_heading_after_abstract:
            analysis.post_abstract_body_run = True

    analysis.body_candidate_text = "\n\n".join(body_chunks)
    analysis.paywall_text_outside_body_ignored = (
        analysis.page_has_paywall_text
        and not analysis.container_has_paywall_text
        and analysis.body_paragraph_count > 0
    )
    analysis.paywall_gate_detected = analysis.body_paragraph_count == 0 and (
        analysis.container_has_paywall_text
        or _final_url_looks_like_access_page(final_url)
    )
    analysis.access_gate_markers = _dedupe_signals(analysis.access_gate_markers)
    _apply_availability_override_policy(
        provider=provider,
        soup=soup,
        analysis=analysis,
        final_url=final_url,
        metadata=metadata,
    )
    return analysis, container_evidence, len(" ".join(container.stripped_strings))


def _analyze_markdown_structure(
    markdown_text: str,
    *,
    metadata: Mapping[str, Any] | None,
    title: str | None,
    section_hints: Any = None,
) -> StructuredBodyAnalysis:
    analysis = StructuredBodyAnalysis(
        narrative_article_type=_is_narrative_article_type(
            _extract_article_type(metadata)
        )
    )
    blocks = [
        normalize_text(block)
        for block in re.split(r"\n\s*\n", markdown_text)
        if normalize_text(block)
    ]
    normalized_title_heading = normalize_heading(title or "")
    coerced_section_hints = coerce_html_section_hints(section_hints)
    state = _availability_section_scan_state()
    body_chunks: list[str] = []
    section_hint_index = 0

    for block in blocks:
        stripped = block.strip()
        is_heading = stripped.startswith("#")
        access_gate_markers = matched_access_gate_patterns(block)
        if is_heading:
            match = re.match(r"^(#+)\s*(.*)$", stripped)
            heading = normalize_text(match.group(2) if match else stripped)
            level = len(match.group(1)) if match else 2
            if (
                normalized_title_heading
                and normalize_heading(heading) == normalized_title_heading
            ):
                state.transition("front_matter", is_heading=False)
                state.reset_body_run()
                continue
            matched_hint, next_hint_index = match_next_html_section_hint(
                coerced_section_hints, section_hint_index, heading
            )
            if matched_hint is not None:
                section_hint_index = next_hint_index
                category = category_for_section_hint_kind(matched_hint["kind"])
            else:
                category = heading_category(f"h{min(level, 6)}", heading, title=title)
        else:
            category = (
                "body_paragraph"
                if _is_substantial_prose(block)
                and not _looks_like_front_matter_paragraph(block, title=title)
                else "front_matter"
            )
            if state.in_back_matter:
                category = "references_or_back_matter"
            elif state.in_front_matter:
                category = "front_matter"
            elif state.in_data_availability:
                category = "data_availability"
            elif state.in_abstract:
                category = "abstract"
            elif state.in_auxiliary:
                category = "ancillary"
            elif _looks_like_access_gate_text(block):
                category = "ancillary"
        if access_gate_markers:
            analysis.access_gate_markers.extend(access_gate_markers)

        if category == "abstract":
            state.transition(category, is_heading=is_heading)
            state.reset_body_run()
            continue
        if category == "references_or_back_matter":
            state.transition(category, is_heading=is_heading)
            state.reset_body_run()
            continue
        if category in {"data_availability", "code_availability"}:
            state.transition(category, is_heading=is_heading)
            state.reset_body_run()
            continue
        if category == "front_matter":
            state.transition(category, is_heading=is_heading)
            state.reset_body_run()
            continue
        if category == "ancillary":
            state.transition(category, is_heading=is_heading)
            state.reset_body_run()
            continue
        if category == "body_heading":
            state.transition(category, is_heading=is_heading)
            continue
        if category != "body_paragraph":
            continue

        body_chunks.append(block)
        state.record_body_paragraph(text_len=len(normalize_text(block)))
        analysis.body_paragraph_count = state.body_paragraph_count
        analysis.body_run_paragraph_count = state.body_run_paragraph_count
        analysis.body_run_char_count = state.body_run_char_count
        if state.abstract_seen and state.body_heading_after_abstract:
            analysis.post_abstract_body_run = True

    analysis.body_candidate_text = "\n\n".join(body_chunks)
    analysis.access_gate_markers = _dedupe_signals(analysis.access_gate_markers)
    return analysis


def _structure_accepts_fulltext(analysis: StructuredBodyAnalysis) -> bool:
    if (
        analysis.explicit_body_container
        and analysis.body_run_paragraph_count >= 1
        and analysis.body_run_char_count >= 80
    ):
        return True
    if (
        analysis.substantive_article_container
        and analysis.post_abstract_body_run
        and analysis.body_run_paragraph_count >= 1
        and analysis.body_run_char_count >= 80
    ):
        return True
    if analysis.post_abstract_body_run and analysis.body_run_paragraph_count >= 2:
        return True
    if analysis.body_run_paragraph_count >= 3:
        return True
    if analysis.narrative_article_type and (
        analysis.body_run_paragraph_count >= 2
        or (
            analysis.explicit_body_container
            and analysis.body_run_char_count >= NARRATIVE_BODY_RUN_MIN_CHARS
        )
    ):
        return True
    return False


def availability_failure_message(diagnostics: FulltextAvailabilityDiagnostics) -> str:
    if diagnostics.reason in {
        STRUCTURED_ARTICLE_NOT_FULLTEXT,
        STRUCTURED_MISSING_BODY_SECTIONS,
    }:
        return html_failure_message(diagnostics.reason)
    return html_failure_message(diagnostics.reason)


def _dedupe_signals(values: list[str]) -> list[str]:
    return list(dict.fromkeys(value for value in values if value))


_IOP_RESIDUAL_CHALLENGE_SIGNALS = frozenset(
    {
        CLOUDFLARE_CHALLENGE,
        "iop_radware_challenge",
        "iop_captcha_challenge",
    }
)


def _residual_challenge_signals_ignored_by_loaded_body(
    provider: str | None,
    structure: StructuredBodyAnalysis,
    *,
    body_ok: bool,
) -> frozenset[str]:
    normalized_provider = normalize_text(provider).lower()
    if normalized_provider != "iop" or not body_ok:
        return frozenset()
    if not structure.explicit_body_container or not structure.post_abstract_body_run:
        return frozenset()
    if (
        structure.body_run_char_count < NARRATIVE_BODY_RUN_MIN_CHARS
        and structure.body_paragraph_count < 1
    ):
        return frozenset()
    return _IOP_RESIDUAL_CHALLENGE_SIGNALS


def _diagnostics_content_kind(
    *,
    body_ok: bool,
    has_abstract: bool,
    blocking_fallback_signals: list[str] | None = None,
) -> str:
    if blocking_fallback_signals:
        return ABSTRACT_ONLY if has_abstract else METADATA_ONLY
    if body_ok:
        return FULLTEXT
    if has_abstract:
        return ABSTRACT_ONLY
    return METADATA_ONLY


def _normalized_text_field(value: Any) -> str:
    return normalize_text(value) if isinstance(value, str) else ""


def _dom_access_hints(
    html_text: str,
    *,
    provider: str | None,
    structure: StructuredBodyAnalysis,
    final_url: str | None,
    metadata: Mapping[str, Any] | None,
) -> tuple[list[str], list[str], list[str]]:
    hard_negative_signals: list[str] = []
    abstract_only_hints: list[str] = []
    blocking_fallback_signals: list[str] = []
    soup = BeautifulSoup(html_text, choose_parser())
    if soup.select_one(".accessDenialWidget"):
        hard_negative_signals.append(PUBLISHER_PAYWALL)
        blocking_fallback_signals.append(PUBLISHER_PAYWALL)
    if _final_url_looks_like_access_page(final_url):
        abstract_only_hints.append(ACCESS_PAGE_URL)
        blocking_fallback_signals.append(ACCESS_PAGE_URL)
    for node in soup.select("[data-article-access], [data-article-access-type]"):
        attrs = getattr(node, "attrs", None) or {}
        access_value = normalize_text(
            str(attrs.get("data-article-access") or "")
        ).lower()
        access_type = normalize_text(
            str(attrs.get("data-article-access-type") or "")
        ).lower()
        values = [access_value, access_type]
        joined = " ".join(value.lower() for value in values if value)
        if access_value == "no":
            blocking_fallback_signals.append(DATA_ARTICLE_ACCESS_NO)
        if any(
            token in joined
            for token in {"abstract", "summary", "preview", "teaser", "limited"}
        ):
            abstract_only_hints.append(DATA_ARTICLE_ACCESS_ABSTRACT)
            blocking_fallback_signals.append(DATA_ARTICLE_ACCESS_ABSTRACT)
        if any(
            token in joined
            for token in {"denied", "subscription", "restricted", "paywall"}
        ):
            hard_negative_signals.append(PUBLISHER_PAYWALL)
            blocking_fallback_signals.append(PUBLISHER_PAYWALL)
    wt_node = soup.select_one("meta[name='WT.z_cg_type']")
    if wt_node is not None:
        wt_value = normalize_text(
            str((getattr(wt_node, "attrs", None) or {}).get("content") or "")
        ).lower()
        if "abstract" in wt_value or "summary" in wt_value:
            abstract_only_hints.append(WT_ABSTRACT_PAGE_TYPE)
            blocking_fallback_signals.append(WT_ABSTRACT_PAGE_TYPE)
    citation_abstract_url = normalize_text(
        str((metadata or {}).get(CITATION_ABSTRACT_HTML_URL) or "")
    )
    citation_fulltext_url = normalize_text(
        str((metadata or {}).get("citation_fulltext_html_url") or "")
    )
    normalized_final_url = normalize_text(final_url or "")
    if citation_abstract_url:
        abstract_only_hints.append(CITATION_ABSTRACT_HTML_URL)
        if normalized_final_url and normalized_final_url == citation_abstract_url:
            abstract_only_hints.append(FINAL_URL_MATCHES_CITATION_ABSTRACT_HTML_URL)
            blocking_fallback_signals.append(
                FINAL_URL_MATCHES_CITATION_ABSTRACT_HTML_URL
            )
    if (
        citation_fulltext_url
        and normalized_final_url
        and normalized_final_url == citation_fulltext_url
    ):
        hard_negative_signals = [
            signal for signal in hard_negative_signals if signal != PUBLISHER_PAYWALL
        ]
        blocking_fallback_signals = [
            signal
            for signal in blocking_fallback_signals
            if signal != PUBLISHER_PAYWALL
        ]
    return (
        _dedupe_signals(hard_negative_signals),
        _dedupe_signals(abstract_only_hints),
        _dedupe_signals(blocking_fallback_signals),
    )


def _count_figures_from_html(html_text: str) -> int:
    soup = BeautifulSoup(html_text, choose_parser())
    figure_count = len(soup.find_all("figure"))
    if figure_count:
        return figure_count
    return len(soup.select(".figure, .figure-wrap, [data-open='viewer']"))


def assess_html_fulltext_availability(
    markdown_text: str,
    metadata: Mapping[str, Any] | None,
    *,
    provider: str | None = None,
    html_text: str | None = None,
    structure_html_text: str | None = None,
    title: str | None = None,
    response_status: int | None = None,
    requested_url: str | None = None,
    final_url: str | None = None,
    container_tag: str | None = None,
    container_text_length: int | None = None,
    container_evidence: HtmlContainerEvidence | None = None,
    section_hints: Any = None,
) -> FulltextAvailabilityDiagnostics:
    metadata_map = dict(metadata or {})
    normalized_title = normalize_text(title or metadata_map.get("title") or "") or None
    page_text = (
        _normalized_page_text(html_text or "")
        if html_text
        else normalize_text(markdown_text)
    )
    hard_negative_signals = _detect_html_hard_negative_signals_impl(
        normalized_title or "",
        page_text,
        response_status,
        requested_url=requested_url,
        final_url=final_url,
        include_paywall_text=False,
        provider_metadata=metadata_map,
    )
    structure = StructuredBodyAnalysis()
    resolved_container_tag = container_tag
    resolved_container_text_length = container_text_length
    resolved_container_evidence = container_evidence
    analyzed_html_text = structure_html_text or html_text
    if analyzed_html_text:
        structure, inferred_container_evidence, inferred_container_text_length = (
            _analyze_html_structure(
                analyzed_html_text,
                provider=provider,
                title=normalized_title,
                metadata=metadata_map,
                final_url=final_url,
            )
        )
        if resolved_container_evidence is None:
            resolved_container_evidence = inferred_container_evidence
        if not resolved_container_tag:
            resolved_container_tag = (
                inferred_container_evidence.tag
                if inferred_container_evidence is not None
                else None
            )
        if not resolved_container_text_length:
            resolved_container_text_length = inferred_container_text_length
    resolved_container_scope = (
        resolved_container_evidence.scope
        if resolved_container_evidence is not None
        else HTML_CONTAINER_SCOPE_PAGE
    )
    if (
        resolved_container_scope == HTML_CONTAINER_SCOPE_EXPLICIT_BODY
        and structure.body_paragraph_count > 0
    ):
        structure.substantive_body_container = True
        structure.explicit_body_container = True
    synthetic_page_wrapper = bool(
        resolved_container_evidence
        and resolved_container_evidence.synthetic
        and resolved_container_scope == HTML_CONTAINER_SCOPE_PAGE
    )
    trusted_container_scope = not analyzed_html_text or (
        resolved_container_scope == HTML_CONTAINER_SCOPE_ARTICLE
        or (structure.substantive_article_container and not synthetic_page_wrapper)
        or structure.substantive_body_container
    )
    structure_ok = _structure_accepts_fulltext(structure)
    body_ok_fallback = has_sufficient_article_body(
        markdown_text,
        metadata_map,
        section_hints=section_hints,
        provider=provider,
    )
    body_ok = trusted_container_scope and (structure_ok or body_ok_fallback)
    metrics = body_metrics(markdown_text, metadata_map, section_hints=section_hints)
    metrics["body_run_paragraph_count"] = structure.body_run_paragraph_count
    metrics["body_run_char_count"] = structure.body_run_char_count
    metrics["body_paragraph_count"] = structure.body_paragraph_count
    metrics["body_marker_present"] = structure.body_marker_present
    metrics["substantive_article_container"] = structure.substantive_article_container
    metrics["explicit_body_container"] = structure.explicit_body_container
    metrics["substantive_body_container"] = structure.substantive_body_container
    metrics["post_abstract_body_run"] = structure.post_abstract_body_run
    metrics["narrative_article_type"] = structure.narrative_article_type
    metrics["container_scope"] = resolved_container_scope
    metrics["container_scope_trusted"] = trusted_container_scope
    metrics["container_selector"] = (
        resolved_container_evidence.selector
        if resolved_container_evidence is not None
        else None
    )
    metrics["container_synthetic"] = bool(
        resolved_container_evidence and resolved_container_evidence.synthetic
    )
    strong_positive_signals: list[str] = []
    soft_positive_signals: list[str] = []
    abstract_only_hints: list[str] = []
    blocking_fallback_signals: list[str] = list(hard_negative_signals)
    figure_count = _count_figures_from_html(html_text or "") if html_text else 0
    if body_ok:
        strong_positive_signals.append(BODY_SUFFICIENT)
    if structure.explicit_body_container:
        strong_positive_signals.append("explicit_body_container")
    elif structure.body_marker_present:
        soft_positive_signals.append("body_container_marker_only")
    if structure.post_abstract_body_run:
        strong_positive_signals.append("post_abstract_body_run")
    if structure.body_run_paragraph_count:
        strong_positive_signals.append("body_run_paragraph_count")
    if resolved_container_text_length and resolved_container_text_length >= 800:
        strong_positive_signals.append("selected_container_has_body_text")
    if resolved_container_tag:
        soft_positive_signals.append("selected_article_container")
    if not trusted_container_scope:
        soft_positive_signals.append("untrusted_container_scope")
    if figure_count:
        soft_positive_signals.append("has_figures")
    if structure.narrative_article_type:
        soft_positive_signals.append("narrative_article_type")
    if structure.paywall_text_outside_body_ignored:
        soft_positive_signals.append("paywall_text_outside_body_ignored")
    if html_text:
        provider_strong, provider_soft, provider_abstract = (
            _evaluate_provider_positive_policy_signals(provider, html_text)
        )
        provider_blocking = _evaluate_provider_blocking_policy_signals(
            provider, html_text
        )
        strong_positive_signals.extend(provider_strong)
        soft_positive_signals.extend(provider_soft)
        blocking_fallback_signals.extend(provider_blocking)
        (
            dom_hard_negative_signals,
            dom_abstract_only_hints,
            dom_blocking_fallback_signals,
        ) = _dom_access_hints(
            html_text,
            provider=provider,
            structure=structure,
            final_url=final_url,
            metadata=metadata_map,
        )
        hard_negative_signals.extend(dom_hard_negative_signals)
        hard_negative_signals.extend(structure.provider_hard_negative_signals)
        abstract_only_hints.extend(dom_abstract_only_hints)
        abstract_only_hints.extend(provider_abstract)
        abstract_only_hints.extend(structure.provider_abstract_only_hints)
        blocking_fallback_signals.extend(dom_blocking_fallback_signals)
        blocking_fallback_signals.extend(structure.provider_blocking_fallback_signals)
    blocking_fallback_signals.extend(structure.access_gate_markers)
    if (
        not blocking_fallback_signals
        and not body_ok
        and structure.paywall_gate_detected
    ):
        hard_negative_signals.append(PUBLISHER_PAYWALL)
        blocking_fallback_signals.append(PUBLISHER_PAYWALL)
    if not body_ok and not metrics["char_count"] and abstract_only_hints:
        metrics["abstract_only_hints"] = _dedupe_signals(abstract_only_hints)
    has_abstract = bool(metrics.get("has_abstract"))
    ignored_residual_challenge_signals = (
        _residual_challenge_signals_ignored_by_loaded_body(
            provider,
            structure,
            body_ok=body_ok,
        )
    )
    if ignored_residual_challenge_signals:
        hard_negative_signals = [
            signal
            for signal in hard_negative_signals
            if signal not in ignored_residual_challenge_signals
        ]
        blocking_fallback_signals = [
            signal
            for signal in blocking_fallback_signals
            if signal not in ignored_residual_challenge_signals
        ]
        soft_positive_signals.append("residual_challenge_outside_body_ignored")
    blocking_fallback_signals = _dedupe_signals(blocking_fallback_signals)
    content_kind = _diagnostics_content_kind(
        body_ok=body_ok,
        has_abstract=has_abstract,
        blocking_fallback_signals=blocking_fallback_signals,
    )
    if (
        not blocking_fallback_signals
        and content_kind != FULLTEXT
        and abstract_only_hints
        and has_abstract
    ):
        content_kind = ABSTRACT_ONLY
    reason = (
        hard_negative_signals[0]
        if hard_negative_signals
        else (
            ABSTRACT_ONLY
            if blocking_fallback_signals and has_abstract
            else (
                PUBLISHER_PAYWALL
                if blocking_fallback_signals
                else (
                    BODY_SUFFICIENT
                    if body_ok
                    else (
                        ABSTRACT_ONLY
                        if content_kind == ABSTRACT_ONLY
                        else INSUFFICIENT_BODY
                    )
                )
            )
        )
    )
    return FulltextAvailabilityDiagnostics(
        accepted=body_ok and not blocking_fallback_signals,
        reason=reason,
        content_kind=content_kind,
        blocking_fallback_signals=blocking_fallback_signals,
        hard_negative_signals=_dedupe_signals(hard_negative_signals),
        strong_positive_signals=_dedupe_signals(strong_positive_signals),
        soft_positive_signals=_dedupe_signals(
            soft_positive_signals + abstract_only_hints
        ),
        body_metrics=metrics,
        figure_count=figure_count,
        title=normalized_title,
        container_tag=resolved_container_tag,
        container_text_length=resolved_container_text_length,
    )


@dataclass(frozen=True)
class HtmlQualityAssessor:
    provider: str | None = None

    def assess(
        self,
        markdown_text: str,
        metadata: Mapping[str, Any] | None,
        **kwargs: Any,
    ) -> FulltextAvailabilityDiagnostics:
        kwargs.setdefault("provider", self.provider)
        return assess_html_fulltext_availability(markdown_text, metadata, **kwargs)


def assess_plain_text_fulltext_availability(
    markdown_text: str,
    metadata: Mapping[str, Any] | None,
    *,
    title: str | None = None,
    section_hints: Any = None,
) -> FulltextAvailabilityDiagnostics:
    metadata_map = dict(metadata or {})
    normalized_title = normalize_text(title or metadata_map.get("title") or "") or None
    structure = _analyze_markdown_structure(
        markdown_text,
        metadata=metadata_map,
        title=normalized_title,
        section_hints=section_hints,
    )
    body_ok = _structure_accepts_fulltext(structure)
    if not body_ok:
        body_ok = has_sufficient_article_body(
            markdown_text, metadata_map, section_hints=section_hints
        )
    metrics = body_metrics(markdown_text, metadata_map, section_hints=section_hints)
    metrics["body_run_paragraph_count"] = structure.body_run_paragraph_count
    metrics["body_run_char_count"] = structure.body_run_char_count
    metrics["body_paragraph_count"] = structure.body_paragraph_count
    metrics["narrative_article_type"] = structure.narrative_article_type
    blocking_fallback_signals = _dedupe_signals(list(structure.access_gate_markers))
    content_kind = _diagnostics_content_kind(
        body_ok=body_ok,
        has_abstract=bool(metrics.get("has_abstract")),
        blocking_fallback_signals=blocking_fallback_signals,
    )
    return FulltextAvailabilityDiagnostics(
        accepted=body_ok and not blocking_fallback_signals,
        reason=(
            ABSTRACT_ONLY
            if blocking_fallback_signals and content_kind == ABSTRACT_ONLY
            else (
                PUBLISHER_PAYWALL
                if blocking_fallback_signals
                else (
                    BODY_SUFFICIENT
                    if body_ok
                    else (
                        ABSTRACT_ONLY
                        if content_kind == ABSTRACT_ONLY
                        else INSUFFICIENT_BODY
                    )
                )
            )
        ),
        content_kind=content_kind,
        blocking_fallback_signals=blocking_fallback_signals,
        strong_positive_signals=[
            signal
            for signal, enabled in (
                (BODY_SUFFICIENT, body_ok),
                ("post_abstract_body_run", structure.post_abstract_body_run),
                ("body_run_paragraph_count", structure.body_run_paragraph_count > 0),
            )
            if enabled
        ],
        soft_positive_signals=["narrative_article_type"]
        if structure.narrative_article_type
        else [],
        body_metrics=metrics,
        title=normalized_title,
    )


def assess_structured_article_fulltext_availability(
    article: Any,
    *,
    title: str | None = None,
) -> FulltextAvailabilityDiagnostics:
    sections = list(getattr(article, "sections", []) or [])
    body_sections = [
        section
        for section in filtered_body_sections(sections)
        if _is_substantial_prose(str(getattr(section, "text", "") or ""))
    ]
    body_text = "\n\n".join(
        normalize_text(str(getattr(section, "text", "") or ""))
        for section in body_sections
    )
    metadata = getattr(article, "metadata", None)
    article_title = (
        normalize_text(
            title or _normalized_text_field(getattr(metadata, "title", None)) or ""
        )
        or None
    )
    article_abstract = (
        _normalized_text_field(getattr(metadata, "abstract", None)) or None
    )
    metrics = body_metrics(
        body_text,
        {"title": article_title, "abstract": article_abstract}
        if article_title or article_abstract
        else {},
    )
    metrics["section_count"] = len(sections)
    metrics["body_section_count"] = len(body_sections)
    strong_positive_signals: list[str] = []
    if body_sections:
        strong_positive_signals.append("structured_body_sections")
    figure_count = len(
        [
            asset
            for asset in list(getattr(article, "assets", []) or [])
            if normalize_text(str(getattr(asset, "kind", "") or "")).lower() == "figure"
        ]
    )
    soft_positive_signals = ["has_figures"] if figure_count else []
    content_kind = classify_article_content(article)
    accepted = content_kind == FULLTEXT and bool(body_sections)
    reason = (
        "structured_body_sections"
        if accepted
        else (
            STRUCTURED_MISSING_BODY_SECTIONS
            if content_kind == ABSTRACT_ONLY
            else STRUCTURED_ARTICLE_NOT_FULLTEXT
        )
    )
    return FulltextAvailabilityDiagnostics(
        accepted=accepted,
        reason=reason,
        content_kind=content_kind,
        blocking_fallback_signals=[],
        strong_positive_signals=strong_positive_signals,
        soft_positive_signals=soft_positive_signals,
        body_metrics=metrics,
        figure_count=figure_count,
        title=article_title,
    )
