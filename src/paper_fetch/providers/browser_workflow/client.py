"""Browser workflow provider client base class."""

from __future__ import annotations

import sys
import threading
from typing import Any, Callable, Mapping

from ...config import build_user_agent, resolve_asset_download_concurrency
from ...extraction.html import decode_html
from ...extraction.html.assets import (
    download_figure_assets_with_image_document_fetcher as _download_figure_assets_with_image_document_fetcher,
    download_supplementary_assets as _download_supplementary_assets,
    split_body_and_supplementary_assets,
)
from ...extraction.html.signals import SciencePnasHtmlFailure
from ...metadata_types import ProviderMetadata
from ...models import AssetProfile
from ...publisher_identity import normalize_doi
from ...runtime import RuntimeContext
from ...tracing import trace_from_markers
from ...utils import empty_asset_results, normalize_text
from .._browser_workflow_shared import (
    build_browser_workflow_html_candidates,
    build_browser_workflow_pdf_candidates,
    extract_pdf_url_from_crossref,
)
from .._flaresolverr import (
    FlareSolverrFailure,
    ensure_runtime_ready as _ensure_runtime_ready,
    fetch_html_with_flaresolverr as _fetch_html_with_flaresolverr,
    load_runtime_config as _load_runtime_config,
    merge_browser_context_seeds,
    probe_runtime_status as _probe_runtime_status,
    warm_browser_context_with_flaresolverr as _warm_browser_context_with_flaresolverr,
)
from .._pdf_fallback import PdfFallbackFailure
from .._waterfall import ProviderWaterfallStep, run_provider_waterfall
from ..base import (
    PreparedFetchResultPayload,
    ProviderArtifacts,
    ProviderClient,
    ProviderFailure,
    RawFulltextPayload,
)
from ..browser_workflow_fetchers import (
    _MemoizedFigurePageFetcher,
    _MemoizedImageDocumentFetcher,
    _build_shared_playwright_file_fetcher as _default_build_shared_playwright_file_fetcher,
    _build_shared_playwright_image_fetcher as _default_build_shared_playwright_image_fetcher,
    _compact_failure_diagnostic,
    _flaresolverr_image_document_payload,
    _flaresolverr_image_payload_failure_reason,
)
from ..science_pnas import (
    extract_science_pnas_markdown as _extract_science_pnas_markdown,
)
from .article import (
    _finalize_abstract_only_provider_article,
    browser_workflow_article_from_payload,
    merge_provider_owned_authors,
)
from .assets import (
    _assets_matching_download_failures,
    _browser_workflow_image_download_candidates,
    _cached_browser_workflow_assets,
    _merge_download_attempt_results,
)
from .bootstrap import bootstrap_browser_workflow as _bootstrap_browser_workflow
from .pdf_fallback import (
    fetch_seeded_browser_pdf_payload as _fetch_seeded_browser_pdf_payload,
)
from .profile import ProviderBrowserProfile


def _facade_attr(name: str, fallback):
    facade = sys.modules.get("paper_fetch.providers.browser_workflow")
    return getattr(facade, name, fallback) if facade is not None else fallback


