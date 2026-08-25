"""Shared helpers for typed provider payload construction."""

from __future__ import annotations

from typing import Any
from collections.abc import Mapping

from ..tracing import trace_from_markers
from .base import ProviderContent, ProviderFailure, RawFulltextPayload


def provider_failure_diagnostics(
    failure: ProviderFailure | None,
) -> dict[str, Any] | None:
    if failure is None:
        return None
    diagnostics: dict[str, Any] = {"code": failure.code, "message": failure.message}
    if failure.source_trail:
        diagnostics["source_trail"] = list(failure.source_trail)
    return diagnostics


def build_provider_payload(  # noqa: PLR0913 - explicit typed payload boundary
    *,
    provider: str,
    route_kind: str,
    route_name: str | None = None,
    source_url: str,
    content_type: str,
    body: bytes,
    markdown_text: str | None = None,
    merged_metadata: Mapping[str, Any] | None = None,
    diagnostics: Mapping[str, Any] | None = None,
    reason: str | None = None,
    fetcher: str | None = None,
    browser_context_seed: Mapping[str, Any] | None = None,
    suggested_filename: str | None = None,
    html_failure_reason: str | None = None,
    html_failure_message: str | None = None,
    extracted_assets: list[dict[str, Any]] | None = None,
    warnings: list[str] | None = None,
    trace_markers: list[str] | tuple[str, ...] | None = None,
    needs_local_copy: bool = False,
    content_needs_local_copy: bool | None = None,
) -> RawFulltextPayload:
    content = ProviderContent(
        route_kind=route_kind,
        source_url=source_url,
        content_type=content_type,
        body=body,
        route_name=route_name,
        markdown_text=markdown_text,
        merged_metadata=dict(merged_metadata)
        if isinstance(merged_metadata, Mapping)
        else None,
        diagnostics=dict(diagnostics or {}),
        reason=reason,
        fetcher=fetcher,
        browser_context_seed=dict(browser_context_seed or {}),
        suggested_filename=suggested_filename,
        html_failure_reason=html_failure_reason,
        html_failure_message=html_failure_message,
        extracted_assets=[dict(item) for item in (extracted_assets or [])],
        needs_local_copy=needs_local_copy
        if content_needs_local_copy is None
        else content_needs_local_copy,
    )
    return RawFulltextPayload(
        provider=provider,
        source_url=source_url,
        content_type=content_type,
        body=body,
        content=content,
        warnings=warnings,
        trace=trace_from_markers(list(trace_markers or [])),
        merged_metadata=merged_metadata,
        needs_local_copy=needs_local_copy,
    )


__all__ = ["build_provider_payload", "provider_failure_diagnostics"]
