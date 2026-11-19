"""Shared HTML full-text availability diagnostics and structure analysis."""

from __future__ import annotations

import copy
from collections.abc import Mapping
from dataclasses import asdict, dataclass, field
from typing import Any

from bs4 import BeautifulSoup, Tag

from ..extraction.html._runtime import body_metrics, has_sufficient_article_body
from ..extraction.html.parsing import choose_parser
from ..extraction.html.provider_rules import availability_rules_for_provider
from ..extraction.html.signals import detect_html_access_signals, html_failure_message
from ..models import classify_article_content, filtered_body_sections
from ..reason_codes import (
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
from ..utils import normalize_text
from ._container_cleanup import (
    HTML_CONTAINER_BODY_SELECTORS,
    HTML_CONTAINER_BROWSER_WORKFLOW_FALLBACK_TAGS,
    HTML_CONTAINER_DROP_AVAILABILITY,
    HTML_CONTAINER_DROP_BROWSER_WORKFLOW,
    HTML_CONTAINER_SCOPE_ARTICLE,
    HTML_CONTAINER_SCOPE_EXPLICIT_BODY,
    HTML_CONTAINER_SCOPE_PAGE,
    HTML_CONTAINER_SCORE_AVAILABILITY,
    HTML_CONTAINER_SCORE_BROWSER_WORKFLOW,
    HtmlContainerEvidence,
    HtmlContainerScope,
    HtmlContainerSelectionPolicy,
    _prefer_complete_ancestor,
    clean_container,
    container_completeness_score,
    extract_page_title,
    html_container_evidence,
    prefer_complete_ancestor,
    score_container,
    select_container,
    should_drop_node,
)
from ._structure_scan import (
    NARRATIVE_ARTICLE_TYPES,
    NARRATIVE_BODY_RUN_MIN_CHARS,
    DomStructureScanInput,
    StructuredBodyAnalysis,
    extract_article_type,
    final_url_looks_like_access_page,
    is_substantial_prose,
    scan_dom_structure,
    scan_markdown_structure,
    structure_accepts_fulltext,
)
from .access_boundary import CONFIRMED_PAYWALL, html_paywall_diagnostics
from .html_profiles import looks_like_abstract_redirect, site_rule_for_publisher
from .html_signals import (
    AvailabilityOverrides,
    AvailabilityOverrideState,
    apply_availability_overrides,
    dedupe_signals,
    default_positive_signals,
    evaluate_datalayer_blocking_signals,
    evaluate_datalayer_positive_signals,
    evaluate_text_marker_blocking_signals,
    evaluate_text_marker_positive_signals,
)

_LOADED_BODY_RESIDUAL_CHALLENGE_SIGNALS = {
    "iop": frozenset(
        {
            CLOUDFLARE_CHALLENGE,
            "iop_radware_challenge",
            "iop_captcha_challenge",
        }
    ),
    # T&F can retain Cloudflare Insights/challenge-platform scripts after a
    # complete article body has loaded. The structural checks below prevent a
    # standalone challenge page from using this exception.
    "tandf": frozenset({CLOUDFLARE_CHALLENGE}),
}


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
    confirmed_article_paywall: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class HtmlAssessmentInput:
    """Structured internal context replacing flat 15-parameter plumbing."""

    markdown_text: str
    metadata: dict[str, Any]
    provider: str | None = None
    html_text: str | None = None
    structure_html_text: str | None = None
    structure_dom: BeautifulSoup | None = None
    title: str | None = None
    response_status: int | None = None
    requested_url: str | None = None
    final_url: str | None = None
    container_tag: str | None = None
    container_text_length: int | None = None
    container_evidence: HtmlContainerEvidence | None = None
    section_hints: Any = None
    context: Any = None


@dataclass(frozen=True)
class _PageHtmlSignals:
    """Read-only signals gathered once from the unmutated page DOM."""

    page_text: str
    article_type: str | None = None
    figure_count: int = 0
    provider_strong_signals: list[str] = field(default_factory=list)
    provider_soft_signals: list[str] = field(default_factory=list)
    provider_abstract_hints: list[str] = field(default_factory=list)
    provider_blocking_signals: list[str] = field(default_factory=list)
    dom_hard_negative_signals: list[str] = field(default_factory=list)
    dom_abstract_only_hints: list[str] = field(default_factory=list)
    dom_blocking_fallback_signals: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class AvailabilityVerdict:
    accepted: bool
    reason: str
    content_kind: str
    blocking_fallback_signals: list[str]


def select_best_container(
    soup: BeautifulSoup,
    publisher: str | None,
    *,
    policy: HtmlContainerSelectionPolicy | None = None,
) -> Tag | None:
    return select_container(
        soup,
        publisher,
        policy=policy,
        site_rule_lookup=site_rule_for_publisher,
        score_fn=score_container,
        completeness_fn=container_completeness_score,
        ancestor_fn=_prefer_complete_ancestor,
    )


def availability_failure_message(diagnostics: FulltextAvailabilityDiagnostics) -> str:
    return html_failure_message(diagnostics.reason)


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
        dedupe_signals(strong),
        dedupe_signals(soft),
        dedupe_signals(abstract_only),
    )


