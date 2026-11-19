"""Browser recovery policies and candidate resolution helpers for HTML assets."""

from __future__ import annotations

import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, replace
from typing import Any

from ....asset_budget import AssetBudgetExceeded
from ....http import HttpTransport, RequestCancelledError, RequestFailure
from ....http.headers import header_value
from ....image_tools import ImageConversionFailure, source_image_format_from_payload
from ....reason_codes import OFFICIAL_FULL_SIZE_ACCESS_RESTRICTED
from ....utils import normalize_text
from ._kind import (
    AssetDownloadKind,
)
from ._kind import (
    failure_from_document_fetch as _failure_from_document_fetch,
)
from ._kind import (
    is_preview_candidate as _is_preview_candidate,
)
from ._kind import (
    requires_image_payload as _requires_image_payload,
)
from .conversion import conversion_failure_attempt, converted_figure_response
from .state import (
    AssetDownloadAttempt,
    AssetDownloadCandidate,
    AssetDownloadResolution,
    AssetFetchResponse,
    asset_failure,
    resolution_from_attempt,
)
from .streaming import (
    AssetFetchPolicy,
    AssetRequestContext,
    rollback_response_reservation,
    stage_browser_response,
    with_asset_timing,
)

ImageDocumentFetcher = Callable[[str, Mapping[str, Any]], Mapping[str, Any] | None]
FileDocumentFetcher = Callable[[str, Mapping[str, Any]], Mapping[str, Any] | None]

_BROWSER_RECOVERABLE_NETWORK_CATEGORIES = {
    "connection_closed",
    "connection_reset",
    "dns_error",
    "network_error",
    "timeout",
    "tls_error",
}
_BROWSER_RECOVERABLE_NETWORK_REASON_TOKENS = (
    "challenge",
    "cloudflare",
    "connection closed",
    "connection reset",
    "dns",
    "name resolution",
    "network error",
    "remote end closed",
    "ssl error",
    "timed out",
    "timeout",
    "tls error",
)


def browser_asset_recovery_allowed(
    *,
    status: int | None,
    content_type: str = "",
    reason: str = "",
    error_category: str = "",
) -> bool:
    """Return whether a failed direct asset request may use browser recovery."""

    if status in {404, 410, 429}:
        return False
    if status in {401, 403}:
        return True
    if status is None:
        normalized_category = normalize_text(error_category).lower()
        normalized_reason = normalize_text(reason).lower()
        return normalized_category in _BROWSER_RECOVERABLE_NETWORK_CATEGORIES or any(
            token in normalized_reason
            for token in _BROWSER_RECOVERABLE_NETWORK_REASON_TOKENS
        )
    normalized_type = normalize_text(content_type).split(";", 1)[0].lower()
    normalized_reason = normalize_text(reason).lower()
    return status == 200 and (
        normalized_type in {"text/html", "application/xhtml+xml"}
        or any(
            token in normalized_reason
            for token in ("challenge", "access", "cloudflare", "html")
        )
    )


def requires_caller_thread(fetcher: Any) -> bool:
    return bool(getattr(fetcher, "requires_caller_thread", False))


def _candidate_source_image_format(candidate_url: str) -> str:
    return source_image_format_from_payload(b"", source_url=candidate_url)


def should_use_document_fetcher_for_candidate(
    kind: AssetDownloadKind,
    candidate_url: str,
    document_fetcher: ImageDocumentFetcher | FileDocumentFetcher | None,
) -> bool:
    if document_fetcher is None:
        return False
    if kind.name == "supplementary":
        return True
    if kind.name != "figure":
        return False
    return _candidate_source_image_format(candidate_url) not in {"eps", "tiff"}


def document_fetch_failure(
    fetcher: ImageDocumentFetcher | FileDocumentFetcher | None,
    candidate_url: str,
) -> dict[str, Any]:
    reporter = getattr(fetcher, "failure_for", None)
    if not callable(reporter):
        return {}
    try:
        failure = reporter(candidate_url)
    except Exception:
        return {}
    return dict(failure) if isinstance(failure, Mapping) else {}


