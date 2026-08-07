"""Atypon browser-workflow profile dispatch for provider-owned browser routes."""

from __future__ import annotations

import copy
from dataclasses import dataclass, field
from functools import cache
from importlib import import_module
from types import ModuleType
from typing import Any
from collections.abc import Callable, Mapping

from ..extraction.html.provider_rules import (
    DomHooks,
    MarkdownHooks,
    provider_html_rules,
)
from ..provider_catalog import (
    provider_base_domains,
    provider_crossref_pdf_position,
    provider_domains,
    provider_html_path_templates,
    provider_pdf_path_templates,
)
from ..quality import html_profiles as _html_profiles
from ..quality.html_signals import (
    default_positive_signals,
    evaluate_datalayer_blocking_signals,
    evaluate_datalayer_positive_signals,
    evaluate_text_marker_blocking_signals,
    evaluate_text_marker_positive_signals,
)
from ..utils import normalize_text
from .browser_workflow.shared import (
    build_browser_workflow_html_candidates,
    build_browser_workflow_pdf_candidates,
    extract_pdf_url_from_crossref,
    preferred_html_candidate_from_landing_page as _preferred_html_candidate_from_landing_page,
)

DEFAULT_SITE_RULE = _html_profiles.DEFAULT_SITE_RULE

__all__ = [
    "ATYPON_BROWSER_WORKFLOW_PROVIDER_NAMES",
    "DEFAULT_SITE_RULE",
    "GENERIC_PROFILE",
    "PublisherProfile",
    "build_html_candidates",
    "build_pdf_candidates",
    "extract_pdf_url_from_crossref",
    "noise_profile_for_publisher",
    "preferred_html_candidate_from_landing_page",
    "publisher_profile",
    "site_rule_for_publisher",
]


@dataclass(frozen=True)
class PublisherProfile:
    name: str
    hosts: tuple[str, ...]
    noise_profile: str = "generic"
    site_rule_overrides: Mapping[str, Any] = field(default_factory=dict)
    positive_signals: Callable[[str], tuple[list[str], list[str], list[str]]] = (
        default_positive_signals
    )
    blocking_fallback_signals: Callable[[str], list[str]] = lambda _html_text: []
    dom_hooks: DomHooks = field(default_factory=DomHooks)
    markdown_hooks: MarkdownHooks = field(default_factory=MarkdownHooks)
    refine_selected_container: Callable[..., Any] | None = None
    select_content_nodes: Callable[..., list[Any]] | None = None
    finalize_extraction: Callable[..., tuple[str, dict[str, Any]]] | None = None
    extract_asset_html_scopes: Callable[..., tuple[str, str]] | None = None
    scoped_asset_extractor: Callable[..., list[dict[str, Any]]] | None = None
    is_front_matter_teaser_figure: Callable[..., bool] | None = None
    prepare_browser_page: Callable[..., Mapping[str, Any] | None] | None = None


ATYPON_BROWSER_WORKFLOW_PROVIDER_NAMES = (
    "science",
    "pnas",
    "wiley",
    "ams",
    "acs",
    "iop",
    "aip",
    "tandf",
)


def _unsupported_atypon_publisher_message(route_kind: str, publisher: str) -> str:
    supported = ", ".join(ATYPON_BROWSER_WORKFLOW_PROVIDER_NAMES)
    return (
        f"Unsupported Atypon browser-workflow {route_kind} publisher: {publisher!r}. "
        f"Supported provider-catalog names: {supported}."
    )


@cache
def _publisher_module(publisher: str | None) -> ModuleType | None:
    normalized = normalize_text(publisher or "").lower()
    if normalized not in ATYPON_BROWSER_WORKFLOW_PROVIDER_NAMES:
        return None
    return import_module(f"._{normalized}_html", package=__package__)


def preferred_html_candidate_from_landing_page(
    publisher: str,
    doi: str,
    landing_page_url: str | None,
) -> str | None:
    normalized = normalize_text(publisher).lower()
    if _publisher_module(normalized) is None:
        return None
    return _preferred_html_candidate_from_landing_page(
        doi,
        landing_page_url,
        hosts=provider_domains(normalized),
    )


GENERIC_PROFILE = PublisherProfile(name="generic", hosts=tuple())


