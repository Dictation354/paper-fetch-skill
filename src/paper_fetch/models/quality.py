"""Article content classification and quality assessment helpers."""

from __future__ import annotations

import re
from collections.abc import Sequence
from typing import Any, Mapping

from ..utils import normalize_text
from .markdown import strip_markdown_images
from .schema import (
    ArticleModel,
    BodyQualityMetrics,
    ContentKind,
    EXTRACTION_REVISION,
    Quality,
    QualityConfidence,
    Section,
    SemanticLosses,
    TokenEstimateBreakdown,
)
from .sections import (
    _normalized_text_field,
    abstract_sections,
    combine_abstract_text,
    filtered_body_sections,
    first_abstract_text,
    renderable_body_sections,
)
from .tokens import build_token_estimate_breakdown, coerce_token_estimate_breakdown

QUALITY_FLAG_ACCESS_GATE_DETECTED = "access_gate_detected"


QUALITY_FLAG_INSUFFICIENT_BODY = "insufficient_body"


QUALITY_FLAG_WEAK_BODY_STRUCTURE = "weak_body_structure"


QUALITY_FLAG_TABLE_FALLBACK_PRESENT = "table_fallback_present"


QUALITY_FLAG_TABLE_LOSSY_PRESENT = "table_lossy_present"


QUALITY_FLAG_TABLE_LAYOUT_DEGRADED = "table_layout_degraded"


QUALITY_FLAG_TABLE_SEMANTIC_LOSS = "table_semantic_loss"


QUALITY_FLAG_FORMULA_FALLBACK_PRESENT = "formula_fallback_present"


QUALITY_FLAG_FORMULA_MISSING_PRESENT = "formula_missing_present"


QUALITY_FLAG_CACHED_WITH_CURRENT_REVISION = "cached_with_current_revision"


_QUALITY_ACCESS_SIGNAL_TOKENS = frozenset(
    {
        "publisher_paywall",
        "access",
        "redirect",
        "no_access",
        "abstract_page",
        "citation_abstract",
        "wt_abstract",
        "preview",
        "limited",
        "teaser",
        "denied",
        "subscription",
    }
)


_QUALITY_DOWNGRADE_REASONS = frozenset(
    {
        "publisher_paywall",
        "insufficient_body",
        "abstract_only",
        "no_access",
        "redirected_to_abstract",
        "access_page_url",
        "final_url_matches_citation_abstract_html_url",
        "data_article_access_abstract",
        "wt_abstract_page_type",
        "citation_abstract_html_url",
    }
)


def coerce_body_quality_metrics(
    value: BodyQualityMetrics | Mapping[str, Any] | None,
    *,
    figure_count: int | None = None,
) -> BodyQualityMetrics:
    if isinstance(value, BodyQualityMetrics):
        metrics = BodyQualityMetrics(
            char_count=int(value.char_count or 0),
            word_count=int(value.word_count or 0),
            body_block_count=int(value.body_block_count or 0),
            body_heading_count=int(value.body_heading_count or 0),
            body_to_abstract_ratio=float(value.body_to_abstract_ratio or 0.0),
            explicit_body_container=bool(value.explicit_body_container),
            post_abstract_body_run=bool(value.post_abstract_body_run),
            figure_count=int(value.figure_count or 0),
        )
    elif isinstance(value, Mapping):
        metrics = BodyQualityMetrics(
            char_count=int(value.get("char_count") or 0),
            word_count=int(value.get("word_count") or 0),
            body_block_count=int(value.get("body_block_count") or 0),
            body_heading_count=int(value.get("body_heading_count") or 0),
            body_to_abstract_ratio=float(value.get("body_to_abstract_ratio") or 0.0),
            explicit_body_container=bool(value.get("explicit_body_container")),
            post_abstract_body_run=bool(value.get("post_abstract_body_run")),
            figure_count=int(value.get("figure_count") or 0),
        )
    else:
        metrics = BodyQualityMetrics()
    if figure_count is not None:
        metrics.figure_count = int(figure_count or 0)
    return metrics


