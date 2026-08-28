"""American Meteorological Society provider client."""

from __future__ import annotations

import re
import urllib.parse
from collections.abc import Mapping
from typing import Any

from ..extraction.html.availability_policy import AvailabilityPolicy
from ..extraction.html.provider_rules import (
    AMS_DOM_POSTPROCESS_CLEANUP_SELECTORS,
    AMS_FRONT_MATTER_EXACT_TEXTS,
    AMS_FRONT_MATTER_PUBLICATION_KEYWORDS,
    AMS_MARKDOWN_PROMO_TOKENS,
    AMS_POST_CONTENT_BREAK_TOKENS,
    AMS_SITE_RULE_OVERRIDES,
    ATYPON_FRONT_MATTER_CONTAINS_TOKENS,
    DomHooks,
    MarkdownHooks,
    ProviderCleanupRules,
    ProviderFormulaRules,
    ProviderFrontMatterRules,
    ProviderHtmlRules,
)
from ..publisher_identity import normalize_doi
from ..provider_catalog import ProviderRouteSpec, ProviderSpec
from ..quality.html_signals import AMS_TEXT_MARKER_SIGNAL_SET
from ..utils import normalize_text
from . import _ams_html, browser_workflow
from .base import RawFulltextPayload
from ._registry import ProviderBundle, register_provider_bundle
from ..reason_codes import PDF_FALLBACK


register_provider_bundle(
    ProviderBundle(
        catalog=ProviderSpec(
            name="ams",
            display_name="AMS",
            official=True,
            domains=("journals.ametsoc.org", "ametsoc.org"),
            doi_prefixes=("10.1175/",),
            publisher_aliases=(
                "american meteorological society",
                "ams",
                "american meteorological society (ams)",
            ),
            asset_default="body",
            probe_capability="routing_signal",
            provider_managed_abstract_only=True,
            client_factory_path="paper_fetch.providers.ams:AmsClient",
            status_order=9,
            base_domains=("journals.ametsoc.org",),
            crossref_pdf_position=0,
            routes=(
                ProviderRouteSpec(name="metadata", kind="metadata"),
                ProviderRouteSpec(
                    name="browser_html",
                    kind="html",
                    browser_required=True,
                    browser_preflight=True,
                    auth_supported=True,
                    requires_playwright=True,
                    concurrency=1,
                ),
                ProviderRouteSpec(
                    name="browser_pdf",
                    kind="pdf",
                    browser_required=True,
                    browser_preflight=True,
                    auth_supported=True,
                    requires_playwright=True,
                    requires_pdf_conversion=True,
                    concurrency=1,
                ),
                ProviderRouteSpec(
                    name="assets",
                    kind="assets",
                    concurrency=2,
                    asset_scope="body",
                ),
            ),
        ),
        html_rules=ProviderHtmlRules(
            name="ams",
            cleanup=ProviderCleanupRules(
                markdown_promo_tokens=AMS_MARKDOWN_PROMO_TOKENS,
                dom_postprocess_cleanup_selectors=AMS_DOM_POSTPROCESS_CLEANUP_SELECTORS,
                post_content_break_tokens=AMS_POST_CONTENT_BREAK_TOKENS,
            ),
            availability=AvailabilityPolicy(
                name="ams",
                site_rule_overrides=AMS_SITE_RULE_OVERRIDES,
                text_marker_signal_set=AMS_TEXT_MARKER_SIGNAL_SET,
            ),
            front_matter=ProviderFrontMatterRules(
                exact_texts=AMS_FRONT_MATTER_EXACT_TEXTS,
                contains_tokens=ATYPON_FRONT_MATTER_CONTAINS_TOKENS,
                publication_keywords=AMS_FRONT_MATTER_PUBLICATION_KEYWORDS,
            ),
            formula=ProviderFormulaRules(
                container_tokens=("formula",),
                display_selectors=("div.formula",),
            ),
            dom_hooks=DomHooks(
                before_block_normalization=_ams_html.ams_before_block_normalization,
                after_block_normalization=_ams_html.ams_after_block_normalization,
                body_container=_ams_html.ams_body_container,
                asset_body_container=_ams_html.ams_asset_body_container,
                asset_figure_extraction=_ams_html.ams_asset_figure_extraction,
            ),
            markdown_hooks=MarkdownHooks(
                normalize_markdown=_ams_html.ams_normalize_markdown,
                classify_heading=_ams_html.ams_classify_heading,
                keep_unknown_abstract_block=_ams_html.ams_keep_unknown_abstract_block,
            ),
        ),
        sources=("ams_html", "ams_pdf"),
    )
)


