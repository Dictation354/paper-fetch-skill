"""Atypon browser-workflow profile dispatch for provider-owned browser routes."""

from __future__ import annotations

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
from ..utils import normalize_text
from . import _ams_assets, _ams_dom, _ams_markdown
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
    if normalized == "ams":
        return _ams_dom
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


def publisher_profile(publisher: str | None) -> PublisherProfile:
    normalized = normalize_text(publisher or "").lower()
    module = _publisher_module(normalized)
    if module is None:
        return GENERIC_PROFILE
    rules = provider_html_rules(normalized)
    if normalized == "ams":
        return PublisherProfile(
            name=normalized,
            hosts=provider_domains(normalized),
            dom_hooks=rules.dom_hooks,
            markdown_hooks=rules.markdown_hooks,
            refine_selected_container=_ams_dom.refine_selected_container,
            select_content_nodes=_ams_dom.select_content_nodes,
            finalize_extraction=_ams_markdown.finalize_extraction,
            extract_asset_html_scopes=_ams_assets.extract_asset_html_scopes,
            scoped_asset_extractor=_ams_assets.scoped_asset_extractor,
        )
    return PublisherProfile(
        name=normalized,
        hosts=provider_domains(normalized),
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
