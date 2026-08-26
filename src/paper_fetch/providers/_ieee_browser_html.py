"""IEEE selected-browser HTML fallback."""

from __future__ import annotations

from collections.abc import Callable
import contextlib
import time
from typing import Any

from ..extraction.html.signals import detect_html_block, summarize_visible_html
from ..failure import FailureDiagnostics
from ..http import (
    RequestCancelledError,
    RequestFailure,
    SafeRemoteUrlPolicy,
    redact_url_for_diagnostics,
)
from ..http.headers import header_value
from ..quality.html_availability import (
    HtmlQualityAssessor,
    availability_failure_message,
)
from ..reason_codes import ERROR, NO_RESULT
from ..runtime import RuntimeContext
from ..runtime_browser import browser_page_user_agent
from ..tracing import fulltext_marker
from ..utils import normalize_text
from . import _ieee_html as ieee_html
from . import _ieee_metadata as ieee_metadata
from . import _ieee_url as ieee_url
from ._ieee_browser_readiness import (
    _BrowserFailureContext,
    _RestHtmlSelection,
    _capture_rest_html,
    _ieee_browser_network_guard,
    _page_content,
    _page_has_article,
    _page_title,
    _playwright_response_headers,
    _playwright_response_status,
    _playwright_timeout_error,
    _unready_browser_failure,
)
from ._payloads import (
    build_provider_payload,
    provider_failure_diagnostics as _provider_failure_diagnostics,
)
from .base import ProviderFailure, RawFulltextPayload
from .browser_workflow.shared import BROWSER_HTML_BLOCKED_RESOURCE_TYPES
from .browser_runtime import (
    BrowserRuntimeFailure,
    BrowserRuntimeConfig,
    browser_context,
    browser_context_seed_from_session,
    merge_browser_context_seeds,
)

IEEE_BROWSER_HTML_NAVIGATION_TIMEOUT_MS = 60000
IEEE_BROWSER_HTML_REST_WAIT_TIMEOUT_MS = 15000
IEEE_BROWSER_HTML_POLL_INTERVAL_MS = 250


def _remaining_timeout_ms(
    context: RuntimeContext,
    maximum_ms: int,
) -> int:
    context.raise_if_cancelled()
    try:
        value = context.remaining_timeout_ms(maximum_ms)
        return max(1, min(maximum_ms, int(value)))
    except (AttributeError, TypeError, ValueError):
        return maximum_ms


def _browser_failure_as_provider_failure(
    exc: BrowserRuntimeFailure,
    *,
    provider_name: str,
) -> ProviderFailure:
    details = dict(exc.details)
    stage = normalize_text(str(details.get("stage") or "")) or None
    return ProviderFailure(
        NO_RESULT,
        exc.message,
        diagnostics=FailureDiagnostics(
            provider=provider_name,
            route="browser_html",
            stage=stage,
            error_category=exc.kind,
            retryable=exc.kind
            in {
                "browser_connect_timeout",
                "browser_navigation_timeout",
                "browser_rest_wait_timeout",
            },
            details={"code": exc.kind, **details},
        ),
    )