class BrowserWorkflowClient(ProviderClient):
    name = "browser_workflow"
    article_source_name: str | None = None
    profile: ProviderBrowserProfile | None = None

    def __init__(self, transport, env: Mapping[str, str]) -> None:
        self.transport = transport
        self.env = dict(env)
        self.user_agent = build_user_agent(env)

    def probe_status(self):
        return _facade_attr("probe_runtime_status", _probe_runtime_status)(
            self.env, provider=self.name
        )

    def fetch_metadata(self, query: Mapping[str, str | None]) -> ProviderMetadata:
        raise ProviderFailure(
            "not_supported",
            f"{self.name} official metadata retrieval is not implemented; routing relies on Crossref metadata.",
        )

    def article_source(self) -> str:
        if self.article_source_name:
            return self.article_source_name
        profile = self.profile
        if profile is not None and profile.article_source_name:
            return profile.article_source_name
        return self.name

    def require_profile(self) -> ProviderBrowserProfile:
        profile = self.profile
        if profile is None:
            raise ProviderFailure(
                "not_supported",
                f"{self.name} must declare a browser workflow profile.",
            )
        return profile

    def provider_label(self) -> str:
        profile = self.profile
        return (
            profile.label
            if profile is not None
            else ("PNAS" if self.name == "pnas" else self.name.title())
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
                "not_supported", f"{self.name} PDF fallback requires a DOI."
            )
        content = raw_payload.content
        if content is None or normalize_text(content.route_kind).lower() != "html":
            raise ProviderFailure(
                "not_supported",
                f"{self.name} PDF fallback recovery requires provider-owned HTML content.",
            )

        html_failure_reason = "abstract_only"
        html_failure_message = f"{self.name} HTML route only exposed abstract-level content after markdown extraction."
        recovery_warning = f"{self.name} HTML route only exposed abstract-level content after markdown extraction; attempting PDF fallback."
        runtime = _facade_attr("load_runtime_config", _load_runtime_config)(
            self.env,
            provider=self.name,
            doi=normalized_doi,
        )
        _facade_attr("ensure_runtime_ready", _ensure_runtime_ready)(runtime)
        return _facade_attr(
            "fetch_seeded_browser_pdf_payload", _fetch_seeded_browser_pdf_payload
        )(
            provider=self.name,
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
                f"fulltext:{self.name}_html_ok",
                f"fulltext:{self.name}_abstract_only",
                f"fulltext:{self.name}_pdf_fallback_ok",
            ],
            context=context,
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
        return _facade_attr(
            "extract_science_pnas_markdown", _extract_science_pnas_markdown
        )(
            html_text,
            final_url,
            publisher,
            metadata=metadata,
        )

    def fetch_raw_fulltext(
        self,
        doi: str,
        metadata: ProviderMetadata,
        *,
        context: RuntimeContext | None = None,
    ) -> RawFulltextPayload:
        context = self._runtime_context(context)
        bootstrap = _facade_attr(
            "bootstrap_browser_workflow", _bootstrap_browser_workflow
        )(
            self,
            doi,
            metadata,
            context=context,
        )
        if bootstrap.html_payload is not None:
            return bootstrap.html_payload

        if not self.allow_pdf_fallback_after_html_failure(
            html_failure_reason=bootstrap.html_failure_reason,
            html_failure_message=bootstrap.html_failure_message,
        ):
            reason = bootstrap.html_failure_message or f"{self.name} HTML route failed."
            raise ProviderFailure(
                "no_result",
                (
                    f"{self.name} HTML route was not usable ({bootstrap.html_failure_reason or 'html_failed'}); "
                    f"PDF fallback is disabled. {reason}"
                ),
                warnings=[
                    f"{self.name} HTML route was not usable; skipping PDF fallback."
                ],
                source_trail=[f"fulltext:{self.name}_html_fail"],
            )

        initial_warning = (
            f"{self.name} HTML route was not usable "
            f"({bootstrap.html_failure_reason or 'html_failed'}); attempting PDF fallback."
        )

        def run_pdf_fallback(_state) -> RawFulltextPayload:
            try:
                return _facade_attr(
                    "fetch_seeded_browser_pdf_payload",
                    _fetch_seeded_browser_pdf_payload,
                )(
                    provider=self.name,
                    runtime=bootstrap.runtime,
                    pdf_candidates=bootstrap.pdf_candidates,
                    html_candidates=bootstrap.html_candidates,
                    landing_page_url=bootstrap.landing_page_url,
                    user_agent=self.user_agent,
                    browser_context_seed=bootstrap.browser_context_seed,
                    html_failure_reason=bootstrap.html_failure_reason,
                    html_failure_message=bootstrap.html_failure_message,
                    warnings=[],
                    success_source_trail=[],
                    context=context,
                )
            except PdfFallbackFailure as exc:
                reason = (
                    bootstrap.html_failure_message or f"{self.name} HTML route failed."
                )
                raise ProviderFailure(
                    "no_result",
                    (
                        f"{self.name} full text could not be retrieved via HTML or PDF fallback. "
                        f"HTML failure: {reason} PDF failure: {exc.message}"
                    ),
                ) from exc

        return run_provider_waterfall(
            [
                ProviderWaterfallStep(
                    label="pdf",
                    run=run_pdf_fallback,
                    success_markers=(f"fulltext:{self.name}_pdf_fallback_ok",),
                )
            ],
            initial_warnings=[*bootstrap.warnings, initial_warning],
            initial_source_trail=[f"fulltext:{self.name}_html_fail"],
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
        raw_payload = prepared.raw_payload
        content = raw_payload.content
        if content is None or normalize_text(content.route_kind).lower() != "html":
            return prepared

        provisional_article = self.to_article_model(
            metadata, raw_payload, context=context
        )
        prepared.provisional_article = provisional_article
        if provisional_article.quality.content_kind != "abstract_only":
            return prepared

        if not self.allow_pdf_fallback_after_html_failure(
            html_failure_reason="abstract_only",
            html_failure_message=f"{self.name} HTML route only exposed abstract-level content after markdown extraction.",
        ):
            return prepared

        try:
            recovered_payload = self._recover_pdf_payload_from_abstract_only_html(
                doi,
                metadata,
                raw_payload,
                context=context,
            )
        except (ProviderFailure, PdfFallbackFailure):
            provider_label = self.provider_label()
            prepared.finalize_warnings.append(
                (
                    f"{provider_label} HTML route only exposed abstract-level content after markdown extraction, "
                    "and PDF fallback did not return usable full text; returning abstract-only content."
                )
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
            or provisional_article.quality.content_kind == "fulltext"
        )

    def finalize_fetch_result_article(
        self,
        article,
        *,
        raw_payload: RawFulltextPayload,
        provisional_article=None,
        finalize_warnings: list[str] | None = None,
    ):
        if article.quality.content_kind != "abstract_only":
            return article
        return _finalize_abstract_only_provider_article(
            self.name,
            article,
            warnings=list(finalize_warnings or []),
        )

    def download_related_assets(
        self,
        doi: str,
        metadata: ProviderMetadata,
        raw_payload: RawFulltextPayload,
        output_dir,
        *,
        asset_profile: AssetProfile = "all",
        context: RuntimeContext | None = None,
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

        html_text = decode_html(raw_payload.body)
        try:
            article_assets = _facade_attr(
                "_cached_browser_workflow_assets", _cached_browser_workflow_assets
            )(
                self,
                html_text,
                raw_payload.source_url,
                asset_profile=asset_profile,
                context=context,
            )
        except SciencePnasHtmlFailure:
            return empty_asset_results()
        if not article_assets:
            return empty_asset_results()
        body_assets, supplementary_assets = split_body_and_supplementary_assets(
            article_assets
        )
        asset_download_concurrency = resolve_asset_download_concurrency(context.env)

        normalized_doi = normalize_doi(str(metadata.get("doi") or doi or ""))
        if not normalized_doi:
            return empty_asset_results()

        runtime = _facade_attr("load_runtime_config", _load_runtime_config)(
            self.env,
            provider=self.name,
            doi=normalized_doi,
        )
        _facade_attr("ensure_runtime_ready", _ensure_runtime_ready)(runtime)
        browser_context_seed = merge_browser_context_seeds(
            content.browser_context_seed if content is not None else None
        )

        article_id = (
            normalized_doi
            or normalize_text(str(metadata.get("title") or ""))
            or raw_payload.source_url
        )

        def seed_urls_for(current_seed: Mapping[str, Any]) -> list[str]:
            return [
                normalized
                for normalized in [
                    raw_payload.source_url,
                    normalize_text(str(current_seed.get("browser_final_url") or "")),
                ]
                if normalized
            ]

        def asset_recovery_urls(image_url: str, asset: Mapping[str, Any]) -> list[str]:
            seen: set[str] = set()
            ordered: list[str] = []
            for candidate in [
                image_url,
                normalize_text(str(asset.get("figure_page_url") or "")),
            ]:
                normalized = normalize_text(candidate)
                if normalized and normalized not in seen:
                    seen.add(normalized)
                    ordered.append(normalized)
            return ordered

        def supplementary_recovery_urls(
            file_url: str, asset: Mapping[str, Any]
        ) -> list[str]:
            seen: set[str] = set()
            ordered: list[str] = []
            for candidate in [
                file_url,
                raw_payload.source_url,
                normalize_text(str(asset.get("source_url") or "")),
                normalize_text(str(asset.get("download_url") or "")),
            ]:
                normalized = normalize_text(candidate)
                if normalized and normalized not in seen:
                    seen.add(normalized)
                    ordered.append(normalized)
            return ordered

        def asset_challenge_recovery_for(
            attempt_seed: dict[str, Any],
            attempt_seed_lock: threading.Lock,
        ) -> Callable[
            [str, Mapping[str, Any], Mapping[str, Any]], Mapping[str, Any] | None
        ]:
            def recover(
                image_url: str, asset: Mapping[str, Any], failure: Mapping[str, Any]
            ) -> Mapping[str, Any]:
                attempts: list[dict[str, Any]] = []
                for recovery_url in asset_recovery_urls(image_url, asset):
                    try:
                        html_result = _facade_attr(
                            "fetch_html_with_flaresolverr",
                            _fetch_html_with_flaresolverr,
                        )(
                            [recovery_url],
                            publisher=self.name,
                            config=runtime,
                            return_image_payload=True,
                        )
                    except FlareSolverrFailure as exc:
                        if exc.browser_context_seed:
                            with attempt_seed_lock:
                                attempt_seed.update(
                                    merge_browser_context_seeds(
                                        attempt_seed, exc.browser_context_seed
                                    )
                                )
                        attempts.append(
                            _compact_failure_diagnostic(
                                {
                                    "url": recovery_url,
                                    "status": "failed",
                                    "reason": "challenge_recovery_failed",
                                    "message": exc.message,
                                }
                            )
                        )
                        continue
                    with attempt_seed_lock:
                        attempt_seed.update(
                            merge_browser_context_seeds(
                                attempt_seed, html_result.browser_context_seed
                            )
                        )
                    image_payload = _flaresolverr_image_document_payload(html_result)
                    recovery_reason = (
                        ""
                        if image_payload is not None
                        else _flaresolverr_image_payload_failure_reason(html_result)
                    )
                    return _compact_failure_diagnostic(
                        {
                            "status": "ok" if image_payload is not None else "failed",
                            "url": recovery_url,
                            "final_url": html_result.final_url,
                            "response_status": html_result.response_status,
                            "content_type": html_result.response_headers.get(
                                "content-type"
                            ),
                            "title_snippet": (html_result.title or "")[:160],
                            "attempts": attempts,
                            "reason": recovery_reason,
                            "image_payload": image_payload,
                        }
                    )
                return _compact_failure_diagnostic(
                    {
                        "status": "failed",
                        "reason": normalize_text(str(failure.get("reason") or ""))
                        or "challenge_recovery_failed",
                        "attempts": attempts,
                    }
                )

            return recover

        def supplementary_challenge_recovery_for(
            attempt_seed: dict[str, Any],
            attempt_seed_lock: threading.Lock,
        ) -> Callable[
            [str, Mapping[str, Any], Mapping[str, Any]], Mapping[str, Any] | None
        ]:
            def recover(
                file_url: str, asset: Mapping[str, Any], failure: Mapping[str, Any]
            ) -> Mapping[str, Any]:
                attempts: list[dict[str, Any]] = []
                for recovery_url in supplementary_recovery_urls(file_url, asset):
                    try:
                        html_result = _facade_attr(
                            "fetch_html_with_flaresolverr",
                            _fetch_html_with_flaresolverr,
                        )(
                            [recovery_url],
                            publisher=self.name,
                            config=runtime,
                        )
                    except FlareSolverrFailure as exc:
                        if exc.browser_context_seed:
                            with attempt_seed_lock:
                                attempt_seed.update(
                                    merge_browser_context_seeds(
                                        attempt_seed, exc.browser_context_seed
                                    )
                                )
                        attempts.append(
                            _compact_failure_diagnostic(
                                {
                                    "url": recovery_url,
                                    "status": "failed",
                                    "reason": "challenge_recovery_failed",
                                    "message": exc.message,
                                }
                            )
                        )
                        continue
                    with attempt_seed_lock:
                        attempt_seed.update(
                            merge_browser_context_seeds(
                                attempt_seed, html_result.browser_context_seed
                            )
                        )
                    return _compact_failure_diagnostic(
                        {
                            "status": "ok",
                            "url": recovery_url,
                            "final_url": html_result.final_url,
                            "response_status": html_result.response_status,
                            "content_type": html_result.response_headers.get(
                                "content-type"
                            ),
                            "title_snippet": (html_result.title or "")[:160],
                            "attempts": attempts,
                        }
                    )
                return _compact_failure_diagnostic(
                    {
                        "status": "failed",
                        "reason": normalize_text(str(failure.get("reason") or ""))
                        or "challenge_recovery_failed",
                        "attempts": attempts,
                    }
                )

            return recover

        def image_document_fetcher_for(
            current_seed: Mapping[str, Any],
            attempt_seed: dict[str, Any],
            attempt_seed_lock: threading.Lock,
            attempt_body_assets: list[dict[str, Any]],
        ) -> Callable[[str, Mapping[str, Any]], dict[str, Any] | None] | None:
            if not attempt_body_assets:
                return None
            profile = self.profile
            if profile is None or not profile.shared_playwright_image_fetcher:
                return None
            # Asset workers may run in parallel threads, so they must not borrow
            # the RuntimeContext-owned shared browser/context.
            fetcher = _facade_attr(
                "_build_shared_playwright_image_fetcher",
                _default_build_shared_playwright_image_fetcher,
            )(
                browser_context_seed_getter=lambda: attempt_seed,
                seed_urls_getter=lambda: seed_urls_for(attempt_seed),
                browser_user_agent=current_seed.get("browser_user_agent")
                or self.user_agent,
                headless=runtime.headless,
                challenge_recovery=asset_challenge_recovery_for(
                    attempt_seed, attempt_seed_lock
                ),
                runtime_context=context,
                use_runtime_shared_browser=False,
            )
            return _MemoizedImageDocumentFetcher(fetcher)

        def file_document_fetcher_for(
            current_seed: Mapping[str, Any],
            attempt_seed: dict[str, Any],
            attempt_seed_lock: threading.Lock,
            attempt_supplementary_assets: list[dict[str, Any]],
        ) -> Callable[[str, Mapping[str, Any]], dict[str, Any] | None] | None:
            if not attempt_supplementary_assets:
                return None
            profile = self.profile
            if profile is None or not profile.shared_playwright_image_fetcher:
                return None
            return _facade_attr(
                "_build_shared_playwright_file_fetcher",
                _default_build_shared_playwright_file_fetcher,
            )(
                browser_context_seed_getter=lambda: attempt_seed,
                seed_urls_getter=lambda: seed_urls_for(attempt_seed),
                browser_user_agent=current_seed.get("browser_user_agent")
                or self.user_agent,
                headless=runtime.headless,
                challenge_recovery=supplementary_challenge_recovery_for(
                    attempt_seed, attempt_seed_lock
                ),
                runtime_context=context,
                use_runtime_shared_browser=False,
                thread_local=True,
            )

        def run_download_attempt(
            current_seed: Mapping[str, Any],
            *,
            attempt_body_assets: list[dict[str, Any]],
            attempt_supplementary_assets: list[dict[str, Any]],
        ) -> dict[str, list[dict[str, Any]]]:
            attempt_seed = merge_browser_context_seeds(current_seed)
            attempt_seed_lock = threading.Lock()

            def raw_figure_page_fetcher(figure_page_url: str) -> tuple[str, str] | None:
                try:
                    html_result = _facade_attr(
                        "fetch_html_with_flaresolverr", _fetch_html_with_flaresolverr
                    )(
                        [figure_page_url],
                        publisher=self.name,
                        config=runtime,
                    )
                except FlareSolverrFailure:
                    return None
                with attempt_seed_lock:
                    attempt_seed.update(
                        merge_browser_context_seeds(
                            attempt_seed, html_result.browser_context_seed
                        )
                    )
                return html_result.html, html_result.final_url

            figure_page_fetcher = _MemoizedFigurePageFetcher(raw_figure_page_fetcher)
            image_document_fetcher = image_document_fetcher_for(
                attempt_seed,
                attempt_seed,
                attempt_seed_lock,
                attempt_body_assets,
            )
            file_document_fetcher = file_document_fetcher_for(
                attempt_seed,
                attempt_seed,
                attempt_seed_lock,
                attempt_supplementary_assets,
            )
            try:
                body_result = (
                    _facade_attr(
                        "download_figure_assets_with_image_document_fetcher",
                        _download_figure_assets_with_image_document_fetcher,
                    )(
                        self.transport,
                        article_id=article_id,
                        assets=attempt_body_assets,
                        output_dir=output_dir,
                        user_agent=self.user_agent,
                        asset_profile=asset_profile,
                        figure_page_fetcher=figure_page_fetcher,
                        candidate_builder=_browser_workflow_image_download_candidates,
                        image_document_fetcher=image_document_fetcher,
                        asset_download_concurrency=asset_download_concurrency,
                    )
                    if attempt_body_assets
                    else empty_asset_results()
                )
                supplementary_result = (
                    _facade_attr(
                        "download_supplementary_assets", _download_supplementary_assets
                    )(
                        self.transport,
                        article_id=article_id,
                        assets=attempt_supplementary_assets,
                        output_dir=output_dir,
                        user_agent=self.user_agent,
                        asset_profile=asset_profile,
                        browser_context_seed=attempt_seed,
                        seed_urls=seed_urls_for(attempt_seed),
                        file_document_fetcher=file_document_fetcher,
                        asset_download_concurrency=asset_download_concurrency,
                    )
                    if attempt_supplementary_assets
                    else empty_asset_results()
                )
                return {
                    "assets": [
                        *list(body_result.get("assets") or []),
                        *list(supplementary_result.get("assets") or []),
                    ],
                    "asset_failures": [
                        *list(body_result.get("asset_failures") or []),
                        *list(supplementary_result.get("asset_failures") or []),
                    ],
                }
            finally:
                for fetcher in (image_document_fetcher, file_document_fetcher):
                    close_fetcher = getattr(fetcher, "close", None)
                    if callable(close_fetcher):
                        close_fetcher()

        initial_result = run_download_attempt(
            browser_context_seed,
            attempt_body_assets=body_assets,
            attempt_supplementary_assets=supplementary_assets,
        )
        if not initial_result.get("asset_failures"):
            return initial_result

        initial_failures = list(initial_result.get("asset_failures") or [])
        failed_body_assets = _assets_matching_download_failures(
            body_assets,
            initial_failures,
            retry_scope="body",
        )
        failed_supplementary_assets = _assets_matching_download_failures(
            supplementary_assets,
            initial_failures,
            retry_scope="supplementary",
        )
        if not failed_body_assets and not failed_supplementary_assets:
            return initial_result

        refreshed_seed = _facade_attr(
            "warm_browser_context_with_flaresolverr",
            _warm_browser_context_with_flaresolverr,
        )(
            seed_urls_for(browser_context_seed),
            publisher=self.name,
            config=runtime,
            browser_context_seed=browser_context_seed,
        )
        retry_result = run_download_attempt(
            refreshed_seed,
            attempt_body_assets=failed_body_assets,
            attempt_supplementary_assets=failed_supplementary_assets,
        )
        return _merge_download_attempt_results(initial_result, retry_result)

    def to_article_model(
        self,
        metadata: ProviderMetadata,
        raw_payload: RawFulltextPayload,
        *,
        downloaded_assets: list[Mapping[str, Any]] | None = None,
        asset_failures: list[Mapping[str, Any]] | None = None,
        context: RuntimeContext | None = None,
    ):
        context = self._runtime_context(context)
        profile = self.require_profile()
        return browser_workflow_article_from_payload(
            self,
            merge_provider_owned_authors(
                metadata,
                raw_payload,
                fallback_extractor=profile.fallback_author_extractor,
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
            != "pdf_fallback"
        ):
            return artifacts
        provider_label = self.provider_label()
        return ProviderArtifacts(
            assets=list(artifacts.assets),
            asset_failures=list(artifacts.asset_failures),
            allow_related_assets=False,
            text_only=True,
            skip_warning=(
                f"{provider_label} PDF fallback currently returns text-only full text; "
                "figure and supplementary asset downloads are not implemented yet."
            ),
            skip_trace=trace_from_markers(
                [f"download:{self.name}_assets_skipped_text_only"]
            ),
        )