def fetch_document_fallback(
    kind: AssetDownloadKind,
    fetcher: ImageDocumentFetcher | FileDocumentFetcher | None,
    candidate_url: str,
    asset: Mapping[str, Any],
    *,
    transport: HttpTransport | None = None,
    request_context: AssetRequestContext | None = None,
) -> AssetFetchResponse | None:
    del transport
    if fetcher is None:
        return None
    if kind.name == "figure" and not _requires_image_payload(asset):
        return None
    try:
        browser_started_at = time.monotonic()
        raw_response = fetcher(candidate_url, asset)
        response = (
            AssetFetchResponse.from_mapping(raw_response) if raw_response else None
        )
    except (RequestCancelledError, AssetBudgetExceeded):
        if (
            request_context is not None
            and request_context.fetch_policy == "browser_only"
        ):
            raise
        return None
    except Exception:
        return None
    if not response:
        return None
    body = response.get("body", b"")
    if not isinstance(body, bytes | bytearray):
        return None
    content_type = header_value(response.get("headers"), "content-type")
    if not kind.accepts_response(content_type, bytes(body)):
        return None
    recovered = response.copy()
    recovered = with_asset_timing(
        recovered,
        "browser_recovery",
        time.monotonic() - browser_started_at,
    )
    backend = getattr(fetcher, "browser_backend", None)
    browser_backend = normalize_text(backend) if isinstance(backend, str) else ""
    if browser_backend:
        recovered.browser_backend = browser_backend
    if request_context is None:
        return recovered
    return stage_browser_response(
        kind,
        recovered,
        request_context=request_context,
    )


def with_browser_recovery_diagnostics(
    response: AssetFetchResponse,
    direct_attempt: AssetDownloadAttempt | None,
) -> AssetFetchResponse:
    recovered = response.copy()
    direct_diagnostic = (
        direct_attempt.failure.diagnostic
        if direct_attempt is not None and direct_attempt.failure is not None
        else {}
    )
    backend = normalize_text(recovered.browser_backend)
    final_fetcher = backend or "selected_browser"
    recovered.final_fetcher = final_fetcher
    direct_entry = {
        key: value
        for key, value in {
            "stage": "direct",
            "status": direct_diagnostic.get("status"),
            "content_type": direct_diagnostic.get("content_type"),
            "reason": direct_diagnostic.get("reason"),
            "error_category": direct_diagnostic.get("error_category"),
        }.items()
        if value not in (None, "")
    }
    browser_entry = {
        key: value
        for key, value in {
            "stage": "browser",
            "browser_backend": backend or None,
            "status": int(recovered.get("status_code") or 0) or None,
            "content_type": header_value(recovered.get("headers"), "content-type"),
            "reason": "recovered",
            "final_fetcher": final_fetcher,
        }.items()
        if value not in (None, "")
    }
    prior_attempts = [
        dict(item) for item in recovered.recovery_attempts if isinstance(item, Mapping)
    ]
    if prior_attempts and prior_attempts[-1].get("stage") == "browser":
        prior_attempts[-1] = {**prior_attempts[-1], **browser_entry}
        recovered.recovery_attempts = [direct_entry, *prior_attempts]
    else:
        recovered.recovery_attempts = [direct_entry, *prior_attempts, browser_entry]
    return recovered


def unsupported_scheme_failure(
    kind: AssetDownloadKind,
    asset: Mapping[str, Any],
    candidate_url: str,
) -> dict[str, Any]:
    label = "supplementary URL" if kind.name == "supplementary" else "asset URL"
    return kind.failure_template(
        asset,
        candidate_url,
        reason=f"Unsupported {label} scheme for {candidate_url}",
    )


def request_failure_attempt(
    kind: AssetDownloadKind,
    asset: Mapping[str, Any],
    candidate: AssetDownloadCandidate,
    exc: RequestFailure,
) -> AssetDownloadAttempt:
    content_type = header_value(exc.headers, "content-type")
    body = exc.body if isinstance(exc.body, bytes | bytearray) else b""
    return AssetDownloadAttempt(
        candidate=candidate,
        failure=asset_failure(
            kind.failure_template(
                asset,
                candidate.url,
                status=exc.status_code,
                content_type=content_type,
                final_url=exc.url,
                body=body,
                reason=normalize_text(str(getattr(exc, "reason_code", "") or ""))
                or str(exc),
                error_category=str(getattr(exc, "error_category", "") or ""),
            )
        ),
    )