def fetch_ieee_browser_html_payload(
    *,
    provider_name: str,
    browser_user_agent: str | None,
    landing_attempt: ieee_metadata.IeeeLandingAttempt,
    document_url: str,
    rest_url: str,
    direct_html_failure: ProviderFailure | None,
    context: RuntimeContext,
    runtime_config: BrowserRuntimeConfig,
    extraction_assets: Callable[
        [ieee_html.IeeeHtmlExtraction, ieee_metadata.IeeeLandingAttempt],
        list[dict[str, Any]],
    ],
    remote_url_policy: SafeRemoteUrlPolicy | None = None,
) -> RawFulltextPayload:
    network_guard, landing_cookies = _ieee_browser_network_guard(
        provider_name=provider_name,
        landing_attempt=landing_attempt,
        document_url=document_url,
        rest_url=rest_url,
        context=context,
        runtime_config=runtime_config,
        remote_url_policy=remote_url_policy,
    )
    PlaywrightTimeoutError = _playwright_timeout_error(runtime_config)

    article_number = landing_attempt.article_number
    browser_session_scope = None
    active_browser_context = None
    page = None
    rest_responses: list[Any] = []
    response_network_failures: list[Exception] = []
    navigation_response = None
    browser_final_url = document_url
    navigation_status: int | None = None
    navigation_headers: dict[str, str] = {}
    payload_source = ""
    response_status: int | None = None
    response_headers: dict[str, str] = {}
    source_url = document_url
    html_text = ""
    browser_context_seed: dict[str, Any] = {}
    rest_selection = _RestHtmlSelection(
        selected=None,
        latest_invalid=None,
        response_count=0,
        invalid_response_count=0,
    )
    request_started = time.monotonic()
    with contextlib.suppress(AttributeError):
        context.initialize_deadline(runtime_config.timeout_ms / 1000.0)

    try:
        _remaining_timeout_ms(context, runtime_config.timeout_ms)
        browser_session_scope = browser_context(
            runtime_config,
            runtime_context=context,
        )
        session = browser_session_scope.__enter__()
        active_browser_context = session.context

        def route_after_validation(route: Any) -> None:
            resource_type = normalize_text(
                getattr(route.request, "resource_type", "")
            ).lower()
            if resource_type in BROWSER_HTML_BLOCKED_RESOURCE_TYPES:
                route.abort()
                return
            route.continue_()

        network_guard.install_on_context(
            active_browser_context,
            after_validation=route_after_validation,
        )
        if landing_cookies:
            active_browser_context.add_cookies(landing_cookies)
        page = active_browser_context.new_page()

        def remember_rest_response(response: Any) -> None:
            response_url = str(getattr(response, "url", "") or "")
            if ieee_url._is_ieee_rest_document_url(response_url, article_number):
                try:
                    network_guard.validate(
                        response_url,
                        previous_url=rest_url,
                        resolve_dns=True,
                    )
                except Exception as exc:
                    response_network_failures.append(exc)
                    return
                rest_responses.append(response)

        page.on("response", remember_rest_response)
        navigation_timed_out = False
        try:
            navigation_response = page.goto(
                document_url,
                wait_until="domcontentloaded",
                timeout=_remaining_timeout_ms(
                    context, IEEE_BROWSER_HTML_NAVIGATION_TIMEOUT_MS
                ),
            )
        except PlaywrightTimeoutError:
            navigation_response = None
            navigation_timed_out = True
        context.raise_if_cancelled()
        browser_final_url = (
            normalize_text(str(getattr(page, "url", "") or "")) or document_url
        )
        try:
            network_guard.validate(
                browser_final_url,
                previous_url=document_url,
                resolve_dns=True,
            )
        except Exception as exc:
            raise RequestFailure(
                None,
                "IEEE browser navigation returned an unsafe final URL.",
                error_category="unsafe_redirect",
            ) from exc
        if response_network_failures:
            raise RequestFailure(
                None,
                "IEEE browser observed an unsafe REST response URL.",
                error_category="unsafe_redirect",
            ) from response_network_failures[0]
        navigation_status = _playwright_response_status(navigation_response)
        navigation_headers = _playwright_response_headers(navigation_response)

        rest_wait_deadline = time.monotonic() + (
            _remaining_timeout_ms(context, IEEE_BROWSER_HTML_REST_WAIT_TIMEOUT_MS)
            / 1000.0
        )
        rest_selection = _capture_rest_html(rest_responses, rest_url, article_number)
        has_article_dom = _page_has_article(page, article_number)
        while (
            rest_selection.selected is None
            and not has_article_dom
            and time.monotonic() < rest_wait_deadline
        ):
            wait_ms = min(
                IEEE_BROWSER_HTML_POLL_INTERVAL_MS,
                _remaining_timeout_ms(context, IEEE_BROWSER_HTML_POLL_INTERVAL_MS),
                max(1, int((rest_wait_deadline - time.monotonic()) * 1000)),
            )
            page.wait_for_timeout(wait_ms)
            context.raise_if_cancelled()
            rest_selection = _capture_rest_html(
                rest_responses, rest_url, article_number
            )
            has_article_dom = _page_has_article(page, article_number)

        captured_rest_html = rest_selection.selected
        if captured_rest_html is not None:
            source_url = captured_rest_html.source_url
            response_headers = captured_rest_html.headers
            html_text = captured_rest_html.html_text
            response_status = captured_rest_html.status
            payload_source = "rest_response"

        if not html_text:
            if not has_article_dom:
                page_html = _page_content(page)
                page_title = _page_title(page)
                raise _unready_browser_failure(
                    _BrowserFailureContext(
                        runtime_context=context,
                        provider_name=provider_name,
                        landing_attempt=landing_attempt,
                        runtime_config=runtime_config,
                        document_url=document_url,
                        rest_url=rest_url,
                        final_url=browser_final_url,
                        navigation_status=navigation_status,
                        navigation_headers=navigation_headers,
                    ),
                    navigation_timed_out=navigation_timed_out,
                    rest_selection=rest_selection,
                    page_html=page_html,
                    page_title=page_title,
                )
            html_text = _page_content(page)
            browser_final_url = (
                normalize_text(str(getattr(page, "url", "") or "")) or browser_final_url
            )
            source_url = browser_final_url
            response_headers = {"content-type": "text/html"}
            response_status = navigation_status
            payload_source = "dom_article"
            if article_number not in html_text:
                raise BrowserRuntimeFailure(
                    "browser_article_identity_missing",
                    "IEEE #article DOM did not contain the requested article number.",
                    details={
                        "stage": "dom_readiness",
                        "article_number": article_number,
                    },
                )
        title = _page_title(page)
        html_summary = summarize_visible_html(html_text)
        detected = detect_html_block(
            title,
            html_summary,
            response_status,
        )
        if detected is not None:
            detected = detect_html_block(
                title,
                html_summary,
                response_status,
                html_text=html_text,
                response_headers=response_headers,
            )
        if detected is not None:
            raise BrowserRuntimeFailure(
                detected.reason,
                detected.message,
                details={
                    "stage": "block_detection",
                    "status": response_status,
                    "payload_source": payload_source,
                    **(
                        {
                            "challenge_provider": "aws_waf",
                            "legacy_reason_code": "cloudflare_challenge",
                        }
                        if detected.reason == "aws_waf_challenge"
                        else {}
                    ),
                },
            )

        context.raise_if_cancelled()
        browser_context_seed = merge_browser_context_seeds(
            landing_attempt.browser_context_seed,
            browser_context_seed_from_session(
                active_browser_context,
                final_url=browser_final_url,
                user_agent=browser_page_user_agent(page) or browser_user_agent,
                backend=runtime_config.backend,
                fetcher=f"{runtime_config.backend}_ieee_html",
            ),
        )
        extraction = ieee_html._extract_ieee_html(
            html_text,
            source_url,
            metadata=landing_attempt.merged_metadata,
            context=context,
        )
        diagnostics = HtmlQualityAssessor("ieee").assess(
            extraction.markdown_text,
            landing_attempt.merged_metadata,
            html_text=extraction.html_text,
            title=str(landing_attempt.merged_metadata.get("title") or ""),
            requested_url=(
                rest_url if payload_source == "rest_response" else document_url
            ),
            final_url=source_url,
            response_status=response_status,
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
        context.raise_if_cancelled()
        content_type = header_value(response_headers, "content-type", "text/html")
        extracted_assets = extraction_assets(extraction, landing_attempt)
        return build_provider_payload(
            provider=provider_name,
            route_kind="html",
            route_name="browser_html",
            source_url=source_url,
            content_type=content_type,
            body=extraction.html_text.encode("utf-8"),
            markdown_text=extraction.markdown_text,
            merged_metadata=landing_attempt.merged_metadata,
            diagnostics={
                "availability_diagnostics": diagnostics.to_dict(),
                "browser_html": {
                    "fetcher": f"{runtime_config.backend}_ieee_html",
                    "backend": runtime_config.backend,
                    "payload_source": payload_source,
                    "document_url": redact_url_for_diagnostics(document_url),
                    "rest_url": redact_url_for_diagnostics(rest_url),
                    "final_url": redact_url_for_diagnostics(browser_final_url),
                    "navigation_status": navigation_status,
                    "response_status": response_status,
                    "rest_response_count": rest_selection.response_count,
                    "invalid_rest_response_count": (
                        rest_selection.invalid_response_count
                    ),
                    "timeout_budget_ms": runtime_config.timeout_ms,
                    "elapsed_ms": round((time.monotonic() - request_started) * 1000, 3),
                    "remaining_ms": max(
                        0,
                        _remaining_timeout_ms(context, runtime_config.timeout_ms),
                    ),
                    "direct_html_failure": _provider_failure_diagnostics(
                        direct_html_failure
                    ),
                },
                "extraction": {
                    "abstract_sections": extraction.abstract_sections,
                    "section_hints": extraction.section_hints,
                    "marker_counts": extraction.marker_counts,
                },
            },
            reason=f"Downloaded full text from the IEEE Xplore {runtime_config.backend} HTML fallback route.",
            fetcher=f"{runtime_config.backend}_ieee_html",
            browser_context_seed=browser_context_seed,
            extracted_assets=extracted_assets,
            trace_markers=[
                fulltext_marker("ieee", "fail", route="html"),
                fulltext_marker("ieee", "ok", route="browser_html"),
                fulltext_marker("ieee", "ok", route="html"),
            ],
        )
    except BrowserRuntimeFailure as exc:
        raise _browser_failure_as_provider_failure(
            exc, provider_name=provider_name
        ) from exc
    except RequestCancelledError:
        raise
    except RequestFailure as exc:
        raise ProviderFailure(
            NO_RESULT,
            "IEEE browser HTML request was blocked by the network safety policy.",
            diagnostics=FailureDiagnostics(
                provider=provider_name,
                route="browser_html",
                stage="network_policy",
                error_category="unsafe_browser_url",
                retryable=False,
            ),
        ) from exc
    except ProviderFailure:
        raise
    except Exception as exc:
        message = normalize_text(str(exc)) or exc.__class__.__name__
        raise ProviderFailure(
            ERROR, f"IEEE browser HTML fallback failed ({message})."
        ) from exc
    finally:
        if page is not None:
            with contextlib.suppress(Exception):
                page.close()
        if browser_session_scope is not None:
            with contextlib.suppress(Exception):
                browser_session_scope.__exit__(None, None, None)
