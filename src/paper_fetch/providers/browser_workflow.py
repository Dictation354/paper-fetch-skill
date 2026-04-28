"""Shared browser-workflow runtime helpers for Wiley/Science/PNAS."""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass, field, replace
from typing import Any, Callable, Mapping

from ..config import build_user_agent, resolve_asset_download_concurrency
from ..extraction.html import decode_html
from ..extraction.html.signals import SciencePnasHtmlFailure
from ..metadata_types import ProviderMetadata
from ..models import AssetProfile, article_from_markdown, coerce_asset_failure_diagnostics, metadata_only_article
from ..publisher_identity import normalize_doi
from ..runtime import RuntimeContext
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
from . import _browser_workflow_html_extraction as _html_extraction
from ._browser_workflow_fetchers import (
    _IMAGE_DOCUMENT_FETCH_TIMEOUT_MS,
    _MemoizedFigurePageFetcher,
    _MemoizedImageDocumentFetcher,
    _SharedPlaywrightImageDocumentFetcher,
    _build_shared_playwright_file_fetcher,
    _build_shared_playwright_image_fetcher,
    _choose_playwright_seed_url,
    _compact_failure_diagnostic,
    _flaresolverr_image_document_payload,
    _flaresolverr_image_payload_failure_reason,
)
from ._browser_workflow_html_extraction import (
    _browser_workflow_html_payload,
    _cached_browser_workflow_markdown,
    extract_science_pnas_markdown,
    fetch_html_with_direct_playwright,
    rewrite_inline_figure_links,
)
from ._browser_workflow_shared import (
    build_browser_workflow_html_candidates,
    build_browser_workflow_pdf_candidates,
    extract_pdf_url_from_crossref,
    preferred_html_candidate_from_landing_page as _preferred_html_candidate_from_landing_page,
)
from ._waterfall import ProviderWaterfallStep, run_provider_waterfall
from .base import PreparedFetchResultPayload, ProviderArtifacts, ProviderClient, ProviderContent, ProviderFailure, RawFulltextPayload
from .html_assets import (
    download_supplementary_assets,
    download_figure_assets_with_image_document_fetcher,
    extract_full_size_figure_image_url,
    extract_scoped_html_assets,
    html_asset_identity_key,
    looks_like_full_size_asset_url,
    split_body_and_supplementary_assets,
)

logger = logging.getLogger("paper_fetch.providers.browser_workflow")

