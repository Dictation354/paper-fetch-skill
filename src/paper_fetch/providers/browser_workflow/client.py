"""Browser workflow provider client base class."""

from __future__ import annotations

from functools import partial
from pathlib import Path
from typing import Any, cast
from collections.abc import Mapping

from ...config import (
    build_browser_user_agent,
    build_publisher_user_agent,
    resolve_asset_download_concurrency,
)
from ...extraction.html import decode_html
from ...extraction.html.signals import HtmlExtractionFailure
from ...metadata.types import ProviderMetadata
from ...models import AssetProfile
from ...publisher_identity import normalize_doi
from ...reason_codes import (
    ABSTRACT_ONLY,
    AWS_WAF_CHALLENGE,
    CLOUDFLARE_CHALLENGE,
    FULLTEXT,
    NO_ACCESS,
    NO_RESULT,
    NOT_SUPPORTED,
    PDF_FALLBACK,
    PUBLISHER_ACCESS_DENIED,
    PUBLISHER_PAYWALL,
    REDIRECTED_TO_ABSTRACT,
)
from ...runtime import RuntimeContext
from ...tracing import download_marker, fulltext_marker, trace_event, trace_from_markers
from ...utils import empty_asset_results, normalize_text, provider_display_name
from .shared import (
    BrowserWorkflowDeps,
    build_browser_workflow_html_candidates,
    build_browser_workflow_pdf_candidates,
    default_browser_workflow_deps,
    extract_pdf_url_from_crossref,
)
from ..browser_runtime import merge_browser_context_seeds
from .._pdf_fallback import PdfFallbackFailure
from .._waterfall import ProviderWaterfallStep, run_provider_waterfall
from ..base import (
    PreparedFetchResultPayload,
    ProviderArtifacts,
    ProviderClient,
    ProviderFailure,
    RawFulltextPayload,
)
from .fetchers import (
    BrowserDocumentFetcherOptions,
    _MemoizedFigurePageFetcher,
    _MemoizedImageDocumentFetcher,
)
from .article import (
    _finalize_abstract_only_provider_article,
    browser_workflow_article_from_payload,
    merge_provider_owned_authors,
)
from .asset_download import (
    BrowserAssetRecoveryContext,
    download_browser_backed_related_assets,
    plan_browser_asset_download,
)
from .profile import ProviderBrowserProfile


_BROWSER_WORKFLOW_ACCESS_FAILURE_REASONS = frozenset(
    {
        AWS_WAF_CHALLENGE,
        CLOUDFLARE_CHALLENGE,
        PUBLISHER_ACCESS_DENIED,
        PUBLISHER_PAYWALL,
        REDIRECTED_TO_ABSTRACT,
    }
)


