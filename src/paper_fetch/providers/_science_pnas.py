"""Shared browser-workflow runtime helpers for Wiley/Science/PNAS."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field, replace
from typing import Any, Callable, Mapping

from ..config import build_user_agent
from ..extraction.html import decode_html, download_figure_assets, extract_html_assets
from ..http import RequestFailure
from ..metadata_types import ProviderMetadata
from ..models import AssetProfile, article_from_markdown, metadata_only_article
from ..publisher_identity import normalize_doi
from ..tracing import merge_trace, source_trail_from_trace, trace_from_markers
from ..utils import dedupe_authors, empty_asset_results, extend_unique, normalize_text
from ._flaresolverr import (
    FlareSolverrFailure,
    ensure_runtime_ready,
    fetch_html_with_flaresolverr,
    load_runtime_config,
    merge_browser_context_seeds,
    probe_runtime_status,
    warm_browser_context_with_flaresolverr,
)
from ._pdf_fallback import PdfFallbackFailure, fetch_pdf_with_playwright
from ._html_access_signals import SciencePnasHtmlFailure
from ._science_pnas_html import extract_science_pnas_markdown, rewrite_inline_figure_links
from ._science_pnas_profiles import (
    extract_pdf_url_from_crossref,
    preferred_html_candidate_from_landing_page,
)
from .base import ProviderArtifacts, ProviderClient, ProviderContent, ProviderFailure, ProviderFetchResult, RawFulltextPayload

logger = logging.getLogger("paper_fetch.providers.browser_workflow")

__all__ = [
    "BrowserWorkflowBootstrapResult",
    "BrowserWorkflowClient",
    "FlareSolverrFailure",
    "PdfFallbackFailure",
    "SciencePnasHtmlFailure",
    "bootstrap_browser_workflow",
    "browser_workflow_article_from_payload",
    "ensure_runtime_ready",
    "extract_pdf_url_from_crossref",
    "extract_science_pnas_markdown",
    "fetch_html_with_flaresolverr",
    "fetch_seeded_browser_pdf_payload",
    "load_runtime_config",
    "merge_browser_context_seeds",
    "merge_provider_owned_authors",
    "preferred_html_candidate_from_landing_page",
    "probe_runtime_status",
    "rewrite_inline_figure_links",
    "warm_browser_context_with_flaresolverr",
]


@dataclass
class BrowserWorkflowBootstrapResult:
    normalized_doi: str
    runtime: Any | None
    landing_page_url: str | None
    html_candidates: list[str]
    pdf_candidates: list[str]
    browser_context_seed: Mapping[str, Any] | None = None
    html_failure_reason: str | None = None
    html_failure_message: str | None = None
    html_payload: RawFulltextPayload | None = None
    runtime_failure: ProviderFailure | None = None
    warnings: list[str] = field(default_factory=list)


def _looks_like_pdf_navigation_url(url: str | None) -> bool:
    normalized = normalize_text(url).lower()
    if not normalized:
        return False
    return any(token in normalized for token in ("/doi/pdf", "/doi/pdfdirect", "/doi/epdf", "/fullpdf", ".pdf"))


def _choose_playwright_seed_url(*candidates: str | None) -> str | None:
    normalized_candidates = [normalize_text(candidate) for candidate in candidates if normalize_text(candidate)]
    for candidate in normalized_candidates:
        if not _looks_like_pdf_navigation_url(candidate):
            return candidate
    return normalized_candidates[0] if normalized_candidates else None


def _leading_body_after_abstract(
    metadata_abstract: str | None,
    extracted_abstract: str | None,
) -> str | None:
    normalized_metadata = normalize_text(metadata_abstract)
    normalized_abstract = normalize_text(extracted_abstract)
    if not normalized_metadata or not normalized_abstract or normalized_metadata == normalized_abstract:
        return None
    if not normalized_metadata.startswith(normalized_abstract):
        return None
    remainder = normalized_metadata[len(normalized_abstract) :].strip()
    return remainder or None


def _prepend_leading_body_markdown(markdown_text: str, lead_body: str | None) -> str:
    normalized_lead_body = normalize_text(lead_body)
    if not normalized_lead_body:
        return markdown_text
    if normalized_lead_body in normalize_text(markdown_text):
        return markdown_text

    main_text_block = f"## Main Text\n\n{normalized_lead_body}"
    stripped_markdown = markdown_text.strip()
    if not stripped_markdown:
        return main_text_block
    if stripped_markdown.startswith("# "):
        parts = stripped_markdown.split("\n\n", 1)
        if len(parts) == 2:
            return f"{parts[0]}\n\n{main_text_block}\n\n{parts[1]}".strip()
    return f"{main_text_block}\n\n{stripped_markdown}".strip()


def _normalized_authors(values: Any) -> list[str]:
    return [
        normalize_text(str(item))
        for item in (values or [])
        if normalize_text(str(item))
    ]


def merge_provider_owned_authors(
    metadata: Mapping[str, Any],
    raw_payload: RawFulltextPayload,
    *,
    fallback_extractor: Callable[[str], list[str]] | None = None,
) -> dict[str, Any]:
    article_metadata = dict(metadata)
    content = getattr(raw_payload, "content", None)
    extraction = content.diagnostics.get("extraction") if content is not None else None
    extracted_authors = _normalized_authors(
        extraction.get("extracted_authors") if isinstance(extraction, Mapping) else []
    )
    if not extracted_authors and fallback_extractor is not None and "html" in normalize_text(raw_payload.content_type).lower():
        html_text = bytes(raw_payload.body or b"").decode("utf-8", errors="replace")
        extracted_authors = _normalized_authors(fallback_extractor(html_text))
    if not extracted_authors:
        return article_metadata

    existing_authors = _normalized_authors(article_metadata.get("authors") or [])
    article_metadata["authors"] = dedupe_authors([*extracted_authors, *existing_authors])
    return article_metadata


def bootstrap_browser_workflow(
    client: "BrowserWorkflowClient",
    doi: str,
    metadata: ProviderMetadata,
    *,
    allow_runtime_failure: bool = False,
) -> BrowserWorkflowBootstrapResult:
    normalized_doi = normalize_doi(doi)
    if not normalized_doi:
        raise ProviderFailure("not_supported", f"{client.name} full-text retrieval requires a DOI.")

    landing_page_url = str(metadata.get("landing_page_url") or "") or None
    html_candidates = client.html_candidates(normalized_doi, metadata)
    pdf_candidates = client.pdf_candidates(normalized_doi, metadata)
    result = BrowserWorkflowBootstrapResult(
        normalized_doi=normalized_doi,
        runtime=None,
        landing_page_url=landing_page_url,
        html_candidates=html_candidates,
        pdf_candidates=pdf_candidates,
    )

    preferred_html_candidate = preferred_html_candidate_from_landing_page(
        client.name,
        normalized_doi,
        landing_page_url,
    )
    logger.debug(
        "browser_workflow_candidates provider=%s doi=%s preferred_hit=%s first_candidate=%s candidate_count=%s",
        client.name,
        normalized_doi,
        bool(preferred_html_candidate and html_candidates and html_candidates[0] == preferred_html_candidate),
        html_candidates[0] if html_candidates else None,
        len(html_candidates),
    )

    try:
        result.runtime = load_runtime_config(client.env, provider=client.name, doi=normalized_doi)
        ensure_runtime_ready(result.runtime)
    except ProviderFailure as exc:
        if not allow_runtime_failure:
            raise
        result.runtime_failure = exc
        result.html_failure_reason = exc.code
        result.html_failure_message = exc.message
        return result

    try:
        html_result = fetch_html_with_flaresolverr(html_candidates, publisher=client.name, config=result.runtime)
        result.browser_context_seed = html_result.browser_context_seed
        markdown_text, extraction = client.extract_markdown(
            html_result.html,
            html_result.final_url,
            metadata=metadata,
        )
        result.html_payload = RawFulltextPayload(
            provider=client.name,
            source_url=html_result.final_url,
            content_type="text/html",
            body=html_result.html.encode("utf-8"),
            content=ProviderContent(
                route_kind="html",
                source_url=html_result.final_url,
                content_type="text/html",
                body=html_result.html.encode("utf-8"),
                markdown_text=markdown_text,
                diagnostics={
                    "extraction": extraction,
                    "availability_diagnostics": extraction.get("availability_diagnostics"),
                },
                fetcher="flaresolverr",
                browser_context_seed=dict(result.browser_context_seed or {}),
            ),
            warnings=list(result.warnings),
            trace=trace_from_markers([f"fulltext:{client.name}_html_ok"]),
            needs_local_copy=False,
        )
        return result
    except FlareSolverrFailure as exc:
        result.browser_context_seed = exc.browser_context_seed or result.browser_context_seed
        result.html_failure_reason = exc.kind
        result.html_failure_message = exc.message
    except SciencePnasHtmlFailure as exc:
        result.html_failure_reason = exc.reason
        result.html_failure_message = exc.message

    return result


def fetch_seeded_browser_pdf_payload(
    *,
    provider: str,
    runtime,
    pdf_candidates: list[str],
    html_candidates: list[str],
    landing_page_url: str | None,
    user_agent: str,
    browser_context_seed: Mapping[str, Any] | None,
    html_failure_reason: str | None,
    html_failure_message: str | None,
    warnings: list[str] | None = None,
    success_source_trail: list[str] | None = None,
    success_warning: str = "Full text was extracted from PDF fallback after the HTML path was not usable.",
    artifact_subdir: str = "pdf_fallback",
) -> RawFulltextPayload:
    pdf_browser_context_seed = warm_browser_context_with_flaresolverr(
        pdf_candidates,
        publisher=provider,
        config=runtime,
        browser_context_seed=browser_context_seed,
    )
    seed_url = _choose_playwright_seed_url(
        (browser_context_seed or {}).get("browser_final_url"),
        html_candidates[0] if html_candidates else None,
        landing_page_url,
        pdf_browser_context_seed.get("browser_final_url"),
    )
    pdf_result = fetch_pdf_with_playwright(
        pdf_candidates,
        artifact_dir=runtime.artifact_dir / artifact_subdir,
        browser_cookies=list(pdf_browser_context_seed.get("browser_cookies") or []),
        browser_user_agent=pdf_browser_context_seed.get("browser_user_agent") or user_agent,
        headless=runtime.headless,
        seed_urls=[seed_url] if seed_url else None,
    )
    payload_warnings = [str(item) for item in warnings or [] if str(item).strip()]
    if success_warning:
        payload_warnings.append(success_warning)
    return RawFulltextPayload(
        provider=provider,
        source_url=pdf_result.final_url,
        content_type="application/pdf",
        body=pdf_result.pdf_bytes,
        content=ProviderContent(
            route_kind="pdf_fallback",
            source_url=pdf_result.final_url,
            content_type="application/pdf",
            body=pdf_result.pdf_bytes,
            markdown_text=pdf_result.markdown_text,
            html_failure_reason=html_failure_reason,
            html_failure_message=html_failure_message,
            suggested_filename=pdf_result.suggested_filename,
        ),
        warnings=payload_warnings,
        trace=trace_from_markers(list(success_source_trail or [])),
        needs_local_copy=True,
    )


def browser_workflow_article_from_payload(
    client: "BrowserWorkflowClient",
    metadata: ProviderMetadata,
    raw_payload: RawFulltextPayload,
    *,
    downloaded_assets: list[Mapping[str, Any]] | None = None,
    asset_failures: list[Mapping[str, Any]] | None = None,
):
    content = raw_payload.content
    markdown_text = str((content.markdown_text if content is not None else "") or "").strip()
    warnings = list(raw_payload.warnings)
    trace = list(raw_payload.trace)
    doi = normalize_doi(metadata.get("doi"))
    source = client.article_source()
    assets = list(downloaded_assets or [])
    content_type = str(raw_payload.content_type or "").lower()

    if not markdown_text and "html" in content_type:
        html_text = bytes(raw_payload.body or b"").decode("utf-8", errors="replace").strip()
        if html_text:
            try:
                markdown_text, extraction = client.extract_markdown(
                    html_text,
                    raw_payload.source_url or str(metadata.get("landing_page_url") or ""),
                    metadata=metadata,
                )
            except SciencePnasHtmlFailure as exc:
                warnings.append(f"{client.name} HTML content was not usable ({exc.message}).")
            else:
                diagnostics_payload = dict(content.diagnostics) if content is not None else {}
                diagnostics_payload["extraction"] = extraction
                diagnostics = extraction.get("availability_diagnostics")
                if diagnostics is not None:
                    diagnostics_payload["availability_diagnostics"] = diagnostics
                if content is not None:
                    raw_payload.content = replace(
                        content,
                        markdown_text=markdown_text,
                        diagnostics=diagnostics_payload,
                    )
                    content = raw_payload.content

    if not markdown_text:
        warnings.append(f"{client.name} retrieval did not produce usable markdown.")
        return metadata_only_article(
            source=source,
            metadata=metadata,
            doi=doi or None,
            warnings=warnings,
            trace=[*trace, *trace_from_markers([f"fulltext:{client.name}_parse_fail"])],
        )
    if asset_failures:
        warnings.append(f"{client.name} related assets were only partially downloaded ({len(asset_failures)} failed).")
    if assets and markdown_text:
        markdown_text = rewrite_inline_figure_links(
            markdown_text,
            figure_assets=assets,
            publisher=client.name,
        )

    article_metadata = dict(metadata)
    extraction_payload = content.diagnostics.get("extraction") if content is not None else None
    extracted_abstract = normalize_text(
        extraction_payload.get("abstract_text") if isinstance(extraction_payload, Mapping) else ""
    )
    extracted_references = (
        list(extraction_payload.get("references") or [])
        if isinstance(extraction_payload, Mapping)
        else []
    )
    abstract_sections = (
        list(extraction_payload.get("abstract_sections") or [])
        if isinstance(extraction_payload, Mapping)
        else []
    )
    section_hints = (
        list(extraction_payload.get("section_hints") or [])
        if isinstance(extraction_payload, Mapping)
        else []
    )
    if extracted_references:
        article_metadata["references"] = extracted_references
    if extracted_abstract:
        lead_body = _leading_body_after_abstract(article_metadata.get("abstract"), extracted_abstract)
        article_metadata["abstract"] = extracted_abstract
        markdown_text = _prepend_leading_body_markdown(markdown_text, lead_body)
    availability_diagnostics = (
        dict(content.diagnostics.get("availability_diagnostics") or {})
        if content is not None and isinstance(content.diagnostics.get("availability_diagnostics"), Mapping)
        else None
    )

    return article_from_markdown(
        source=source,
        metadata=article_metadata,
        doi=doi or None,
        markdown_text=markdown_text,
        abstract_sections=abstract_sections,
        section_hints=section_hints,
        assets=assets,
        warnings=warnings,
        trace=trace,
        availability_diagnostics=availability_diagnostics,
        allow_downgrade_from_diagnostics=True,
    )


def _finalize_abstract_only_provider_article(
    provider_name: str,
    article,
    *,
    warnings: list[str] | None = None,
):
    marker = f"fulltext:{provider_name}_abstract_only"
    article.quality.trace = merge_trace(article.quality.trace, trace_from_markers([marker]))
    article.quality.source_trail = source_trail_from_trace(article.quality.trace)
    extend_unique(article.quality.warnings, list(warnings or []))
    return article


class BrowserWorkflowClient(ProviderClient):
    name = "browser_workflow"
    article_source_name: str | None = None

    def __init__(self, transport, env: Mapping[str, str]) -> None:
        self.transport = transport
        self.env = dict(env)
        self.user_agent = build_user_agent(env)

    def probe_status(self):
        return probe_runtime_status(self.env, provider=self.name)

    def fetch_metadata(self, query: Mapping[str, str | None]) -> ProviderMetadata:
        raise ProviderFailure(
            "not_supported",
            f"{self.name} official metadata retrieval is not implemented; routing relies on Crossref metadata.",
        )

    def article_source(self) -> str:
        return self.article_source_name or self.name

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
    ) -> RawFulltextPayload:
        normalized_doi = normalize_doi(doi)
        if not normalized_doi:
            raise ProviderFailure("not_supported", f"{self.name} PDF fallback requires a DOI.")
        content = raw_payload.content
        if content is None or normalize_text(content.route_kind).lower() != "html":
            raise ProviderFailure("not_supported", f"{self.name} PDF fallback recovery requires provider-owned HTML content.")

        html_failure_reason = "abstract_only"
        html_failure_message = f"{self.name} HTML route only exposed abstract-level content after markdown extraction."
        recovery_warning = (
            f"{self.name} HTML route only exposed abstract-level content after markdown extraction; attempting PDF fallback."
        )
        runtime = load_runtime_config(self.env, provider=self.name, doi=normalized_doi)
        ensure_runtime_ready(runtime)
        return fetch_seeded_browser_pdf_payload(
            provider=self.name,
            runtime=runtime,
            pdf_candidates=self.pdf_candidates(normalized_doi, metadata),
            html_candidates=self.html_candidates(normalized_doi, metadata),
            landing_page_url=str(metadata.get("landing_page_url") or raw_payload.source_url or "") or None,
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
        )

    def html_candidates(self, doi: str, metadata: ProviderMetadata) -> list[str]:
        raise ProviderFailure(
            "not_supported",
            f"{self.name} must provide provider-owned HTML candidate selection.",
        )

    def pdf_candidates(self, doi: str, metadata: ProviderMetadata) -> list[str]:
        raise ProviderFailure(
            "not_supported",
            f"{self.name} must provide provider-owned PDF candidate selection.",
        )

    def extract_markdown(
        self,
        html_text: str,
        final_url: str,
        *,
        metadata: ProviderMetadata,
    ) -> tuple[str, dict[str, Any]]:
        raise ProviderFailure(
            "not_supported",
            f"{self.name} must provide provider-owned HTML extraction.",
        )

    def fetch_raw_fulltext(self, doi: str, metadata: ProviderMetadata) -> RawFulltextPayload:
        bootstrap = bootstrap_browser_workflow(self, doi, metadata)
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
                warnings=[f"{self.name} HTML route was not usable; skipping PDF fallback."],
                source_trail=[f"fulltext:{self.name}_html_fail"],
            )

        bootstrap.warnings.append(
            (
                f"{self.name} HTML route was not usable "
                f"({bootstrap.html_failure_reason or 'html_failed'}); attempting PDF fallback."
            )
        )

        try:
            return fetch_seeded_browser_pdf_payload(
                provider=self.name,
                runtime=bootstrap.runtime,
                pdf_candidates=bootstrap.pdf_candidates,
                html_candidates=bootstrap.html_candidates,
                landing_page_url=bootstrap.landing_page_url,
                user_agent=self.user_agent,
                browser_context_seed=bootstrap.browser_context_seed,
                html_failure_reason=bootstrap.html_failure_reason,
                html_failure_message=bootstrap.html_failure_message,
                warnings=bootstrap.warnings,
                success_source_trail=[
                    f"fulltext:{self.name}_html_fail",
                    f"fulltext:{self.name}_pdf_fallback_ok",
                ],
            )
        except PdfFallbackFailure as exc:
            reason = bootstrap.html_failure_message or f"{self.name} HTML route failed."
            raise ProviderFailure(
                "no_result",
                (
                    f"{self.name} full text could not be retrieved via HTML or PDF fallback. "
                    f"HTML failure: {reason} PDF failure: {exc.message}"
                ),
            ) from exc

    def fetch_result(
        self,
        doi: str,
        metadata: Mapping[str, Any],
        output_dir,
        *,
        asset_profile: AssetProfile = "none",
    ) -> ProviderFetchResult:
        raw_payload = self.fetch_raw_fulltext(doi, metadata)
        content = raw_payload.content
        if content is not None and content.needs_local_copy != raw_payload.needs_local_copy:
            content = replace(content, needs_local_copy=raw_payload.needs_local_copy)
            raw_payload.content = content

        provisional_article = None
        abstract_only_result_warnings: list[str] = []
        if content is not None and normalize_text(content.route_kind).lower() == "html":
            provisional_article = self.to_article_model(metadata, raw_payload)
            if provisional_article.quality.content_kind == "abstract_only" and self.allow_pdf_fallback_after_html_failure(
                html_failure_reason="abstract_only",
                html_failure_message=f"{self.name} HTML route only exposed abstract-level content after markdown extraction.",
            ):
                try:
                    recovered_payload = self._recover_pdf_payload_from_abstract_only_html(doi, metadata, raw_payload)
                except (ProviderFailure, PdfFallbackFailure):
                    provider_label = "PNAS" if self.name == "pnas" else self.name
                    abstract_only_result_warnings.append(
                        (
                            f"{provider_label} HTML route only exposed abstract-level content after markdown extraction, "
                            "and PDF fallback did not return usable full text; returning abstract-only content."
                        )
                    )
                else:
                    raw_payload = recovered_payload
                    content = raw_payload.content
                    if content is not None and content.needs_local_copy != raw_payload.needs_local_copy:
                        content = replace(content, needs_local_copy=raw_payload.needs_local_copy)
                        raw_payload.content = content
                    provisional_article = None

        artifact_policy = self.describe_artifacts(raw_payload)
        downloaded_assets: list[Mapping[str, Any]] = []
        asset_failures: list[Mapping[str, Any]] = []
        warnings = list(raw_payload.warnings)
        trace = list(raw_payload.trace)
        if (
            output_dir is not None
            and asset_profile != "none"
            and artifact_policy.allow_related_assets
            and (provisional_article is None or provisional_article.quality.content_kind == "fulltext")
        ):
            try:
                asset_results = self.download_related_assets(
                    doi,
                    metadata,
                    raw_payload,
                    output_dir,
                    asset_profile=asset_profile,
                )
                downloaded_assets = list(asset_results.get("assets") or [])
                asset_failures = list(asset_results.get("asset_failures") or [])
            except ProviderFailure as exc:
                warnings.append(f"{self.name.replace('_', ' ').title()} related assets could not be downloaded: {exc.message}")
                trace.extend(trace_from_markers([f"download:{self.name}_assets_failed"]))
            except (RequestFailure, OSError) as exc:
                warnings.append(f"{self.name.replace('_', ' ').title()} related assets could not be downloaded: {exc}")
                trace.extend(trace_from_markers([f"download:{self.name}_assets_failed"]))

        if provisional_article is not None and not downloaded_assets and not asset_failures:
            article = provisional_article
        else:
            article = self.to_article_model(
                metadata,
                raw_payload,
                downloaded_assets=downloaded_assets,
                asset_failures=asset_failures,
            )
        if article.quality.content_kind == "abstract_only":
            article = _finalize_abstract_only_provider_article(
                self.name,
                article,
                warnings=abstract_only_result_warnings,
            )
        artifacts = self.describe_artifacts(
            raw_payload,
            downloaded_assets=downloaded_assets,
            asset_failures=asset_failures,
        )
        return ProviderFetchResult(
            provider=raw_payload.provider or self.name,
            article=article,
            content=content,
            warnings=warnings,
            trace=list(trace or trace_from_markers(article.quality.source_trail)),
            artifacts=artifacts,
        )

    def download_related_assets(
        self,
        doi: str,
        metadata: ProviderMetadata,
        raw_payload: RawFulltextPayload,
        output_dir,
        *,
        asset_profile: AssetProfile = "all",
    ) -> dict[str, list[dict[str, Any]]]:
        if output_dir is None or asset_profile == "none":
            return empty_asset_results()
        content = raw_payload.content
        if normalize_text(content.route_kind if content is not None else "").lower() != "html":
            return empty_asset_results()

        html_text = decode_html(raw_payload.body)
        article_assets = extract_html_assets(
            html_text,
            raw_payload.source_url,
            asset_profile=asset_profile,
        )
        if not article_assets:
            return empty_asset_results()

        normalized_doi = normalize_doi(str(metadata.get("doi") or doi or ""))
        if not normalized_doi:
            return empty_asset_results()

        runtime = load_runtime_config(self.env, provider=self.name, doi=normalized_doi)
        ensure_runtime_ready(runtime)
        browser_context_seed = merge_browser_context_seeds(content.browser_context_seed if content is not None else None)

        def figure_page_fetcher(figure_page_url: str) -> tuple[str, str] | None:
            try:
                html_result = fetch_html_with_flaresolverr(
                    [figure_page_url],
                    publisher=self.name,
                    config=runtime,
                )
            except FlareSolverrFailure:
                return None
            browser_context_seed.update(
                merge_browser_context_seeds(browser_context_seed, html_result.browser_context_seed)
            )
            return html_result.html, html_result.final_url

        article_id = (
            normalized_doi
            or normalize_text(str(metadata.get("title") or ""))
            or raw_payload.source_url
        )
        return download_figure_assets(
            self.transport,
            article_id=article_id,
            assets=article_assets,
            output_dir=output_dir,
            user_agent=self.user_agent,
            asset_profile=asset_profile,
            figure_page_fetcher=figure_page_fetcher,
            browser_context_seed=browser_context_seed,
            seed_urls=[raw_payload.source_url],
        )

    def to_article_model(
        self,
        metadata: ProviderMetadata,
        raw_payload: RawFulltextPayload,
        *,
        downloaded_assets: list[Mapping[str, Any]] | None = None,
        asset_failures: list[Mapping[str, Any]] | None = None,
    ):
        raise ProviderFailure(
            "not_supported",
            f"{self.name} must provide provider-owned article assembly.",
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
        if normalize_text(content.route_kind if content is not None else "").lower() != "pdf_fallback":
            return artifacts
        provider_label = "PNAS" if self.name == "pnas" else self.name.title()
        return ProviderArtifacts(
            assets=list(artifacts.assets),
            asset_failures=list(artifacts.asset_failures),
            allow_related_assets=False,
            text_only=True,
            skip_warning=(
                f"{provider_label} PDF fallback currently returns text-only full text; "
                "figure and supplementary asset downloads are not implemented yet."
            ),
            skip_trace=trace_from_markers([f"download:{self.name}_assets_skipped_text_only"]),
        )


class SciencePnasClient(BrowserWorkflowClient):
    """Backward-compatible alias for existing tests and imports."""