def blocked_response_attempt(
    kind: AssetDownloadKind,
    asset: Mapping[str, Any],
    candidate: AssetDownloadCandidate,
    response: AssetFetchResponse,
    source_url: str,
    reason: str,
) -> AssetDownloadAttempt:
    body = response.get("body", b"")
    if not isinstance(body, bytes | bytearray):
        body = b""
    return AssetDownloadAttempt(
        candidate=candidate,
        failure=asset_failure(
            kind.failure_template(
                asset,
                source_url,
                status=response.get("status_code"),
                content_type=header_value(response.get("headers"), "content-type"),
                final_url=normalize_text(str(response.get("url") or source_url)),
                body=body,
                reason=reason,
            ),
            timing=response.timing,
            started_at=response.started_at,
            route_diagnostics=response.route_diagnostics,
        ),
    )


def preview_fallback_provenance(
    candidate_url: str,
    *,
    preview_url: str,
    full_size_url: str,
    full_size_access_failed: bool,
) -> tuple[str, ...]:
    if full_size_access_failed and _is_preview_candidate(
        candidate_url,
        preview_url=preview_url,
        full_size_url=full_size_url,
    ):
        return (OFFICIAL_FULL_SIZE_ACCESS_RESTRICTED,)
    return ()


def with_conversion_provenance(
    resolution: AssetDownloadResolution,
    *,
    conversion_degraded: bool,
    additional: Sequence[str] = (),
) -> AssetDownloadResolution:
    provenance = tuple(
        dict.fromkeys(
            [
                *resolution.provenance,
                *(["conversion_degraded"] if conversion_degraded else []),
                *(normalize_text(str(item)) for item in additional if item),
            ]
        )
    )
    if provenance == resolution.provenance:
        return resolution
    return replace(resolution, provenance=provenance)


def budget_failure_resolution(
    kind: AssetDownloadKind,
    asset: Mapping[str, Any],
    exc: AssetBudgetExceeded,
    candidate: AssetDownloadCandidate,
    *,
    preview_url: str,
    full_size_url: str,
    response: AssetFetchResponse | None = None,
) -> AssetDownloadResolution:
    rollback_response_reservation(response)
    diagnostic = kind.failure_template(
        asset,
        candidate.url,
        reason=exc.reason_code,
    )
    diagnostic.update(exc.diagnostic)
    attempt = AssetDownloadAttempt(
        candidate=candidate,
        failure=asset_failure(
            diagnostic,
            timing=response.timing if response is not None else None,
            started_at=response.started_at if response is not None else None,
            route_diagnostics=(
                response.route_diagnostics if response is not None else None
            ),
        ),
    )
    return resolution_from_attempt(
        asset=asset,
        attempt=attempt,
        preview_url=preview_url,
        full_size_url=full_size_url,
    )


@dataclass(frozen=True)
class CandidateRecoveryResult:
    attempt: AssetDownloadAttempt | None = None
    resolution: AssetDownloadResolution | None = None
    conversion_degraded: bool = False
    budget_error: AssetBudgetExceeded | None = None
    budget_response: AssetFetchResponse | None = None
    budget_candidate: AssetDownloadCandidate | None = None


@dataclass
class CandidateResolutionLoopState:
    """Mutable loop state eliminating repeated recovery-unpacking boilerplate."""

    kind: AssetDownloadKind
    asset: Mapping[str, Any]
    preview_url: str
    full_size_url: str
    last_attempt: AssetDownloadAttempt | None = None
    conversion_degraded: bool = False
    full_size_access_failed: bool = False

    def mark_non_preview_failure(self, candidate_url: str) -> None:
        if not _is_preview_candidate(
            candidate_url,
            preview_url=self.preview_url,
            full_size_url=self.full_size_url,
        ):
            self.full_size_access_failed = True

    def apply(
        self,
        recovery: CandidateRecoveryResult,
        candidate: AssetDownloadCandidate,
        *,
        preserve_last_attempt: bool = False,
    ) -> AssetDownloadResolution | None:
        self.conversion_degraded = (
            self.conversion_degraded or recovery.conversion_degraded
        )
        if not preserve_last_attempt:
            self.last_attempt = recovery.attempt
        if recovery.budget_error is not None:
            return budget_failure_resolution(
                self.kind,
                self.asset,
                recovery.budget_error,
                recovery.budget_candidate or candidate,
                preview_url=self.preview_url,
                full_size_url=self.full_size_url,
                response=recovery.budget_response,
            )
        if recovery.resolution is not None:
            return with_conversion_provenance(
                recovery.resolution,
                conversion_degraded=self.conversion_degraded,
                additional=preview_fallback_provenance(
                    candidate.url,
                    preview_url=self.preview_url,
                    full_size_url=self.full_size_url,
                    full_size_access_failed=self.full_size_access_failed,
                ),
            )
        self.mark_non_preview_failure(candidate.url)
        return None


