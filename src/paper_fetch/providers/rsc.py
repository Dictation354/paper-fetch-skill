"""Royal Society of Chemistry journal provider."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any
from urllib.parse import quote

from ..errors import ProviderFailure
from ..extraction.html._metadata import parse_html_metadata
from ..extraction.html.availability_policy import AvailabilityPolicy
from ..extraction.html.landing import LandingHtmlFetchResult
from ..extraction.html.provider_rules import ProviderHtmlRules
from ..metadata.types import ProviderMetadata
from ..publisher_identity import normalize_doi
from ..quality.access_boundary import (
    CONFIRMED_PAYWALL,
    confirmed_paywall,
    html_paywall_diagnostics,
    paywall_failure,
)
from ..rsc_url import (
    is_rsc_main_pdf,
    is_rsc_silverchair_article,
    rsc_legacy_article_url,
)
from ..runtime import RuntimeContext
from ..utils import normalize_text
from . import _rsc_html, browser_workflow
from ._definitions import PROVIDER_DEFINITIONS
from ._registry import BrowserAssetPolicy, BrowserPagePolicy, ProviderBundle
from .base import RawFulltextPayload
from .browser_runtime.api import (
    ensure_runtime_ready,
    fetch_html_with_browser,
    load_runtime_config,
)
from .browser_runtime.types import BrowserHtmlReadiness, BrowserRuntimeFailure

_DEFINITION = PROVIDER_DEFINITIONS["rsc"]
_PROFILE = browser_workflow.make_browser_profile(
    "rsc",
    catalog=_DEFINITION.catalog,
    fallback_author_extractor=None,
    html_readiness=BrowserHtmlReadiness(wait_for_article_body=False),
    policy=browser_workflow.BrowserWorkflowPolicy(fast_html_attempt=False),
    scoped_asset_extractor=_rsc_html.extract_scoped_assets,
)


@dataclass(frozen=True)
class RscArticleIdentity:
    doi: str
    url: str
    title: str | None
    access_failure: ProviderFailure | None = None


def resolve_article_page(
    url: str,
    *,
    landing: LandingHtmlFetchResult | None,
    env: Mapping[str, str],
    context: RuntimeContext | None,
) -> RscArticleIdentity | None:
    if landing is not None and is_rsc_silverchair_article(landing.final_url):
        doi = normalize_doi(landing.metadata.get("doi"))
        if doi.startswith("10.1039/") and _rsc_html.article_matches(
            landing.metadata, landing.final_url, doi
        ):
            diagnostics = html_paywall_diagnostics(
                landing.html_text,
                metadata={"doi": doi},
                source_url=landing.final_url,
                provider="rsc",
                context=context,
            )
            return RscArticleIdentity(
                doi,
                landing.final_url,
                landing.metadata.get("title"),
                paywall_failure(diagnostics, body=landing.html_text)
                if diagnostics
                else None,
            )

    access_failure: ProviderFailure | None = None
    try:
        runtime = load_runtime_config(env, provider="rsc", doi="")
        ensure_runtime_ready(runtime)
        page = fetch_html_with_browser(
            [url],
            publisher="rsc",
            config=runtime,
            readiness=BrowserHtmlReadiness(wait_for_article_body=False),
            runtime_context=context,
        )
    except BrowserRuntimeFailure:
        return None
    except ProviderFailure as exc:
        if not confirmed_paywall(exc):
            return None
        details = exc.diagnostics.details
        final_url = str(details[CONFIRMED_PAYWALL].get("source_url") or "")
        html_text = str(details.get("received_html") or "")
        access_failure = exc
    else:
        final_url, html_text = page.final_url, page.html
    if not is_rsc_silverchair_article(final_url):
        return None
    metadata = parse_html_metadata(html_text, final_url)
    if browser_doi := _rsc_html.citation_doi(metadata):
        return RscArticleIdentity(
            browser_doi, final_url, metadata.get("title"), access_failure
        )
    return None


def _article_urls(metadata: ProviderMetadata) -> list[str]:
    return list(
        filter(
            None,
            map(
                normalize_text,
                (metadata.get("source_url"), metadata.get("landing_page_url")),
            ),
        )
    )


class RscClient(browser_workflow.BrowserWorkflowClient):
    name = _PROFILE.name
    profile = _PROFILE

    def fetch_raw_fulltext(
        self,
        doi: str,
        metadata: Mapping[str, Any],
        *,
        context: RuntimeContext | None = None,
    ) -> RawFulltextPayload:
        return super().fetch_raw_fulltext(
            doi, {**metadata, "doi": normalize_doi(doi)}, context=context
        )

    def html_candidates(self, doi: str, metadata: ProviderMetadata) -> list[str]:
        doi = normalize_doi(doi)
        urls = [
            article
            for url in _article_urls(metadata)
            if (
                article := (
                    url
                    if is_rsc_silverchair_article(url)
                    else rsc_legacy_article_url(url, doi)
                )
            )
        ]
        if doi:
            urls.append(f"https://doi.org/{quote(doi, safe='/')}")
        return list(dict.fromkeys(urls))

    def pdf_candidates(self, doi: str, metadata: ProviderMetadata) -> list[str]:
        doi = normalize_doi(doi)
        urls = [
            url
            for link in metadata.get("fulltext_links") or []
            if (url := normalize_text(link.get("url")))
            if is_rsc_main_pdf(url, doi)
        ]
        urls.extend(
            pdf
            for url in _article_urls(metadata)
            if (pdf := rsc_legacy_article_url(url, doi, pdf=True))
        )
        return list(dict.fromkeys(urls))

    def pdf_candidates_from_html(
        self, html_text: str, source_url: str, *, doi: str
    ) -> list[str]:
        return _rsc_html.pdf_candidates_from_html(html_text, source_url, doi=doi)

    def extract_asset_html_scopes(
        self, html_text: str, source_url: str
    ) -> tuple[str, str]:
        return _rsc_html.extract_asset_html_scopes(html_text, source_url)

    def extract_markdown(
        self, html_text: str, final_url: str, *, metadata: ProviderMetadata
    ):
        return _rsc_html.extract_markdown(html_text, final_url, metadata=metadata)


PROVIDER_BUNDLE = ProviderBundle(
    client_factory=RscClient,
    catalog=_DEFINITION.catalog,
    sources=_DEFINITION.sources,
    browser_page_policy=BrowserPagePolicy(
        document_hosts=_DEFINITION.catalog.domains,
        remaining_review_candidates=_rsc_html.remaining_html_candidates,
    ),
    browser_asset_policy=BrowserAssetPolicy(click_supplements=True),
    browser_pdf_only=True,
    html_rules=ProviderHtmlRules(
        name=_DEFINITION.rules_name,
        availability=AvailabilityPolicy(
            name="rsc",
            site_rule_overrides={"candidate_selectors": [_rsc_html.FULLTEXT_SELECTOR]},
            paywall_abstract_selector=_rsc_html.ABSTRACT_SELECTOR,
            paywall_gate_selectors=".widget-ArticlePaywall, .article-access-options",
            paywall_body_selector=_rsc_html.FULLTEXT_SELECTOR,
            paywall_paragraph_selector=_rsc_html.BODY_PARAGRAPH_SELECTOR,
            paywall_hosts=_DEFINITION.catalog.domains,
        ),
    ),
)