def _evaluate_provider_blocking_policy_signals(
    provider: str | None, html_text: str, *, soup: BeautifulSoup
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
            soup=soup,
            structure=StructuredBodyAnalysis(),
        )
        apply_availability_overrides(
            state,
            AvailabilityOverrides(empty_shell_rules=policy.overrides.empty_shell_rules),
        )
        signals.extend(state.blocking_fallback_signals or [])
    return dedupe_signals(signals)


def _dom_access_hints(
    soup: BeautifulSoup,
    *,
    final_url: str | None,
    metadata: Mapping[str, Any],
) -> tuple[list[str], list[str], list[str]]:
    hard_negative_signals: list[str] = []
    abstract_only_hints: list[str] = []
    blocking_fallback_signals: list[str] = []
    if soup.select_one(".accessDenialWidget"):
        hard_negative_signals.append(PUBLISHER_PAYWALL)
        blocking_fallback_signals.append(PUBLISHER_PAYWALL)
    if final_url_looks_like_access_page(final_url):
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
        joined = " ".join(value for value in (access_value, access_type) if value)
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
        str(metadata.get(CITATION_ABSTRACT_HTML_URL) or "")
    )
    citation_fulltext_url = normalize_text(
        str(metadata.get("citation_fulltext_html_url") or "")
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
        dedupe_signals(hard_negative_signals),
        dedupe_signals(abstract_only_hints),
        dedupe_signals(blocking_fallback_signals),
    )


def _count_figures_from_soup(soup: BeautifulSoup) -> int:
    figure_count = len(soup.find_all("figure"))
    if figure_count:
        return figure_count
    return len(soup.select(".figure, .figure-wrap, [data-open='viewer']"))


def _collect_page_html_signals(
    assessment: HtmlAssessmentInput, page_soup: BeautifulSoup | None
) -> _PageHtmlSignals:
    if page_soup is None or not assessment.html_text:
        return _PageHtmlSignals(page_text=normalize_text(assessment.markdown_text))
    html_text = assessment.html_text
    page_text = normalize_text(" ".join(page_soup.stripped_strings))
    article_type = extract_article_type(assessment.metadata, soup=page_soup)
    figure_count = _count_figures_from_soup(page_soup)
    provider_strong, provider_soft, provider_abstract = (
        _evaluate_provider_positive_policy_signals(assessment.provider, html_text)
    )
    provider_blocking = _evaluate_provider_blocking_policy_signals(
        assessment.provider, html_text, soup=page_soup
    )
    dom_hard, dom_abstract, dom_blocking = _dom_access_hints(
        page_soup,
        final_url=assessment.final_url,
        metadata=assessment.metadata,
    )
    return _PageHtmlSignals(
        page_text=page_text,
        article_type=article_type,
        figure_count=figure_count,
        provider_strong_signals=provider_strong,
        provider_soft_signals=provider_soft,
        provider_abstract_hints=provider_abstract,
        provider_blocking_signals=provider_blocking,
        dom_hard_negative_signals=dom_hard,
        dom_abstract_only_hints=dom_abstract,
        dom_blocking_fallback_signals=dom_blocking,
    )


def _resolve_structure_soup(
    assessment: HtmlAssessmentInput, page_soup: BeautifulSoup | None
) -> BeautifulSoup | None:
    if assessment.structure_dom is not None:
        return copy.deepcopy(assessment.structure_dom)
    if (
        assessment.structure_html_text
        and assessment.structure_html_text != assessment.html_text
    ):
        return BeautifulSoup(assessment.structure_html_text, choose_parser())
    return page_soup


def _residual_challenge_signals_ignored_by_loaded_body(
    provider: str | None,
    structure: StructuredBodyAnalysis,
    *,
    body_ok: bool,
) -> frozenset[str]:
    normalized_provider = normalize_text(provider).lower()
    residual_signals = _LOADED_BODY_RESIDUAL_CHALLENGE_SIGNALS.get(normalized_provider)
    if not residual_signals or not body_ok:
        return frozenset()
    if not structure.explicit_body_container or not structure.post_abstract_body_run:
        return frozenset()
    if (
        structure.body_run_char_count < NARRATIVE_BODY_RUN_MIN_CHARS
        and structure.body_paragraph_count < 1
    ):
        return frozenset()
    return residual_signals


