"""Internal HTML extraction helpers for provider browser workflows."""

from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass, replace
import time
from typing import TYPE_CHECKING, Any, cast
from collections.abc import Callable, Mapping, Sequence

from ...extraction.html.assets import extract_scoped_html_assets
from ...extraction.html.signals import (
    HtmlExtractionFailure,
    html_failure_message,
    summarize_html,
)
from ...http import diagnostic_url_payload
from ...metadata.types import ProviderMetadata
from ...models import AssetProfile
from ...reason_codes import (
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
    BrowserHtmlFetchOptions,
    BrowserRuntimeConfig,
    BrowserRuntimeFailure,
    merge_browser_context_seeds,
)
from ..browser_runtime.api import (
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
from .shared import normalize_browser_url

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
_FAST_BROWSER_ACCESS_FAILURE_KINDS = {
    AWS_WAF_CHALLENGE,
    CLOUDFLARE_CHALLENGE,
    PUBLISHER_ACCESS_DENIED,
    PUBLISHER_PAYWALL,
    REDIRECTED_TO_ABSTRACT,
    ABSTRACT_ONLY,
}
_FAST_BROWSER_RETRY_TIMEOUT_KINDS = {
    "timeout",
    "pool_timeout",
    "browser_connect_timeout",
    "browser_navigation_timeout",
    "browser_rest_wait_timeout",
}
_INCOMPLETE_HTML_CANDIDATE_REORDER_KINDS = {
    EMPTY_ARTICLE_SHELL,
    INSUFFICIENT_BODY,
    STRUCTURED_ARTICLE_NOT_FULLTEXT,
    STRUCTURED_MISSING_BODY_SECTIONS,
    "article_container_not_found",
}
_HTTP_ACCESS_STATUS_REVIEW_KEY = "http_access_status_review"


@dataclass(frozen=True)
class BrowserHtmlFetchPolicy:
    disable_media: bool = False
    wait_seconds: int = DEFAULT_BROWSER_RUNTIME_WAIT_SECONDS
    warm_wait_seconds: int = DEFAULT_BROWSER_RUNTIME_WARM_WAIT_SECONDS
    max_timeout_ms: int | None = None
    attempt: int = 1


@dataclass(frozen=True)
class BrowserHtmlPriorAttemptState:
    attempts: tuple[Mapping[str, Any], ...] = ()
    browser_trace: Mapping[str, Any] | None = None


def _finalize_http_access_status_review(
    html_result: BrowserFetchedHtml,
    *,
    accepted: bool,
    reason: str,
) -> BrowserFetchedHtml:
    """Finalize a provisional browser status review after HTML extraction."""

    if html_result.response_status not in {401, 403}:
        return html_result
    diagnostics = dict(html_result.diagnostics or {})
    trace_value = diagnostics.get("browser_runtime_trace")
    if not isinstance(trace_value, Mapping):
        return html_result
    trace = dict(trace_value)
    candidates_value = trace.get("candidates")
    if not isinstance(candidates_value, list):
        return html_result

    candidates = [
        dict(candidate) if isinstance(candidate, Mapping) else candidate
        for candidate in candidates_value
    ]
    updated = False
    source_url = normalize_browser_url(html_result.source_url)
    for candidate in reversed(candidates):
        if not isinstance(candidate, dict):
            continue
        candidate_url = normalize_browser_url(
            str(candidate.get("url") or candidate.get("final_url") or "")
        )
        if source_url and candidate_url and candidate_url != source_url:
            continue
        review_value = candidate.get(_HTTP_ACCESS_STATUS_REVIEW_KEY)
        if not isinstance(review_value, Mapping):
            continue
        review = dict(review_value)
        if review.get("candidate_confirmed") is not True:
            continue
        review.update(
            {
                "fulltext_acceptance": "accepted" if accepted else "rejected",
                "accepted": bool(accepted),
                "reason": normalize_text(reason).lower()
                or ("fulltext_accepted" if accepted else "fulltext_rejected"),
            }
        )
        candidate[_HTTP_ACCESS_STATUS_REVIEW_KEY] = review
        if not accepted:
            candidate["result"] = "extraction_failure"
            candidate["block_reason"] = review["reason"]
        updated = True
        break
    if not updated:
        return html_result
    trace["candidates"] = candidates
    diagnostics["browser_runtime_trace"] = trace
    return replace(html_result, diagnostics=diagnostics)


def _browser_runtime_trace(
    diagnostics: Mapping[str, Any] | None,
) -> dict[str, Any]:
    trace = (diagnostics or {}).get("browser_runtime_trace")
    return dict(trace) if isinstance(trace, Mapping) else {}


def _merge_browser_runtime_trace_history(
    prior_trace: Mapping[str, Any] | None,
    current_trace: Mapping[str, Any] | None,
) -> dict[str, Any]:
    prior = dict(prior_trace or {})
    current = dict(current_trace or {})
    if not prior:
        return current
    if not current:
        return prior

    merged = dict(current)
    prior_candidates = [
        dict(item)
        for item in list(prior.get("candidates") or [])
        if isinstance(item, Mapping)
    ]
    current_candidates = [
        dict(item)
        for item in list(current.get("candidates") or [])
        if isinstance(item, Mapping)
    ]
    merged["candidates"] = [*prior_candidates, *current_candidates]
    merged["candidate_count"] = max(
        int(prior.get("candidate_count") or 0),
        int(current.get("candidate_count") or 0),
        len(merged["candidates"]),
    )
    for key in ("navigation_count", "blocked_request_count"):
        merged[key] = int(prior.get(key) or 0) + int(current.get(key) or 0)
    prior_challenges = [
        dict(item)
        for item in list(prior.get("challenge_signals") or [])
        if isinstance(item, Mapping)
    ]
    current_challenges = [
        dict(item)
        for item in list(current.get("challenge_signals") or [])
        if isinstance(item, Mapping)
    ]
    if prior_challenges or current_challenges:
        merged["challenge_signals"] = [*prior_challenges, *current_challenges]
    return merged


def _with_browser_runtime_trace_history(
    html_result: BrowserFetchedHtml,
    prior_trace: Mapping[str, Any] | None,
) -> BrowserFetchedHtml:
    if not prior_trace:
        return html_result
    diagnostics = dict(html_result.diagnostics or {})
    diagnostics["browser_runtime_trace"] = _merge_browser_runtime_trace_history(
        prior_trace,
        _browser_runtime_trace(diagnostics),
    )
    return replace(html_result, diagnostics=diagnostics)


def _remaining_wiley_review_candidates(
    provider: str,
    html_candidates: Sequence[str],
    html_result: BrowserFetchedHtml,
) -> list[str]:
    if normalize_text(
        provider
    ).lower() != "wiley" or html_result.response_status not in {401, 403}:
        return []
    trace = _browser_runtime_trace(html_result.diagnostics)
    candidates = trace.get("candidates")
    if not isinstance(candidates, list):
        return []
    confirmed_review = False
    for candidate in reversed(candidates):
        if not isinstance(candidate, Mapping):
            continue
        review = candidate.get(_HTTP_ACCESS_STATUS_REVIEW_KEY)
        if not isinstance(review, Mapping):
            continue
        if (
            review.get("candidate_confirmed") is True
            and review.get("fulltext_acceptance") == "rejected"
        ):
            confirmed_review = True
            break
    if not confirmed_review:
        return []

    failed_source = normalize_browser_url(html_result.source_url)
    if not failed_source:
        return []
    normalized_candidates = [
        normalize_browser_url(candidate) or normalize_text(candidate)
        for candidate in html_candidates
    ]
    try:
        failed_index = normalized_candidates.index(failed_source)
    except ValueError:
        return []
    return list(html_candidates[failed_index + 1 :])


def _browser_page_state(
    html_result: BrowserFetchedHtml,
) -> dict[str, Any]:
    page_sha256 = hashlib.sha256(html_result.html.encode("utf-8")).hexdigest()
    return {
        "route": "browser_html",
        "page_sha256": page_sha256,
    }


def _empty_shell_retry_decision(
    *,
    policy: BrowserHtmlFetchPolicy,
    html_candidates: list[str],
    html_result: BrowserFetchedHtml,
    page_state: Mapping[str, Any],
    prior_attempts: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    failed_source = normalize_text(html_result.source_url)
    remaining_candidates = [
        candidate
        for candidate in html_candidates
        if normalize_text(candidate) and normalize_text(candidate) != failed_source
    ]
    candidate_changed = bool(remaining_candidates)
    profile_changed = bool(policy.attempt == 1 and policy.disable_media)
    previous_state = next(
        (
            item.get("page_state")
            for item in reversed(prior_attempts)
            if isinstance(item.get("page_state"), Mapping)
        ),
        None,
    )
    identical_page_state = bool(
        isinstance(previous_state, Mapping)
        and previous_state.get("page_sha256") == page_state.get("page_sha256")
    )
    retry = bool(
        policy.attempt == 1
        and not identical_page_state
        and (candidate_changed or profile_changed)
    )
    if identical_page_state:
        reason = "identical_page"
    elif policy.attempt != 1:
        reason = "state_change_retry_limit_reached"
    elif candidate_changed:
        reason = "candidate_url_changed"
    elif profile_changed:
        reason = "browser_fetch_profile_changed"
    else:
        reason = "unchanged_route_and_profile"
    decision: dict[str, Any] = {
        "retry": retry,
        "reason": reason,
        "attempt": policy.attempt,
        "candidate_changed": candidate_changed,
        "profile_changed": profile_changed,
        "identical_page_state": identical_page_state,
    }
    if remaining_candidates:
        decision["next_candidate"] = diagnostic_url_payload(remaining_candidates[0])
    return decision


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
        if not runtime.persist_storage_state:
            runtime_trace["storage_state_save"] = {
                "attempted": False,
                "staged": False,
                "saved": False,
                "path": None,
                "reason": "provider_runtime_fingerprint_boundary",
            }
            diagnostics["browser_runtime_trace"] = runtime_trace
            return (
                replace(
                    html_result,
                    diagnostics=diagnostics,
                    staged_storage_state=None,
                ),
                [],
            )
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
        content=ProviderContent(
            route_kind="html",
            source_url=html_result.final_url,
            content_type="text/html",
            body=html_bytes,
            route_name="browser_html",
            markdown_text=markdown_text,
            diagnostics=diagnostics,
            fetcher=fetcher,
            browser_context_seed=dict(html_result.browser_context_seed or {}),
        ),
        warnings=list(warnings or []),
        trace=trace_from_markers([fulltext_marker(client.name, "ok", route="html")]),
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
    prior_state: BrowserHtmlPriorAttemptState = BrowserHtmlPriorAttemptState(),
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
    profile = client.require_profile()
    fetch_kwargs: dict[str, Any] = {
        "publisher": client.name,
        "config": runtime,
        "wait_seconds": policy.wait_seconds,
        "warm_wait_seconds": policy.warm_wait_seconds,
        "max_timeout_ms": operation_timeout_ms,
        "disable_media": policy.disable_media,
        "runtime_context": context,
        "options": BrowserHtmlFetchOptions(
            blocked_resource_types=profile.blocked_resource_types or None,
            empty_script_response_urls=profile.empty_script_response_urls,
            readiness_budget_seconds=profile.html_readiness_budget_seconds,
        ),
    }
    if profile.html_readiness is not None:
        fetch_kwargs["readiness"] = profile.html_readiness
    if browser_context_seed and browser_context_seed.get("browser_cookies"):
        fetch_kwargs["browser_context_seed"] = browser_context_seed
    attempt_history = [dict(item) for item in prior_state.attempts]
    try:
        html_result = html_fetcher(
            html_candidates,
            **fetch_kwargs,
        )
    except BrowserRuntimeFailure as exc:
        failure_details = dict(exc.details or {})
        if prior_state.browser_trace:
            failure_details["trace"] = _merge_browser_runtime_trace_history(
                prior_state.browser_trace,
                failure_details.get("trace")
                if isinstance(failure_details.get("trace"), Mapping)
                else None,
            )
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
    html_result = _with_browser_runtime_trace_history(
        html_result,
        prior_state.browser_trace,
    )
    result_diagnostics = dict(html_result.diagnostics or {})
    page_state = _browser_page_state(html_result)
    result_diagnostics["page_state"] = page_state
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
        "page_state": page_state,
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
        html_result = _finalize_http_access_status_review(
            html_result,
            accepted=False,
            reason=exc.reason,
        )
        retry_decision = (
            _empty_shell_retry_decision(
                policy=policy,
                html_candidates=html_candidates,
                html_result=html_result,
                page_state=page_state,
                prior_attempts=attempt_history,
            )
            if exc.reason == EMPTY_ARTICLE_SHELL
            else None
        )
        attempt_record["result"] = "extraction_failure"
        attempt_record["failure_code"] = exc.reason
        page_details = dict(html_result.diagnostics or {})
        if retry_decision is not None:
            attempt_record["retry_decision"] = retry_decision
            page_details["retry_decision"] = retry_decision
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
                backend="camoufox",
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
        remaining_candidates = _remaining_wiley_review_candidates(
            client.name,
            html_candidates,
            html_result,
        )
        if remaining_candidates:
            attempt_record["candidate_continuation"] = True
            page_details["html_attempts"] = [*attempt_history, attempt_record]
            if policy.max_timeout_ms is None:
                return _fetch_browser_html_payload(
                    client,
                    remaining_candidates,
                    runtime=runtime,
                    metadata=metadata,
                    context=context,
                    warnings=warnings,
                    html_fetcher=html_fetcher,
                    policy=policy,
                    browser_context_seed=merge_browser_context_seeds(
                        browser_context_seed,
                        html_result.browser_context_seed,
                    ),
                    prior_state=BrowserHtmlPriorAttemptState(
                        attempts=tuple(page_details["html_attempts"]),
                        browser_trace=_browser_runtime_trace(html_result.diagnostics),
                    ),
                )
        raise
    html_result = _finalize_http_access_status_review(
        html_result,
        accepted=True,
        reason="fulltext_accepted",
    )
    result_diagnostics = dict(html_result.diagnostics or {})
    attempt_record["result"] = "success"
    result_diagnostics["html_attempts"] = [*attempt_history, attempt_record]
    html_result = replace(html_result, diagnostics=result_diagnostics)
    html_result, storage_warnings = _commit_accepted_storage_state(
        html_result,
        runtime,
        context=context,
    )
    fetcher_attr = getattr(html_fetcher, "paper_fetch_html_fetcher_name", None)
    fetcher_name = "camoufox"
    if isinstance(fetcher_attr, str) and normalize_text(fetcher_attr).endswith("_fast"):
        fetcher_name = "camoufox_fast"
    payload = _browser_workflow_html_payload(
        client,
        html_result,
        markdown_text=markdown_text,
        extraction=extraction,
        fetcher=fetcher_name,
        warnings=[*list(warnings or []), *storage_warnings],
    )
    return html_result, payload


def _should_retry_fast_browser_failure(exc: Exception) -> bool:
    if isinstance(exc, BrowserRuntimeFailure):
        return exc.kind in _FAST_BROWSER_HTML_RETRY_KINDS
    if isinstance(exc, HtmlExtractionFailure):
        return True
    return False


def _browser_failure_kind(exc: Exception) -> str:
    return normalize_text(
        str(getattr(exc, "kind", None) or getattr(exc, "reason", None) or "")
    ).lower()


def _preserve_fast_access_failure_after_retry_timeout(
    fast_failure: BrowserRuntimeFailure | HtmlExtractionFailure,
    retry_failure: BrowserRuntimeFailure | HtmlExtractionFailure,
) -> bool:
    """Keep a stable access-boundary result when its retry exhausts the budget."""

    if _browser_failure_kind(fast_failure) not in _FAST_BROWSER_ACCESS_FAILURE_KINDS:
        return False
    if _browser_failure_kind(retry_failure) not in _FAST_BROWSER_RETRY_TIMEOUT_KINDS:
        return False

    fast_details = dict(getattr(fast_failure, "details", None) or {})
    retry_details = dict(getattr(retry_failure, "details", None) or {})
    retry_attempts = retry_details.get("html_attempts")
    if isinstance(retry_attempts, list):
        fast_details["html_attempts"] = [
            dict(item) for item in retry_attempts if isinstance(item, Mapping)
        ]
    fast_details["retry_failure"] = {
        "failure_code": _browser_failure_kind(retry_failure),
        "message": normalize_text(
            str(getattr(retry_failure, "message", None) or retry_failure)
        ),
    }
    fast_failure.details = fast_details

    if isinstance(fast_failure, BrowserRuntimeFailure):
        fast_failure.browser_context_seed = {
            key: value
            for key, value in merge_browser_context_seeds(
                fast_failure.browser_context_seed,
                getattr(retry_failure, "browser_context_seed", None),
            ).items()
            if value is not None
        }
    return True


def _retry_candidates_after_fast_failure(
    client: BrowserWorkflowClient,
    html_candidates: list[str],
    fast_failure: BrowserRuntimeFailure | HtmlExtractionFailure | None,
) -> list[str]:
    candidates = list(html_candidates)
    failure_kind = _browser_failure_kind(fast_failure) if fast_failure else ""
    retry_incomplete = client.require_profile().retry_incomplete_html_candidates
    html_result = getattr(fast_failure, "html_result", None)
    if isinstance(html_result, BrowserFetchedHtml):
        remaining_wiley_candidates = _remaining_wiley_review_candidates(
            client.name,
            candidates,
            html_result,
        )
        if remaining_wiley_candidates:
            return remaining_wiley_candidates
    if (
        not isinstance(fast_failure, HtmlExtractionFailure)
        or (
            failure_kind != EMPTY_ARTICLE_SHELL
            and (
                not retry_incomplete
                or failure_kind not in _INCOMPLETE_HTML_CANDIDATE_REORDER_KINDS
            )
        )
        or len(candidates) < 2
    ):
        return candidates
    failed_source = normalize_text(str(getattr(html_result, "source_url", "") or ""))
    if not failed_source:
        return candidates
    for index, candidate in enumerate(candidates):
        if normalize_text(candidate) == failed_source:
            return [*candidates[:index], *candidates[index + 1 :], candidate]
    return candidates


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
    profile = client.require_profile()
    if not profile.fast_html_attempt:
        return _fetch_browser_html_payload(
            client,
            html_candidates,
            runtime=runtime,
            metadata=metadata,
            context=context,
            warnings=warnings,
            html_fetcher=html_fetcher,
            policy=BrowserHtmlFetchPolicy(attempt=1),
        )
    retry_seed: dict[str, Any] = {}
    prior_attempts: list[Mapping[str, Any]] = []
    prior_browser_trace: dict[str, Any] = {}
    fast_failure: BrowserRuntimeFailure | HtmlExtractionFailure | None = None
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
        fast_failure = exc
        if isinstance(exc, BrowserRuntimeFailure):
            retry_seed = dict(exc.browser_context_seed)
            failure_details = dict(exc.details or {})
            trace_value = failure_details.get("trace")
            if isinstance(trace_value, Mapping):
                prior_browser_trace = dict(trace_value)
        else:
            extraction_html_result = getattr(exc, "html_result", None)
            retry_seed = dict(
                getattr(extraction_html_result, "browser_context_seed", None) or {}
            )
            failure_details = dict(getattr(exc, "details", None) or {})
            if isinstance(extraction_html_result, BrowserFetchedHtml):
                prior_browser_trace = _browser_runtime_trace(
                    extraction_html_result.diagnostics
                )
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
        retry_decision = failure_details.get("retry_decision")
        if (
            _browser_failure_kind(exc) == EMPTY_ARTICLE_SHELL
            and isinstance(retry_decision, Mapping)
            and not bool(retry_decision.get("retry"))
        ):
            raise
        logger.debug(
            "browser_workflow_fast_browser_path provider=%s action=fallback reason=%s message=%s",
            client.name,
            getattr(exc, "kind", None)
            or getattr(exc, "reason", None)
            or exc.__class__.__name__,
            getattr(exc, "message", None) or normalize_text(str(exc)),
        )

    retry_candidates = _retry_candidates_after_fast_failure(
        client,
        html_candidates,
        fast_failure,
    )
    try:
        return _fetch_browser_html_payload(
            client,
            retry_candidates,
            runtime=runtime,
            metadata=metadata,
            context=context,
            warnings=warnings,
            html_fetcher=html_fetcher,
            policy=BrowserHtmlFetchPolicy(attempt=2),
            browser_context_seed=retry_seed,
            prior_state=BrowserHtmlPriorAttemptState(
                attempts=tuple(prior_attempts),
                browser_trace=prior_browser_trace,
            ),
        )
    except (BrowserRuntimeFailure, HtmlExtractionFailure) as retry_failure:
        if (
            fast_failure is not None
            and _preserve_fast_access_failure_after_retry_timeout(
                fast_failure,
                retry_failure,
            )
        ):
            raise fast_failure from retry_failure
        raise