def coerce_semantic_losses(value: SemanticLosses | Mapping[str, Any] | None) -> SemanticLosses:
    if isinstance(value, SemanticLosses):
        return SemanticLosses(
            table_fallback_count=int(value.table_fallback_count or 0),
            table_lossy_count=int(value.table_lossy_count or 0),
            table_layout_degraded_count=int(value.table_layout_degraded_count or 0),
            table_semantic_loss_count=int(value.table_semantic_loss_count or 0),
            formula_fallback_count=int(value.formula_fallback_count or 0),
            formula_missing_count=int(value.formula_missing_count or 0),
        )
    if isinstance(value, Mapping):
        legacy_lossy_count = int(value.get("table_lossy_count") or 0)
        return SemanticLosses(
            table_fallback_count=int(value.get("table_fallback_count") or 0),
            table_lossy_count=legacy_lossy_count,
            table_layout_degraded_count=int(value.get("table_layout_degraded_count") or 0),
            table_semantic_loss_count=int(value.get("table_semantic_loss_count") or legacy_lossy_count or 0),
            formula_fallback_count=int(value.get("formula_fallback_count") or 0),
            formula_missing_count=int(value.get("formula_missing_count") or 0),
        )
    return SemanticLosses()


def classify_content(*, sections: Sequence["Section"], abstract_text: str | None) -> ContentKind:
    if filtered_body_sections(sections):
        return "fulltext"
    if normalize_text(abstract_text) or abstract_sections(sections):
        return "abstract_only"
    return "metadata_only"


def classify_article_content(article: "ArticleModel") -> ContentKind:
    metadata = getattr(article, "metadata", None)
    abstract_text = _normalized_text_field(getattr(metadata, "abstract", None))
    sections = list(getattr(article, "sections", []) or [])
    if not abstract_text:
        abstract_text = next(
            (
                _normalized_text_field(getattr(section, "text", None))
                for section in sections
                if _normalized_text_field(getattr(section, "kind", None)).lower() == "abstract"
                and _normalized_text_field(getattr(section, "text", None))
            ),
            "",
        )
    return classify_content(sections=sections, abstract_text=abstract_text)


def _dedupe_strings(values: Sequence[str] | None) -> list[str]:
    return list(dict.fromkeys(normalize_text(value) for value in (values or []) if normalize_text(value)))


def _coerce_diagnostic_value(value: Any) -> Any:
    if value is None or isinstance(value, (bool, int, float)):
        return value
    if isinstance(value, Mapping):
        return {
            normalize_text(str(key)): _coerce_diagnostic_value(item)
            for key, item in value.items()
            if normalize_text(str(key))
        }
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [_coerce_diagnostic_value(item) for item in value]
    return normalize_text(str(value))