def _positive_signals_for_policy(
    availability: Any, html_text: str
) -> tuple[list[str], list[str], list[str]]:
    strong, soft, abstract_only = default_positive_signals(html_text)
    if availability.datalayer_signal_set is not None:
        data_strong, data_soft, data_abstract = evaluate_datalayer_positive_signals(
            html_text, availability.datalayer_signal_set
        )
        strong.extend(data_strong)
        soft.extend(data_soft)
        abstract_only.extend(data_abstract)
    if availability.text_marker_signal_set is not None:
        text_strong, text_soft, text_abstract = evaluate_text_marker_positive_signals(
            html_text, availability.text_marker_signal_set
        )
        strong.extend(text_strong)
        soft.extend(text_soft)
        abstract_only.extend(text_abstract)
    return (
        _html_profiles.dedupe_signals(strong),
        _html_profiles.dedupe_signals(soft),
        _html_profiles.dedupe_signals(abstract_only),
    )


def _blocking_signals_for_policy(availability: Any, html_text: str) -> list[str]:
    signals: list[str] = []
    if availability.datalayer_signal_set is not None:
        signals.extend(
            evaluate_datalayer_blocking_signals(
                html_text, availability.datalayer_signal_set
            )
        )
    if availability.text_marker_signal_set is not None:
        signals.extend(
            evaluate_text_marker_blocking_signals(
                html_text, availability.text_marker_signal_set
            )
        )
    return _html_profiles.dedupe_signals(signals)


def publisher_profile(publisher: str | None) -> PublisherProfile:
    normalized = normalize_text(publisher or "").lower()
    module = _publisher_module(normalized)
    if module is None:
        return GENERIC_PROFILE
    rules = provider_html_rules(normalized)
    availability = rules.availability
    return PublisherProfile(
        name=normalized,
        hosts=provider_domains(normalized),
        noise_profile=normalize_text(rules.noise_profile) or "generic",
        site_rule_overrides=copy.deepcopy(dict(availability.site_rule_overrides)),
        positive_signals=lambda html_text: _positive_signals_for_policy(
            availability, html_text
        ),
        blocking_fallback_signals=lambda html_text: _blocking_signals_for_policy(
            availability, html_text
        ),
        dom_hooks=rules.dom_hooks,
        markdown_hooks=rules.markdown_hooks,
        refine_selected_container=getattr(module, "refine_selected_container", None),
        select_content_nodes=getattr(module, "select_content_nodes", None),
        finalize_extraction=getattr(module, "finalize_extraction", None),
        extract_asset_html_scopes=getattr(module, "extract_asset_html_scopes", None),
        scoped_asset_extractor=getattr(module, "scoped_asset_extractor", None),
        is_front_matter_teaser_figure=getattr(
            module, "is_front_matter_teaser_figure", None
        ),
        prepare_browser_page=getattr(module, "prepare_browser_page", None),
    )


def site_rule_for_publisher(publisher: str | None) -> dict[str, Any]:
    return _html_profiles.site_rule_for_publisher(publisher)


def noise_profile_for_publisher(publisher: str | None) -> str:
    return _html_profiles.noise_profile_for_publisher(publisher)


def build_html_candidates(
    publisher: str, doi: str, landing_page_url: str | None = None
) -> list[str]:
    normalized = normalize_text(publisher).lower()
    if _publisher_module(normalized) is None:
        raise ValueError(_unsupported_atypon_publisher_message("HTML", publisher))
    return build_browser_workflow_html_candidates(
        doi,
        landing_page_url,
        hosts=provider_domains(normalized),
        base_hosts=provider_base_domains(normalized),
        path_templates=provider_html_path_templates(normalized),
    )


def build_pdf_candidates(
    publisher: str, doi: str, crossref_pdf_url: str | None
) -> list[str]:
    normalized = normalize_text(publisher).lower()
    if _publisher_module(normalized) is None:
        raise ValueError(_unsupported_atypon_publisher_message("PDF", publisher))
    if normalized == "ams":
        return []
    crossref_pdf_position = provider_crossref_pdf_position(normalized)
    return build_browser_workflow_pdf_candidates(
        doi,
        crossref_pdf_url,
        hosts=provider_domains(normalized),
        base_hosts=provider_base_domains(normalized),
        path_templates=provider_pdf_path_templates(normalized),
        crossref_pdf_position=crossref_pdf_position,
        base_seed_url=crossref_pdf_url if crossref_pdf_position == 0 else None,
    )