def _resolve_availability_verdict(
    *,
    body_ok: bool,
    has_abstract: bool,
    blocking_fallback_signals: list[str],
    hard_negative_signals: list[str] | None = None,
    boundary: Mapping[str, Any] | None = None,
) -> AvailabilityVerdict:
    """Resolve acceptance, content kind, and reason in one priority order."""
    blocking = dedupe_signals(blocking_fallback_signals)
    hard_negatives = dedupe_signals(hard_negative_signals or [])

    if boundary:
        content_kind = str(boundary["content_kind"])
        reason = ABSTRACT_ONLY if content_kind == ABSTRACT_ONLY else PUBLISHER_PAYWALL
        return AvailabilityVerdict(
            accepted=False,
            reason=reason,
            content_kind=content_kind,
            blocking_fallback_signals=dedupe_signals([*blocking, PUBLISHER_PAYWALL]),
        )

    if blocking or hard_negatives:
        content_kind = ABSTRACT_ONLY if has_abstract else METADATA_ONLY
        if hard_negatives:
            reason = hard_negatives[0]
        elif has_abstract:
            reason = ABSTRACT_ONLY
        else:
            reason = PUBLISHER_PAYWALL
        return AvailabilityVerdict(
            accepted=False,
            reason=reason,
            content_kind=content_kind,
            blocking_fallback_signals=blocking or hard_negatives,
        )

    if body_ok:
        return AvailabilityVerdict(
            accepted=True,
            reason=BODY_SUFFICIENT,
            content_kind=FULLTEXT,
            blocking_fallback_signals=[],
        )

    if has_abstract:
        return AvailabilityVerdict(
            accepted=False,
            reason=ABSTRACT_ONLY,
            content_kind=ABSTRACT_ONLY,
            blocking_fallback_signals=[],
        )

    return AvailabilityVerdict(
        accepted=False,
        reason=INSUFFICIENT_BODY,
        content_kind=METADATA_ONLY,
        blocking_fallback_signals=[],
    )


