"""Browser HTML candidate navigation, atomic DOM snapshots, and context warming."""

from __future__ import annotations

import contextlib
import logging
import time
import urllib.parse
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field, replace
from typing import TYPE_CHECKING, Any

from bs4 import BeautifulSoup

from ...browser_runtime_policy import engine_name
from ...extraction.html.signals import (
    HtmlExtractionFailure,
    detect_html_block,
    html_failure_message,
    summarize_html,
    summarize_visible_html,
)
from ...http import RequestCancelledError, diagnostic_url_payload
from ...page_diagnostics import PageDiagnosticRequest, capture_page_diagnostic
from ...provider_catalog import compile_route_execution_policy_for_kind
from ...publisher_identity import extract_doi_from_url, normalize_doi
from ...quality.access_boundary import propagate_paywall, raise_for_paywall
from ...quality.html_availability import choose_parser, extract_page_title
from ...quality.html_signals import looks_like_abstract_redirect
from ...reason_codes import (
    ABSTRACT_ONLY,
    AWS_WAF_CHALLENGE,
    BROWSER_CONTEXT_CREATE_FAILED,
    BROWSER_PAGE_CREATE_FAILED,
    CLOUDFLARE_CHALLENGE,
    PUBLISHER_ACCESS_DENIED,
    PUBLISHER_PAYWALL,
    REDIRECTED_TO_ABSTRACT,
)
from ...utils import normalize_text
from .._atypon_browser_workflow_profiles import publisher_profile
from .._registry import BrowserPagePolicy, provider_bundle
from ..browser_workflow.fetchers.context import (
    _browser_response_headers,
    _browser_response_status,
    _runtime_figure_page_session,
)
from .context import open_browser_context
from .navigation import navigate_page, settle_page_navigation
from .readiness import wait_for_browser_html_readiness
from .seed import (
    browser_context_seed_from_mapping,
    browser_context_seed_from_session,
    filter_browser_cookies_for_url,
    merge_browser_context_seeds,
)
from .telemetry import (
    _bounded_diagnostic_text,
    _diagnostic_event_attr,
    _diagnostic_event_value,
    _install_page_diagnostic_listeners,
    _record_browser_challenge_signal,
    _record_candidate_document_diagnostics,
    _remove_page_diagnostic_listeners,
    browser_page_user_agent,
)
from .types import (
    DEFAULT_BROWSER_RUNTIME_WAIT_SECONDS,
    BrowserFetchedHtml,
    BrowserHtmlFetchOptions,
    BrowserHtmlReadiness,
    BrowserRuntimeConfig,
    BrowserRuntimeFailure,
    BrowserWarmResult,
)

if TYPE_CHECKING:
    from ...runtime import RuntimeContext

logger = logging.getLogger("paper_fetch.providers.browser_runtime")

DEFAULT_BROWSER_HTML_READINESS = BrowserHtmlReadiness()
DEFAULT_BROWSER_HTML_FETCH_OPTIONS = BrowserHtmlFetchOptions()
_HTTP_ACCESS_STATUS_REVIEW_KEY = "http_access_status_review"
_MAIN_CONTEXT_SNAPSHOT_PROVIDERS = frozenset({"pnas", "science", "wiley", "elsevier"})
_MAIN_CONTEXT_HTML_SNAPSHOT_SCRIPT = """
() => ({
  html: (document.doctype ? new XMLSerializer().serializeToString(document.doctype) + '\\n' : '')
    + document.documentElement.outerHTML,
  title: document.title,
  url: location.href,
})
"""
_STABLE_BROWSER_ACCESS_FAILURE_KINDS = frozenset(
    {
        ABSTRACT_ONLY,
        AWS_WAF_CHALLENGE,
        CLOUDFLARE_CHALLENGE,
        PUBLISHER_ACCESS_DENIED,
        PUBLISHER_PAYWALL,
        REDIRECTED_TO_ABSTRACT,
        "iop_captcha_challenge",
        "iop_radware_challenge",
    }
)