AMS_BROWSER_PROFILE = browser_workflow.make_atypon_browser_profile(
    "ams",
    fallback_author_extractor=_ams_html.extract_authors,
    policy=browser_workflow.BrowserWorkflowPolicy(
        blocked_resource_types=("image", "font", "media"),
        preflight_html_reuse=True,
        doi_route_hint=True,
    ),
)
AMS_SICI_DOI_PATTERN = re.compile(
    r"^10\.1175/[0-9]{4}-[0-9]{4}\(\d{4}\)\d{3}<[^>]+>2\.0\.co;2$",
    flags=re.IGNORECASE,
)


def _append_unique(candidates: list[str], candidate: str | None) -> None:
    normalized = normalize_text(candidate)
    if normalized and normalized not in candidates:
        candidates.append(normalized)


def _ams_old_style_doi_url(doi: str) -> str | None:
    normalized = normalize_text(doi)
    if not AMS_SICI_DOI_PATTERN.match(normalized):
        return None
    return f"https://doi.org/{urllib.parse.quote(normalized, safe='/')}"


def _ams_pdf_candidate_urls_from_landing_url(
    landing_page_url: str | None, *, derive_from_article_url: bool
) -> list[str]:
    url = normalize_text(landing_page_url)
    if not url:
        return []
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return []

    candidates: list[str] = []

    def append_path(path: str, query: str = "") -> None:
        candidate = urllib.parse.urlunparse(
            (parsed.scheme, parsed.netloc, path, "", query, "")
        )
        _append_unique(candidates, candidate)

    path = parsed.path
    lowered_path = path.lower()
    if "/downloadpdf/" in lowered_path or lowered_path.endswith(".pdf"):
        append_path(path, parsed.query)
        return candidates

    if not derive_from_article_url or not path.startswith("/view/"):
        return candidates

    suffix = path.removeprefix("/view")
    for prefix in ("/downloadpdf", "/downloadpdf/view"):
        append_path(f"{prefix}{suffix}")
        if suffix.lower().endswith(".xml"):
            append_path(f"{prefix}{suffix[:-4]}.pdf")
    return candidates


class AmsClient(browser_workflow.BrowserWorkflowClient):
    name = AMS_BROWSER_PROFILE.name
    profile = AMS_BROWSER_PROFILE

    def html_candidates(self, doi: str, metadata: Mapping[str, Any]) -> list[str]:
        candidates: list[str] = []
        for candidate in super().html_candidates(doi, metadata):
            _append_unique(candidates, candidate)
        _append_unique(candidates, _ams_old_style_doi_url(doi))
        return candidates

    def pdf_candidates(self, doi: str, metadata: Mapping[str, Any]) -> list[str]:
        candidates: list[str] = []
        normalized_doi = normalize_doi(doi) or normalize_text(doi)
        old_style_doi = bool(AMS_SICI_DOI_PATTERN.match(normalized_doi))
        _append_unique(
            candidates,
            browser_workflow.extract_pdf_url_from_crossref(metadata),
        )
        for key in ("landing_page_url", "source_url"):
            for candidate in _ams_pdf_candidate_urls_from_landing_url(
                str(metadata.get(key) or "") or None,
                derive_from_article_url=not old_style_doi,
            ):
                _append_unique(candidates, candidate)
        return candidates

    def article_source_for_payload(self, raw_payload: RawFulltextPayload) -> str:
        if (
            raw_payload.content is not None
            and normalize_text(raw_payload.content.route_kind).lower() == PDF_FALLBACK
        ):
            return "ams_pdf"
        return "ams_html"

    def to_article_model(self, *args, **kwargs):
        article = super().to_article_model(*args, **kwargs)
        return _ams_html.normalize_article_model(article)
