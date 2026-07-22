"""Internal HTML extraction helpers for provider browser workflows."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, cast
from collections.abc import Callable, Mapping

from ...extraction.html.assets import extract_scoped_html_assets
from ...extraction.html.signals import HtmlExtractionFailure
from ...metadata.types import ProviderMetadata
from ...models import AssetProfile
from ...quality.reason_codes import (
    ABSTRACT_ONLY,
    CLOUDFLARE_CHALLENGE,
    INSUFFICIENT_BODY,
    PUBLISHER_ACCESS_DENIED,
    PUBLISHER_PAYWALL,
    REDIRECTED_TO_ABSTRACT,
    STRUCTURED_ARTICLE_NOT_FULLTEXT,
    STRUCTURED_MISSING_BODY_SECTIONS,
)
from ...runtime import RuntimeContext
from ...tracing import fulltext_marker, trace_from_markers
from ...utils import normalize_text
from ..browser_runtime import (
    BrowserFetchedHtml,
    BrowserRuntimeConfig,
    BrowserRuntimeFailure,
)
from ..browser_runtime.api import (
    DEFAULT_BROWSER_RUNTIME_WAIT_SECONDS,
    DEFAULT_BROWSER_RUNTIME_WARM_WAIT_SECONDS,
    fetch_html_with_browser,
    load_runtime_config,
)
from ..atypon_browser_workflow import (
    extract_browser_workflow_asset_html_scopes,
    extract_atypon_browser_workflow_markdown,
    rewrite_inline_figure_links,
)
from ..base import ProviderContent, RawFulltextPayload

logger = logging.getLogger("paper_fetch.providers.browser_workflow")

if TYPE_CHECKING:
    from .client import BrowserWorkflowClient

_FAST_BROWSER_HTML_TIMEOUT_MS = 15000
_FAST_BROWSER_HTML_WAIT_SECONDS = 0
_FAST_BROWSER_HTML_WARM_WAIT_SECONDS = 0
_FAST_BROWSER_HTML_RETRY_KINDS = {
    CLOUDFLARE_CHALLENGE,
    PUBLISHER_ACCESS_DENIED,
    PUBLISHER_PAYWALL,
    REDIRECTED_TO_ABSTRACT,
    ABSTRACT_ONLY,
    INSUFFICIENT_BODY,
    STRUCTURED_ARTICLE_NOT_FULLTEXT,
    STRUCTURED_MISSING_BODY_SECTIONS,
}

__all__ = [
    "_FAST_BROWSER_HTML_RETRY_KINDS",
    "_FAST_BROWSER_HTML_TIMEOUT_MS",
    "_FAST_BROWSER_HTML_WAIT_SECONDS",
    "_FAST_BROWSER_HTML_WARM_WAIT_SECONDS",
    "_browser_workflow_html_payload",
    "_cached_browser_workflow_assets",
    "_cached_browser_workflow_markdown",
    "_fetch_browser_html_payload",
    "_fetch_browser_html_payload_with_fast_path",
    "extract_atypon_browser_workflow_markdown",
    "extract_browser_workflow_asset_html_scopes",
    "fetch_html_with_fast_browser",
    "rewrite_inline_figure_links",
]


def _cached_browser_workflow_markdown(
    client: BrowserWorkflowClient,
    html_text: str,
    final_url: str,
    *,
    metadata: ProviderMetadata | Mapping[str, Any],
    context: RuntimeContext,
) -> tuple[str, dict[str, Any]]:
    key = context.build_parse_cache_key(
        provider=client.name,
        role="browser_workflow_markdown",
        source=final_url,
        body=html_text,
        parser="BeautifulSoup:browser_workflow",
        config={
            "publisher": client.name,
            "doi": normalize_text(str(metadata.get("doi") or "")),
            "title": normalize_text(str(metadata.get("title") or "")),
        },
    )
    markdown_text, extraction = context.get_or_set_parse_cache(
        key,
        lambda: client.extract_markdown(
            html_text,
            final_url,
            metadata=cast(ProviderMetadata, metadata),
        ),
        copy_value=True,
    )
    return str(markdown_text or ""), dict(extraction or {})


def _cached_browser_workflow_assets(
    client: BrowserWorkflowClient,
    html_text: str,
    source_url: str,
    *,
    asset_profile: AssetProfile,
    context: RuntimeContext,
    scoped_asset_extractor: Callable[
        ..., list[dict[str, Any]]
    ] = extract_scoped_html_assets,
) -> list[dict[str, Any]]:
    key = context.build_parse_cache_key(
        provider=client.name,
        role="browser_workflow_assets",
        source=source_url,
        body=html_text,
        parser="BeautifulSoup:browser_workflow_assets",
        config={"publisher": client.name, "asset_profile": asset_profile},
    )

    def extract_assets() -> list[dict[str, Any]]:
        body_asset_html, supplementary_asset_html = (
            extract_browser_workflow_asset_html_scopes(
                html_text,
                source_url,
                client.name,
            )
        )
        return scoped_asset_extractor(
            body_asset_html,
            source_url,
            asset_profile=asset_profile,
            supplementary_html_text=supplementary_asset_html,
        )

    return context.get_or_set_parse_cache(key, extract_assets, copy_value=True)


def fetch_html_with_fast_browser(
    candidate_urls: list[str],
    *,
    publisher: str,
    user_agent: str | None = None,
    headless: bool = True,
    timeout_ms: int = _FAST_BROWSER_HTML_TIMEOUT_MS,
    context: RuntimeContext | None = None,
    browser_config: Any | None = None,
) -> BrowserFetchedHtml:
    config = (
        browser_config
        if isinstance(browser_config, BrowserRuntimeConfig)
        else load_runtime_config(
            context.env if context is not None and context.env is not None else {},
            provider=publisher,
            doi="fast-browser",
        )
    )
    if not isinstance(config, BrowserRuntimeConfig):
        raise HtmlExtractionFailure(
            "browser_runtime_unavailable",
            f"Browser runtime is not available for fast {publisher} HTML preflight.",
        )
    user_agent_changed = bool(
        config.backend == "cloakbrowser"
        and normalize_text(user_agent)
        and normalize_text(user_agent) != config.user_agent
    )
    if config.headless != headless or user_agent_changed:
        from dataclasses import replace

        config = replace(
            config,
            headless=headless,
            user_agent=(
                normalize_text(user_agent) or config.user_agent
                if config.backend == "cloakbrowser"
                else None
            ),
            timeout_ms=timeout_ms or config.timeout_ms,
        )
    return fetch_html_with_browser(
        candidate_urls,
        publisher=publisher,
        config=config,
        wait_seconds=_FAST_BROWSER_HTML_WAIT_SECONDS,
        warm_wait_seconds=_FAST_BROWSER_HTML_WARM_WAIT_SECONDS,
        max_timeout_ms=timeout_ms,
        disable_media=True,
        runtime_context=context,
    )


fetch_html_with_fast_browser.paper_fetch_html_fetcher_name = "selected_browser_fast"  # type: ignore[attr-defined]


def _browser_workflow_html_payload(
    client: BrowserWorkflowClient,
    html_result: BrowserFetchedHtml,
    *,
    markdown_text: str,
    extraction: Mapping[str, Any],
    fetcher: str,
    warnings: list[str] | None = None,
) -> RawFulltextPayload:
    html_bytes = html_result.html.encode("utf-8")
    diagnostics = {
        "extraction": dict(extraction),
        "availability_diagnostics": extraction.get("availability_diagnostics"),
        "html_fetcher": fetcher,
    }
    if isinstance(html_result.diagnostics, Mapping):
        diagnostics.update(dict(html_result.diagnostics))
    return RawFulltextPayload(
        provider=client.name,
        source_url=html_result.final_url,
        content_type="text/html",
        body=html_bytes,
        content=ProviderContent(
            route_kind="html",
            source_url=html_result.final_url,
            content_type="text/html",
            body=html_bytes,
            markdown_text=markdown_text,
            diagnostics=diagnostics,
            fetcher=fetcher,
            browser_context_seed=dict(html_result.browser_context_seed or {}),
        ),
        warnings=list(warnings or []),
        trace=trace_from_markers([fulltext_marker(client.name, "ok", route="html")]),
        needs_local_copy=False,
    )


def _fetch_browser_html_payload(
    client: BrowserWorkflowClient,
    html_candidates: list[str],
    *,
    runtime,
    metadata: ProviderMetadata,
    context: RuntimeContext,
    warnings: list[str] | None = None,
    html_fetcher: Callable[..., BrowserFetchedHtml] = fetch_html_with_browser,
    disable_media: bool = False,
    wait_seconds: int = DEFAULT_BROWSER_RUNTIME_WAIT_SECONDS,
    warm_wait_seconds: int = DEFAULT_BROWSER_RUNTIME_WARM_WAIT_SECONDS,
) -> tuple[BrowserFetchedHtml, RawFulltextPayload]:
    html_result = html_fetcher(
        html_candidates,
        publisher=client.name,
        config=runtime,
        wait_seconds=wait_seconds,
        warm_wait_seconds=warm_wait_seconds,
        disable_media=disable_media,
        runtime_context=context,
    )
    try:
        markdown_text, extraction = _cached_browser_workflow_markdown(
            client,
            html_result.html,
            html_result.final_url,
            metadata=metadata,
            context=context,
        )
    except HtmlExtractionFailure as exc:
        exc.html_result = html_result
        raise
    fetcher_attr = getattr(html_fetcher, "paper_fetch_html_fetcher_name", None)
    runtime_backend_value = runtime.backend
    runtime_backend = normalize_text(runtime_backend_value)
    if not runtime_backend:
        raise RuntimeError("BrowserRuntimeConfig.backend must not be empty.")
    fetcher_name = runtime_backend
    if isinstance(fetcher_attr, str) and normalize_text(fetcher_attr).endswith("_fast"):
        fetcher_name = f"{runtime_backend}_fast"
    return html_result, _browser_workflow_html_payload(
        client,
        html_result,
        markdown_text=markdown_text,
        extraction=extraction,
        fetcher=fetcher_name,
        warnings=warnings,
    )


def _should_retry_fast_browser_failure(exc: Exception) -> bool:
    if isinstance(exc, BrowserRuntimeFailure):
        return exc.kind in _FAST_BROWSER_HTML_RETRY_KINDS
    if isinstance(exc, HtmlExtractionFailure):
        return True
    return False


def _fetch_browser_html_payload_with_fast_path(
    client: BrowserWorkflowClient,
    html_candidates: list[str],
    *,
    runtime,
    metadata: ProviderMetadata,
    context: RuntimeContext,
    warnings: list[str] | None = None,
    html_fetcher: Callable[..., BrowserFetchedHtml] = fetch_html_with_browser,
) -> tuple[BrowserFetchedHtml, RawFulltextPayload]:
    try:
        return _fetch_browser_html_payload(
            client,
            html_candidates,
            runtime=runtime,
            metadata=metadata,
            context=context,
            warnings=warnings,
            html_fetcher=html_fetcher,
            disable_media=True,
            wait_seconds=_FAST_BROWSER_HTML_WAIT_SECONDS,
            warm_wait_seconds=_FAST_BROWSER_HTML_WARM_WAIT_SECONDS,
        )
    except (BrowserRuntimeFailure, HtmlExtractionFailure) as exc:
        if not _should_retry_fast_browser_failure(exc):
            raise
        logger.debug(
            "browser_workflow_fast_browser_path provider=%s action=fallback reason=%s message=%s",
            client.name,
            getattr(exc, "kind", None)
            or getattr(exc, "reason", None)
            or exc.__class__.__name__,
            getattr(exc, "message", None) or normalize_text(str(exc)),
        )

    return _fetch_browser_html_payload(
        client,
        html_candidates,
        runtime=runtime,
        metadata=metadata,
        context=context,
        warnings=warnings,
        html_fetcher=html_fetcher,
        disable_media=False,
        wait_seconds=DEFAULT_BROWSER_RUNTIME_WAIT_SECONDS,
        warm_wait_seconds=DEFAULT_BROWSER_RUNTIME_WARM_WAIT_SECONDS,
    )
