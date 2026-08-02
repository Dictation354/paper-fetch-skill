"""Internal HTML extraction helpers for provider browser workflows."""

from __future__ import annotations

import logging
from dataclasses import dataclass, replace
import time
from typing import TYPE_CHECKING, Any, cast
from collections.abc import Callable, Mapping

from ...extraction.html.assets import extract_scoped_html_assets
from ...extraction.html.signals import (
    HtmlExtractionFailure,
    html_failure_message,
    summarize_html,
)
from ...http import diagnostic_url_payload
from ...metadata.types import ProviderMetadata
from ...models import AssetProfile
from ...quality.reason_codes import (
    ABSTRACT_ONLY,
    AWS_WAF_CHALLENGE,
    CLOUDFLARE_CHALLENGE,
    EMPTY_ARTICLE_SHELL,
    INSUFFICIENT_BODY,
    PUBLISHER_ACCESS_DENIED,
    PUBLISHER_PAYWALL,
    REDIRECTED_TO_ABSTRACT,
    STRUCTURED_ARTICLE_NOT_FULLTEXT,
    STRUCTURED_MISSING_BODY_SECTIONS,
)
from ...runtime import RuntimeContext
from ...page_diagnostics import (
    PageDiagnosticRequest,
    capture_page_diagnostic,
    is_empty_article_shell,
)
from ...tracing import fulltext_marker, trace_from_markers
from ...utils import normalize_text
from ..browser_runtime import (
    BrowserFetchedHtml,
    BrowserRuntimeConfig,
    BrowserRuntimeFailure,
    merge_browser_context_seeds,
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
    AWS_WAF_CHALLENGE,
    CLOUDFLARE_CHALLENGE,
    PUBLISHER_ACCESS_DENIED,
    PUBLISHER_PAYWALL,
    REDIRECTED_TO_ABSTRACT,
    ABSTRACT_ONLY,
    INSUFFICIENT_BODY,
    STRUCTURED_ARTICLE_NOT_FULLTEXT,
    STRUCTURED_MISSING_BODY_SECTIONS,
}


@dataclass(frozen=True)
class BrowserHtmlFetchPolicy:
    disable_media: bool = False
    wait_seconds: int = DEFAULT_BROWSER_RUNTIME_WAIT_SECONDS
    warm_wait_seconds: int = DEFAULT_BROWSER_RUNTIME_WARM_WAIT_SECONDS
    max_timeout_ms: int | None = None
    attempt: int = 1