def _assess_html_input(
    assessment: HtmlAssessmentInput,
) -> FulltextAvailabilityDiagnostics:
    boundary = html_paywall_diagnostics(
        assessment.html_text or "",
        metadata=assessment.metadata,
        source_url=assessment.final_url or assessment.requested_url or "",
        provider=assessment.provider,
        context=assessment.context,
    )
    normalized_title = (
        normalize_text(assessment.title or assessment.metadata.get("title") or "")
        or None
    )
    page_soup = (
        BeautifulSoup(assessment.html_text, choose_parser())
        if assessment.html_text
        else None
    )
    page_signals = _collect_page_html_signals(assessment, page_soup)

    redirected_to_abstract = bool(
        assessment.requested_url
        and looks_like_abstract_redirect(assessment.requested_url, assessment.final_url)
    )
    hard_negative_signals = detect_html_access_signals(
        normalized_title or "",
        page_signals.page_text,
        assessment.response_status,
        redirected_to_abstract=redirected_to_abstract,
        include_paywall_text=False,
        explicit_no_access=bool(assessment.metadata.get("explicit_no_access")),
        html_text=assessment.html_text or "",
    )

    structure = StructuredBodyAnalysis()
    resolved_container_tag = assessment.container_tag
    resolved_container_text_length = assessment.container_text_length
    resolved_container_evidence = assessment.container_evidence
    structure_soup = _resolve_structure_soup(assessment, page_soup)
    analyzed_html = structure_soup is not None
    if structure_soup is not None:
        reusing_page_soup = structure_soup is page_soup
        scan_result = scan_dom_structure(
            DomStructureScanInput(
                soup=structure_soup,
                provider=assessment.provider,
                title=normalized_title,
                metadata=assessment.metadata,
                final_url=assessment.final_url,
                article_type=page_signals.article_type if reusing_page_soup else None,
                page_text=page_signals.page_text if reusing_page_soup else None,
            ),
            select_container_fn=select_best_container,
            clean_container_fn=clean_container,
        )
        structure = scan_result.analysis
        if resolved_container_evidence is None:
            resolved_container_evidence = scan_result.container_evidence
        if not resolved_container_tag and scan_result.container_evidence is not None:
            resolved_container_tag = scan_result.container_evidence.tag
        if not resolved_container_text_length:
            resolved_container_text_length = scan_result.container_text_length

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
    trusted_container_scope = not analyzed_html or (
        resolved_container_scope == HTML_CONTAINER_SCOPE_ARTICLE
        or (structure.substantive_article_container and not synthetic_page_wrapper)
        or structure.substantive_body_container
    )
    body_ok = trusted_container_scope and (
        structure_accepts_fulltext(structure)
        or has_sufficient_article_body(
            assessment.markdown_text,
            assessment.metadata,
            section_hints=assessment.section_hints,
            provider=assessment.provider,
        )
    )

    metrics = body_metrics(
        assessment.markdown_text,
        assessment.metadata,
        section_hints=assessment.section_hints,
    )
    metrics.update(
        {
            "body_run_paragraph_count": structure.body_run_paragraph_count,
            "body_run_char_count": structure.body_run_char_count,
            "body_paragraph_count": structure.body_paragraph_count,
            "body_marker_present": structure.body_marker_present,
            "substantive_article_container": structure.substantive_article_container,
            "explicit_body_container": structure.explicit_body_container,
            "substantive_body_container": structure.substantive_body_container,
            "post_abstract_body_run": structure.post_abstract_body_run,
            "narrative_article_type": structure.narrative_article_type,
            "container_scope": resolved_container_scope,
            "container_scope_trusted": trusted_container_scope,
            "container_selector": (
                resolved_container_evidence.selector
                if resolved_container_evidence is not None
                else None
            ),
            "container_synthetic": bool(
                resolved_container_evidence and resolved_container_evidence.synthetic
            ),
        }
    )

    strong_positive_signals: list[str] = []
    soft_positive_signals: list[str] = []
    abstract_only_hints: list[str] = []
    blocking_fallback_signals: list[str] = list(hard_negative_signals)

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
    if page_signals.figure_count:
        soft_positive_signals.append("has_figures")
    if structure.narrative_article_type:
        soft_positive_signals.append("narrative_article_type")
    if structure.paywall_text_outside_body_ignored:
        soft_positive_signals.append("paywall_text_outside_body_ignored")

    if assessment.html_text:
        strong_positive_signals.extend(page_signals.provider_strong_signals)
        soft_positive_signals.extend(page_signals.provider_soft_signals)
        blocking_fallback_signals.extend(page_signals.provider_blocking_signals)
        hard_negative_signals.extend(page_signals.dom_hard_negative_signals)
        hard_negative_signals.extend(structure.provider_hard_negative_signals)
        abstract_only_hints.extend(page_signals.dom_abstract_only_hints)
        abstract_only_hints.extend(page_signals.provider_abstract_hints)
        abstract_only_hints.extend(structure.provider_abstract_only_hints)
        blocking_fallback_signals.extend(page_signals.dom_blocking_fallback_signals)
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
        metrics["abstract_only_hints"] = dedupe_signals(abstract_only_hints)

    ignored_residual = _residual_challenge_signals_ignored_by_loaded_body(
        assessment.provider,
        structure,
        body_ok=body_ok,
    )
    if ignored_residual:
        hard_negative_signals = [
            signal for signal in hard_negative_signals if signal not in ignored_residual
        ]
        blocking_fallback_signals = [
            signal
            for signal in blocking_fallback_signals
            if signal not in ignored_residual
        ]
        soft_positive_signals.append("residual_challenge_outside_body_ignored")

    verdict = _resolve_availability_verdict(
        body_ok=body_ok,
        has_abstract=bool(metrics.get("has_abstract")),
        blocking_fallback_signals=blocking_fallback_signals,
        hard_negative_signals=hard_negative_signals,
        boundary=boundary,
    )
    return FulltextAvailabilityDiagnostics(
        accepted=verdict.accepted,
        reason=verdict.reason,
        content_kind=verdict.content_kind,
        blocking_fallback_signals=verdict.blocking_fallback_signals,
        hard_negative_signals=dedupe_signals(hard_negative_signals),
        strong_positive_signals=dedupe_signals(strong_positive_signals),
        soft_positive_signals=dedupe_signals(
            soft_positive_signals + abstract_only_hints
        ),
        body_metrics=metrics,
        figure_count=page_signals.figure_count,
        title=normalized_title,
        container_tag=resolved_container_tag,
        container_text_length=resolved_container_text_length,
        confirmed_article_paywall=boundary.get(CONFIRMED_PAYWALL, {}),
    )


