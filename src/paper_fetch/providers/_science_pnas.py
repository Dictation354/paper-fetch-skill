"""Shared Science/PNAS provider implementation."""

from __future__ import annotations

import logging
from typing import Any, Mapping

from ..config import build_user_agent
from ..metadata_types import ProviderMetadata
from ..models import article_from_markdown, metadata_only_article
from ..publisher_identity import normalize_doi
from ._flaresolverr import (
    FlareSolverrFailure,
    ensure_runtime_ready,
    fetch_html_with_flaresolverr,
    load_runtime_config,
    probe_runtime_status,
)
from ._pdf_fallback import PdfFallbackFailure, fetch_pdf_with_playwright
from ._science_pnas_html import (
    SciencePnasHtmlFailure,
    build_html_candidates,
    build_pdf_candidates,
    extract_pdf_url_from_crossref,
    extract_science_pnas_markdown,
    preferred_html_candidate_from_landing_page,
)
from .base import ProviderClient, ProviderFailure, RawFulltextPayload

logger = logging.getLogger("paper_fetch.providers.science_pnas")


class SciencePnasClient(ProviderClient):
    name = "science_pnas"

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

    def fetch_raw_fulltext(self, doi: str, metadata: ProviderMetadata) -> RawFulltextPayload:
        normalized_doi = normalize_doi(doi)
        if not normalized_doi:
            raise ProviderFailure("not_supported", f"{self.name} full-text retrieval requires a DOI.")

        runtime = load_runtime_config(self.env, provider=self.name, doi=normalized_doi)
        ensure_runtime_ready(runtime)

        landing_page_url = str(metadata.get("landing_page_url") or "") or None
        html_candidates = build_html_candidates(self.name, normalized_doi, landing_page_url=landing_page_url)
        pdf_candidates = build_pdf_candidates(self.name, normalized_doi, extract_pdf_url_from_crossref(metadata))
        preferred_html_candidate = preferred_html_candidate_from_landing_page(self.name, normalized_doi, landing_page_url)
        logger.debug(
            "science_pnas_candidates provider=%s doi=%s preferred_hit=%s first_candidate=%s candidate_count=%s",
            self.name,
            normalized_doi,
            bool(preferred_html_candidate and html_candidates and html_candidates[0] == preferred_html_candidate),
            html_candidates[0] if html_candidates else None,
            len(html_candidates),
        )
        html_failure_reason: str | None = None
        html_failure_message: str | None = None
        browser_context_seed: Mapping[str, Any] | None = None
        warnings: list[str] = []

        try:
            html_result = fetch_html_with_flaresolverr(html_candidates, publisher=self.name, config=runtime)
            browser_context_seed = html_result.browser_context_seed
            markdown_text, extraction = extract_science_pnas_markdown(
                html_result.html,
                html_result.final_url,
                self.name,
                metadata=metadata,
            )
            return RawFulltextPayload(
                provider=self.name,
                source_url=html_result.final_url,
                content_type="text/html",
                body=html_result.html.encode("utf-8"),
                metadata={
                    "route": "html",
                    "markdown_text": markdown_text,
                    "warnings": warnings,
                    "source_trail": [f"fulltext:{self.name}_html_ok"],
                    "html_fetcher": "flaresolverr",
                    "extraction": extraction,
                },
                needs_local_copy=False,
            )
        except FlareSolverrFailure as exc:
            browser_context_seed = exc.browser_context_seed or browser_context_seed
            html_failure_reason = exc.kind
            html_failure_message = exc.message
        except SciencePnasHtmlFailure as exc:
            html_failure_reason = exc.reason
            html_failure_message = exc.message

        warnings.append(
            f"{self.name} HTML route was not usable ({html_failure_reason or 'html_failed'}); attempting PDF fallback."
        )

        try:
            pdf_result = fetch_pdf_with_playwright(
                pdf_candidates,
                artifact_dir=runtime.artifact_dir / "pdf_fallback",
                browser_cookies=list((browser_context_seed or {}).get("browser_cookies") or []),
                browser_user_agent=(browser_context_seed or {}).get("browser_user_agent") or self.user_agent,
                headless=runtime.headless,
            )
            warnings.append("Full text was extracted from PDF fallback after the HTML path was not usable.")
            return RawFulltextPayload(
                provider=self.name,
                source_url=pdf_result.final_url,
                content_type="application/pdf",
                body=pdf_result.pdf_bytes,
                metadata={
                    "route": "pdf_fallback",
                    "markdown_text": pdf_result.markdown_text,
                    "warnings": warnings,
                    "html_failure_reason": html_failure_reason,
                    "html_failure_message": html_failure_message,
                    "source_trail": [
                        f"fulltext:{self.name}_html_fail",
                        f"fulltext:{self.name}_pdf_fallback_ok",
                    ],
                    "suggested_filename": pdf_result.suggested_filename,
                },
                needs_local_copy=True,
            )
        except PdfFallbackFailure as exc:
            reason = html_failure_message or f"{self.name} HTML route failed."
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

        if not markdown_text:
            warnings.append(f"{self.name} retrieval did not produce usable markdown.")
            return metadata_only_article(
                source=self.name,
                metadata=metadata,
                doi=doi or None,
                warnings=warnings,
                source_trail=source_trail + [f"fulltext:{self.name}_parse_fail"],
            )

        return article_from_markdown(
            source=self.name,
            metadata=metadata,
            doi=doi or None,
            markdown_text=markdown_text,
            warnings=warnings,
            source_trail=source_trail,
        )
