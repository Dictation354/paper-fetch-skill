"""Internal HTML extraction helpers for provider browser workflows."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, Callable, Mapping

from ..config import build_user_agent
from ..extraction.html.signals import SciencePnasHtmlFailure, detect_html_block, summarize_html
from ..metadata_types import ProviderMetadata
from ..models import AssetProfile
from ..runtime import RuntimeContext
from ..tracing import trace_from_markers
from ..utils import normalize_text
from .browser_workflow_fetchers import _normalized_response_headers
from ._flaresolverr import (
    DEFAULT_FLARESOLVERR_WAIT_SECONDS,
    DEFAULT_FLARESOLVERR_WARM_WAIT_SECONDS,
    FetchedPublisherHtml,
    FlareSolverrFailure,
    fetch_html_with_flaresolverr,
)
from .science_pnas import (
    extract_browser_workflow_asset_html_scopes,
    extract_science_pnas_markdown,
    rewrite_inline_figure_links,
)
from .base import ProviderContent, RawFulltextPayload
from ..extraction.html.assets import extract_scoped_html_assets

logger = logging.getLogger("paper_fetch.providers.browser_workflow")

if TYPE_CHECKING:
    from .browser_workflow import BrowserWorkflowClient

_DIRECT_PLAYWRIGHT_HTML_TIMEOUT_MS = 15000
_FAST_FLARESOLVERR_HTML_WAIT_SECONDS = 0
_FAST_FLARESOLVERR_HTML_WARM_WAIT_SECONDS = 0
_DIRECT_PLAYWRIGHT_HTML_BLOCKED_RESOURCE_TYPES = {"image", "font", "stylesheet", "media"}
_FAST_FLARESOLVERR_RETRY_KINDS = {
    "cloudflare_challenge",
    "publisher_access_denied",
    "publisher_paywall",
    "redirected_to_abstract",
    "abstract_only",
    "insufficient_body",
    "structured_article_not_fulltext",
    "structured_missing_body_sections",
}

__all__ = [
    "_DIRECT_PLAYWRIGHT_HTML_TIMEOUT_MS",
    "_FAST_FLARESOLVERR_HTML_WAIT_SECONDS",
    "_FAST_FLARESOLVERR_HTML_WARM_WAIT_SECONDS",
    "_browser_workflow_html_payload",
    "_cached_browser_workflow_assets",
    "_cached_browser_workflow_markdown",
    "_fetch_flaresolverr_html_payload",
    "_fetch_flaresolverr_html_payload_with_fast_path",
    "extract_browser_workflow_asset_html_scopes",
    "extract_science_pnas_markdown",
    "fetch_html_with_direct_playwright",
    "rewrite_inline_figure_links",
]

def _cached_browser_workflow_markdown(
    client: "BrowserWorkflowClient",
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
            metadata=metadata,
        ),
        copy_value=True,
    )
    return str(markdown_text or ""), dict(extraction or {})


def _cached_browser_workflow_assets(
    client: "BrowserWorkflowClient",
    html_text: str,
    source_url: str,
    *,
    asset_profile: AssetProfile,
    context: RuntimeContext,
    scoped_asset_extractor: Callable[..., list[dict[str, Any]]] = extract_scoped_html_assets,
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
        body_asset_html, supplementary_asset_html = extract_browser_workflow_asset_html_scopes(
            html_text,
            source_url,
            client.name,
        )
        return scoped_asset_extractor(
            body_asset_html,
            source_url,
            asset_profile=asset_profile,
            supplementary_html_text=supplementary_asset_html,
        )

    return context.get_or_set_parse_cache(key, extract_assets, copy_value=True)


def _response_headers(response: Any) -> dict[str, str]:
    if response is None:
        return {}
    try:
        return _normalized_response_headers(response.all_headers())
    except Exception:
        return _normalized_response_headers(getattr(response, "headers", {}) or {})


def _response_status(response: Any) -> int | None:
    if response is None:
        return None
    try:
        return int(getattr(response, "status", 0) or 0) or None
    except (TypeError, ValueError):
        return None


def _direct_playwright_browser_context_seed(context: Any, *, final_url: str, user_agent: str) -> dict[str, Any]:
    try:
        cookies = context.cookies()
    except Exception:
        cookies = []
    return {
        "browser_cookies": list(cookies or []),
        "browser_user_agent": normalize_text(user_agent) or None,
        "browser_final_url": final_url,
    }


def fetch_html_with_direct_playwright(
    candidate_urls: list[str],
    *,
    publisher: str,
    user_agent: str,
    headless: bool = True,
    timeout_ms: int = _DIRECT_PLAYWRIGHT_HTML_TIMEOUT_MS,
    context: RuntimeContext | None = None,
) -> FetchedPublisherHtml:
    if not candidate_urls:
        raise SciencePnasHtmlFailure("empty_html_attempts", "No publisher HTML candidates were attempted.")
    try:
        from playwright.sync_api import sync_playwright
    except Exception as exc:
        raise SciencePnasHtmlFailure(
            "playwright_unavailable",
            f"Playwright is not available for direct {publisher} HTML preflight: {exc}",
        ) from exc

    last_failure: SciencePnasHtmlFailure | None = None
    manager = None
    browser = None
    browser_context = None
    page = None
    try:
        context_kwargs = {
            "user_agent": normalize_text(user_agent) or build_user_agent({}),
            "locale": "en-US",
            "viewport": {"width": 1440, "height": 1600},
        }
        if context is not None:
            browser_context = context.new_playwright_context(headless=headless, **context_kwargs)
        else:
            manager = sync_playwright().start()
            browser = manager.chromium.launch(headless=headless)
            browser_context = browser.new_context(**context_kwargs)
        page = browser_context.new_page()

        def route_handler(route: Any) -> None:
            try:
                resource_type = normalize_text(str(route.request.resource_type or "")).lower()
                if resource_type in _DIRECT_PLAYWRIGHT_HTML_BLOCKED_RESOURCE_TYPES:
                    route.abort()
                    return
                route.continue_()
            except Exception:
                try:
                    route.continue_()
                except Exception:
                    pass

        try:
            page.route("**/*", route_handler)
        except Exception:
            pass

        for url in candidate_urls:
            normalized_url = normalize_text(url)
            if not normalized_url:
                continue
            try:
                response = page.goto(normalized_url, wait_until="domcontentloaded", timeout=timeout_ms)
                final_url = normalize_text(str(getattr(page, "url", "") or "")) or normalized_url
                html_text = page.content()
                title = normalize_text(str(page.title() or "")) or None
            except Exception as exc:
                last_failure = SciencePnasHtmlFailure(
                    "playwright_direct_failed",
                    normalize_text(str(exc)) or f"Direct {publisher} Playwright HTML preflight failed.",
                )
                continue

            status = _response_status(response)
            headers = _response_headers(response)
            summary = summarize_html(html_text)
            detected = detect_html_block(title or "", summary, status)
            if detected is not None:
                last_failure = detected
                continue
            if not normalize_text(html_text):
                last_failure = SciencePnasHtmlFailure(
                    "empty_html_response",
                    f"Direct {publisher} Playwright HTML preflight returned empty HTML.",
                )
                continue
            return FetchedPublisherHtml(
                source_url=normalized_url,
                final_url=final_url,
                html=html_text,
                response_status=status,
                response_headers=headers,
                title=title,
                summary=summary,
                browser_context_seed=_direct_playwright_browser_context_seed(
                    browser_context,
                    final_url=final_url,
                    user_agent=normalize_text(user_agent) or build_user_agent({}),
                ),
            )
    finally:
        for value in (page, browser_context, browser):
            if value is None:
                continue
            try:
                value.close()
            except Exception:
                pass
        if manager is not None:
            try:
                manager.stop()
            except Exception:
                pass

    if last_failure is not None:
        raise last_failure
    raise SciencePnasHtmlFailure("empty_html_attempts", "No publisher HTML candidates were attempted.")


def _browser_workflow_html_payload(
    client: "BrowserWorkflowClient",
    html_result: FetchedPublisherHtml,
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
        trace=trace_from_markers([f"fulltext:{client.name}_html_ok"]),
        needs_local_copy=False,
    )


def _fetch_flaresolverr_html_payload(
    client: "BrowserWorkflowClient",
    html_candidates: list[str],
    *,
    runtime,
    metadata: ProviderMetadata,
    context: RuntimeContext,
    warnings: list[str] | None = None,
    html_fetcher: Callable[..., FetchedPublisherHtml] = fetch_html_with_flaresolverr,
    disable_media: bool = False,
    wait_seconds: int = DEFAULT_FLARESOLVERR_WAIT_SECONDS,
    warm_wait_seconds: int = DEFAULT_FLARESOLVERR_WARM_WAIT_SECONDS,
) -> tuple[FetchedPublisherHtml, RawFulltextPayload]:
    html_result = html_fetcher(
        html_candidates,
        publisher=client.name,
        config=runtime,
        wait_seconds=wait_seconds,
        warm_wait_seconds=warm_wait_seconds,
        disable_media=disable_media,
    )
    markdown_text, extraction = _cached_browser_workflow_markdown(
        client,
        html_result.html,
        html_result.final_url,
        metadata=metadata,
        context=context,
    )
    return html_result, _browser_workflow_html_payload(
        client,
        html_result,
        markdown_text=markdown_text,
        extraction=extraction,
        fetcher="flaresolverr",
        warnings=warnings,
    )


def _should_retry_fast_flaresolverr_failure(exc: Exception) -> bool:
    if isinstance(exc, FlareSolverrFailure):
        return exc.kind in _FAST_FLARESOLVERR_RETRY_KINDS
    if isinstance(exc, SciencePnasHtmlFailure):
        return True
    return False


def _fetch_flaresolverr_html_payload_with_fast_path(
    client: "BrowserWorkflowClient",
    html_candidates: list[str],
    *,
    runtime,
    metadata: ProviderMetadata,
    context: RuntimeContext,
    warnings: list[str] | None = None,
    html_fetcher: Callable[..., FetchedPublisherHtml] = fetch_html_with_flaresolverr,
) -> tuple[FetchedPublisherHtml, RawFulltextPayload]:
    try:
        return _fetch_flaresolverr_html_payload(
            client,
            html_candidates,
            runtime=runtime,
            metadata=metadata,
            context=context,
            warnings=warnings,
            html_fetcher=html_fetcher,
            disable_media=True,
            wait_seconds=_FAST_FLARESOLVERR_HTML_WAIT_SECONDS,
            warm_wait_seconds=_FAST_FLARESOLVERR_HTML_WARM_WAIT_SECONDS,
        )
    except (FlareSolverrFailure, SciencePnasHtmlFailure) as exc:
        if not _should_retry_fast_flaresolverr_failure(exc):
            raise
        logger.debug(
            "browser_workflow_flaresolverr_fast_path provider=%s action=fallback reason=%s message=%s",
            client.name,
            getattr(exc, "kind", None) or getattr(exc, "reason", None) or exc.__class__.__name__,
            getattr(exc, "message", None) or normalize_text(str(exc)),
        )

    return _fetch_flaresolverr_html_payload(
        client,
        html_candidates,
        runtime=runtime,
        metadata=metadata,
        context=context,
        warnings=warnings,
        html_fetcher=html_fetcher,
        disable_media=False,
        wait_seconds=DEFAULT_FLARESOLVERR_WAIT_SECONDS,
        warm_wait_seconds=DEFAULT_FLARESOLVERR_WARM_WAIT_SECONDS,
    )
