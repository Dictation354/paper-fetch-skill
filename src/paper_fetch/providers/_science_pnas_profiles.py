"""Compatibility wrappers and provider-owned behavior dispatch for browser workflow."""

from __future__ import annotations

import copy
from dataclasses import dataclass, field
from typing import Any, Callable, Mapping

from ..quality import html_profiles as _html_profiles
from ..utils import normalize_text
from . import _pnas_html, _science_html, _wiley_html
from ._browser_workflow_shared import (
    extract_pdf_url_from_crossref,
    preferred_html_candidate_from_landing_page as _preferred_html_candidate_from_landing_page,
)
DEFAULT_SITE_RULE = _html_profiles.DEFAULT_SITE_RULE
looks_like_abstract_redirect = _html_profiles.looks_like_abstract_redirect

__all__ = [
    "DEFAULT_SITE_RULE",
    "GENERIC_PROFILE",
    "PublisherProfile",
    "build_html_candidates",
    "build_pdf_candidates",
    "extract_pdf_url_from_crossref",
    "looks_like_abstract_redirect",
    "noise_profile_for_publisher",
    "preferred_html_candidate_from_landing_page",
    "provider_blocking_fallback_signals",
    "provider_positive_signals",
    "publisher_profile",
    "site_rule_for_publisher",
]


@dataclass(frozen=True)
class PublisherProfile:
    name: str
    hosts: tuple[str, ...]
    noise_profile: str = "generic"
    site_rule_overrides: Mapping[str, Any] = field(default_factory=dict)
    positive_signals: Callable[[str], tuple[list[str], list[str], list[str]]] = _html_profiles.default_positive_signals
    blocking_fallback_signals: Callable[[str], list[str]] = lambda _html_text: []
    markdown_postprocess: Callable[[str], str] | None = None
    dom_postprocess: Callable[[Any], None] | None = None
    refine_selected_container: Callable[..., Any] | None = None
    select_content_nodes: Callable[..., list[Any]] | None = None
    finalize_extraction: Callable[..., tuple[str, dict[str, Any]]] | None = None


_PUBLISHER_MODULES = {
    "science": _science_html,
    "pnas": _pnas_html,
    "wiley": _wiley_html,
}


def preferred_html_candidate_from_landing_page(
    publisher: str,
    doi: str,
    landing_page_url: str | None,
) -> str | None:
    module = _PUBLISHER_MODULES.get(normalize_text(publisher).lower())
    if module is None:
        return None
    hosts = tuple(getattr(module, "HOSTS", ()))
    return _preferred_html_candidate_from_landing_page(
        doi,
        landing_page_url,
        hosts=hosts,
    )


GENERIC_PROFILE = PublisherProfile(name="generic", hosts=tuple())


def publisher_profile(publisher: str | None) -> PublisherProfile:
    normalized = normalize_text(publisher or "").lower()
    module = _PUBLISHER_MODULES.get(normalized)
    if module is None:
        return GENERIC_PROFILE
    availability_profile = _html_profiles.availability_profile_for_publisher(normalized)
    return PublisherProfile(
        name=normalized,
        hosts=tuple(getattr(module, "HOSTS", ())),
        noise_profile=normalize_text(availability_profile.noise_profile) or "generic",
        site_rule_overrides=copy.deepcopy(availability_profile.site_rule_overrides),
        positive_signals=availability_profile.positive_signals,
        blocking_fallback_signals=availability_profile.blocking_fallback_signals,
        markdown_postprocess=getattr(module, "markdown_postprocess", None),
        dom_postprocess=getattr(module, "dom_postprocess", None),
        refine_selected_container=getattr(module, "refine_selected_container", None),
        select_content_nodes=getattr(module, "select_content_nodes", None),
        finalize_extraction=getattr(module, "finalize_extraction", None),
    )


def site_rule_for_publisher(publisher: str | None) -> dict[str, Any]:
    return _html_profiles.site_rule_for_publisher(publisher)


def noise_profile_for_publisher(publisher: str | None) -> str:
    return _html_profiles.noise_profile_for_publisher(publisher)


def build_html_candidates(publisher: str, doi: str, landing_page_url: str | None = None) -> list[str]:
    module = _PUBLISHER_MODULES.get(normalize_text(publisher).lower())
    if module is None:
        raise ValueError(f"Unsupported browser-workflow HTML publisher: {publisher!r}")
    return list(module.build_html_candidates(doi, landing_page_url))


def build_pdf_candidates(publisher: str, doi: str, crossref_pdf_url: str | None) -> list[str]:
    module = _PUBLISHER_MODULES.get(normalize_text(publisher).lower())
    if module is None:
        raise ValueError(f"Unsupported browser-workflow PDF publisher: {publisher!r}")
    return list(module.build_pdf_candidates(doi, crossref_pdf_url))


def provider_positive_signals(
    publisher: str | None,
    html_text: str,
) -> tuple[list[str], list[str], list[str]]:
    return _html_profiles.provider_positive_signals(publisher, html_text)


def provider_blocking_fallback_signals(
    publisher: str | None,
    html_text: str,
) -> list[str]:
    return _html_profiles.provider_blocking_fallback_signals(publisher, html_text)