__all__ = [
    "BrowserWorkflowBootstrapResult",
    "BrowserWorkflowClient",
    "FlareSolverrFailure",
    "_IMAGE_DOCUMENT_FETCH_TIMEOUT_MS",
    "_SharedPlaywrightImageDocumentFetcher",
    "PdfFallbackFailure",
    "ProviderBrowserProfile",
    "SciencePnasHtmlFailure",
    "bootstrap_browser_workflow",
    "browser_workflow_article_from_payload",
    "build_browser_workflow_html_candidates",
    "build_browser_workflow_pdf_candidates",
    "ensure_runtime_ready",
    "extract_pdf_url_from_crossref",
    "extract_science_pnas_markdown",
    "fetch_html_with_direct_playwright",
    "fetch_html_with_flaresolverr",
    "fetch_seeded_browser_pdf_payload",
    "load_runtime_config",
    "merge_browser_context_seeds",
    "merge_provider_owned_authors",
    "preferred_html_candidate_from_landing_page",
    "probe_runtime_status",
    "rewrite_inline_figure_links",
    "time",
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


@dataclass(frozen=True)
class ProviderBrowserProfile:
    name: str
    article_source_name: str | None
    label: str
    hosts: tuple[str, ...]
    base_hosts: tuple[str, ...]
    html_path_templates: tuple[str, ...]
    pdf_path_templates: tuple[str, ...]
    crossref_pdf_position: int
    markdown_publisher: str
    fallback_author_extractor: Callable[[str], list[str]] | None
    shared_playwright_image_fetcher: bool
    direct_playwright_html_preflight: bool = False


def preferred_html_candidate_from_landing_page(
    publisher: str,
    doi: str,
    landing_page_url: str | None,
) -> str | None:
    """Backward-compatible provider-name wrapper for legacy imports."""

    from ._science_pnas_profiles import preferred_html_candidate_from_landing_page as legacy_preferred

    return legacy_preferred(publisher, doi, landing_page_url)


def _fetch_flaresolverr_html_payload(*args, **kwargs):
    kwargs.setdefault("html_fetcher", fetch_html_with_flaresolverr)
    return _html_extraction._fetch_flaresolverr_html_payload(*args, **kwargs)


def _fetch_flaresolverr_html_payload_with_fast_path(*args, **kwargs):
    kwargs.setdefault("html_fetcher", fetch_html_with_flaresolverr)
    return _html_extraction._fetch_flaresolverr_html_payload_with_fast_path(*args, **kwargs)


def _cached_browser_workflow_assets(*args, **kwargs):
    kwargs.setdefault("scoped_asset_extractor", extract_scoped_html_assets)
    return _html_extraction._cached_browser_workflow_assets(*args, **kwargs)


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


def _download_asset_result_key(asset: Mapping[str, Any]) -> str:
    key = normalize_text(html_asset_identity_key(asset))
    if key:
        return key
    parts = [
        normalize_text(str(asset.get("kind") or "")),
        normalize_text(str(asset.get("heading") or "")),
        normalize_text(str(asset.get("caption") or "")),
        normalize_text(str(asset.get("download_url") or "")),
        normalize_text(str(asset.get("source_url") or "")),
    ]
    return "|".join(part for part in parts if part)


def _download_asset_match_tokens(asset: Mapping[str, Any]) -> set[str]:
    tokens = {
        normalize_text(str(asset.get(field) or ""))
        for field in (
            "heading",
            "caption",
            "url",
            "download_url",
            "original_url",
            "source_url",
            "figure_page_url",
        )
    }
    return {token for token in tokens if token}


def _browser_workflow_image_download_candidates(
    _transport,
    *,
    asset: Mapping[str, Any],
    user_agent: str,
    figure_page_fetcher: Callable[[str], tuple[str, str] | None] | None = None,
) -> list[str]:
    del user_agent
    direct_full_size_url = normalize_text(str(asset.get("full_size_url") or ""))
    primary_url = normalize_text(str(asset.get("url") or ""))
    preview_url = normalize_text(str(asset.get("preview_url") or "")) or primary_url
    candidates: list[str] = []

    if direct_full_size_url:
        candidates.append(direct_full_size_url)

    figure_page_url = normalize_text(str(asset.get("figure_page_url") or ""))
    if figure_page_url and figure_page_fetcher is not None:
        try:
            page_result = figure_page_fetcher(figure_page_url)
        except Exception:
            page_result = None
        if page_result is not None:
            page_html, page_url = page_result
            full_size_url = extract_full_size_figure_image_url(page_html, page_url)
            if full_size_url:
                candidates.append(full_size_url)

    if primary_url and looks_like_full_size_asset_url(primary_url):
        candidates.append(primary_url)
    if preview_url:
        candidates.append(preview_url)

    deduped: list[str] = []
    seen: set[str] = set()
    for candidate in candidates:
        if candidate and candidate not in seen:
            seen.add(candidate)
            deduped.append(candidate)
    return deduped


def _merge_download_attempt_results(
    initial: Mapping[str, Any],
    retry: Mapping[str, Any],
) -> dict[str, list[dict[str, Any]]]:
    downloads_by_key: dict[str, dict[str, Any]] = {}
    for result in (initial, retry):
        for asset in list(result.get("assets") or []):
            key = _download_asset_result_key(asset)
            downloads_by_key[key or str(len(downloads_by_key))] = dict(asset)

    merged_downloads = list(downloads_by_key.values())
    resolved_tokens = set().union(*(_download_asset_match_tokens(asset) for asset in merged_downloads)) if merged_downloads else set()
    failure_candidates = list(retry.get("asset_failures") or []) or list(initial.get("asset_failures") or [])
    unresolved_failures = []
    for failure in failure_candidates:
        failure_tokens = {
            normalize_text(str(failure.get(field) or ""))
            for field in ("heading", "caption", "source_url")
        }
        failure_tokens = {token for token in failure_tokens if token}
        if failure_tokens and failure_tokens & resolved_tokens:
            continue
        unresolved_failures.append(dict(failure))

    return {
        "assets": merged_downloads,
        "asset_failures": unresolved_failures,
    }


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
    context: RuntimeContext | None = None,
) -> BrowserWorkflowBootstrapResult:
    context = client._runtime_context(context)
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

    profile = client.require_profile()
    preferred_html_candidate = _preferred_html_candidate_from_landing_page(
        normalized_doi,
        landing_page_url,
        hosts=profile.hosts,
    )
    logger.debug(
        "browser_workflow_candidates provider=%s doi=%s preferred_hit=%s first_candidate=%s candidate_count=%s",
        client.name,
        normalized_doi,
        bool(preferred_html_candidate and html_candidates and html_candidates[0] == preferred_html_candidate),
        html_candidates[0] if html_candidates else None,
        len(html_candidates),
    )

    if profile.direct_playwright_html_preflight:
        try:
            html_result = fetch_html_with_direct_playwright(
                html_candidates,
                publisher=client.name,
                user_agent=client.user_agent,
                context=context,
            )
            result.browser_context_seed = html_result.browser_context_seed
            markdown_text, extraction = _cached_browser_workflow_markdown(
                client,
                html_result.html,
                html_result.final_url,
                metadata=metadata,
                context=context,
            )
            result.html_payload = _browser_workflow_html_payload(
                client,
                html_result,
                markdown_text=markdown_text,
                extraction=extraction,
                fetcher="playwright_direct",
                warnings=result.warnings,
            )
            return result
        except SciencePnasHtmlFailure as exc:
            logger.debug(
                "browser_workflow_direct_html_preflight provider=%s doi=%s action=fallback reason=%s message=%s",
                client.name,
                normalized_doi,
                exc.reason,
                exc.message,
            )
        except Exception as exc:
            logger.debug(
                "browser_workflow_direct_html_preflight provider=%s doi=%s action=fallback error=%s",
                client.name,
                normalized_doi,
                normalize_text(str(exc)) or exc.__class__.__name__,
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
        html_result, html_payload = _fetch_flaresolverr_html_payload_with_fast_path(
            client,
            html_candidates,
            runtime=result.runtime,
            metadata=metadata,
            context=context,
            warnings=result.warnings,
        )
        result.browser_context_seed = html_result.browser_context_seed
        result.html_payload = html_payload
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
    context: RuntimeContext | None = None,
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
        context=context,
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
    context: RuntimeContext | None = None,
):
    context = client._runtime_context(context)
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
                markdown_text, extraction = _cached_browser_workflow_markdown(
                    client,
                    html_text,
                    raw_payload.source_url or str(metadata.get("landing_page_url") or ""),
                    metadata=metadata,
                    context=context,
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

    article = article_from_markdown(
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
    article.quality.asset_failures = coerce_asset_failure_diagnostics(asset_failures)
    return article


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
    profile: ProviderBrowserProfile | None = None

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
        return profile.label if profile is not None else ("PNAS" if self.name == "pnas" else self.name.title())

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
            base_seed_url=crossref_pdf_url if profile.crossref_pdf_position == 0 else None,
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
        return extract_science_pnas_markdown(html_text, final_url, publisher, metadata=metadata)

    def fetch_raw_fulltext(
        self,
        doi: str,
        metadata: ProviderMetadata,
        *,
        context: RuntimeContext | None = None,
    ) -> RawFulltextPayload:
        context = self._runtime_context(context)
        bootstrap = bootstrap_browser_workflow(self, doi, metadata, context=context)
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

        initial_warning = (
            f"{self.name} HTML route was not usable "
            f"({bootstrap.html_failure_reason or 'html_failed'}); attempting PDF fallback."
        )

        def run_pdf_fallback(_state) -> RawFulltextPayload:
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
                    warnings=[],
                    success_source_trail=[],
                    context=context,
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

        provisional_article = self.to_article_model(metadata, raw_payload, context=context)
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
        return provisional_article is None or provisional_article.quality.content_kind == "fulltext"

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
        if normalize_text(content.route_kind if content is not None else "").lower() != "html":
            return empty_asset_results()

        html_text = decode_html(raw_payload.body)
        try:
            article_assets = _cached_browser_workflow_assets(
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
        body_assets, supplementary_assets = split_body_and_supplementary_assets(article_assets)
        asset_download_concurrency = resolve_asset_download_concurrency(context.env)

        normalized_doi = normalize_doi(str(metadata.get("doi") or doi or ""))
        if not normalized_doi:
            return empty_asset_results()

        runtime = load_runtime_config(self.env, provider=self.name, doi=normalized_doi)
        ensure_runtime_ready(runtime)
        browser_context_seed = merge_browser_context_seeds(content.browser_context_seed if content is not None else None)

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

        def supplementary_recovery_urls(file_url: str, asset: Mapping[str, Any]) -> list[str]:
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
        ) -> Callable[[str, Mapping[str, Any], Mapping[str, Any]], Mapping[str, Any] | None]:
            def recover(image_url: str, asset: Mapping[str, Any], failure: Mapping[str, Any]) -> Mapping[str, Any]:
                attempts: list[dict[str, Any]] = []
                for recovery_url in asset_recovery_urls(image_url, asset):
                    try:
                        html_result = fetch_html_with_flaresolverr(
                            [recovery_url],
                            publisher=self.name,
                            config=runtime,
                            return_image_payload=True,
                        )
                    except FlareSolverrFailure as exc:
                        if exc.browser_context_seed:
                            with attempt_seed_lock:
                                attempt_seed.update(
                                    merge_browser_context_seeds(attempt_seed, exc.browser_context_seed)
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
                            merge_browser_context_seeds(attempt_seed, html_result.browser_context_seed)
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
                            "content_type": html_result.response_headers.get("content-type"),
                            "title_snippet": (html_result.title or "")[:160],
                            "attempts": attempts,
                            "reason": recovery_reason,
                            "image_payload": image_payload,
                        }
                    )
                return _compact_failure_diagnostic(
                    {
                        "status": "failed",
                        "reason": normalize_text(str(failure.get("reason") or "")) or "challenge_recovery_failed",
                        "attempts": attempts,
                    }
                )

            return recover

        def supplementary_challenge_recovery_for(
            attempt_seed: dict[str, Any],
            attempt_seed_lock: threading.Lock,
        ) -> Callable[[str, Mapping[str, Any], Mapping[str, Any]], Mapping[str, Any] | None]:
            def recover(file_url: str, asset: Mapping[str, Any], failure: Mapping[str, Any]) -> Mapping[str, Any]:
                attempts: list[dict[str, Any]] = []
                for recovery_url in supplementary_recovery_urls(file_url, asset):
                    try:
                        html_result = fetch_html_with_flaresolverr(
                            [recovery_url],
                            publisher=self.name,
                            config=runtime,
                        )
                    except FlareSolverrFailure as exc:
                        if exc.browser_context_seed:
                            with attempt_seed_lock:
                                attempt_seed.update(
                                    merge_browser_context_seeds(attempt_seed, exc.browser_context_seed)
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
                            merge_browser_context_seeds(attempt_seed, html_result.browser_context_seed)
                        )
                    return _compact_failure_diagnostic(
                        {
                            "status": "ok",
                            "url": recovery_url,
                            "final_url": html_result.final_url,
                            "response_status": html_result.response_status,
                            "content_type": html_result.response_headers.get("content-type"),
                            "title_snippet": (html_result.title or "")[:160],
                            "attempts": attempts,
                        }
                    )
                return _compact_failure_diagnostic(
                    {
                        "status": "failed",
                        "reason": normalize_text(str(failure.get("reason") or "")) or "challenge_recovery_failed",
                        "attempts": attempts,
                    }
                )

            return recover

        def image_document_fetcher_for(
            current_seed: Mapping[str, Any],
            attempt_seed: dict[str, Any],
            attempt_seed_lock: threading.Lock,
        ) -> Callable[[str, Mapping[str, Any]], dict[str, Any] | None] | None:
            if not body_assets:
                return None
            profile = self.profile
            if profile is None or not profile.shared_playwright_image_fetcher:
                return None
            fetcher = _build_shared_playwright_image_fetcher(
                browser_context_seed_getter=lambda: attempt_seed,
                seed_urls_getter=lambda: seed_urls_for(attempt_seed),
                browser_user_agent=current_seed.get("browser_user_agent") or self.user_agent,
                headless=runtime.headless,
                challenge_recovery=asset_challenge_recovery_for(attempt_seed, attempt_seed_lock),
                runtime_context=context,
            )
            return _MemoizedImageDocumentFetcher(fetcher)

        def file_document_fetcher_for(
            current_seed: Mapping[str, Any],
            attempt_seed: dict[str, Any],
            attempt_seed_lock: threading.Lock,
        ) -> Callable[[str, Mapping[str, Any]], dict[str, Any] | None] | None:
            if not supplementary_assets:
                return None
            profile = self.profile
            if profile is None or not profile.shared_playwright_image_fetcher:
                return None
            return _build_shared_playwright_file_fetcher(
                browser_context_seed_getter=lambda: attempt_seed,
                seed_urls_getter=lambda: seed_urls_for(attempt_seed),
                browser_user_agent=current_seed.get("browser_user_agent") or self.user_agent,
                headless=runtime.headless,
                challenge_recovery=supplementary_challenge_recovery_for(attempt_seed, attempt_seed_lock),
                runtime_context=context,
            )

        def run_download_attempt(current_seed: Mapping[str, Any]) -> dict[str, list[dict[str, Any]]]:
            attempt_seed = merge_browser_context_seeds(current_seed)
            attempt_seed_lock = threading.Lock()

            def raw_figure_page_fetcher(figure_page_url: str) -> tuple[str, str] | None:
                try:
                    html_result = fetch_html_with_flaresolverr(
                        [figure_page_url],
                        publisher=self.name,
                        config=runtime,
                    )
                except FlareSolverrFailure:
                    return None
                with attempt_seed_lock:
                    attempt_seed.update(
                        merge_browser_context_seeds(attempt_seed, html_result.browser_context_seed)
                    )
                return html_result.html, html_result.final_url

            figure_page_fetcher = _MemoizedFigurePageFetcher(raw_figure_page_fetcher)
            image_document_fetcher = image_document_fetcher_for(attempt_seed, attempt_seed, attempt_seed_lock)
            file_document_fetcher = file_document_fetcher_for(attempt_seed, attempt_seed, attempt_seed_lock)
            try:
                body_result = download_figure_assets_with_image_document_fetcher(
                    self.transport,
                    article_id=article_id,
                    assets=body_assets,
                    output_dir=output_dir,
                    user_agent=self.user_agent,
                    asset_profile=asset_profile,
                    figure_page_fetcher=figure_page_fetcher,
                    candidate_builder=_browser_workflow_image_download_candidates,
                    image_document_fetcher=image_document_fetcher,
                    asset_download_concurrency=asset_download_concurrency,
                )
                supplementary_result = download_supplementary_assets(
                    self.transport,
                    article_id=article_id,
                    assets=supplementary_assets,
                    output_dir=output_dir,
                    user_agent=self.user_agent,
                    asset_profile=asset_profile,
                    browser_context_seed=attempt_seed,
                    seed_urls=seed_urls_for(attempt_seed),
                    file_document_fetcher=file_document_fetcher,
                    asset_download_concurrency=asset_download_concurrency,
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

        initial_result = run_download_attempt(browser_context_seed)
        if not initial_result.get("asset_failures"):
            return initial_result

        refreshed_seed = warm_browser_context_with_flaresolverr(
            seed_urls_for(browser_context_seed),
            publisher=self.name,
            config=runtime,
            browser_context_seed=browser_context_seed,
        )
        retry_result = run_download_attempt(refreshed_seed)
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
        if normalize_text(content.route_kind if content is not None else "").lower() != "pdf_fallback":
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
            skip_trace=trace_from_markers([f"download:{self.name}_assets_skipped_text_only"]),
        )