def coerce_asset_failure_diagnostics(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        return []
    failures: list[dict[str, Any]] = []
    for item in value:
        if not isinstance(item, Mapping):
            continue
        normalized = _coerce_diagnostic_value(item)
        if isinstance(normalized, dict) and normalized:
            failures.append(normalized)
    return failures


def _word_count(text: str) -> int:
    normalized = normalize_text(text)
    if not normalized:
        return 0
    return len(re.findall(r"\w+", normalized, flags=re.UNICODE))


def _article_body_quality_metrics(article: "ArticleModel") -> BodyQualityMetrics:
    body_sections = filtered_body_sections(article.sections)
    body_chunks = [strip_markdown_images(section.text) for section in body_sections if strip_markdown_images(section.text)]
    body_text = normalize_text("\n\n".join(body_chunks))
    abstract_text = first_abstract_text(abstract_text=article.metadata.abstract, sections=article.sections)
    abstract_word_count = _word_count(abstract_text)
    word_count = _word_count(body_text)
    body_to_abstract_ratio = (
        word_count / max(abstract_word_count, 1)
        if abstract_word_count
        else (float(word_count) if word_count else 0.0)
    )
    figure_count = len(
        [
            asset
            for asset in article.assets
            if normalize_text(asset.kind).lower() == "figure" and normalize_text(asset.section).lower() != "supplementary"
        ]
    )
    return BodyQualityMetrics(
        char_count=len(body_text),
        word_count=word_count,
        body_block_count=len(body_sections),
        body_heading_count=len([section for section in body_sections if normalize_text(section.heading)]),
        body_to_abstract_ratio=body_to_abstract_ratio,
        explicit_body_container=False,
        post_abstract_body_run=False,
        figure_count=figure_count,
    )


def _quality_body_metrics(
    article: "ArticleModel",
    *,
    availability_diagnostics: Mapping[str, Any] | None,
) -> BodyQualityMetrics:
    article_metrics = _article_body_quality_metrics(article)
    if not isinstance(availability_diagnostics, Mapping):
        return article_metrics
    diagnostics_metrics = coerce_body_quality_metrics(
        availability_diagnostics.get("body_metrics") if isinstance(availability_diagnostics.get("body_metrics"), Mapping) else None,
        figure_count=int(availability_diagnostics.get("figure_count") or 0),
    )
    has_article_metrics = any(
        (
            article_metrics.char_count,
            article_metrics.word_count,
            article_metrics.body_block_count,
            article_metrics.body_heading_count,
            article_metrics.figure_count,
        )
    )
    if not has_article_metrics:
        return diagnostics_metrics
    return BodyQualityMetrics(
        char_count=article_metrics.char_count,
        word_count=article_metrics.word_count,
        body_block_count=article_metrics.body_block_count,
        body_heading_count=article_metrics.body_heading_count,
        body_to_abstract_ratio=article_metrics.body_to_abstract_ratio,
        explicit_body_container=article_metrics.explicit_body_container or diagnostics_metrics.explicit_body_container,
        post_abstract_body_run=article_metrics.post_abstract_body_run or diagnostics_metrics.post_abstract_body_run,
        figure_count=max(article_metrics.figure_count, diagnostics_metrics.figure_count),
    )


def _diagnostic_signals(value: Mapping[str, Any] | None) -> list[str]:
    if not isinstance(value, Mapping):
        return []
    signals = [
        normalize_text(value.get("reason")).lower(),
        *[normalize_text(item).lower() for item in value.get("blocking_fallback_signals") or []],
        *[normalize_text(item).lower() for item in value.get("hard_negative_signals") or []],
        *[normalize_text(item).lower() for item in value.get("soft_positive_signals") or []],
        *[normalize_text(item).lower() for item in value.get("strong_positive_signals") or []],
    ]
    return [signal for signal in signals if signal]


def _diagnostic_access_gate_signals(value: Mapping[str, Any] | None) -> list[str]:
    if not isinstance(value, Mapping):
        return []
    signals = [
        normalize_text(value.get("reason")).lower(),
        *[normalize_text(item).lower() for item in value.get("blocking_fallback_signals") or []],
        *[normalize_text(item).lower() for item in value.get("hard_negative_signals") or []],
    ]
    if value.get("accepted") is False:
        signals.extend(
            normalize_text(item).lower()
            for item in value.get("soft_positive_signals") or []
        )
    return [signal for signal in signals if signal]


def _diagnostics_access_gate_detected(value: Mapping[str, Any] | None) -> bool:
    if isinstance(value, Mapping) and [item for item in value.get("blocking_fallback_signals") or [] if normalize_text(item)]:
        return True
    for signal in _diagnostic_access_gate_signals(value):
        if any(token in signal for token in _QUALITY_ACCESS_SIGNAL_TOKENS):
            return True
    return False


def _has_weak_body_structure(metrics: BodyQualityMetrics) -> bool:
    if metrics.word_count <= 0 and metrics.char_count <= 0:
        return False
    if metrics.explicit_body_container or metrics.post_abstract_body_run:
        return False
    if metrics.body_block_count >= 2 and metrics.body_heading_count >= 1:
        return False
    return True


def _diagnostics_require_downgrade(
    diagnostics: Mapping[str, Any] | None,
    *,
    body_metrics: BodyQualityMetrics,
) -> bool:
    if not isinstance(diagnostics, Mapping):
        return False
    if [item for item in diagnostics.get("blocking_fallback_signals") or [] if normalize_text(item)]:
        return True
    if diagnostics.get("accepted") is not False:
        return False
    reason = normalize_text(diagnostics.get("reason")).lower()
    if reason in _QUALITY_DOWNGRADE_REASONS:
        return True
    if _diagnostics_access_gate_detected(diagnostics):
        return True
    if reason == QUALITY_FLAG_INSUFFICIENT_BODY and body_metrics.word_count <= 40:
        return True
    return False


def _clone_quality(quality: "Quality") -> "Quality":
    return Quality(
        has_fulltext=quality.has_fulltext,
        token_estimate=quality.token_estimate,
        content_kind=quality.content_kind,
        has_abstract=quality.has_abstract,
        warnings=list(quality.warnings),
        source_trail=list(quality.source_trail),
        trace=list(quality.trace),
        token_estimate_breakdown=coerce_token_estimate_breakdown(quality.token_estimate_breakdown),
        confidence=quality.confidence,
        flags=list(quality.flags),
        body_metrics=coerce_body_quality_metrics(quality.body_metrics),
        semantic_losses=coerce_semantic_losses(quality.semantic_losses),
        asset_failures=coerce_asset_failure_diagnostics(quality.asset_failures),
        extraction_revision=quality.extraction_revision,
    )


def _refresh_article_quality(
    article: "ArticleModel",
    *,
    explicit_content_kind: ContentKind | None = None,
    recompute_tokens: bool = True,
) -> None:
    abstract_text = first_abstract_text(abstract_text=article.metadata.abstract, sections=article.sections)
    if abstract_text and not normalize_text(article.metadata.abstract):
        article.metadata.abstract = abstract_text
    if recompute_tokens or article.quality.token_estimate_breakdown == TokenEstimateBreakdown():
        token_estimate_breakdown = build_token_estimate_breakdown(
            abstract_text=article.metadata.abstract,
            sections=article.sections,
            references=article.references,
        )
        article.quality.token_estimate_breakdown = token_estimate_breakdown
    token_estimate_breakdown = article.quality.token_estimate_breakdown
    if recompute_tokens or article.quality.token_estimate <= 0:
        article.quality.token_estimate = token_estimate_breakdown.abstract + token_estimate_breakdown.body
    content_kind = explicit_content_kind or classify_content(sections=article.sections, abstract_text=article.metadata.abstract)
    article.quality.content_kind = content_kind
    article.quality.has_abstract = bool(first_abstract_text(abstract_text=article.metadata.abstract, sections=article.sections))
    article.quality.has_fulltext = content_kind == "fulltext"


def _downgrade_article(article: "ArticleModel", *, target_kind: ContentKind) -> None:
    if target_kind == "metadata_only":
        article.sections = []
        article.assets = []
        _refresh_article_quality(article, explicit_content_kind="metadata_only")
        return
    article.sections = [
        section
        for section in article.sections
        if normalize_text(section.kind).lower() == "abstract"
    ]
    article.assets = []
    if not first_abstract_text(abstract_text=article.metadata.abstract, sections=article.sections):
        article.sections = []
        _refresh_article_quality(article, explicit_content_kind="metadata_only")
        return
    _refresh_article_quality(article, explicit_content_kind="abstract_only")


def _semantic_loss_warning_messages(losses: SemanticLosses) -> list[str]:
    warnings: list[str] = []
    if losses.table_fallback_count:
        warnings.append("Some tables could only be retained as original-resource fallbacks; structured table data may be incomplete.")
    if losses.table_semantic_loss_count or losses.table_lossy_count:
        warnings.append("Some tables lost semantic content during Markdown conversion.")
    if losses.table_layout_degraded_count:
        warnings.append("Some tables were flattened lossily for Markdown output; merged-cell structure was not preserved exactly.")
    if losses.formula_fallback_count:
        warnings.append("Some formulas required degraded fallback rendering.")
    if losses.formula_missing_count:
        warnings.append("Some formulas could not be converted faithfully and were replaced with explicit placeholders.")
    return warnings


def _resolve_quality_confidence(
    *,
    content_kind: ContentKind,
    flags: Sequence[str],
    semantic_losses: SemanticLosses,
    diagnostics: Mapping[str, Any] | None,
) -> QualityConfidence:
    normalized_flags = set(_dedupe_strings(flags))
    hard_negative = bool(
        isinstance(diagnostics, Mapping)
        and [normalize_text(item) for item in diagnostics.get("hard_negative_signals") or [] if normalize_text(item)]
    )
    if (
        content_kind != "fulltext"
        or hard_negative
        or QUALITY_FLAG_ACCESS_GATE_DETECTED in normalized_flags
        or QUALITY_FLAG_INSUFFICIENT_BODY in normalized_flags
    ):
        return "low"
    if (
        QUALITY_FLAG_WEAK_BODY_STRUCTURE in normalized_flags
        or semantic_losses.table_fallback_count > 0
        or semantic_losses.table_semantic_loss_count > 0
        or semantic_losses.table_lossy_count > 0
        or semantic_losses.formula_fallback_count > 0
        or semantic_losses.formula_missing_count > 0
    ):
        return "medium"
    return "high"


def apply_quality_assessment(
    article: "ArticleModel",
    *,
    availability_diagnostics: Mapping[str, Any] | None = None,
    semantic_losses: SemanticLosses | Mapping[str, Any] | None = None,
    extra_flags: Sequence[str] | None = None,
    allow_downgrade_from_diagnostics: bool = False,
    cached_with_current_revision: bool = False,
    recompute_tokens: bool = True,
) -> "ArticleModel":
    losses = coerce_semantic_losses(semantic_losses)
    body_metrics = _quality_body_metrics(article, availability_diagnostics=availability_diagnostics)
    flags = _dedupe_strings(extra_flags)
    reason = normalize_text((availability_diagnostics or {}).get("reason") if isinstance(availability_diagnostics, Mapping) else "").lower()

    if _diagnostics_access_gate_detected(availability_diagnostics):
        flags.append(QUALITY_FLAG_ACCESS_GATE_DETECTED)
    if reason == "insufficient_body":
        flags.append(QUALITY_FLAG_INSUFFICIENT_BODY)
    if article.quality.content_kind == "fulltext" and _has_weak_body_structure(body_metrics):
        flags.append(QUALITY_FLAG_WEAK_BODY_STRUCTURE)
    if losses.table_fallback_count > 0:
        flags.append(QUALITY_FLAG_TABLE_FALLBACK_PRESENT)
    if losses.table_layout_degraded_count > 0:
        flags.append(QUALITY_FLAG_TABLE_LAYOUT_DEGRADED)
    if losses.table_semantic_loss_count > 0 or losses.table_lossy_count > 0:
        flags.append(QUALITY_FLAG_TABLE_SEMANTIC_LOSS)
    if losses.table_lossy_count > 0:
        flags.append(QUALITY_FLAG_TABLE_LOSSY_PRESENT)
    if losses.formula_fallback_count > 0:
        flags.append(QUALITY_FLAG_FORMULA_FALLBACK_PRESENT)
    if losses.formula_missing_count > 0:
        flags.append(QUALITY_FLAG_FORMULA_MISSING_PRESENT)
    if cached_with_current_revision:
        flags.append(QUALITY_FLAG_CACHED_WITH_CURRENT_REVISION)

    if allow_downgrade_from_diagnostics and _diagnostics_require_downgrade(
        availability_diagnostics,
        body_metrics=body_metrics,
    ):
        target_kind = normalize_text((availability_diagnostics or {}).get("content_kind") if isinstance(availability_diagnostics, Mapping) else "").lower()
        if target_kind not in {"abstract_only", "metadata_only"}:
            target_kind = "abstract_only" if first_abstract_text(abstract_text=article.metadata.abstract, sections=article.sections) else "metadata_only"
        _downgrade_article(article, target_kind=target_kind)
    else:
        _refresh_article_quality(article, recompute_tokens=recompute_tokens)

    article.quality.flags = _dedupe_strings(flags)
    article.quality.body_metrics = body_metrics
    article.quality.semantic_losses = losses
    article.quality.extraction_revision = EXTRACTION_REVISION
    article.quality.confidence = _resolve_quality_confidence(
        content_kind=article.quality.content_kind,
        flags=article.quality.flags,
        semantic_losses=losses,
        diagnostics=availability_diagnostics,
    )
    article.quality.warnings = _dedupe_strings([*article.quality.warnings, *_semantic_loss_warning_messages(losses)])
    return article


__all__ = [
    "QUALITY_FLAG_ACCESS_GATE_DETECTED",
    "QUALITY_FLAG_INSUFFICIENT_BODY",
    "QUALITY_FLAG_WEAK_BODY_STRUCTURE",
    "QUALITY_FLAG_TABLE_FALLBACK_PRESENT",
    "QUALITY_FLAG_TABLE_LOSSY_PRESENT",
    "QUALITY_FLAG_TABLE_LAYOUT_DEGRADED",
    "QUALITY_FLAG_TABLE_SEMANTIC_LOSS",
    "QUALITY_FLAG_FORMULA_FALLBACK_PRESENT",
    "QUALITY_FLAG_FORMULA_MISSING_PRESENT",
    "QUALITY_FLAG_CACHED_WITH_CURRENT_REVISION",
    "_QUALITY_ACCESS_SIGNAL_TOKENS",
    "_QUALITY_DOWNGRADE_REASONS",
    "coerce_body_quality_metrics",
    "coerce_semantic_losses",
    "classify_content",
    "classify_article_content",
    "coerce_asset_failure_diagnostics",
    "apply_quality_assessment",
    "abstract_sections",
    "combine_abstract_text",
    "filtered_body_sections",
    "first_abstract_text",
    "renderable_body_sections",
]
