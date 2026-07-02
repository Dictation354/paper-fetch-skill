"""Internal HTML extraction helpers for provider browser workflows."""

from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast
from collections.abc import Callable, Mapping

from ...config import (
    CLOAKBROWSER_BINARY_PATH_ENV_VAR,
    CLOAKBROWSER_CDP_ENDPOINT_ENV_VAR,
    CLOAKBROWSER_PROFILE_DIR_ENV_VAR,
    CLOAKBROWSER_USER_DATA_DIR_ENV_VAR,
    build_runtime_env,
)
from ...extraction.html.assets import extract_scoped_html_assets
from ...extraction.html.signals import (
    HtmlExtractionFailure,
    detect_html_block,
    summarize_html,
)
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
from ...runtime_browser import (
    BrowserContextManager,
    browser_context_options,
    browser_page_user_agent,
)
from ...tracing import fulltext_marker, trace_from_markers
from ...utils import normalize_text
from .fetchers.context import (
    _browser_response_headers as _response_headers,
    _browser_response_status as _response_status,
)
from .fetchers.readiness import wait_for_atypon_body_dom_ready
from .shared import BROWSER_HTML_BLOCKED_RESOURCE_TYPES, looks_like_abstract_redirect
from ..browser_runtime import (
    BrowserFetchedHtml,
    BrowserRuntimeFailure,
    DEFAULT_BROWSER_RUNTIME_WAIT_SECONDS,
    DEFAULT_BROWSER_RUNTIME_WARM_WAIT_SECONDS,
    fetch_html_with_browser,
)
from ..atypon_browser_workflow import (
    extract_browser_workflow_asset_html_scopes,
    extract_atypon_browser_workflow_markdown,
    rewrite_inline_figure_links,
)
from ..base import ProviderContent, RawFulltextPayload
import contextlib

logger = logging.getLogger("paper_fetch.providers.browser_workflow")

if TYPE_CHECKING:
    from .client import BrowserWorkflowClient

_FAST_BROWSER_HTML_TIMEOUT_MS = 15000
_FAST_BROWSER_HTML_WAIT_SECONDS = 0
_FAST_BROWSER_HTML_WARM_WAIT_SECONDS = 0
_FAST_BROWSER_HTML_BLOCKED_RESOURCE_TYPES = BROWSER_HTML_BLOCKED_RESOURCE_TYPES
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


