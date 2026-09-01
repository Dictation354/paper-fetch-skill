"""IEEE browser payload construction."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any

from ..http import redact_url_for_diagnostics
from ..http.headers import header_value
from ..quality.html_availability import (
    HtmlQualityAssessor,
    availability_failure_message,
)
from ..runtime import RuntimeContext
from ..tracing import fulltext_marker
from . import _ieee_html as ieee_html
from . import _ieee_metadata as ieee_metadata
from ._payloads import (
    build_provider_payload,
    provider_failure_diagnostics as _provider_failure_diagnostics,
)
from .base import ProviderFailure, RawFulltextPayload
from .browser_runtime import BrowserRuntimeConfig, BrowserRuntimeFailure

IeeeAssetExtractor = Callable[
    [ieee_html.IeeeHtmlExtraction, ieee_metadata.IeeeLandingAttempt],
    list[dict[str, Any]],
]


@dataclass(frozen=True)
class IeeeBrowserPayloadRequest:
    provider_name: str
    landing_attempt: ieee_metadata.IeeeLandingAttempt
    document_url: str
    rest_url: str
    direct_html_failure: ProviderFailure | None
    context: RuntimeContext
    runtime_config: BrowserRuntimeConfig
    extraction_assets: IeeeAssetExtractor


@dataclass(frozen=True)
class IeeeBrowserPayloadSource:
    html_text: str
    source_url: str
    requested_url: str
    response_status: int | None
    response_headers: Mapping[str, str]
    browser_context_seed: Mapping[str, Any]
    browser_diagnostics: Mapping[str, Any]
    reason: str


def build_ieee_browser_payload(
    request: IeeeBrowserPayloadRequest,
    source: IeeeBrowserPayloadSource,
) -> RawFulltextPayload:
    context = request.context
    landing_attempt = request.landing_attempt
    context.raise_if_cancelled()
    extraction = ieee_html._extract_ieee_html(
        source.html_text,
        source.source_url,
        metadata=landing_attempt.merged_metadata,
        context=context,
    )
    diagnostics = HtmlQualityAssessor("ieee").assess(
        extraction.markdown_text,
        landing_attempt.merged_metadata,
        html_text=extraction.html_text,
        title=str(landing_attempt.merged_metadata.get("title") or ""),
        requested_url=source.requested_url,
        final_url=source.source_url,
        response_status=source.response_status,
        section_hints=extraction.section_hints,
    )
    if not diagnostics.accepted:
        raise BrowserRuntimeFailure(
            "browser_html_quality_failed",
            availability_failure_message(diagnostics),
            details={
                "stage": "quality",
                "availability_diagnostics": diagnostics.to_dict(),
            },
        )
    content_type = header_value(source.response_headers, "content-type", "text/html")
    return build_provider_payload(
        provider=request.provider_name,
        route_kind="html",
        route_name="browser_html",
        source_url=source.source_url,
        content_type=content_type,
        body=extraction.html_text.encode("utf-8"),
        markdown_text=extraction.markdown_text,
        merged_metadata=landing_attempt.merged_metadata,
        diagnostics={
            "availability_diagnostics": diagnostics.to_dict(),
            "browser_html": {
                **dict(source.browser_diagnostics),
                "document_url": redact_url_for_diagnostics(request.document_url),
                "rest_url": redact_url_for_diagnostics(request.rest_url),
                "response_status": source.response_status,
                "direct_html_failure": _provider_failure_diagnostics(
                    request.direct_html_failure
                ),
            },
            "extraction": {
                "abstract_sections": extraction.abstract_sections,
                "section_hints": extraction.section_hints,
                "marker_counts": extraction.marker_counts,
            },
        },
        reason=source.reason,
        fetcher="camoufox_ieee_html",
        browser_context_seed=dict(source.browser_context_seed),
        extracted_assets=request.extraction_assets(extraction, landing_attempt),
        trace_markers=[
            fulltext_marker("ieee", "fail", route="html"),
            fulltext_marker("ieee", "ok", route="browser_html"),
            fulltext_marker("ieee", "ok", route="html"),
        ],
    )