def browser_first_candidate_recovery(
    kind: AssetDownloadKind,
    asset: Mapping[str, Any],
    candidate: AssetDownloadCandidate,
    *,
    transport: HttpTransport,
    request_context: AssetRequestContext,
    document_fetcher: ImageDocumentFetcher | FileDocumentFetcher | None,
    preview_url: str,
    full_size_url: str,
) -> CandidateRecoveryResult:
    try:
        response = fetch_document_fallback(
            kind,
            document_fetcher,
            candidate.url,
            asset,
            transport=transport,
            request_context=request_context,
        )
    except AssetBudgetExceeded as exc:
        return CandidateRecoveryResult(budget_error=exc)
    if response is None:
        failure = document_fetch_failure(document_fetcher, candidate.url)
        return CandidateRecoveryResult(
            attempt=AssetDownloadAttempt(
                candidate=candidate,
                failure=asset_failure(
                    _failure_from_document_fetch(kind, asset, candidate.url, failure)
                ),
            )
        )
    try:
        converted = response
        if request_context.fetch_policy != "browser_only" and kind.name == "figure":
            converted, _source_format = converted_figure_response(
                response,
                source_url=candidate.url,
                asset_budget=request_context.asset_budget,
                path_converter=request_context.path_converter,
            )
    except AssetBudgetExceeded as exc:
        return CandidateRecoveryResult(
            budget_error=exc,
            budget_response=response,
        )
    except ImageConversionFailure as exc:
        return CandidateRecoveryResult(
            attempt=conversion_failure_attempt(kind, asset, candidate, response, exc),
            conversion_degraded=True,
        )
    return CandidateRecoveryResult(
        resolution=resolution_from_attempt(
            asset=asset,
            attempt=AssetDownloadAttempt(
                candidate=candidate,
                response=converted,
                source_url=candidate.url,
            ),
            preview_url=preview_url,
            full_size_url=full_size_url,
        )
    )


def recover_failed_candidate(
    kind: AssetDownloadKind,
    asset: Mapping[str, Any],
    candidate: AssetDownloadCandidate,
    *,
    transport: HttpTransport,
    request_context: AssetRequestContext,
    document_fetcher: ImageDocumentFetcher | FileDocumentFetcher | None,
    last_attempt: AssetDownloadAttempt,
    preview_url: str,
    full_size_url: str,
    recovery_allowed: bool,
) -> CandidateRecoveryResult:
    if not recovery_allowed:
        return CandidateRecoveryResult(attempt=last_attempt)
    try:
        response = fetch_document_fallback(
            kind,
            document_fetcher,
            candidate.url,
            asset,
            transport=transport,
            request_context=request_context,
        )
    except AssetBudgetExceeded as exc:
        return CandidateRecoveryResult(
            attempt=last_attempt,
            budget_error=exc,
        )
    if response is None:
        fetch_failure = document_fetch_failure(document_fetcher, candidate.url)
        if fetch_failure and last_attempt.failure is not None:
            # Browser fetchers commonly report sparse fields. Do not erase the
            # direct response status or MIME with their empty placeholders,
            # while still allowing an actionable browser reason to supersede a
            # generic HTTP failure.
            last_attempt.failure.diagnostic.update(
                {
                    key: value
                    for key, value in fetch_failure.items()
                    if value not in (None, "", [], {})
                }
            )
        return CandidateRecoveryResult(attempt=last_attempt)
    response = with_browser_recovery_diagnostics(response, last_attempt)
    try:
        converted = response
        if kind.name == "figure":
            converted, _source_format = converted_figure_response(
                response,
                source_url=candidate.url,
                asset_budget=request_context.asset_budget,
                path_converter=request_context.path_converter,
            )
    except AssetBudgetExceeded as exc:
        return CandidateRecoveryResult(
            attempt=last_attempt,
            budget_error=exc,
            budget_response=response,
        )
    except ImageConversionFailure as exc:
        return CandidateRecoveryResult(
            attempt=conversion_failure_attempt(kind, asset, candidate, response, exc),
            conversion_degraded=True,
        )
    return CandidateRecoveryResult(
        attempt=last_attempt,
        resolution=resolution_from_attempt(
            asset=asset,
            attempt=AssetDownloadAttempt(
                candidate=candidate,
                response=converted,
                source_url=candidate.url,
            ),
            preview_url=preview_url,
            full_size_url=full_size_url,
        ),
    )