def assess_html_fulltext_availability(
    markdown_text: str,
    metadata: Mapping[str, Any] | None,
    *,
    provider: str | None = None,
    html_text: str | None = None,
    structure_html_text: str | None = None,
    structure_dom: BeautifulSoup | None = None,
    title: str | None = None,
    response_status: int | None = None,
    requested_url: str | None = None,
    final_url: str | None = None,
    container_tag: str | None = None,
    container_text_length: int | None = None,
    container_evidence: HtmlContainerEvidence | None = None,
    section_hints: Any = None,
    context: Any = None,
) -> FulltextAvailabilityDiagnostics:
    return _assess_html_input(
        HtmlAssessmentInput(
            markdown_text=markdown_text,
            metadata=dict(metadata or {}),
            provider=provider,
            html_text=html_text,
            structure_html_text=structure_html_text,
            structure_dom=structure_dom,
            title=title,
            response_status=response_status,
            requested_url=requested_url,
            final_url=final_url,
            container_tag=container_tag,
            container_text_length=container_text_length,
            container_evidence=container_evidence,
            section_hints=section_hints,
            context=context,
        )
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
    structure = scan_markdown_structure(
        markdown_text,
        metadata=metadata_map,
        title=normalized_title,
        section_hints=section_hints,
    )
    body_ok = structure_accepts_fulltext(structure) or has_sufficient_article_body(
        markdown_text, metadata_map, section_hints=section_hints
    )
    metrics = body_metrics(markdown_text, metadata_map, section_hints=section_hints)
    metrics.update(
        {
            "body_run_paragraph_count": structure.body_run_paragraph_count,
            "body_run_char_count": structure.body_run_char_count,
            "body_paragraph_count": structure.body_paragraph_count,
            "narrative_article_type": structure.narrative_article_type,
        }
    )
    verdict = _resolve_availability_verdict(
        body_ok=body_ok,
        has_abstract=bool(metrics.get("has_abstract")),
        blocking_fallback_signals=list(structure.access_gate_markers),
    )
    return FulltextAvailabilityDiagnostics(
        accepted=verdict.accepted,
        reason=verdict.reason,
        content_kind=verdict.content_kind,
        blocking_fallback_signals=verdict.blocking_fallback_signals,
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


def _normalized_text_field(value: Any) -> str:
    return normalize_text(value) if isinstance(value, str) else ""


def assess_structured_article_fulltext_availability(
    article: Any,
    *,
    title: str | None = None,
) -> FulltextAvailabilityDiagnostics:
    sections = list(getattr(article, "sections", []) or [])
    body_sections = [
        section
        for section in filtered_body_sections(sections)
        if is_substantial_prose(str(getattr(section, "text", "") or ""))
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
    strong_positive_signals = ["structured_body_sections"] if body_sections else []
    figure_count = sum(
        1
        for asset in list(getattr(article, "assets", []) or [])
        if normalize_text(str(getattr(asset, "kind", "") or "")).lower() == "figure"
    )
    soft_positive_signals = ["has_figures"] if figure_count else []
    content_kind = classify_article_content(article)
    accepted = content_kind == FULLTEXT and bool(body_sections)
    if accepted:
        reason = "structured_body_sections"
    elif content_kind == ABSTRACT_ONLY:
        reason = STRUCTURED_MISSING_BODY_SECTIONS
    else:
        reason = STRUCTURED_ARTICLE_NOT_FULLTEXT
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


__all__ = [
    "HTML_CONTAINER_BODY_SELECTORS",
    "HTML_CONTAINER_BROWSER_WORKFLOW_FALLBACK_TAGS",
    "HTML_CONTAINER_DROP_AVAILABILITY",
    "HTML_CONTAINER_DROP_BROWSER_WORKFLOW",
    "HTML_CONTAINER_SCOPE_ARTICLE",
    "HTML_CONTAINER_SCOPE_EXPLICIT_BODY",
    "HTML_CONTAINER_SCOPE_PAGE",
    "HTML_CONTAINER_SCORE_AVAILABILITY",
    "HTML_CONTAINER_SCORE_BROWSER_WORKFLOW",
    "NARRATIVE_ARTICLE_TYPES",
    "NARRATIVE_BODY_RUN_MIN_CHARS",
    "AvailabilityVerdict",
    "FulltextAvailabilityDiagnostics",
    "HtmlAssessmentInput",
    "HtmlContainerEvidence",
    "HtmlContainerScope",
    "HtmlContainerSelectionPolicy",
    "HtmlQualityAssessor",
    "StructuredBodyAnalysis",
    "assess_html_fulltext_availability",
    "assess_plain_text_fulltext_availability",
    "assess_structured_article_fulltext_availability",
    "availability_failure_message",
    "choose_parser",
    "clean_container",
    "container_completeness_score",
    "extract_page_title",
    "html_container_evidence",
    "prefer_complete_ancestor",
    "score_container",
    "select_best_container",
    "should_drop_node",
]
