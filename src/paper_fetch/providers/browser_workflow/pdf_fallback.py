"""Seeded browser PDF fallback for provider browser workflows."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from collections.abc import Mapping

from ...http import PDF_MIME_TYPE
from ...runtime import RuntimeContext
from ...tracing import trace_from_markers
from ...reason_codes import PDF_FALLBACK
from ..base import ProviderContent, RawFulltextPayload
from .._pdf_common import pdf_asset_output_dir, pdf_asset_profile_from_context, pdf_fetch_result_assets
from .fetchers import _choose_browser_seed_url
from .shared import BrowserWorkflowDeps, default_browser_workflow_deps


def _runtime_storage_state_path(runtime: Any) -> Any | None:
    storage_state_path = getattr(runtime, "storage_state_path", None)
    if storage_state_path is not None:
        path = Path(storage_state_path).expanduser()
        return path if path.is_file() else None
    profile_dir = getattr(runtime, "profile_dir", None) or getattr(runtime, "user_data_dir", None)
    if profile_dir is None:
        return None
    path = Path(profile_dir).expanduser() / "storage-state.json"
    return path if path.is_file() else None


def fetch_seeded_browser_pdf_payload(
    *,
    provider: str,
    doi: str | None,
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
    artifact_subdir: str = PDF_FALLBACK,
    context: RuntimeContext | None = None,
    deps: BrowserWorkflowDeps | None = None,
) -> RawFulltextPayload:
    deps = deps or default_browser_workflow_deps()
    context_warmer = deps.warm_browser_context
    if deps.pdf_browser_context_seed is not deps.warm_browser_context:
        from ..browser_runtime import warm_browser_context as default_warm_browser_context

        if deps.warm_browser_context is default_warm_browser_context:
            context_warmer = deps.pdf_browser_context_seed
    pdf_context_seed = context_warmer(
        pdf_candidates,
        publisher=provider,
        config=runtime,
        browser_context_seed=browser_context_seed,
    )
    seed_url = _choose_browser_seed_url(
        (browser_context_seed or {}).get("browser_final_url"),
        html_candidates[0] if html_candidates else None,
        landing_page_url,
        pdf_context_seed.get("browser_final_url"),
    )
    pdf_result = deps.fetch_pdf_with_browser(
        pdf_candidates,
        artifact_dir=runtime.artifact_dir / artifact_subdir,
        asset_profile=pdf_asset_profile_from_context(context),
        asset_output_dir=pdf_asset_output_dir(context, doi=doi),
        browser_cookies=list(pdf_context_seed.get("browser_cookies") or []),
        browser_user_agent=pdf_context_seed.get("browser_user_agent")
        or getattr(runtime, "user_agent", None),
        headless=runtime.headless,
        binary_path=getattr(runtime, "binary_path", None),
        cdp_endpoint=getattr(runtime, "cdp_endpoint", None),
        profile_dir=getattr(runtime, "profile_dir", None),
        user_data_dir=getattr(runtime, "user_data_dir", None),
        storage_state_path=_runtime_storage_state_path(runtime),
        seed_urls=[seed_url] if seed_url else None,
        context=context,
    )
    payload_warnings = [str(item) for item in warnings or [] if str(item).strip()]
    if success_warning:
        payload_warnings.append(success_warning)
    return RawFulltextPayload(
        provider=provider,
        source_url=pdf_result.final_url,
        content_type=PDF_MIME_TYPE,
        body=pdf_result.pdf_bytes,
        content=ProviderContent(
            route_kind=PDF_FALLBACK,
            source_url=pdf_result.final_url,
            content_type=PDF_MIME_TYPE,
            body=pdf_result.pdf_bytes,
            markdown_text=pdf_result.markdown_text,
            html_failure_reason=html_failure_reason,
            html_failure_message=html_failure_message,
            suggested_filename=pdf_result.suggested_filename,
            extracted_assets=pdf_fetch_result_assets(pdf_result),
        ),
        warnings=payload_warnings,
        trace=trace_from_markers(list(success_source_trail or [])),
        needs_local_copy=True,
    )