def _commit_accepted_storage_state(
    html_result: BrowserFetchedHtml,
    runtime: BrowserRuntimeConfig,
    *,
    context: RuntimeContext | None = None,
) -> tuple[BrowserFetchedHtml, list[str]]:
    """Commit staged state only after provider HTML extraction succeeded."""

    stage = html_result.staged_storage_state
    diagnostics = dict(html_result.diagnostics or {})
    runtime_trace = (
        dict(diagnostics.get("browser_runtime_trace") or {})
        if isinstance(diagnostics.get("browser_runtime_trace"), Mapping)
        else {}
    )
    if stage is not None:
        from ..browser_runtime.paths import commit_staged_storage_state

        save_result = commit_staged_storage_state(
            stage,
            runtime,
            runtime_context=context,
        )
        runtime_trace["storage_state_save"] = save_result
        diagnostics["browser_runtime_trace"] = runtime_trace
        warnings = (
            []
            if save_result.get("saved")
            else [
                "Provider HTML was accepted, but the staged browser storage state "
                f"could not be saved ({save_result.get('reason') or 'save_failed'})."
            ]
        )
        return (
            replace(
                html_result,
                diagnostics=diagnostics,
                staged_storage_state=None,
            ),
            warnings,
        )

    storage_result = runtime_trace.get("storage_state_save")
    if (
        runtime.persist_storage_state
        and isinstance(storage_result, Mapping)
        and not storage_result.get("saved")
    ):
        return (
            replace(html_result, staged_storage_state=None),
            [
                "Provider HTML was accepted, but browser storage state was not "
                f"staged ({storage_result.get('reason') or 'stage_failed'})."
            ],
        )
    return replace(html_result, staged_storage_state=None), []


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
    if config.headless != headless:
        from dataclasses import replace

        config = replace(
            config,
            headless=headless,
            user_agent=None,
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
    policy: BrowserHtmlFetchPolicy = BrowserHtmlFetchPolicy(),
    browser_context_seed: Mapping[str, Any] | None = None,
    prior_attempts: list[Mapping[str, Any]] | None = None,
) -> tuple[BrowserFetchedHtml, RawFulltextPayload]:
    configured_timeout_ms = max(1, int(runtime.timeout_ms))
    context.initialize_deadline(configured_timeout_ms / 1000.0)
    operation_cap_ms = min(
        configured_timeout_ms,
        policy.max_timeout_ms
        if policy.max_timeout_ms is not None
        else configured_timeout_ms,
    )
    try:
        operation_timeout_ms = context.remaining_timeout_ms(operation_cap_ms)
    except TimeoutError as exc:
        raise BrowserRuntimeFailure(
            "browser_connect_timeout",
            f"{client.name} browser request deadline was exhausted.",
            details={
                "timeout_budget_ms": configured_timeout_ms,
                "remaining_ms": 0,
            },
        ) from exc
    operation_started_at = time.monotonic()
    fetch_kwargs: dict[str, Any] = {
        "publisher": client.name,
        "config": runtime,
        "wait_seconds": policy.wait_seconds,
        "warm_wait_seconds": policy.warm_wait_seconds,
        "max_timeout_ms": operation_timeout_ms,
        "disable_media": policy.disable_media,
        "runtime_context": context,
    }
    profile = client.require_profile()
    if profile.html_readiness is not None:
        fetch_kwargs["readiness"] = profile.html_readiness
    if browser_context_seed and browser_context_seed.get("browser_cookies"):
        fetch_kwargs["browser_context_seed"] = browser_context_seed
    attempt_history = [dict(item) for item in list(prior_attempts or [])]
    try:
        html_result = html_fetcher(
            html_candidates,
            **fetch_kwargs,
        )
    except BrowserRuntimeFailure as exc:
        failure_details = dict(exc.details or {})
        attempt_history.append(
            {
                "attempt": policy.attempt,
                "result": "browser_failure",
                "failure_code": exc.kind,
            }
        )
        failure_details["html_attempts"] = attempt_history
        exc.details = failure_details
        exc.browser_context_seed = {
            key: value
            for key, value in merge_browser_context_seeds(
                browser_context_seed,
                exc.browser_context_seed,
            ).items()
            if value is not None
        }
        raise
    result_diagnostics = dict(html_result.diagnostics or {})
    result_diagnostics["deadline"] = {
        "timeout_budget_ms": configured_timeout_ms,
        "operation_timeout_ms": operation_timeout_ms,
        "elapsed_ms": round((time.monotonic() - operation_started_at) * 1000, 3),
        "remaining_ms": max(
            0,
            int(context.remaining_seconds() * 1000),
        ),
    }
    attempt_record: dict[str, Any] = {
        "attempt": policy.attempt,
        "result": "html_received",
        "response_status": html_result.response_status,
        "final_url": diagnostic_url_payload(html_result.final_url),
    }
    result_diagnostics["html_attempts"] = [*attempt_history, attempt_record]
    html_result = replace(html_result, diagnostics=result_diagnostics)
    try:
        markdown_text, extraction = _cached_browser_workflow_markdown(
            client,
            html_result.html,
            html_result.final_url,
            metadata=metadata,
            context=context,
        )
    except HtmlExtractionFailure as exc:
        if exc.reason == "article_container_not_found" and is_empty_article_shell(
            html_result.html,
            response_status=html_result.response_status,
        ):
            exc.reason = EMPTY_ARTICLE_SHELL
            exc.message = html_failure_message(EMPTY_ARTICLE_SHELL)
        attempt_record["result"] = "extraction_failure"
        attempt_record["failure_code"] = exc.reason
        page_details = dict(html_result.diagnostics or {})
        page_details["html_attempts"] = [*attempt_history, attempt_record]
        page_diagnostic = capture_page_diagnostic(
            context,
            PageDiagnosticRequest(
                provider=client.name,
                route="html",
                attempt=policy.attempt,
                failure_code=exc.reason,
                stage="html_extraction",
                html_text=html_result.html,
                doi=normalize_text(str(metadata.get("doi") or "")) or None,
                target_url=html_candidates[0] if html_candidates else None,
                final_url=html_result.final_url,
                backend=normalize_text(runtime.backend) or None,
                response_status=html_result.response_status,
                title=html_result.title,
                summary=summarize_html(html_result.html),
                details=page_details,
            ),
        )
        page_details["page_diagnostic"] = page_diagnostic
        if page_diagnostic.get("diagnostic_path"):
            page_details["diagnostic_path"] = page_diagnostic["diagnostic_path"]
        exc.details = page_details
        exc.html_result = html_result
        raise
    attempt_record["result"] = "success"
    result_diagnostics["html_attempts"] = [*attempt_history, attempt_record]
    html_result = replace(html_result, diagnostics=result_diagnostics)
    html_result, storage_warnings = _commit_accepted_storage_state(
        html_result,
        runtime,
        context=context,
    )
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
        warnings=[*list(warnings or []), *storage_warnings],
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
    retry_seed: dict[str, Any] = {}
    prior_attempts: list[Mapping[str, Any]] = []
    try:
        return _fetch_browser_html_payload(
            client,
            html_candidates,
            runtime=runtime,
            metadata=metadata,
            context=context,
            warnings=warnings,
            html_fetcher=html_fetcher,
            policy=BrowserHtmlFetchPolicy(
                disable_media=True,
                wait_seconds=_FAST_BROWSER_HTML_WAIT_SECONDS,
                warm_wait_seconds=_FAST_BROWSER_HTML_WARM_WAIT_SECONDS,
                max_timeout_ms=_FAST_BROWSER_HTML_TIMEOUT_MS,
                attempt=1,
            ),
        )
    except (BrowserRuntimeFailure, HtmlExtractionFailure) as exc:
        if not _should_retry_fast_browser_failure(exc):
            raise
        if isinstance(exc, BrowserRuntimeFailure):
            retry_seed = dict(exc.browser_context_seed)
            failure_details = dict(exc.details or {})
        else:
            extraction_html_result = getattr(exc, "html_result", None)
            retry_seed = dict(
                getattr(extraction_html_result, "browser_context_seed", None) or {}
            )
            failure_details = dict(getattr(exc, "details", None) or {})
        recorded_attempts = failure_details.get("html_attempts")
        if isinstance(recorded_attempts, list):
            prior_attempts = [
                dict(item) for item in recorded_attempts if isinstance(item, Mapping)
            ]
        if not prior_attempts:
            prior_attempts = [
                {
                    "attempt": 1,
                    "result": "failure",
                    "failure_code": getattr(exc, "kind", None)
                    or getattr(exc, "reason", None)
                    or exc.__class__.__name__,
                }
            ]
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
        policy=BrowserHtmlFetchPolicy(attempt=2),
        browser_context_seed=retry_seed,
        prior_attempts=prior_attempts,
    )
