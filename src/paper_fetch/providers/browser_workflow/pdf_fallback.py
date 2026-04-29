"""Seeded browser PDF fallback for provider browser workflows."""

from __future__ import annotations

import sys
from typing import Any, Mapping

from ...runtime import RuntimeContext
from ...tracing import trace_from_markers
from .._flaresolverr import (
    warm_browser_context_with_flaresolverr as _warm_browser_context_with_flaresolverr,
)
from .._pdf_fallback import fetch_pdf_with_playwright as _fetch_pdf_with_playwright
from ..base import ProviderContent, RawFulltextPayload
from ..browser_workflow_fetchers import _choose_playwright_seed_url


def _facade_attr(name: str, fallback):
    facade = sys.modules.get("paper_fetch.providers.browser_workflow")
    return getattr(facade, name, fallback) if facade is not None else fallback


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
    pdf_browser_context_seed = _facade_attr(
        "warm_browser_context_with_flaresolverr",
        _warm_browser_context_with_flaresolverr,
    )(
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
    pdf_result = _facade_attr("fetch_pdf_with_playwright", _fetch_pdf_with_playwright)(
        pdf_candidates,
        artifact_dir=runtime.artifact_dir / artifact_subdir,
        browser_cookies=list(pdf_browser_context_seed.get("browser_cookies") or []),
        browser_user_agent=pdf_browser_context_seed.get("browser_user_agent")
        or user_agent,
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