def browser_preview_upgrade(
    kind: AssetDownloadKind,
    asset: Mapping[str, Any],
    *,
    candidate_url: str,
    response: AssetFetchResponse,
    transport: HttpTransport,
    request_context: AssetRequestContext,
    document_fetcher: ImageDocumentFetcher | FileDocumentFetcher,
    preview_url: str,
    full_size_url: str,
) -> CandidateRecoveryResult:
    """Try browser-owned full-size alternatives without complicating the main loop."""

    conversion_degraded = False
    upgrade_targets = kind.upgrade_targets
    if upgrade_targets is None:
        return CandidateRecoveryResult()
    for upgrade_target in upgrade_targets(candidate_url, asset):
        if upgrade_target == candidate_url:
            continue
        budget_candidate = AssetDownloadCandidate(upgrade_target)
        try:
            fallback_response = fetch_document_fallback(
                kind,
                document_fetcher,
                upgrade_target,
                asset,
                transport=transport,
                request_context=request_context,
            )
        except AssetBudgetExceeded as exc:
            rollback_response_reservation(response)
            return CandidateRecoveryResult(
                budget_error=exc,
                budget_candidate=budget_candidate,
                conversion_degraded=conversion_degraded,
            )
        if fallback_response is None:
            continue
        try:
            if kind.name == "figure":
                fallback_response, _ = converted_figure_response(
                    fallback_response,
                    source_url=upgrade_target,
                    asset_budget=request_context.asset_budget,
                    path_converter=request_context.path_converter,
                )
        except AssetBudgetExceeded as exc:
            rollback_response_reservation(response)
            return CandidateRecoveryResult(
                budget_error=exc,
                budget_response=fallback_response,
                budget_candidate=budget_candidate,
                conversion_degraded=conversion_degraded,
            )
        except ImageConversionFailure:
            conversion_degraded = True
            continue
        rollback_response_reservation(response)
        return CandidateRecoveryResult(
            resolution=resolution_from_attempt(
                asset=asset,
                attempt=AssetDownloadAttempt(
                    candidate=budget_candidate,
                    response=fallback_response,
                    source_url=upgrade_target,
                    download_tier_override="playwright_canvas_fallback",
                ),
                preview_url=preview_url,
                full_size_url=full_size_url,
            ),
            conversion_degraded=conversion_degraded,
        )
    return CandidateRecoveryResult(conversion_degraded=conversion_degraded)


__all__ = [
    "AssetFetchPolicy",
    "CandidateRecoveryResult",
    "CandidateResolutionLoopState",
    "FileDocumentFetcher",
    "ImageDocumentFetcher",
    "blocked_response_attempt",
    "browser_asset_recovery_allowed",
    "browser_first_candidate_recovery",
    "browser_preview_upgrade",
    "budget_failure_resolution",
    "document_fetch_failure",
    "fetch_document_fallback",
    "preview_fallback_provenance",
    "recover_failed_candidate",
    "request_failure_attempt",
    "requires_caller_thread",
    "should_use_document_fetcher_for_candidate",
    "unsupported_scheme_failure",
    "with_browser_recovery_diagnostics",
    "with_conversion_provenance",
]