class BrowserWorkflowClient(ProviderClient):
    name = "browser_workflow"
    article_source_name: str | None = None
    profile: ProviderBrowserProfile | None = None
    route_order: tuple[str, ...] = ()

    def __init__(
        self,
        transport,
        env: Mapping[str, str],
        deps: BrowserWorkflowDeps = default_browser_workflow_deps(),
    ) -> None:
        self.transport = transport
        self.env = dict(env)
        self.user_agent = build_publisher_user_agent(env)
        self.browser_user_agent = build_browser_user_agent(env)
        self.deps = deps

    def probe_status(self):
        return self.deps.probe_runtime_status(self.env, provider=self.name)

    def _html_failure_code(self, reason: str | None) -> str:
        return (
            NO_ACCESS
            if reason in _BROWSER_WORKFLOW_ACCESS_FAILURE_REASONS
            else NO_RESULT
        )

    def fetch_metadata(self, query: Mapping[str, str | None]) -> ProviderMetadata:
        raise ProviderFailure(
            NOT_SUPPORTED,
            f"{self.name} official metadata retrieval is not implemented; routing relies on Crossref metadata.",
        )

    def article_source(self) -> str:
        if self.article_source_name:
            return self.article_source_name
        profile = self.profile
        if profile is not None and profile.article_source_name:
            return profile.article_source_name
        return self.name

    def article_source_for_payload(self, raw_payload: RawFulltextPayload) -> str:
        del raw_payload
        return self.article_source()

    def require_profile(self) -> ProviderBrowserProfile:
        profile = self.profile
        if profile is None:
            raise ProviderFailure(
                NOT_SUPPORTED,
                f"{self.name} must declare a browser workflow profile.",
            )
        return profile

    def provider_label(self) -> str:
        profile = self.profile
        if profile is not None and profile.label:
            return profile.label
        return provider_display_name(self.name)

    def _direct_http_asset_mode(self, seed: Mapping[str, Any]) -> bool:
        return (
            self.name == "ams"
            and normalize_text(str(seed.get("paper_fetch_html_fetcher") or ""))
            == "direct_http"
        )

    def allow_pdf_fallback_after_html_failure(
        self,
        *,
        html_failure_reason: str | None,
        html_failure_message: str | None,
    ) -> bool:
        return True

    def _recover_pdf_payload_from_abstract_only_html(
        self,
        doi: str,
        metadata: ProviderMetadata,
        raw_payload: RawFulltextPayload,
        *,
        context: RuntimeContext | None = None,
    ) -> RawFulltextPayload:
        normalized_doi = normalize_doi(doi)
        if not normalized_doi:
            raise ProviderFailure(
                NOT_SUPPORTED, f"{self.name} PDF fallback requires a DOI."
            )
        content = raw_payload.content
        if content is None or normalize_text(content.route_kind).lower() != "html":
            raise ProviderFailure(
                NOT_SUPPORTED,
                f"{self.name} PDF fallback recovery requires provider-owned HTML content.",
            )

        html_failure_reason = ABSTRACT_ONLY
        html_failure_message = f"{self.name} HTML route only exposed abstract-level content after markdown extraction."
        recovery_warning = f"{self.name} HTML route only exposed abstract-level content after markdown extraction; attempting PDF fallback."
        runtime = self.deps.load_runtime_config(
            self.env,
            provider=self.name,
            doi=normalized_doi,
        )
        self.deps.ensure_runtime_ready(runtime)
        return self.deps.fetch_seeded_browser_pdf_payload(
            provider=self.name,
            doi=normalized_doi,
            runtime=runtime,
            pdf_candidates=self.pdf_candidates(normalized_doi, metadata),
            html_candidates=self.html_candidates(normalized_doi, metadata),
            landing_page_url=str(
                metadata.get("landing_page_url") or raw_payload.source_url or ""
            )
            or None,
            user_agent=self.user_agent,
            browser_context_seed=dict(content.browser_context_seed or {}),
            html_failure_reason=html_failure_reason,
            html_failure_message=html_failure_message,
            warnings=[*raw_payload.warnings, recovery_warning],
            success_source_trail=[
                fulltext_marker(self.name, "ok", route="html"),
                fulltext_marker(self.name, ABSTRACT_ONLY),
                fulltext_marker(self.name, "ok", route=PDF_FALLBACK),
            ],
            context=context,
            deps=self.deps,
        )

    def html_candidates(self, doi: str, metadata: ProviderMetadata) -> list[str]:
        profile = self.require_profile()
        landing_page_url = str(metadata.get("landing_page_url") or "") or None
        return build_browser_workflow_html_candidates(
            doi,
            landing_page_url,
            hosts=profile.hosts,
            base_hosts=profile.base_hosts,
            path_templates=profile.html_path_templates,
        )

    def pdf_candidates(self, doi: str, metadata: ProviderMetadata) -> list[str]:
        profile = self.require_profile()
        crossref_pdf_url = extract_pdf_url_from_crossref(metadata)
        return build_browser_workflow_pdf_candidates(
            doi,
            crossref_pdf_url,
            hosts=profile.hosts,
            base_hosts=profile.base_hosts,
            path_templates=profile.pdf_path_templates,
            crossref_pdf_position=profile.crossref_pdf_position,
            base_seed_url=crossref_pdf_url
            if profile.crossref_pdf_position == 0
            else None,
        )

    def extract_markdown(
        self,
        html_text: str,
        final_url: str,
        *,
        metadata: ProviderMetadata,
    ) -> tuple[str, dict[str, Any]]:
        profile = self.require_profile()
        publisher = normalize_text(profile.markdown_publisher) or profile.name
        return self.deps.extract_atypon_browser_workflow_markdown(
            html_text,
            final_url,
            publisher,
            metadata=metadata,
        )

    def fetch_raw_fulltext(
        self,
        doi: str,
        metadata: Mapping[str, Any],
        *,
        context: RuntimeContext | None = None,
    ) -> RawFulltextPayload:
        context = self._runtime_context(context)
        provider_metadata = cast(ProviderMetadata, metadata)
        bootstrap = self.deps.bootstrap_browser_workflow(
            self,
            doi,
            provider_metadata,
            context=context,
            deps=self.deps,
        )
        if bootstrap.html_payload is not None:
            return bootstrap.html_payload

        if not self.allow_pdf_fallback_after_html_failure(
            html_failure_reason=bootstrap.html_failure_reason,
            html_failure_message=bootstrap.html_failure_message,
        ):
            reason = bootstrap.html_failure_message or f"{self.name} HTML route failed."
            raise ProviderFailure(
                self._html_failure_code(bootstrap.html_failure_reason),
                (
                    f"{self.name} HTML route was not usable ({bootstrap.html_failure_reason or 'html_failed'}); "
                    f"PDF fallback is disabled. {reason}"
                ),
                warnings=[
                    f"{self.name} HTML route was not usable; skipping PDF fallback."
                ],
                source_trail=[fulltext_marker(self.name, "fail", route="html")],
                trace=(
                    [
                        trace_event(
                            "fulltext",
                            f"{self.name}_html",
                            "fail",
                            code=bootstrap.html_failure_reason,
                            message=bootstrap.html_failure_message,
                        )
                    ]
                    if bootstrap.html_failure_reason
                    else []
                ),
            )

        initial_warning = (
            f"{self.name} HTML route was not usable "
            f"({bootstrap.html_failure_reason or 'html_failed'}); attempting PDF fallback."
        )

        def run_pdf_fallback(_state) -> RawFulltextPayload:
            try:
                return self.deps.fetch_seeded_browser_pdf_payload(
                    provider=self.name,
                    doi=normalize_doi(str(metadata.get("doi") or "")) or doi,
                    runtime=bootstrap.runtime,
                    pdf_candidates=bootstrap.pdf_candidates,
                    html_candidates=bootstrap.html_candidates,
                    landing_page_url=bootstrap.landing_page_url,
                    user_agent=self.user_agent,
                    browser_context_seed=bootstrap.browser_context_seed,
                    html_failure_reason=bootstrap.html_failure_reason,
                    html_failure_message=bootstrap.html_failure_message,
                    html_failure_diagnostics=bootstrap.html_failure_diagnostics,
                    warnings=[],
                    success_source_trail=[],
                    context=context,
                    deps=self.deps,
                )
            except PdfFallbackFailure as exc:
                reason = (
                    bootstrap.html_failure_message or f"{self.name} HTML route failed."
                )
                raise ProviderFailure(
                    self._html_failure_code(bootstrap.html_failure_reason),
                    (
                        f"{self.name} full text could not be retrieved via HTML or PDF fallback. "
                        f"HTML failure: {reason} PDF failure: {exc.message}"
                    ),
                    trace=(
                        [
                            trace_event(
                                "fulltext",
                                f"{self.name}_html",
                                "fail",
                                code=bootstrap.html_failure_reason,
                                message=bootstrap.html_failure_message,
                            )
                        ]
                        if bootstrap.html_failure_reason
                        else []
                    ),
                ) from exc

        return run_provider_waterfall(
            [
                ProviderWaterfallStep(
                    label="pdf",
                    route_name="browser_pdf",
                    run=run_pdf_fallback,
                    success_markers=(
                        fulltext_marker(self.name, "ok", route=PDF_FALLBACK),
                    ),
                )
            ],
            doi=doi,
            metadata=metadata,
            context=context,
            client=self,
            initial_warnings=[*bootstrap.warnings, initial_warning],
            initial_source_trail=[fulltext_marker(self.name, "fail", route="html")],
        )

    def html_to_markdown(
        self,
        html_text: str,
        source_url: str,
        *,
        metadata: Mapping[str, Any],
        context: RuntimeContext,
    ) -> tuple[str, Mapping[str, Any]]:
        return self.deps._cached_browser_workflow_markdown(
            self,
            html_text,
            source_url,
            metadata=metadata,
            context=context,
        )

    def maybe_recover_fetch_result_payload(
        self,
        doi: str,
        metadata: Mapping[str, Any],
        prepared: PreparedFetchResultPayload,
        *,
        asset_profile: AssetProfile = "none",
        context: RuntimeContext | None = None,
    ) -> PreparedFetchResultPayload:
        context = self._runtime_context(context)
        provider_metadata = cast(ProviderMetadata, metadata)
        raw_payload = prepared.raw_payload
        content = raw_payload.content
        if content is None or normalize_text(content.route_kind).lower() != "html":
            return prepared

        provisional_article = self.to_article_model(
            metadata, raw_payload, context=context
        )
        prepared.provisional_article = provisional_article
        if provisional_article.quality.content_kind != ABSTRACT_ONLY:
            return prepared

        if not self.allow_pdf_fallback_after_html_failure(
            html_failure_reason=ABSTRACT_ONLY,
            html_failure_message=f"{self.name} HTML route only exposed abstract-level content after markdown extraction.",
        ):
            return prepared

        try:
            recovered_payload = self._recover_pdf_payload_from_abstract_only_html(
                doi,
                provider_metadata,
                raw_payload,
                context=context,
            )
        except (ProviderFailure, PdfFallbackFailure):
            provider_label = self.provider_label()
            prepared.finalize_warnings.append(
                f"{provider_label} HTML route only exposed abstract-level content after markdown extraction, "
                "and PDF fallback did not return usable full text; returning abstract-only content."
            )
            return prepared

        return PreparedFetchResultPayload(raw_payload=recovered_payload)

    def should_download_related_assets_for_result(
        self,
        raw_payload: RawFulltextPayload,
        *,
        provisional_article=None,
    ) -> bool:
        return (
            provisional_article is None
            or provisional_article.quality.content_kind == FULLTEXT
        )

    def finalize_fetch_result_article(
        self,
        article,
        *,
        raw_payload: RawFulltextPayload,
        provisional_article=None,
        finalize_warnings: list[str] | None = None,
    ):
        if article.quality.content_kind != ABSTRACT_ONLY:
            return article
        return _finalize_abstract_only_provider_article(
            self.name,
            article,
            warnings=list(finalize_warnings or []),
        )

    def download_related_assets(
        self,
        doi: str,
        metadata: Mapping[str, Any],
        raw_payload: RawFulltextPayload,
        output_dir,
        *,
        asset_profile: AssetProfile = "all",
        context: RuntimeContext | None = None,
    ) -> dict[str, list[dict[str, Any]]]:
        return self._download_browser_backed_related_assets(
            doi,
            metadata,
            raw_payload,
            output_dir,
            asset_profile=asset_profile,
            context=context,
        )

    def _download_browser_backed_related_assets(
        self,
        doi: str,
        metadata: Mapping[str, Any],
        raw_payload: RawFulltextPayload,
        output_dir,
        *,
        asset_profile: AssetProfile = "all",
        context: RuntimeContext | None = None,
        assets: list[Mapping[str, Any]] | None = None,
    ) -> dict[str, list[dict[str, Any]]]:
        context = self._runtime_context(context, output_dir=output_dir)
        if output_dir is None or asset_profile == "none":
            return empty_asset_results()
        content = raw_payload.content
        if (
            normalize_text(content.route_kind if content is not None else "").lower()
            != "html"
        ):
            return empty_asset_results()

        normalized_doi = normalize_doi(str(metadata.get("doi") or doi or ""))
        if not normalized_doi:
            return empty_asset_results()
        plan_profile: Mapping[str, Any]
        if assets is None:
            plan_profile = {
                "client": self,
                "context": context,
                "asset_profile": asset_profile,
            }
            html_text = decode_html(
                raw_payload.body,
                content_type=content.content_type
                if content is not None
                else raw_payload.content_type,
            )
        else:
            plan_profile = {
                "assets": [dict(asset) for asset in assets],
                "asset_profile": asset_profile,
            }
            html_text = ""
        try:
            plan = plan_browser_asset_download(
                article_id=normalized_doi,
                output_dir=Path(output_dir),
                html_text=html_text,
                source_url=raw_payload.source_url,
                profile=plan_profile,
                deps=self.deps,
            )
        except HtmlExtractionFailure:
            return empty_asset_results()
        if not plan.body_assets and not plan.supplementary_assets:
            return empty_asset_results()

        raw_browser_context_seed = (
            dict(content.browser_context_seed or {}) if content is not None else {}
        )
        direct_http_asset_mode = self._direct_http_asset_mode(raw_browser_context_seed)
        browser_context_seed = merge_browser_context_seeds(raw_browser_context_seed)
        if direct_http_asset_mode:
            browser_context_seed["paper_fetch_html_fetcher"] = "direct_http"
        if direct_http_asset_mode:
            runtime = None
        else:
            runtime = self.deps.load_runtime_config(
                self.env,
                provider=self.name,
                doi=normalized_doi,
            )
            self.deps.ensure_runtime_ready(runtime)
        camoufox_backend = runtime is not None
        asset_download_concurrency = resolve_asset_download_concurrency(context.env)
        recovery = BrowserAssetRecoveryContext(
            runtime=runtime,
            provider=self.name,
            user_agent=self.user_agent,
            browser_context_seed=browser_context_seed,
            browser_cookies=list(browser_context_seed.get("browser_cookies") or []),
            active_seed_urls=[
                normalized
                for normalized in (
                    raw_payload.source_url,
                    normalize_text(
                        str(browser_context_seed.get("browser_final_url") or "")
                    ),
                )
                if normalized
            ],
            runtime_context=context,
        )

        download_settings = {
            "transport": self.transport,
            "asset_download_concurrency": asset_download_concurrency,
            "figure_page_fetcher_factory": _MemoizedFigurePageFetcher,
            "serial_browser_assets": camoufox_backend,
        }
        image_fetcher_factory = (
            (lambda **_request: None)
            if direct_http_asset_mode
            else partial(self._browser_asset_image_fetcher, context)
        )
        file_fetcher_factory = (
            (lambda **_request: None)
            if direct_http_asset_mode
            else partial(self._browser_asset_file_fetcher, context)
        )
        return download_browser_backed_related_assets(
            plan,
            recovery,
            image_fetcher_factory=image_fetcher_factory,
            file_fetcher_factory=file_fetcher_factory,
            download_settings=download_settings,
            deps=self.deps,
        )

    def _browser_asset_image_fetcher(self, context: RuntimeContext, **request):
        profile = self.profile
        if (
            not request["attempt_body_assets"]
            or profile is None
            or not profile.shared_browser_image_fetcher
        ):
            return None
        fetcher = self.deps._build_shared_browser_image_fetcher(
            browser_context_seed_getter=request["browser_context_seed_getter"],
            seed_urls_getter=request["seed_urls_getter"],
            browser_user_agent=request["browser_user_agent"],
            headless=request["headless"],
            runtime_context=context,
            use_runtime_shared_browser=True,
            browser_options=BrowserDocumentFetcherOptions(
                runtime_config=request.get("browser_config")
            ),
        )
        # Figures fan out several candidate URLs per asset (full-size, figure
        # page, preview), so the same image URL is frequently fetched more than
        # once across candidates and retries; memoizing collapses those to a
        # single browser round-trip. Supplementary files have a single unique
        # URL each, so the file fetcher below is left unmemoized on purpose.
        return _MemoizedImageDocumentFetcher(fetcher)

    def _browser_asset_file_fetcher(self, context: RuntimeContext, **request):
        profile = self.profile
        if (
            not request["attempt_supplementary_assets"]
            or profile is None
            or not profile.shared_browser_image_fetcher
        ):
            return None
        return self.deps._build_shared_browser_file_fetcher(
            browser_context_seed_getter=request["browser_context_seed_getter"],
            seed_urls_getter=request["seed_urls_getter"],
            browser_user_agent=request["browser_user_agent"],
            headless=request["headless"],
            runtime_context=context,
            use_runtime_shared_browser=True,
            browser_options=BrowserDocumentFetcherOptions(
                runtime_config=request.get("browser_config")
            ),
            thread_local=True,
        )

    def to_article_model(
        self,
        metadata: Mapping[str, Any],
        raw_payload: RawFulltextPayload,
        *,
        downloaded_assets: list[Mapping[str, Any]] | None = None,
        asset_failures: list[Mapping[str, Any]] | None = None,
        context: RuntimeContext | None = None,
    ):
        context = self._runtime_context(context)
        profile = self.require_profile()
        provider_metadata = cast(ProviderMetadata, metadata)
        return browser_workflow_article_from_payload(
            self,
            cast(
                ProviderMetadata,
                merge_provider_owned_authors(
                    provider_metadata,
                    raw_payload,
                    fallback_extractor=profile.fallback_author_extractor,
                ),
            ),
            raw_payload,
            downloaded_assets=downloaded_assets,
            asset_failures=asset_failures,
            context=context,
        )

    def describe_artifacts(
        self,
        raw_payload: RawFulltextPayload,
        *,
        downloaded_assets: list[Mapping[str, Any]] | None = None,
        asset_failures: list[Mapping[str, Any]] | None = None,
    ) -> ProviderArtifacts:
        artifacts = super().describe_artifacts(
            raw_payload,
            downloaded_assets=downloaded_assets,
            asset_failures=asset_failures,
        )
        content = raw_payload.content
        if (
            normalize_text(content.route_kind if content is not None else "").lower()
            != PDF_FALLBACK
        ):
            return artifacts
        pdf_assets = list(content.extracted_assets if content is not None else [])
        return ProviderArtifacts(
            assets=[*list(artifacts.assets), *pdf_assets],
            asset_failures=list(artifacts.asset_failures),
            allow_related_assets=False,
            text_only=not pdf_assets,
            skip_trace=trace_from_markers(
                [download_marker(f"{self.name}_assets_skipped_text_only")]
            )
            if not pdf_assets
            else [],
        )
