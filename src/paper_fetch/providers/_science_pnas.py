"""Shared browser-workflow provider implementation for Wiley/Science/PNAS."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Mapping

from ..config import build_user_agent
from ..metadata_types import ProviderMetadata
from ..models import article_from_markdown, metadata_only_article
from ..publisher_identity import normalize_doi
from ..utils import normalize_text
from ._flaresolverr import (
    FlareSolverrFailure,
    ensure_runtime_ready,
    fetch_html_with_flaresolverr,
    load_runtime_config,
    probe_runtime_status,
    warm_browser_context_with_flaresolverr,
)
from ._pdf_fallback import PdfFallbackFailure, fetch_pdf_with_playwright
from ._science_pnas_html import (
    SciencePnasHtmlFailure,
    build_html_candidates,
    build_pdf_candidates,
    extract_science_pnas_markdown,
    extract_pdf_url_from_crossref,
    preferred_html_candidate_from_landing_page,
)
from .base import ProviderClient, ProviderFailure, RawFulltextPayload

logger = logging.getLogger("paper_fetch.providers.browser_workflow")


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
            metadata={
                "route": "html",
                "markdown_text": markdown_text,
                "warnings": result.warnings,
                "source_trail": [f"fulltext:{client.name}_html_ok"],
                "html_fetcher": "flaresolverr",
                "extraction": extraction,
            },
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
        metadata={
            "route": "pdf_fallback",
            "markdown_text": pdf_result.markdown_text,
            "warnings": payload_warnings,
            "html_failure_reason": html_failure_reason,
            "html_failure_message": html_failure_message,
            "source_trail": list(success_source_trail or []),
            "suggested_filename": pdf_result.suggested_filename,
        },
        needs_local_copy=True,
    )


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

    def html_candidates(self, doi: str, metadata: ProviderMetadata) -> list[str]:
        landing_page_url = str(metadata.get("landing_page_url") or "") or None
        return build_html_candidates(self.name, doi, landing_page_url=landing_page_url)

    def pdf_candidates(self, doi: str, metadata: ProviderMetadata) -> list[str]:
        return build_pdf_candidates(self.name, doi, extract_pdf_url_from_crossref(metadata))

    def extract_markdown(
        self,
        html_text: str,
        final_url: str,
        *,
        metadata: ProviderMetadata,
    ) -> tuple[str, dict[str, Any]]:
        return extract_science_pnas_markdown(
            html_text,
            final_url,
            self.name,
            metadata=metadata,
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

    def to_article_model(
        self,
        metadata: ProviderMetadata,
        raw_payload: RawFulltextPayload,
        *,
        downloaded_assets: list[Mapping[str, Any]] | None = None,
        asset_failures: list[Mapping[str, Any]] | None = None,
    ):
        markdown_text = str(raw_payload.metadata.get("markdown_text") or "").strip()
        warnings = [str(item) for item in raw_payload.metadata.get("warnings") or [] if str(item).strip()]
        source_trail = [str(item) for item in raw_payload.metadata.get("source_trail") or [] if str(item).strip()]
        doi = normalize_doi(metadata.get("doi"))
        source = self.article_source()

        if not markdown_text:
            warnings.append(f"{self.name} retrieval did not produce usable markdown.")
            return metadata_only_article(
                source=source,
                metadata=metadata,
                doi=doi or None,
                warnings=warnings,
                source_trail=source_trail + [f"fulltext:{self.name}_parse_fail"],
            )

        return article_from_markdown(
            source=source,
            metadata=metadata,
            doi=doi or None,
            markdown_text=markdown_text,
            warnings=warnings,
            source_trail=source_trail,
        )


class SciencePnasClient(BrowserWorkflowClient):
    """Backward-compatible alias for existing tests and imports."""
