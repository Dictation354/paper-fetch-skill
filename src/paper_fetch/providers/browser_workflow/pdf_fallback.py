"""Seeded browser PDF fallback for provider browser workflows."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from ...http import PDF_MIME_TYPE
from ...reason_codes import PDF_FALLBACK
from ...runtime import RuntimeContext
from ...tracing import TraceEvent, trace_event
from .._pdf_common import (
    pdf_asset_output_dir,
    pdf_asset_profile_from_context,
    pdf_fetch_result_assets,
)
from .._pdf_fallback import PdfRequestContext
from .._registry import provider_bundle
from ..base import ProviderContent, RawFulltextPayload
from .fetchers import _choose_browser_seed_url
from .shared import BrowserWorkflowDeps, default_browser_workflow_deps


def fetch_seeded_browser_pdf_payload(
    *,
    provider: str,
    doi: str | None,
    runtime: Any,
    pdf_candidates: list[str],
    html_candidates: list[str],
    landing_page_url: str | None,
    user_agent: str,
    browser_context_seed: Mapping[str, Any] | None,
    html_failure_reason: str | None,
    html_failure_message: str | None,
    expected_title: str | None = None,
    html_failure_diagnostics: Mapping[str, Any] | None = None,
    warnings: list[str] | None = None,
    success_events: list[TraceEvent] | None = None,
    success_warning: str = "Full text was extracted from PDF fallback after the HTML path was not usable.",
    artifact_subdir: str = PDF_FALLBACK,
    context: RuntimeContext | None = None,
    deps: BrowserWorkflowDeps | None = None,
) -> RawFulltextPayload:
    del user_agent
    if context is not None:
        context.raise_if_cancelled()
    active_deps = deps or default_browser_workflow_deps()
    try:
        browser_only = provider_bundle(provider).browser_pdf_only
    except KeyError:
        browser_only = False
    context_warmer = active_deps.warm_browser_context
    if active_deps.pdf_browser_context_seed is not active_deps.warm_browser_context:
        from ..browser_runtime.api import (
            warm_browser_context as default_warm_browser_context,
        )

        if active_deps.warm_browser_context is default_warm_browser_context:
            context_warmer = active_deps.pdf_browser_context_seed

    if browser_only or provider == "elsevier":
        # Reuse the HTML session and let the PDF fetcher install its listener
        # before navigating to a URL that may start a download.
        pdf_context_seed = dict(browser_context_seed or {})
    else:
        pdf_context_seed = context_warmer(
            pdf_candidates,
            publisher=provider,
            config=runtime,
            browser_context_seed=browser_context_seed,
            runtime_context=context,
            lightweight=True,
        ).seed

    if context is not None:
        context.raise_if_cancelled()
    seed_url = _choose_browser_seed_url(
        (browser_context_seed or {}).get("browser_final_url"),
        html_candidates[0] if html_candidates else None,
        landing_page_url,
        pdf_context_seed.get("browser_final_url"),
    )
    seeded_browser_cookies = list(pdf_context_seed.get("browser_cookies") or [])
    seed_urls = (
        [seed_url]
        if seed_url and not (browser_only or seeded_browser_cookies)
        else None
    )
    pdf_result = active_deps.fetch_pdf_with_browser(
        pdf_candidates,
        artifact_dir=runtime.artifact_dir / artifact_subdir,
        asset_profile=pdf_asset_profile_from_context(context),
        asset_output_dir=pdf_asset_output_dir(context, doi=doi),
        browser_cookies=seeded_browser_cookies,
        browser_user_agent=pdf_context_seed.get("browser_user_agent")
        or getattr(runtime, "user_agent", None),
        referer=seed_url,
        browser_config=runtime,
        seed_urls=seed_urls,
        allow_pdf_only=True,
        request=PdfRequestContext(
            expected_identity={
                **({"doi": doi} if doi else {}),
                **({"title": expected_title} if expected_title else {}),
            }
            if doi or expected_title
            else None,
            runtime=context,
            browser_only=browser_only,
        ),
    )
    if context is not None:
        context.raise_if_cancelled()

    payload_warnings = [str(item) for item in warnings or [] if str(item).strip()]
    pdf_result_warnings = getattr(pdf_result, "warnings", [])
    if isinstance(pdf_result_warnings, Sequence) and not isinstance(
        pdf_result_warnings, str | bytes | bytearray
    ):
        payload_warnings.extend(
            str(item) for item in pdf_result_warnings if str(item).strip()
        )
    if success_warning:
        payload_warnings.append(success_warning)

    failure_diagnostics = dict(html_failure_diagnostics or {})
    payload_trace = list(success_events or [])
    if html_failure_reason:
        payload_trace.append(
            trace_event(
                "fulltext",
                f"{provider}_html",
                "fail",
                code=html_failure_reason,
                message=html_failure_message,
            )
        )
    pdf_diagnostics = getattr(pdf_result, "diagnostics", None)
    return RawFulltextPayload(
        provider=provider,
        content=ProviderContent(
            route_kind=PDF_FALLBACK,
            source_url=pdf_result.final_url,
            content_type=PDF_MIME_TYPE,
            body=pdf_result.pdf_bytes,
            markdown_text=pdf_result.markdown_text,
            diagnostics={
                **(
                    {"html_failure": failure_diagnostics} if failure_diagnostics else {}
                ),
                "pdf": (
                    dict(pdf_diagnostics)
                    if isinstance(pdf_diagnostics, Mapping)
                    else {}
                ),
            },
            html_failure_reason=html_failure_reason,
            html_failure_message=html_failure_message,
            suggested_filename=pdf_result.suggested_filename,
            extracted_assets=pdf_fetch_result_assets(pdf_result),
            needs_local_copy=True,
        ),
        warnings=payload_warnings,
        trace=payload_trace,
    )