def _fast_browser_context_seed(
    context: Any, *, final_url: str, user_agent: str | None
) -> dict[str, Any]:
    try:
        cookies = context.cookies()
    except Exception:
        cookies = []
    return {
        "browser_cookies": list(cookies or []),
        "browser_user_agent": normalize_text(user_agent) or None,
        "browser_final_url": final_url,
    }


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
    if not candidate_urls:
        raise HtmlExtractionFailure(
            "empty_html_attempts", "No publisher HTML candidates were attempted."
        )

    last_failure: HtmlExtractionFailure | None = None
    manager = None
    browser_context = None
    page = None
    configured_user_agent = normalize_text(user_agent)
    try:
        context_kwargs = browser_context_options(user_agent=configured_user_agent)
        try:
            if (
                context is not None
                and browser_config is not None
                and isinstance(context, RuntimeContext)
            ):
                browser_context = context.new_browser_context_for_config(
                    headless=headless,
                    binary_path=getattr(browser_config, "binary_path", None),
                    cdp_endpoint=getattr(browser_config, "cdp_endpoint", None),
                    profile_dir=getattr(browser_config, "profile_dir", None),
                    user_data_dir=getattr(browser_config, "user_data_dir", None),
                    **context_kwargs,
                )
            elif context is not None:
                browser_context = context.new_browser_context(
                    headless=headless, **context_kwargs
                )
            else:
                runtime_env = build_runtime_env()
                endpoint = normalize_text(
                    getattr(browser_config, "cdp_endpoint", None)
                ) or normalize_text(runtime_env.get(CLOAKBROWSER_CDP_ENDPOINT_ENV_VAR))
                binary_path = normalize_text(
                    getattr(browser_config, "binary_path", None)
                ) or normalize_text(runtime_env.get(CLOAKBROWSER_BINARY_PATH_ENV_VAR))
                profile_dir = normalize_text(
                    str(getattr(browser_config, "profile_dir", "") or "")
                ) or normalize_text(runtime_env.get(CLOAKBROWSER_PROFILE_DIR_ENV_VAR))
                user_data_dir = normalize_text(
                    str(getattr(browser_config, "user_data_dir", "") or "")
                ) or normalize_text(runtime_env.get(CLOAKBROWSER_USER_DATA_DIR_ENV_VAR))
                manager = BrowserContextManager(
                    binary_path=binary_path or None,
                    cdp_endpoint=endpoint or None,
                    profile_dir=Path(profile_dir).expanduser() if profile_dir else None,
                    user_data_dir=Path(user_data_dir).expanduser()
                    if user_data_dir
                    else None,
                )
                browser_context = manager.new_context(
                    headless=headless, **context_kwargs
                )
        except Exception as exc:
            raise HtmlExtractionFailure(
                "browser_runtime_unavailable",
                f"CDP browser runtime is not available for fast {publisher} HTML preflight: {exc}",
            ) from exc
        page = browser_context.new_page()

        def route_handler(route: Any) -> None:
            try:
                resource_type = normalize_text(
                    str(route.request.resource_type or "")
                ).lower()
                if resource_type in _FAST_BROWSER_HTML_BLOCKED_RESOURCE_TYPES:
                    route.abort()
                    return
                route.continue_()
            except Exception:
                with contextlib.suppress(Exception):
                    route.continue_()

        with contextlib.suppress(Exception):
            page.route("**/*", route_handler)

        for url in candidate_urls:
            normalized_url = normalize_text(url)
            if not normalized_url:
                continue
            try:
                request_started = time.monotonic()
                response = page.goto(
                    normalized_url, wait_until="domcontentloaded", timeout=timeout_ms
                )
                remaining_timeout_seconds = max(
                    0.0,
                    (float(timeout_ms) / 1000.0) - (time.monotonic() - request_started),
                )
                readiness = wait_for_atypon_body_dom_ready(
                    page,
                    publisher,
                    timeout_seconds=min(8.0, remaining_timeout_seconds),
                )
                final_url = (
                    normalize_text(str(getattr(page, "url", "") or ""))
                    or normalized_url
                )
                html_text = page.content()
                title = normalize_text(str(page.title() or "")) or None
            except Exception as exc:
                last_failure = HtmlExtractionFailure(
                    "fast_browser_failed",
                    normalize_text(str(exc))
                    or f"Fast {publisher} browser HTML preflight failed.",
                )
                continue

            if looks_like_abstract_redirect(normalized_url, final_url):
                last_failure = HtmlExtractionFailure(
                    REDIRECTED_TO_ABSTRACT,
                    f"Fast {publisher} browser HTML preflight redirected to an abstract page.",
                )
                continue
            status = _response_status(response)
            headers = _response_headers(response)
            summary = summarize_html(html_text)
            detected = (
                None
                if readiness.attempted and readiness.ready
                else detect_html_block(title or "", summary, status)
            )
            if detected is not None:
                last_failure = detected
                continue
            if not normalize_text(html_text):
                last_failure = HtmlExtractionFailure(
                    "empty_html_response",
                    f"Fast {publisher} browser HTML preflight returned empty HTML.",
                )
                continue
            return BrowserFetchedHtml(
                source_url=normalized_url,
                final_url=final_url,
                html=html_text,
                response_status=status,
                response_headers=headers,
                title=title,
                summary=summary,
                browser_context_seed=_fast_browser_context_seed(
                    browser_context,
                    final_url=final_url,
                    user_agent=configured_user_agent or browser_page_user_agent(page),
                ),
            )
    finally:
        for value in (page, browser_context):
            if value is None:
                continue
            with contextlib.suppress(Exception):
                value.close()
        if manager is not None:
            with contextlib.suppress(Exception):
                manager.close()

    if last_failure is not None:
        raise last_failure
    raise HtmlExtractionFailure(
        "empty_html_attempts", "No publisher HTML candidates were attempted."
    )


fetch_html_with_fast_browser.paper_fetch_html_fetcher_name = "cloakbrowser_fast"  # type: ignore[attr-defined]


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
            diagnostics={
                "extraction": dict(extraction),
                "availability_diagnostics": extraction.get("availability_diagnostics"),
                "html_fetcher": fetcher,
            },
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
    fetcher_name = (
        normalize_text(fetcher_attr)
        if isinstance(fetcher_attr, str)
        else "cloakbrowser"
    )
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