def _safe_int(value: Any, *, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _safe_close(value: Any) -> None:
    if value is None:
        return
    with contextlib.suppress(Exception):
        value.close()


def _same_site_navigation(candidate_url: str, final_url: str) -> bool:
    candidate_host = normalize_text(
        urllib.parse.urlsplit(candidate_url).hostname
    ).lower()
    final_host = normalize_text(urllib.parse.urlsplit(final_url).hostname).lower()
    if not candidate_host or not final_host:
        return False
    return bool(
        final_host == candidate_host
        or final_host.endswith(f".{candidate_host}")
        or candidate_host.endswith(f".{final_host}")
    )


def _cookie_state(seed: Mapping[str, Any] | None) -> dict[tuple[str, str, str], str]:
    state: dict[tuple[str, str, str], str] = {}
    for cookie in list((seed or {}).get("browser_cookies") or []):
        if not isinstance(cookie, Mapping):
            continue
        key = (
            normalize_text(str(cookie.get("name") or "")),
            normalize_text(str(cookie.get("domain") or "")).lower(),
            normalize_text(str(cookie.get("path") or "")) or "/",
        )
        if key[0]:
            state[key] = str(cookie.get("value") or "")
    return state


def _cookie_delta(
    before: Mapping[str, Any] | None,
    after: Mapping[str, Any] | None,
) -> dict[str, int]:
    before_state = _cookie_state(before)
    after_state = _cookie_state(after)
    return {
        "added": len(after_state.keys() - before_state.keys()),
        "updated": sum(
            1
            for key in before_state.keys() & after_state.keys()
            if before_state[key] != after_state[key]
        ),
        "removed": len(before_state.keys() - after_state.keys()),
    }


def _build_session_context_seed(
    browser_context: Any,
    *,
    page: Any,
    final_url: str,
    configured_user_agent: str,
    backend_name: str,
) -> dict[str, Any]:
    seed = browser_context_seed_from_session(
        browser_context,
        final_url=final_url,
        user_agent=configured_user_agent or browser_page_user_agent(page),
        backend=backend_name,
    )
    return merge_browser_context_seeds(
        seed,
        {
            "paper_fetch_html_fetcher": backend_name,
            "diagnostics": {
                "browser_backend": backend_name,
                "browser_engine": (
                    engine_name() if backend_name == "byparr" else "camoufox"
                ),
            },
        },
    )


def _navigate_browser_page(page: Any, *, url: str, timeout_ms: int) -> Any:
    return navigate_page(
        page, url, wait_until="commit", timeout=timeout_ms, mode="html"
    )


def _main_context_html_snapshot(
    page: Any, *, runtime_context: RuntimeContext | None = None
) -> tuple[str, str, str] | None:
    """Capture one document synchronously, falling back on a navigation race."""
    if runtime_context is not None:
        runtime_context.raise_if_cancelled()
    try:
        before_url = str(page.url or "")
        raw = page.evaluate(_MAIN_CONTEXT_HTML_SNAPSHOT_SCRIPT)
        if runtime_context is not None:
            runtime_context.raise_if_cancelled()
        if not isinstance(raw, Mapping):
            return None
        html, title, url = (raw.get(key) for key in ("html", "title", "url"))
        if (
            not isinstance(html, str)
            or not html.strip()
            or not isinstance(title, str)
            or not isinstance(url, str)
            or not url.strip()
            or url != before_url
            or url != str(page.url or "")
        ):
            return None
        return html, normalize_text(title), url
    except RequestCancelledError:
        raise
    except Exception:
        return None


def _prepare_provider_browser_page(
    page: Any,
    *,
    publisher: str,
    timeout_ms: int,
    candidate_trace: dict[str, Any],
    runtime_context: RuntimeContext | None = None,
) -> None:
    prepare_browser_page = publisher_profile(publisher).prepare_browser_page
    if prepare_browser_page is None:
        return
    preparation_started = time.monotonic()
    try:
        preparation = prepare_browser_page(
            page,
            timeout_ms=timeout_ms,
            cancel_check=(
                runtime_context.raise_if_cancelled
                if runtime_context is not None
                else None
            ),
        )
        if isinstance(preparation, Mapping):
            candidate_trace["provider_page_preparation"] = dict(preparation)
    except RequestCancelledError:
        raise
    except Exception as exc:
        propagate_paywall(exc)
        candidate_trace["provider_page_preparation"] = {
            "attempted": True,
            "error_type": type(exc).__name__,
        }
    candidate_trace["provider_page_preparation_seconds"] = round(
        time.monotonic() - preparation_started,
        3,
    )


def _browser_html_summary(publisher: str, html_text: str) -> str:
    if normalize_text(publisher).lower() == "ieee":
        return summarize_visible_html(html_text)
    return summarize_html(html_text)


def _browser_page_failure_details(
    *,
    trace: Mapping[str, Any],
    runtime_context: RuntimeContext | None,
    request: PageDiagnosticRequest,
) -> dict[str, Any]:
    details: dict[str, Any] = {
        "trace": dict(trace),
        "stage": request.stage,
        "final_url": diagnostic_url_payload(request.final_url or ""),
        "response_status": request.response_status,
        "title_summary": (request.title or "")[:500] or None,
        "page_summary": (request.summary or "")[:1000] or None,
    }
    if request.failure_code == "aws_waf_challenge":
        details.update({"challenge_provider": "aws_waf"})
    if runtime_context is None:
        return details
    diagnostic = capture_page_diagnostic(runtime_context, request)
    details["failure_diagnostic"] = diagnostic
    diagnostic_path = normalize_text(str(diagnostic.get("diagnostic_path") or ""))
    if diagnostic_path:
        details["diagnostic_path"] = diagnostic_path
    return details


def _lightweight_seed_rejection(
    *,
    status: int | None,
    requested_url: str,
    final_url: str,
    detected: Any | None,
) -> tuple[str, str] | None:
    if status is not None and status >= 400:
        return f"http_{status}", f"Browser warm navigation returned HTTP {status}."
    if not _same_site_navigation(requested_url, final_url):
        return (
            "warm_cross_site_redirect",
            "Browser warm navigation left the provider host.",
        )
    if looks_like_abstract_redirect(requested_url, final_url):
        return (
            REDIRECTED_TO_ABSTRACT,
            "Browser warm navigation redirected to an abstract page.",
        )
    if detected is not None:
        return detected.reason, detected.message
    return None


def _candidate_deadline_failure(
    last_failure: BrowserRuntimeFailure | None,
    *,
    trace: Mapping[str, Any],
) -> BrowserRuntimeFailure:
    timeout_failure = BrowserRuntimeFailure(
        "browser_connect_timeout",
        "Browser HTML request deadline was exhausted before another candidate.",
        details={"trace": dict(trace)},
    )
    if (
        last_failure is None
        or normalize_text(last_failure.kind).lower()
        not in _STABLE_BROWSER_ACCESS_FAILURE_KINDS
    ):
        return timeout_failure

    details = dict(last_failure.details or {})
    details["trace"] = dict(trace)
    details["candidate_deadline_failure"] = {
        "failure_code": timeout_failure.kind,
        "message": timeout_failure.message,
    }
    last_failure.details = details
    return last_failure


def _candidate_failure_outcome(
    observed_failure: BrowserRuntimeFailure | None,
    candidate_failure: BrowserRuntimeFailure,
    *,
    trace: Mapping[str, Any],
) -> BrowserRuntimeFailure:
    """Keep an observed access boundary ahead of later transport failures."""

    if (
        observed_failure is None
        or normalize_text(observed_failure.kind).lower()
        not in _STABLE_BROWSER_ACCESS_FAILURE_KINDS
        or normalize_text(candidate_failure.kind).lower()
        in _STABLE_BROWSER_ACCESS_FAILURE_KINDS
    ):
        return candidate_failure

    details = dict(observed_failure.details or {})
    details["trace"] = dict(trace)
    subsequent_failures = list(details.get("subsequent_candidate_failures") or [])
    subsequent_failures.append(
        {
            "failure_code": candidate_failure.kind,
            "message": candidate_failure.message,
        }
    )
    details["subsequent_candidate_failures"] = subsequent_failures
    observed_failure.details = details
    return observed_failure


def _seed_browser_html_context(
    browser_context: Any,
    *,
    browser_context_seed: Mapping[str, Any] | None,
    candidate_url: str | None,
    trace: dict[str, Any],
) -> None:
    """Apply a transient provider-scoped cookie seed before page navigation."""

    typed_seed = browser_context_seed_from_mapping(browser_context_seed)
    cookies = filter_browser_cookies_for_url(
        list(typed_seed.get("browser_cookies") or []),
        candidate_url,
    )
    seed_trace: dict[str, Any] = {
        "provided": browser_context_seed is not None,
        "cookie_count": len(cookies),
        "applied": False,
        "user_agent_reused": False,
    }
    trace["browser_context_seed"] = seed_trace
    if not cookies:
        seed_trace["reason"] = "no_compatible_cookies"
        return
    try:
        browser_context.add_cookies(cookies)
    except Exception as exc:
        seed_trace["reason"] = "cookie_injection_failed"
        seed_trace["error_type"] = type(exc).__name__
        raise BrowserRuntimeFailure(
            "invalid_browser_context_seed",
            "Failed to apply transient browser cookies before HTML retry.",
            browser_context_seed=typed_seed,
            details={"trace": trace},
        ) from exc
    seed_trace["applied"] = True
    seed_trace["reason"] = "cookies_applied"


def _active_browser_resource_types(
    *,
    disable_media: bool,
    options: BrowserHtmlFetchOptions,
) -> set[str]:
    configured = {
        normalize_text(str(item)).lower()
        for item in (options.blocked_resource_types or ())
        if normalize_text(str(item))
    }
    if disable_media:
        configured.add("media")
    return configured


def _open_browser_html_context(
    config: BrowserRuntimeConfig,
    *,
    runtime_context: RuntimeContext | None,
    shared_page_session: Any | None,
    trace: dict[str, Any],
) -> tuple[Any, Any, Any | None]:
    manager = None
    browser_context = None
    page = None
    reused = False
    connect_started = time.monotonic()
    try:
        if (
            shared_page_session is not None
            and shared_page_session.context is not None
            and shared_page_session.page is not None
        ):
            reused = True
            manager = shared_page_session.manager
            browser_context = shared_page_session.context
            page = shared_page_session.page
        else:
            manager, browser_context = open_browser_context(
                config,
                runtime_context=runtime_context,
            )
        trace["runtime_page_reused"] = reused
        trace["browser_connect_seconds"] = round(time.monotonic() - connect_started, 3)
        return manager, browser_context, page
    except BrowserRuntimeFailure:
        if not reused:
            _safe_close(manager)
        raise
    except Exception as exc:
        trace["browser_connect_seconds"] = round(time.monotonic() - connect_started, 3)
        message = normalize_text(str(exc)) or "Browser context creation failed."
        if not reused:
            _safe_close(manager)
        raise BrowserRuntimeFailure(
            BROWSER_CONTEXT_CREATE_FAILED,
            message,
            details={
                "trace": trace,
                "browser_failure": {
                    "stage": "browser_context_create",
                    "code": BROWSER_CONTEXT_CREATE_FAILED,
                    "message": message,
                },
            },
        ) from exc


def _ensure_browser_html_page(
    browser_context: Any,
    page: Any | None,
    *,
    manager: Any,
    shared_page_session: Any | None,
    trace: dict[str, Any],
) -> Any:
    if page is not None:
        return page
    try:
        page = browser_context.new_page()
        if shared_page_session is not None:
            shared_page_session.bind(
                manager=manager,
                context=browser_context,
                page=page,
            )
        return page
    except Exception as exc:
        message = normalize_text(str(exc)) or "Browser page creation failed."
        raise BrowserRuntimeFailure(
            BROWSER_PAGE_CREATE_FAILED,
            message,
            details={
                "trace": trace,
                "browser_failure": {
                    "stage": "browser_page_create",
                    "code": BROWSER_PAGE_CREATE_FAILED,
                    "message": message,
                },
            },
        ) from exc


def _browser_route_timeout_ms(
    publisher: str,
    *,
    configured_timeout_ms: int,
) -> int:
    """Cap the caller budget with the catalog-compiled browser route timeout."""

    try:
        route_timeout_ms = (
            compile_route_execution_policy_for_kind(
                publisher,
                "html",
                prefer_transport="browser",
            ).timeout_seconds
            * 1000
        )
    except ValueError:
        route_timeout_ms = configured_timeout_ms
    return min(configured_timeout_ms, route_timeout_ms)


def _browser_html_deadline(
    *,
    started_at: float,
    timeout_ms: int,
    runtime_context: RuntimeContext | None,
) -> float:
    deadline = started_at + (timeout_ms / 1000.0)
    if (
        runtime_context is not None
        and runtime_context.browser_deadline_monotonic is not None
    ):
        return min(deadline, runtime_context.browser_deadline_monotonic)
    return deadline


def _reject_http_access_status_review(
    review: dict[str, Any] | None,
    *,
    blocking_reason: str,
) -> None:
    if review is None or review.get("candidate_confirmed") is not True:
        return
    signals = list(review.get("blocking_signals") or [])
    normalized_reason = normalize_text(blocking_reason).lower()
    if normalized_reason and normalized_reason not in signals:
        signals.append(normalized_reason)
    review.update(
        {
            "blocking_signals": signals,
            "candidate_confirmed": False,
            "status_override_applied": False,
            "fulltext_acceptance": "not_attempted",
            "accepted": False,
            "reason": "blocking_signal",
        }
    )


def _record_http_access_status_review(
    candidate_trace: dict[str, Any],
    review: dict[str, Any] | None,
    *,
    apply_override: bool = False,
) -> bool:
    if review is None:
        return False
    confirmed = review.get("candidate_confirmed") is True
    if apply_override:
        review["status_override_applied"] = confirmed
    candidate_trace[_HTTP_ACCESS_STATUS_REVIEW_KEY] = review
    return confirmed


@dataclass
class _OwnedDocumentTracker:
    """Track replacement main-frame document responses during readiness waits."""

    hosts: set[str]
    page_policy: BrowserPagePolicy
    requests: dict[int, Any] = field(default_factory=dict)
    responses: list[Any] = field(default_factory=list)
    finished_requests: set[int] = field(default_factory=set)

    def reset(self) -> None:
        self.requests.clear()
        self.responses.clear()
        self.finished_requests.clear()

    def install(
        self,
        page: Any,
        listeners: list[tuple[str, Callable[[Any], None]]],
    ) -> None:
        if not self.hosts or not callable(getattr(page, "on", None)):
            return

        def on_request(request: Any) -> None:
            if (
                _diagnostic_event_value(
                    getattr(request, "is_navigation_request", False)
                )
                and _diagnostic_event_attr(request, "resource_type") == "document"
                and getattr(page, "main_frame", None) is not None
                and _diagnostic_event_attr(request, "frame")
                is getattr(page, "main_frame", None)
            ):
                self.requests[id(request)] = request

        def on_response(response: Any) -> None:
            if id(_diagnostic_event_attr(response, "request")) in self.requests:
                self.responses.append(response)

        def on_finished(request: Any) -> None:
            if id(request) in self.requests:
                self.finished_requests.add(id(request))

        for event, callback in (
            ("request", on_request),
            ("response", on_response),
            ("requestfinished", on_finished),
        ):
            page.on(event, callback)
            listeners.append((event, callback))

    def select_response(
        self,
        response: Any,
        *,
        final_url: str,
        html: str,
        doi: str,
    ) -> Any:
        if not self.responses:
            return response
        current_response = self.responses[-1]
        current_url = normalize_text(
            str(_diagnostic_event_attr(current_response, "url") or "")
        )
        target_doi = normalize_doi(doi)
        request_id = id(_diagnostic_event_attr(current_response, "request"))
        if (
            request_id in self.finished_requests
            and request_id == next(reversed(self.requests))
            and urllib.parse.urldefrag(current_url)[0]
            == urllib.parse.urldefrag(final_url)[0]
            and urllib.parse.urlsplit(current_url).hostname in self.hosts
            and target_doi
            and (
                self.page_policy.document_matches(
                    current_url, final_url, html, target_doi
                )
                if self.page_policy.document_matches is not None
                else normalize_doi(extract_doi_from_url(current_url)) == target_doi
            )
        ):
            return current_response
        return response


def _install_page_route_filter(
    page: Any,
    *,
    active_blocked_resource_types: set[str],
    empty_script_response_urls: frozenset[str],
    empty_request: Callable[[str], bool] | None,
    trace: dict[str, Any],
) -> None:
    if not (
        active_blocked_resource_types or empty_script_response_urls or empty_request
    ):
        return
    observed_blocked_resource_types: set[str] = set()

    def route_handler(route: Any) -> None:
        try:
            resource_type = normalize_text(
                str(route.request.resource_type or "")
            ).lower()
            request_url = str(route.request.url or "")
            if resource_type == "script" and request_url in empty_script_response_urls:
                try:
                    route.fulfill(
                        status=200,
                        content_type="application/javascript",
                        body="",
                    )
                except Exception:
                    with contextlib.suppress(Exception):
                        route.continue_()
                else:
                    trace["empty_script_response_count"] = (
                        int(trace.get("empty_script_response_count") or 0) + 1
                    )
                return
            sidebar_metrics = bool(empty_request and empty_request(request_url))
            if resource_type in active_blocked_resource_types or sidebar_metrics:
                trace["blocked_request_count"] = (
                    int(trace.get("blocked_request_count") or 0) + 1
                )
                observed_blocked_resource_types.add(resource_type)
                trace["blocked_request_types"] = sorted(observed_blocked_resource_types)
                if sidebar_metrics:
                    trace["blocked_sidebar_metrics_count"] = (
                        int(trace.get("blocked_sidebar_metrics_count") or 0) + 1
                    )
                route.abort()
                return
            route.continue_()
        except Exception:
            with contextlib.suppress(Exception):
                route.continue_()

    with contextlib.suppress(Exception):
        page.route("**/*", route_handler)


def _capture_browser_html(
    page: Any,
    *,
    use_main_context_snapshot: bool,
    runtime_context: RuntimeContext | None,
    candidate_url: str,
) -> tuple[str, str, str]:
    snapshot = (
        _main_context_html_snapshot(page, runtime_context=runtime_context)
        if use_main_context_snapshot
        else None
    )
    if snapshot is not None:
        return snapshot
    final_url = normalize_text(str(getattr(page, "url", "") or "")) or candidate_url
    return str(page.content() or ""), normalize_text(str(page.title() or "")), final_url


def _complete_lightweight_seed_candidate(
    *,
    page: Any,
    browser_context: Any,
    response: Any,
    normalized_url: str,
    publisher: str,
    configured_user_agent: str,
    backend_name: str,
    candidate_started: float,
    candidate_trace: dict[str, Any],
    trace: dict[str, Any],
    document_request_diagnostics: Mapping[int, tuple[Mapping[str, Any], float]],
    remaining_timeout_ms: Callable[[], int],
    last_failure: BrowserRuntimeFailure | None,
    latest_browser_context_seed: Mapping[str, Any] | None,
) -> tuple[
    BrowserFetchedHtml | None,
    BrowserRuntimeFailure | None,
    Mapping[str, Any] | None,
]:
    settle_page_navigation(page, timeout_ms=max(1, remaining_timeout_ms()))
    final_url = normalize_text(str(getattr(page, "url", "") or "")) or normalized_url
    status = _browser_response_status(response, zero_as_none=False)
    headers = _browser_response_headers(response)
    try:
        html = str(page.content() or "")
    except Exception:
        html = ""
    _record_candidate_document_diagnostics(
        candidate_trace,
        response=response,
        page=page,
        final_url=final_url,
        status=status,
        headers=headers,
        document_requests=document_request_diagnostics,
        html=html,
    )
    try:
        title = normalize_text(str(page.title() or ""))
    except Exception:
        title = ""
    summary = _browser_html_summary(publisher, html)
    detected = detect_html_block(
        title,
        summary,
        status,
        html_text=html,
        response_headers=headers,
    )
    context_seed = _build_session_context_seed(
        browser_context,
        page=page,
        final_url=final_url,
        configured_user_agent=configured_user_agent,
        backend_name=backend_name,
    )
    candidate_trace["duration_seconds"] = round(time.monotonic() - candidate_started, 3)
    rejection = _lightweight_seed_rejection(
        status=status,
        requested_url=normalized_url,
        final_url=final_url,
        detected=detected,
    )
    if rejection is not None:
        reason, message = rejection
        candidate_trace["result"] = "rejected"
        candidate_trace["block_reason"] = reason
        updated_failure = _candidate_failure_outcome(
            last_failure,
            BrowserRuntimeFailure(reason, message, details={"trace": trace}),
            trace=trace,
        )
        return None, updated_failure, latest_browser_context_seed
    if context_seed.get("browser_cookies") or context_seed.get("browser_user_agent"):
        latest_browser_context_seed = context_seed
    candidate_trace["result"] = "success"
    return (
        BrowserFetchedHtml(
            source_url=normalized_url,
            final_url=final_url,
            html="",
            response_status=status,
            response_headers=headers,
            title=title or None,
            summary=summary,
            browser_context_seed=context_seed,
            diagnostics={"browser_runtime_trace": trace},
        ),
        last_failure,
        latest_browser_context_seed,
    )


def _complete_full_html_candidate(
    *,
    page: Any,
    browser_context: Any,
    response: Any,
    normalized_url: str,
    publisher: str,
    config: BrowserRuntimeConfig,
    readiness: BrowserHtmlReadiness,
    wait_seconds: int,
    candidate_timeout_ms: int,
    request_started: float,
    candidate_started: float,
    supplementary_index: bool,
    readiness_budget_seconds: float | None,
    readiness_deadline: float | None,
    page_policy: BrowserPagePolicy,
    owned_tracker: _OwnedDocumentTracker,
    configured_user_agent: str,
    backend_name: str,
    runtime_context: RuntimeContext | None,
    candidate_trace: dict[str, Any],
    trace: dict[str, Any],
    document_request_diagnostics: Mapping[int, tuple[Mapping[str, Any], float]],
    remaining_timeout_ms: Callable[[], int],
    last_failure: BrowserRuntimeFailure | None,
    latest_browser_context_seed: Mapping[str, Any] | None,
) -> tuple[
    BrowserFetchedHtml | None,
    BrowserRuntimeFailure | None,
    Mapping[str, Any] | None,
    float | None,
]:
    if readiness_budget_seconds is not None and (
        readiness_deadline is None or page_policy.readiness_per_candidate
    ):
        readiness_deadline = time.monotonic() + max(
            0.0, float(readiness_budget_seconds)
        )
    body_readiness = wait_for_browser_html_readiness(
        page,
        publisher=publisher,
        readiness=readiness,
        wait_seconds=wait_seconds,
        timeout_ms=candidate_timeout_ms,
        request_started=request_started,
        runtime_context=runtime_context,
        candidate_trace=candidate_trace,
        readiness_timeout_seconds=(
            max(0.0, readiness_deadline - time.monotonic())
            if readiness_deadline is not None
            else None
        ),
    )
    use_main_context_snapshot = bool(
        normalize_text(publisher).lower() in _MAIN_CONTEXT_SNAPSHOT_PROVIDERS
        and body_readiness is not None
        and body_readiness.ready
    )
    settle_page_navigation(page, timeout_ms=max(1, remaining_timeout_ms()))
    if not supplementary_index:
        snapshot = (
            _main_context_html_snapshot(page, runtime_context=runtime_context)
            if use_main_context_snapshot
            else None
        )
        raise_for_paywall(
            snapshot[0] if snapshot is not None else str(page.content() or ""),
            metadata={"doi": config.doi},
            source_url=(
                snapshot[2]
                if snapshot is not None
                else str(getattr(page, "url", "") or normalized_url)
            ),
            provider=publisher,
            context=runtime_context,
        )
    _prepare_provider_browser_page(
        page,
        publisher=publisher,
        timeout_ms=remaining_timeout_ms(),
        candidate_trace=candidate_trace,
        runtime_context=runtime_context,
    )
    html, title, final_url = _capture_browser_html(
        page,
        use_main_context_snapshot=use_main_context_snapshot,
        runtime_context=runtime_context,
        candidate_url=normalized_url,
    )
    if not title and normalize_text(publisher).lower() != "ieee":
        title = extract_page_title(BeautifulSoup(html, choose_parser())) or ""
    response = owned_tracker.select_response(
        response,
        final_url=final_url,
        html=html,
        doi=config.doi,
    )
    status = _browser_response_status(response, zero_as_none=False)
    headers = _browser_response_headers(response)
    _record_candidate_document_diagnostics(
        candidate_trace,
        response=response,
        page=page,
        final_url=final_url,
        status=status,
        headers=headers,
        document_requests=document_request_diagnostics,
        html=html,
    )
    summary = _browser_html_summary(publisher, html)
    context_seed = _build_session_context_seed(
        browser_context,
        page=page,
        final_url=final_url,
        configured_user_agent=configured_user_agent,
        backend_name=backend_name,
    )
    if context_seed.get("browser_cookies") or context_seed.get("browser_user_agent"):
        latest_browser_context_seed = context_seed

    if not supplementary_index and looks_like_abstract_redirect(
        normalized_url, final_url
    ):
        candidate_trace["duration_seconds"] = round(
            time.monotonic() - candidate_started, 3
        )
        candidate_trace["block_reason"] = REDIRECTED_TO_ABSTRACT
        return (
            None,
            _candidate_failure_outcome(
                last_failure,
                BrowserRuntimeFailure(
                    REDIRECTED_TO_ABSTRACT,
                    "Publisher redirected the full-text URL to an abstract page.",
                    browser_context_seed=context_seed,
                    details={"trace": trace},
                ),
                trace=trace,
            ),
            latest_browser_context_seed,
            readiness_deadline,
        )

    if not supplementary_index:
        raise_for_paywall(
            html,
            metadata={"doi": config.doi},
            source_url=final_url,
            provider=publisher,
            context=runtime_context,
        )

    required_selector_ready = bool(
        readiness.require_selector and candidate_trace.get("selector_readiness_ready")
    )
    substantive_body_ready = bool(
        readiness.wait_for_article_body and candidate_trace.get("dom_readiness_ready")
    )
    stable_body_ready = bool(
        substantive_body_ready
        and candidate_trace.get("dom_readiness_fingerprint_present")
    )
    http_access_status_review = (
        page_policy.review_http_status(
            status=status,
            requested_doi=config.doi,
            requested_url=normalized_url,
            final_url=final_url,
            html_text=html,
            title=title or "",
            body_ready=stable_body_ready,
            runtime_context=runtime_context,
        )
        if page_policy.review_http_status is not None
        else None
    )
    candidate_confirmed = _record_http_access_status_review(
        candidate_trace,
        http_access_status_review,
    )
    status_for_block_detection = None if candidate_confirmed else status
    detected = detect_html_block(
        title or "",
        summary,
        status_for_block_detection,
        substantive_body_ready=substantive_body_ready,
        include_paywall_text=not supplementary_index,
        html_text="" if required_selector_ready else html,
        response_headers={} if required_selector_ready else headers,
    )
    if candidate_trace.get("dom_readiness_blocking_reason"):
        reason = candidate_trace["dom_readiness_blocking_reason"]
        detected = HtmlExtractionFailure(reason, html_failure_message(reason))
    if detected is not None:
        _reject_http_access_status_review(
            http_access_status_review,
            blocking_reason=detected.reason,
        )
        _record_browser_challenge_signal(
            trace,
            reason=detected.reason,
            status=status,
            final_url=final_url,
        )
        candidate_trace["duration_seconds"] = round(
            time.monotonic() - candidate_started, 3
        )
        candidate_trace["block_reason"] = detected.reason
        return (
            None,
            _candidate_failure_outcome(
                last_failure,
                BrowserRuntimeFailure(
                    detected.reason,
                    detected.message,
                    browser_context_seed=context_seed,
                    details=_browser_page_failure_details(
                        trace=trace,
                        runtime_context=runtime_context,
                        request=PageDiagnosticRequest(
                            provider=publisher,
                            route="browser_html",
                            attempt=max(1, len(list(trace.get("candidates") or []))),
                            failure_code=detected.reason,
                            stage="block_detection",
                            html_text=html,
                            doi=config.doi,
                            target_url=normalized_url,
                            final_url=final_url,
                            backend=config.backend,
                            response_status=status,
                            title=title or "",
                            summary=summary,
                            details={"browser_runtime_trace": dict(trace)},
                        ),
                    ),
                ),
                trace=trace,
            ),
            latest_browser_context_seed,
            readiness_deadline,
        )

    _record_http_access_status_review(
        candidate_trace,
        http_access_status_review,
        apply_override=True,
    )
    if readiness.require_selector and not bool(
        candidate_trace.get("selector_readiness_ready")
    ):
        reason = "browser_article_not_ready"
        message = (
            "Publisher browser page did not expose the required article "
            "container before the readiness timeout."
        )
        candidate_trace["duration_seconds"] = round(
            time.monotonic() - candidate_started, 3
        )
        candidate_trace["block_reason"] = reason
        return (
            None,
            _candidate_failure_outcome(
                last_failure,
                BrowserRuntimeFailure(
                    reason,
                    message,
                    browser_context_seed=context_seed,
                    details=_browser_page_failure_details(
                        trace=trace,
                        runtime_context=runtime_context,
                        request=PageDiagnosticRequest(
                            provider=publisher,
                            route="browser_html",
                            attempt=max(1, len(list(trace.get("candidates") or []))),
                            failure_code=reason,
                            stage="dom_readiness",
                            html_text=html,
                            doi=config.doi,
                            target_url=normalized_url,
                            final_url=final_url,
                            backend=config.backend,
                            response_status=status,
                            title=title or "",
                            summary=summary,
                            details={"browser_runtime_trace": dict(trace)},
                        ),
                    ),
                ),
                trace=trace,
            ),
            latest_browser_context_seed,
            readiness_deadline,
        )

    if not normalize_text(html):
        candidate_trace["duration_seconds"] = round(
            time.monotonic() - candidate_started, 3
        )
        candidate_trace["block_reason"] = "empty_html_response"
        return (
            None,
            _candidate_failure_outcome(
                last_failure,
                BrowserRuntimeFailure(
                    "empty_html_response",
                    f"{backend_name} returned empty publisher HTML.",
                    browser_context_seed=context_seed,
                    details={"trace": trace},
                ),
                trace=trace,
            ),
            latest_browser_context_seed,
            readiness_deadline,
        )

    candidate_trace["duration_seconds"] = round(time.monotonic() - candidate_started, 3)
    candidate_trace["result"] = "success"
    return (
        BrowserFetchedHtml(
            source_url=normalized_url,
            final_url=final_url,
            html=html,
            response_status=status,
            response_headers=headers,
            title=title,
            summary=summary,
            browser_context_seed=context_seed,
            diagnostics={"browser_runtime_trace": trace},
        ),
        last_failure,
        latest_browser_context_seed,
        readiness_deadline,
    )


def fetch_browser_html(
    candidate_urls: list[str],
    *,
    publisher: str,
    config: BrowserRuntimeConfig,
    wait_seconds: int = DEFAULT_BROWSER_RUNTIME_WAIT_SECONDS,
    max_timeout_ms: int | None = None,
    disable_media: bool = False,
    readiness: BrowserHtmlReadiness = DEFAULT_BROWSER_HTML_READINESS,
    runtime_context: RuntimeContext | None = None,
    browser_context_seed: Mapping[str, Any] | None = None,
    options: BrowserHtmlFetchOptions = DEFAULT_BROWSER_HTML_FETCH_OPTIONS,
) -> BrowserFetchedHtml:
    if not candidate_urls:
        raise BrowserRuntimeFailure(
            "empty_html_attempts", "No publisher HTML candidates were attempted."
        )
    backend_name = config.backend
    active_blocked_resource_types = _active_browser_resource_types(
        disable_media=disable_media,
        options=options,
    )
    empty_script_response_urls = frozenset(
        str(item).strip()
        for item in options.empty_script_response_urls
        if str(item).strip()
    )
    try:
        page_policy = provider_bundle(publisher).browser_page_policy
    except KeyError:
        page_policy = BrowserPagePolicy()

    last_failure: BrowserRuntimeFailure | None = None
    latest_browser_context_seed: Mapping[str, Any] | None = None
    caller_timeout_ms = (
        config.timeout_ms if max_timeout_ms is None else max(1, max_timeout_ms)
    )
    timeout_ms = _browser_route_timeout_ms(
        publisher,
        configured_timeout_ms=caller_timeout_ms,
    )
    artifact_dir = config.artifact_dir / backend_name
    configured_user_agent = normalize_text(config.user_agent)
    normalized_wait_for_selector = normalize_text(readiness.selector)
    trace: dict[str, Any] = {
        "backend": backend_name,
        "engine": engine_name() if backend_name == "byparr" else "camoufox",
        "candidate_count": len(candidate_urls),
        "candidates": [],
        "navigation_count": 0,
        "media_blocking": "media" in active_blocked_resource_types,
        "blocked_resource_types": sorted(active_blocked_resource_types),
        "blocked_request_count": 0,
        "blocked_request_types": [],
        "empty_script_response_count": 0,
        "lightweight_seed_only": bool(options.lightweight_seed_only),
        "article_body_wait_enabled": bool(readiness.wait_for_article_body),
        "selector_wait_enabled": bool(normalized_wait_for_selector),
        "wait_for_selector": normalized_wait_for_selector or None,
        "native_profile_write_enabled": True,
        "readiness_budget_seconds": options.readiness_budget_seconds,
        "runtime_page_reuse_enabled": bool(options.reuse_runtime_page),
    }
    overall_started = time.monotonic()
    local_deadline = _browser_html_deadline(
        started_at=overall_started,
        timeout_ms=timeout_ms,
        runtime_context=runtime_context,
    )
    trace["timeout_budget_ms"] = timeout_ms
    readiness_deadline: float | None = None

    def remaining_timeout_ms() -> int:
        remaining = max(0.0, local_deadline - time.monotonic())
        if remaining <= 0:
            return 0
        return max(1, min(timeout_ms, int(remaining * 1000)))

    manager = None
    browser_context = None
    page = None
    page_diagnostic_listeners: list[tuple[str, Callable[[Any], None]]] = []
    document_request_diagnostics: dict[int, tuple[dict[str, Any], float]] = {}
    shared_page_session = _runtime_figure_page_session(
        runtime_context,
        create=bool(options.reuse_runtime_page),
    )

    try:
        if runtime_context is not None:
            runtime_context.raise_if_cancelled()
        launch_config = (
            replace(config, timeout_ms=max(1, remaining_timeout_ms()))
            if config.backend == "byparr"
            else config
        )
        manager, browser_context, page = _open_browser_html_context(
            launch_config,
            runtime_context=runtime_context,
            shared_page_session=shared_page_session,
            trace=trace,
        )
        overall_started = time.monotonic()
        local_deadline = _browser_html_deadline(
            started_at=overall_started,
            timeout_ms=timeout_ms,
            runtime_context=runtime_context,
        )
        trace["persistent_profile"] = (
            runtime_context.browser_profile_diagnostics(browser_context)
            if runtime_context is not None
            else dict(getattr(manager, "diagnostics", {}))
        )
        if trace.get("runtime_page_reused"):
            trace["browser_context_seed"] = {
                "provided": browser_context_seed is not None,
                "applied": False,
                "reason": "reused_runtime_page_context",
            }
        else:
            _seed_browser_html_context(
                browser_context,
                browser_context_seed=browser_context_seed,
                candidate_url=candidate_urls[0] if candidate_urls else None,
                trace=trace,
            )
        page = _ensure_browser_html_page(
            browser_context,
            page,
            manager=manager,
            shared_page_session=shared_page_session,
            trace=trace,
        )
        (
            page_diagnostic_listeners,
            document_request_diagnostics,
        ) = _install_page_diagnostic_listeners(page, trace)

        owned_tracker = _OwnedDocumentTracker(
            hosts=set(page_policy.document_hosts),
            page_policy=page_policy,
        )
        owned_tracker.install(page, page_diagnostic_listeners)
        _install_page_route_filter(
            page,
            active_blocked_resource_types=active_blocked_resource_types,
            empty_script_response_urls=empty_script_response_urls,
            empty_request=page_policy.empty_request,
            trace=trace,
        )

        for url in candidate_urls:
            if runtime_context is not None:
                runtime_context.raise_if_cancelled()
            candidate_timeout_ms = remaining_timeout_ms()
            if candidate_timeout_ms <= 0:
                trace["deadline_exhausted"] = True
                last_failure = _candidate_deadline_failure(
                    last_failure,
                    trace=trace,
                )
                break
            normalized_url = normalize_text(url)
            if not normalized_url:
                continue

            candidate_trace: dict[str, Any] = {
                **diagnostic_url_payload(normalized_url),
                "started_at": round(time.time(), 3),
                "remaining_before_ms": candidate_timeout_ms,
            }
            trace["candidates"].append(candidate_trace)
            candidate_started = time.monotonic()
            owned_tracker.reset()
            try:
                logger.debug(
                    "browser_request backend=%s provider=%s action=request wait_seconds=%s url=%s",
                    backend_name,
                    publisher,
                    wait_seconds,
                    candidate_trace.get("url"),
                )
                request_started = time.monotonic()
                trace["navigation_count"] = int(trace.get("navigation_count") or 0) + 1
                if shared_page_session is not None:
                    trace["runtime_page_navigation_count"] = (
                        shared_page_session.mark_navigation()
                    )
                try:
                    response = _navigate_browser_page(
                        page,
                        url=normalized_url,
                        timeout_ms=candidate_timeout_ms,
                    )
                finally:
                    navigator = getattr(browser_context, "__dict__", {}).get(
                        "_paper_fetch_navigator"
                    )
                    if navigator is not None:
                        candidate_trace["byparr"] = dict(navigator.diagnostics)
                candidate_trace["navigation_seconds"] = round(
                    time.monotonic() - request_started, 3
                )
                if options.lightweight_seed_only:
                    result, last_failure, latest_browser_context_seed = (
                        _complete_lightweight_seed_candidate(
                            page=page,
                            browser_context=browser_context,
                            response=response,
                            normalized_url=normalized_url,
                            publisher=publisher,
                            configured_user_agent=configured_user_agent,
                            backend_name=backend_name,
                            candidate_started=candidate_started,
                            candidate_trace=candidate_trace,
                            trace=trace,
                            document_request_diagnostics=document_request_diagnostics,
                            remaining_timeout_ms=remaining_timeout_ms,
                            last_failure=last_failure,
                            latest_browser_context_seed=latest_browser_context_seed,
                        )
                    )
                else:
                    (
                        result,
                        last_failure,
                        latest_browser_context_seed,
                        readiness_deadline,
                    ) = _complete_full_html_candidate(
                        page=page,
                        browser_context=browser_context,
                        response=response,
                        normalized_url=normalized_url,
                        publisher=publisher,
                        config=config,
                        readiness=readiness,
                        wait_seconds=wait_seconds,
                        candidate_timeout_ms=candidate_timeout_ms,
                        request_started=request_started,
                        candidate_started=candidate_started,
                        supplementary_index=options.supplementary_index,
                        readiness_budget_seconds=options.readiness_budget_seconds,
                        readiness_deadline=readiness_deadline,
                        page_policy=page_policy,
                        owned_tracker=owned_tracker,
                        configured_user_agent=configured_user_agent,
                        backend_name=backend_name,
                        runtime_context=runtime_context,
                        candidate_trace=candidate_trace,
                        trace=trace,
                        document_request_diagnostics=document_request_diagnostics,
                        remaining_timeout_ms=remaining_timeout_ms,
                        last_failure=last_failure,
                        latest_browser_context_seed=latest_browser_context_seed,
                    )
                if result is not None:
                    return result
            except RequestCancelledError:
                candidate_trace["duration_seconds"] = round(
                    time.monotonic() - candidate_started,
                    3,
                )
                candidate_trace["error"] = "cancelled"
                raise
            except Exception as exc:
                propagate_paywall(exc)
                candidate_trace["duration_seconds"] = round(
                    time.monotonic() - candidate_started,
                    3,
                )
                candidate_trace["error"] = (
                    _bounded_diagnostic_text(exc) or exc.__class__.__name__
                )
                if isinstance(exc, BrowserRuntimeFailure):
                    candidate_failure = exc
                    if backend_name == "byparr":
                        candidate_failure.details.setdefault(
                            "browser_runtime_trace", trace
                        )
                        candidate_failure.details.setdefault(
                            "stage", "byparr_navigation"
                        )
                else:
                    candidate_failure = BrowserRuntimeFailure(
                        f"{backend_name}_request_failed",
                        normalize_text(str(exc))
                        or f"{backend_name} page request failed.",
                        details={"trace": trace},
                    )
                last_failure = _candidate_failure_outcome(
                    last_failure,
                    candidate_failure,
                    trace=trace,
                )
    finally:
        trace["duration_seconds"] = round(time.monotonic() - overall_started, 3)
        trace["remaining_ms"] = remaining_timeout_ms()
        _remove_page_diagnostic_listeners(page, page_diagnostic_listeners)
        if (
            shared_page_session is None
            or shared_page_session.context is not browser_context
        ):
            _safe_close(page)
            _safe_close(manager)

    if last_failure is None:
        last_failure = BrowserRuntimeFailure(
            "empty_html_attempts",
            "No publisher HTML candidates were attempted.",
            browser_context_seed=latest_browser_context_seed,
            details={"trace": trace},
        )
    if artifact_dir:
        with contextlib.suppress(OSError):
            artifact_dir.mkdir(parents=True, exist_ok=True)
    raise last_failure


fetch_browser_html.paper_fetch_html_fetcher_name = "byparr"  # type: ignore[attr-defined]


def warm_browser_html_context(
    candidate_urls: list[str],
    *,
    publisher: str,
    config: BrowserRuntimeConfig,
    browser_context_seed: Mapping[str, Any] | None = None,
    runtime_context: RuntimeContext | None = None,
    lightweight: bool = False,
) -> BrowserWarmResult:
    merged_seed = merge_browser_context_seeds(browser_context_seed)
    if not candidate_urls:
        return BrowserWarmResult(
            seed=merged_seed,
            changed=False,
            accepted=False,
            status=None,
            reason="empty_warm_candidates",
        )

    try:
        result = fetch_browser_html(
            candidate_urls,
            publisher=publisher,
            config=config,
            browser_context_seed=merged_seed,
            runtime_context=runtime_context,
            options=BrowserHtmlFetchOptions(lightweight_seed_only=lightweight),
        )
    except BrowserRuntimeFailure as exc:
        trace = exc.details.get("trace")
        status = None
        if isinstance(trace, Mapping):
            candidates = trace.get("candidates")
            if isinstance(candidates, list) and candidates:
                candidate = candidates[-1]
                if isinstance(candidate, Mapping):
                    status = _safe_int(candidate.get("status"), default=0) or None
        return BrowserWarmResult(
            seed=merged_seed,
            changed=False,
            accepted=False,
            status=status,
            reason=exc.kind,
            final_url=(
                normalize_text(
                    str((exc.browser_context_seed or {}).get("browser_final_url") or "")
                )
                or None
            ),
            diagnostics=dict(exc.details),
        )
    refreshed_seed = merge_browser_context_seeds(
        merged_seed, result.browser_context_seed
    )
    delta = _cookie_delta(merged_seed, refreshed_seed)
    changed = any(delta.values())
    return BrowserWarmResult(
        seed=refreshed_seed,
        changed=changed,
        accepted=True,
        status=result.response_status,
        reason="refreshed" if changed else "no_cookie_change",
        final_url=result.final_url,
        cookie_delta=delta,
        diagnostics=dict(result.diagnostics or {}),
    )
