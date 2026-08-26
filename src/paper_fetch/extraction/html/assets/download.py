"""Asset download helpers with typed asset kinds."""

from __future__ import annotations

import contextlib
from dataclasses import dataclass, replace
import hashlib
import json
from pathlib import Path
import threading
from typing import Any, Literal
import urllib.parse
import urllib.request
import uuid
from collections.abc import Callable, Mapping, Sequence

from ....asset_budget import (
    AssetBudget,
    AssetBudgetExceeded,
    AssetReservation,
    current_asset_budget,
)
from ....http import (
    DEFAULT_FULLTEXT_TIMEOUT_SECONDS,
    HttpTransport,
    RequestFailure,
    is_retryable_network_error,
    is_transient_http_status,
)
from ....http.headers import header_value
from ...image_payloads import image_dimensions_from_path
from ....image_tools import (
    ImageConversionFailure,
    convert_source_image_path_to_png,
    convert_source_image_response_to_png,
    source_image_format_from_payload,
)
from ....models.schema import AssetProfile
from ....reason_codes import (
    ASSET_BYTES_PER_ASSET_EXCEEDED,
    ASSET_BYTES_TOTAL_EXCEEDED,
    ASSET_CANCELLED,
    ASSET_FILE_LIMIT_EXCEEDED,
    BROWSER_STREAM_UNAVAILABLE,
)
from ....utils import (
    build_asset_output_path,
    empty_asset_results,
    normalize_text,
    sanitize_filename,
    save_payload,
)
from ._kind import (
    FIGURE_KIND,
    SUPPLEMENTARY_KIND,
    AssetDownloadKind,
    active_seed_urls as _active_seed_urls,
    failure_from_document_fetch as _failure_from_document_fetch,
    is_preview_candidate as _is_preview_candidate,
    requires_image_payload as _requires_image_payload,
    resolved_full_size_url as _resolved_full_size_url,
)
from .dom import (
    SUPPLEMENTARY_BLOCKING_BODY_TOKENS,
    SUPPLEMENTARY_BLOCKING_TITLE_TOKENS,
    _CLOUDFLARE_CHALLENGE_TOKENS,
    _response_dimensions,
    looks_like_full_size_asset_url,
    preview_dimensions_are_acceptable,
)
from .figures import FigurePageFetcher, figure_download_candidates
from .identity import html_asset_is_supplementary
from .requester import (
    PinnedAssetSession,
    build_cookie_seeded_opener as _build_cookie_seeded_opener,
    cookie_header_for_url as _cookie_header_for_url,
    request_with_opener as _request_with_opener,
)
from .state import (
    AssetDownloadAttempt as _AssetDownloadAttempt,
    AssetDownloadCandidate as _AssetDownloadCandidate,
    AssetDownloadFailure as _AssetDownloadFailure,
    AssetDownloadResolution as _AssetDownloadResolution,
    asset_failure as _asset_failure,
    resolve_and_collect_downloads_as_completed as _resolve_and_collect_downloads_as_completed,
    resolution_from_attempt as _resolution_from_attempt,
)

ImageDocumentFetcher = Callable[[str, Mapping[str, Any]], dict[str, Any] | None]
FileDocumentFetcher = Callable[[str, Mapping[str, Any]], dict[str, Any] | None]
AssetFetchPolicy = Literal["browser_first", "direct_then_browser"]


@dataclass(frozen=True)
class _AssetRequestContext:
    headers: Mapping[str, str] | None
    user_agent: str
    browser_context_seed: Mapping[str, Any] | None
    browser_cookies: list[dict[str, Any]]
    active_seed_urls: list[str]
    cookie_opener_builder: Callable[..., urllib.request.OpenerDirector | None]
    opener_requester: Callable[..., dict[str, Any]]
    fetch_policy: AssetFetchPolicy
    asset_budget: AssetBudget
    staging_dir: Path
    session_pool: _AssetSessionPool
    use_legacy_requester: bool = False


@dataclass(frozen=True)
class AssetResolutionOptions:
    """Dependencies and runtime state for one asset resolution."""

    transport: HttpTransport
    headers: Mapping[str, str] | None
    user_agent: str
    browser_context_seed: Mapping[str, Any] | None
    browser_cookies: list[dict[str, Any]]
    active_seed_urls: list[str]
    document_fetcher: ImageDocumentFetcher | FileDocumentFetcher | None
    cookie_opener_builder: Callable[..., urllib.request.OpenerDirector | None]
    opener_requester: Callable[..., dict[str, Any]]
    candidate_url_resolver: Callable[[Mapping[str, Any]], list[str]] | None = None
    fetch_policy: AssetFetchPolicy = "browser_first"
    asset_budget: AssetBudget | None = None
    staging_dir: Path | None = None
    session_pool: _AssetSessionPool | None = None
    use_legacy_requester: bool = False


@dataclass(frozen=True)
class AssetDownloadOptions:
    """Optional fetch, safety, and execution controls for ``download_assets``."""

    headers: Mapping[str, str] | None = None
    browser_context_seed: Mapping[str, Any] | None = None
    seed_urls: Sequence[str] | None = None
    figure_page_fetcher: FigurePageFetcher | None = None
    candidate_builder: Callable[..., list[str]] | None = None
    document_fetcher: ImageDocumentFetcher | FileDocumentFetcher | None = None
    image_document_fetcher: ImageDocumentFetcher | None = None
    file_document_fetcher: FileDocumentFetcher | None = None
    cookie_opener_builder: (
        Callable[..., urllib.request.OpenerDirector | None] | None
    ) = None
    opener_requester: Callable[..., dict[str, Any]] | None = None
    asset_download_concurrency: int | None = None
    fetch_policy: AssetFetchPolicy = "browser_first"
    asset_budget: AssetBudget | None = None
    route_concurrency_cap: int | None = None
    allowed_hosts: Sequence[str] | None = None
    provider_name: str | None = None
    artifact_store: Any | None = None
    runtime_context: Any | None = None
    asset_session_pool: Any | None = None


def _coerce_asset_download_options(
    options: AssetDownloadOptions | None,
    legacy_options: Mapping[str, Any],
) -> AssetDownloadOptions:
    if not legacy_options:
        return options or AssetDownloadOptions()
    known = frozenset(AssetDownloadOptions.__dataclass_fields__)
    unexpected = sorted(set(legacy_options) - known)
    if unexpected:
        raise TypeError(
            "unexpected download_assets option(s): " + ", ".join(unexpected)
        )
    return replace(options or AssetDownloadOptions(), **dict(legacy_options))


class _AssetSessionPool:
    """Create one pinned, cookie-aware session per asset worker thread."""

    def __init__(
        self,
        transport: HttpTransport,
        *,
        provider_name: str | None,
        route_name: str | None,
        browser_cookies: list[dict[str, Any]],
        seed_urls: list[str],
        headers: Mapping[str, str] | None,
        allowed_hosts: tuple[str, ...] | None,
    ) -> None:
        self._transport = transport
        self._provider_name = normalize_text(provider_name).lower() or None
        self._browser_cookies = [dict(cookie) for cookie in browser_cookies]
        self._seed_urls = list(seed_urls)
        self._headers = dict(headers or {})
        self._allowed_hosts = allowed_hosts
        self._route_name = normalize_text(route_name).lower() or None
        self._timeout = DEFAULT_FULLTEXT_TIMEOUT_SECONDS
        if self._provider_name:
            from ....provider_catalog import (
                compile_route_execution_policy,
                compile_route_execution_policy_for_kind,
            )

            try:
                execution_policy = (
                    compile_route_execution_policy(
                        self._provider_name, self._route_name
                    )
                    if self._route_name
                    else compile_route_execution_policy_for_kind(
                        self._provider_name, "assets"
                    )
                )
            except ValueError:
                execution_policy = None
            if execution_policy is not None:
                self._route_name = execution_policy.route
                self._timeout = execution_policy.timeout_seconds
        self._local = threading.local()
        self._sessions: list[PinnedAssetSession] = []
        self._lock = threading.Lock()

    def current(self) -> PinnedAssetSession:
        session = getattr(self._local, "session", None)
        if isinstance(session, PinnedAssetSession):
            return session
        session = PinnedAssetSession(
            self._transport,
            browser_cookies=self._browser_cookies,
            seed_urls=self._seed_urls,
            headers=self._headers,
            allowed_hosts=self._allowed_hosts,
            provider_name=self._provider_name,
            route_name=self._route_name,
            timeout=self._timeout,
        )
        self._local.session = session
        with self._lock:
            self._sessions.append(session)
        return session

    @property
    def sessions(self) -> tuple[PinnedAssetSession, ...]:
        with self._lock:
            return tuple(self._sessions)


def _asset_session_pool_cache_key(
    transport: HttpTransport,
    *,
    provider_name: str | None,
    route_name: str | None,
    browser_cookies: list[dict[str, Any]],
    seed_urls: list[str],
    headers: Mapping[str, str] | None,
    allowed_hosts: tuple[str, ...] | None,
) -> tuple[str, str, int, str]:
    payload = json.dumps(
        {
            "provider_name": normalize_text(provider_name).lower(),
            "route_name": normalize_text(route_name).lower(),
            "browser_cookies": browser_cookies,
            "seed_urls": seed_urls,
            "headers": dict(headers or {}),
            "allowed_hosts": list(allowed_hosts or ()),
        },
        ensure_ascii=False,
        sort_keys=True,
        default=str,
    ).encode("utf-8", errors="surrogatepass")
    return (
        "asset_download",
        "pinned_session_pool",
        id(transport),
        hashlib.sha256(payload).hexdigest(),
    )


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


def _requires_caller_thread(fetcher: Any) -> bool:
    return bool(getattr(fetcher, "requires_caller_thread", False))


def _fetch_document_fallback(
    kind: AssetDownloadKind,
    fetcher: ImageDocumentFetcher | FileDocumentFetcher | None,
    candidate_url: str,
    asset: Mapping[str, Any],
    *,
    transport: HttpTransport | None = None,
    request_context: _AssetRequestContext | None = None,
) -> dict[str, Any] | None:
    if fetcher is None:
        return None
    if kind.name == "figure" and not _requires_image_payload(asset):
        return None
    try:
        response = fetcher(candidate_url, asset)
    except Exception:
        return None
    if not response:
        return None
    stream_url = normalize_text(
        str(response.get("_paper_fetch_browser_stream_url") or "")
    )
    if stream_url:
        parsed_stream_url = urllib.parse.urlsplit(stream_url)
        if (
            transport is None
            or request_context is None
            or parsed_stream_url.scheme.lower() not in {"http", "https"}
        ):
            _record_browser_stream_failure(
                fetcher,
                candidate_url,
                reason=BROWSER_STREAM_UNAVAILABLE,
            )
            return None
        browser_cookies = response.get("_paper_fetch_browser_cookies")
        if isinstance(browser_cookies, list):
            request_context.session_pool.current().import_browser_cookies(
                [
                    dict(cookie)
                    for cookie in browser_cookies
                    if isinstance(cookie, Mapping)
                ]
            )
        request_headers = kind.request_headers(
            request_context.headers,
            request_context.user_agent,
            request_context.browser_context_seed,
        )
        descriptor_headers = response.get("_paper_fetch_direct_headers")
        if isinstance(descriptor_headers, Mapping):
            for header_name in ("Accept", "Referer"):
                descriptor_value = descriptor_headers.get(header_name)
                if descriptor_value:
                    request_headers[header_name] = str(descriptor_value)
        try:
            streamed = _stream_asset_candidate(
                kind,
                transport,
                stream_url,
                request_headers=request_headers,
                request_context=request_context,
            )
        except AssetBudgetExceeded:
            raise
        except Exception as exc:
            _record_browser_stream_failure(
                fetcher,
                candidate_url,
                reason=BROWSER_STREAM_UNAVAILABLE,
                error_message=normalize_text(str(exc)),
            )
            return None
        for key in (
            "_paper_fetch_browser_backend",
            "_paper_fetch_final_fetcher",
            "dimensions",
        ):
            if key in response:
                streamed[key] = response[key]
        return streamed
    if bool(getattr(type(fetcher), "browser_stream_discovery", False)):
        _record_browser_stream_failure(
            fetcher,
            candidate_url,
            reason=BROWSER_STREAM_UNAVAILABLE,
        )
        return None
    body = response.get("body", b"")
    if not isinstance(body, (bytes, bytearray)):
        return None
    content_type = header_value(response.get("headers"), "content-type")
    if not kind.accepts_response(content_type, bytes(body)):
        return None
    recovered = dict(response)
    browser_backend = normalize_text(str(getattr(fetcher, "browser_backend", "")))
    if browser_backend:
        recovered["_paper_fetch_browser_backend"] = browser_backend
    return recovered


def _record_browser_stream_failure(
    fetcher: Any,
    source_url: str,
    *,
    reason: str,
    error_message: str = "",
) -> None:
    recorder = getattr(fetcher, "record_stream_failure", None)
    if not callable(recorder):
        return
    with contextlib.suppress(Exception):
        recorder(
            source_url,
            reason=reason,
            error_message=error_message,
        )


def _with_browser_recovery_diagnostics(
    response: Mapping[str, Any],
    direct_attempt: _AssetDownloadAttempt | None,
) -> dict[str, Any]:
    recovered = dict(response)
    direct_diagnostic = (
        direct_attempt.failure.diagnostic
        if direct_attempt is not None and direct_attempt.failure is not None
        else {}
    )
    backend = normalize_text(str(recovered.get("_paper_fetch_browser_backend") or ""))
    recovered["_paper_fetch_final_fetcher"] = backend or "selected_browser"
    recovered["_paper_fetch_recovery_attempts"] = [
        {
            key: value
            for key, value in {
                "stage": "direct",
                "status": direct_diagnostic.get("status"),
                "content_type": direct_diagnostic.get("content_type"),
                "reason": direct_diagnostic.get("reason"),
                "error_category": direct_diagnostic.get("error_category"),
            }.items()
            if value not in (None, "")
        },
        {
            key: value
            for key, value in {
                "stage": "browser",
                "browser_backend": backend or None,
                "status": int(recovered.get("status_code") or 0) or None,
                "content_type": header_value(recovered.get("headers"), "content-type"),
                "reason": "recovered",
                "final_fetcher": backend or "selected_browser",
            }.items()
            if value not in (None, "")
        },
    ]
    return recovered


def _candidate_source_image_format(candidate_url: str) -> str:
    return source_image_format_from_payload(b"", source_url=candidate_url)


def _should_use_figure_document_fetcher_for_candidate(
    kind: AssetDownloadKind,
    candidate_url: str,
    document_fetcher: ImageDocumentFetcher | FileDocumentFetcher | None,
) -> bool:
    if kind.name != "figure" or document_fetcher is None:
        return False
    return _candidate_source_image_format(candidate_url) not in {"eps", "tiff"}


def _converted_figure_response(
    response: Mapping[str, Any],
    *,
    source_url: str,
    asset_budget: AssetBudget | None = None,
) -> tuple[dict[str, Any], str]:
    if response.get("_paper_fetch_streamed"):
        staging_value = response.get("staging_path")
        source_path = Path(staging_value) if isinstance(staging_value, str) else None
        source_reservation = response.get("_paper_fetch_asset_reservation")
        if (
            source_path is None
            or not source_path.is_file()
            or not isinstance(source_reservation, AssetReservation)
            or asset_budget is None
        ):
            return dict(response), ""
        converted_path = _unique_asset_staging_path(source_path.parent)
        converted_reservation = asset_budget.reserve()
        converted_reservation.register_staging(converted_path)
        try:
            path_conversion = convert_source_image_path_to_png(
                source_path,
                converted_path,
                content_type=header_value(response.get("headers"), "content-type"),
                source_url=source_url,
                max_output_bytes=asset_budget.max_bytes_per_asset,
            )
            if path_conversion is None:
                converted_reservation.rollback()
                return dict(response), ""
            converted_reservation.declare_content_length(path_conversion.output_bytes)
            converted_reservation.consume(path_conversion.output_bytes)
            dimensions = image_dimensions_from_path(converted_path)
            if dimensions is not None:
                converted_reservation.validate_pixels(*dimensions)
            with converted_path.open("rb") as converted_stream:
                preview = converted_stream.read(8192)
        except ImageConversionFailure as exc:
            converted_reservation.rollback()
            if exc.reason_code == ASSET_BYTES_PER_ASSET_EXCEEDED:
                diagnostic = {
                    "max_bytes_per_asset": asset_budget.max_bytes_per_asset,
                    "boundary": "image_conversion",
                }
                asset_budget.cancel(exc.reason_code, diagnostic=diagnostic)
                raise AssetBudgetExceeded(
                    exc.reason_code,
                    diagnostic=diagnostic,
                    fatal=True,
                ) from exc
            raise
        except BaseException:
            converted_reservation.rollback()
            raise
        converted = dict(response)
        converted_headers = dict(response.get("headers") or {})
        converted_headers["content-type"] = path_conversion.content_type
        converted.update(
            {
                "headers": converted_headers,
                "body": preview,
                "body_preview": preview,
                "staging_path": str(converted_path),
                "downloaded_bytes": path_conversion.output_bytes,
                "_paper_fetch_asset_reservation": converted_reservation,
                "_paper_fetch_original_staging_path": str(source_path),
                "_paper_fetch_original_reservation": source_reservation,
                "_paper_fetch_original_downloaded_bytes": int(
                    response.get("downloaded_bytes") or source_path.stat().st_size
                ),
                "_paper_fetch_original_content_type": header_value(
                    response.get("headers"), "content-type"
                ),
                "_paper_fetch_original_source_format": path_conversion.source_format,
                "_paper_fetch_conversion_tool": path_conversion.tool,
            }
        )
        if dimensions is not None:
            converted["dimensions"] = {
                "width": dimensions[0],
                "height": dimensions[1],
            }
        return converted, path_conversion.source_format
    source_format = source_image_format_from_payload(
        response.get("body", b""),
        content_type=header_value(response.get("headers"), "content-type"),
        source_url=source_url,
    )
    if source_format not in {"eps", "tiff"}:
        return dict(response), ""
    memory_conversion = convert_source_image_response_to_png(
        response, source_url=source_url
    )
    if memory_conversion is None:
        return dict(response), ""
    converted = dict(response)
    converted_headers = dict(response.get("headers") or {})
    converted_headers["content-type"] = memory_conversion.content_type
    converted["headers"] = converted_headers
    converted["body"] = memory_conversion.body
    converted["_paper_fetch_original_body"] = response.get("body", b"")
    converted["_paper_fetch_original_content_type"] = header_value(
        response.get("headers"),
        "content-type",
    )
    converted["_paper_fetch_original_source_format"] = memory_conversion.source_format
    converted["_paper_fetch_conversion_tool"] = memory_conversion.tool
    return converted, memory_conversion.source_format


def _attach_browser_recovery_diagnostics(
    download: dict[str, Any], response: Mapping[str, Any]
) -> None:
    browser_backend = normalize_text(
        str(response.get("_paper_fetch_browser_backend") or "")
    )
    final_fetcher = normalize_text(
        str(response.get("_paper_fetch_final_fetcher") or "")
    )
    if browser_backend:
        download["browser_backend"] = browser_backend
        final_fetcher = final_fetcher or browser_backend
    if final_fetcher:
        download["final_fetcher"] = final_fetcher
    attempts = response.get("_paper_fetch_recovery_attempts")
    if not isinstance(attempts, list):
        return
    normalized_attempts = [
        dict(attempt) for attempt in attempts if isinstance(attempt, Mapping)
    ]
    if not normalized_attempts:
        return
    download["recovery_attempts"] = normalized_attempts
    browser_attempt = next(
        (
            attempt
            for attempt in reversed(normalized_attempts)
            if attempt.get("stage") == "browser"
        ),
        {},
    )
    if browser_attempt.get("browser_backend"):
        download["browser_backend"] = browser_attempt["browser_backend"]
    if browser_attempt.get("final_fetcher"):
        download["final_fetcher"] = browser_attempt["final_fetcher"]


def _conversion_failure_attempt(
    kind: AssetDownloadKind,
    asset: Mapping[str, Any],
    candidate: _AssetDownloadCandidate,
    response: Mapping[str, Any],
    exc: ImageConversionFailure,
) -> _AssetDownloadAttempt:
    _rollback_response_reservation(response)
    return _AssetDownloadAttempt(
        candidate=candidate,
        failure=_asset_failure(
            kind.failure_template(
                asset,
                candidate.url,
                status=response.get("status_code"),
                content_type=header_value(response.get("headers"), "content-type"),
                final_url=normalize_text(str(response.get("url") or candidate.url)),
                reason=f"{exc.reason_code}: {exc}",
            )
        ),
    )


def _document_fetch_failure(
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


def _unsupported_scheme_failure(
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


def _unique_asset_staging_path(staging_dir: Path) -> Path:
    return staging_dir / f".paper-fetch-asset-{uuid.uuid4().hex}.part"


def _transport_supports_pinned_streaming(transport: object) -> bool:
    return bool(
        getattr(transport, "_pinned_streaming_ready", False) is True
        and callable(getattr(transport, "stream_to_file", None))
    )


def _rollback_response_reservation(response: Mapping[str, Any] | None) -> None:
    if not isinstance(response, Mapping):
        return
    for key in (
        "_paper_fetch_asset_reservation",
        "_paper_fetch_original_reservation",
    ):
        reservation = response.get(key)
        if isinstance(reservation, AssetReservation):
            reservation.rollback()


def _stream_asset_candidate(
    kind: AssetDownloadKind,
    transport: HttpTransport,
    candidate_url: str,
    *,
    request_headers: Mapping[str, str],
    request_context: _AssetRequestContext,
) -> dict[str, Any]:
    session = request_context.session_pool.current()
    if request_context.fetch_policy == "browser_first":
        session.ensure_seeded()
    last_failure: RequestFailure | None = None
    request_policy = session.request_policy_for(
        candidate_url,
        max_response_bytes=request_context.asset_budget.max_bytes_per_asset,
        max_compressed_response_bytes=request_context.asset_budget.max_bytes_per_asset,
    )
    max_stream_attempts = (
        max(0, int(request_policy.transient_retries or 0)) + 1
        if request_policy.retry_on_transient
        else 1
    )
    for stream_attempt in range(max_stream_attempts):
        reservation = request_context.asset_budget.reserve()
        staging_path = _unique_asset_staging_path(request_context.staging_dir)
        reservation.register_staging(staging_path)
        try:
            # A prior validated redirect/final response may have refreshed this
            # worker-local jar, so rebuild Cookie immediately before each try.
            active_headers = session.request_headers_for(candidate_url, request_headers)
            response = transport.stream_to_file(
                "GET",
                candidate_url,
                staging_path,
                headers=active_headers,
                # Transient retries live in this layer so partial-body retries
                # receive a fresh exclusive staging path and reservation. The
                # attempt count/backoff still comes from the compiled policy.
                retry_on_transient=False,
                transient_retries=0,
                request_policy=request_policy,
                on_content_length=reservation.declare_content_length,
                on_chunk=reservation.consume,
                on_response_headers=session.observe_response_headers,
                request_headers_provider=session.prepare_hop_headers,
            )
            dimensions = (
                image_dimensions_from_path(staging_path)
                if kind.name == "figure"
                else None
            )
            if dimensions is not None:
                reservation.validate_pixels(*dimensions)
            streamed = dict(response)
            # Only a fixed-size prefix is retained for signature/challenge
            # diagnostics. The binary remains solely in the staging file.
            streamed["body"] = bytes(response.get("body_preview") or b"")
            streamed["_paper_fetch_streamed"] = True
            streamed["_paper_fetch_asset_reservation"] = reservation
            if dimensions is not None:
                streamed["dimensions"] = {
                    "width": dimensions[0],
                    "height": dimensions[1],
                }
            return streamed
        except AssetBudgetExceeded:
            reservation.rollback()
            raise
        except RequestFailure as exc:
            reservation.rollback()
            last_failure = exc
            reason_code = normalize_text(str(getattr(exc, "reason_code", "") or ""))
            if reason_code in {
                ASSET_BYTES_PER_ASSET_EXCEEDED,
                ASSET_BYTES_TOTAL_EXCEEDED,
            }:
                request_context.asset_budget.cancel(
                    reason_code,
                    diagnostic={
                        "boundary": "asset_stream_transport",
                    },
                )
                raise
            retryable = is_retryable_network_error(exc) or is_transient_http_status(
                exc.status_code
            )
            if stream_attempt + 1 < max_stream_attempts and retryable:
                sleeper = getattr(transport, "_cancellable_sleep", None)
                if callable(sleeper):
                    sleeper(
                        request_policy.transient_backoff_base_seconds
                        * (2**stream_attempt)
                    )
                continue
            raise
        except BaseException:
            reservation.rollback()
            raise
    assert last_failure is not None
    raise last_failure


def _request_asset_candidate(
    kind: AssetDownloadKind,
    transport: HttpTransport,
    candidate_url: str,
    *,
    request_context: _AssetRequestContext,
) -> dict[str, Any]:
    request_headers = kind.request_headers(
        request_context.headers,
        request_context.user_agent,
        request_context.browser_context_seed,
    )
    if _transport_supports_pinned_streaming(transport):
        return _stream_asset_candidate(
            kind,
            transport,
            candidate_url,
            request_headers=request_headers,
            request_context=request_context,
        )

    # Compatibility path for injected unit-test transports. Runtime transports
    # always expose pinned streaming and never reach urllib here.
    cookie_header = _cookie_header_for_url(
        request_context.browser_cookies, candidate_url
    )
    if cookie_header:
        request_headers["Cookie"] = cookie_header

    browser_first = request_context.fetch_policy == "browser_first"
    opener_seed_urls = request_context.active_seed_urls if browser_first else []
    opener = (
        request_context.cookie_opener_builder(
            opener_seed_urls,
            headers=request_headers,
            timeout=DEFAULT_FULLTEXT_TIMEOUT_SECONDS,
            browser_cookies=request_context.browser_cookies,
            cancel_check=lambda: bool(getattr(transport, "cancelled", False)),
            force=kind.name == "supplementary" and browser_first,
        )
        if request_context.use_legacy_requester
        and browser_first
        and (
            request_context.browser_cookies
            or request_context.active_seed_urls
            or kind.name == "supplementary"
        )
        else None
    )
    if opener is not None:
        return request_context.opener_requester(
            opener,
            candidate_url,
            headers=request_headers,
            timeout=DEFAULT_FULLTEXT_TIMEOUT_SECONDS,
            cancel_check=lambda: bool(getattr(transport, "cancelled", False)),
        )
    return transport.request(
        "GET",
        candidate_url,
        headers=request_headers,
        timeout=DEFAULT_FULLTEXT_TIMEOUT_SECONDS,
        retry_on_rate_limit=True,
        retry_on_transient=True,
    )


def _request_failure_attempt(
    kind: AssetDownloadKind,
    asset: Mapping[str, Any],
    candidate: _AssetDownloadCandidate,
    exc: RequestFailure,
) -> _AssetDownloadAttempt:
    content_type = header_value(exc.headers, "content-type")
    body = exc.body if isinstance(exc.body, (bytes, bytearray)) else b""
    return _AssetDownloadAttempt(
        candidate=candidate,
        failure=_asset_failure(
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


def _blocked_response_attempt(
    kind: AssetDownloadKind,
    asset: Mapping[str, Any],
    candidate: _AssetDownloadCandidate,
    response: Mapping[str, Any],
    source_url: str,
    reason: str,
) -> _AssetDownloadAttempt:
    body = response.get("body", b"")
    if not isinstance(body, (bytes, bytearray)):
        body = b""
    return _AssetDownloadAttempt(
        candidate=candidate,
        failure=_asset_failure(
            kind.failure_template(
                asset,
                source_url,
                status=response.get("status_code"),
                content_type=header_value(response.get("headers"), "content-type"),
                final_url=normalize_text(str(response.get("url") or source_url)),
                body=body,
                reason=reason,
            )
        ),
    )


def _should_retry_seeded_full_size_candidate(
    candidate_url: str,
    *,
    preview_url: str,
    full_size_url: str,
    active_seed_urls: list[str],
    browser_cookies: list[dict[str, Any]],
) -> bool:
    if not active_seed_urls and not browser_cookies:
        return False
    candidate = normalize_text(candidate_url)
    if not candidate or _is_preview_candidate(
        candidate,
        preview_url=preview_url,
        full_size_url=full_size_url,
    ):
        return False
    if full_size_url and candidate == full_size_url:
        return True
    if preview_url and candidate != preview_url:
        return True
    return looks_like_full_size_asset_url(candidate.lower())


def _resolution_preview_fields(
    kind: AssetDownloadKind,
    asset: Mapping[str, Any],
    candidate_urls: list[str],
) -> tuple[str, str]:
    if kind.name != "figure":
        return "", ""
    preview_url = normalize_text(
        str(
            asset.get("preview_url")
            or asset.get("url")
            or asset.get("original_url")
            or asset.get("link")
            or ""
        )
    )
    full_size_url = _resolved_full_size_url(
        asset, preview_url=preview_url, candidate_urls=candidate_urls
    )
    return preview_url, full_size_url


def _retry_seeded_figure_candidate(
    kind: AssetDownloadKind,
    transport: HttpTransport,
    asset: Mapping[str, Any],
    candidate: _AssetDownloadCandidate,
    *,
    request_context: _AssetRequestContext,
    preview_url: str,
    full_size_url: str,
    last_attempt: _AssetDownloadAttempt,
) -> tuple[_AssetDownloadAttempt, _AssetDownloadResolution | None]:
    if kind.name != "figure" or not _should_retry_seeded_full_size_candidate(
        candidate.url,
        preview_url=preview_url,
        full_size_url=full_size_url,
        active_seed_urls=request_context.active_seed_urls,
        browser_cookies=request_context.browser_cookies,
    ):
        return last_attempt, None
    try:
        response = _request_asset_candidate(
            kind,
            transport,
            candidate.url,
            request_context=request_context,
        )
    except RequestFailure as exc:
        return _request_failure_attempt(kind, asset, candidate, exc), None
    body = response.get("body", b"")
    if not isinstance(body, (bytes, bytearray)):
        body = b""
    block_reason = kind.response_block_reason(
        header_value(response.get("headers"), "content-type"), bytes(body)
    )
    if block_reason:
        _rollback_response_reservation(response)
        return _blocked_response_attempt(
            kind, asset, candidate, response, candidate.url, block_reason
        ), None
    return last_attempt, _resolution_from_attempt(
        asset=asset,
        attempt=_AssetDownloadAttempt(
            candidate=candidate, response=response, source_url=candidate.url
        ),
        preview_url=preview_url,
        full_size_url=full_size_url,
    )


def _asset_request_context(
    kind: AssetDownloadKind,
    asset: Mapping[str, Any],
    options: AssetResolutionOptions,
) -> _AssetRequestContext:
    active_budget = options.asset_budget or current_asset_budget() or AssetBudget()
    staging_root = options.staging_dir or Path.cwd()
    output_subdir = kind.output_subdir(asset)
    active_staging_dir = (
        staging_root / output_subdir if output_subdir is not None else staging_root
    )
    session_pool = options.session_pool or _AssetSessionPool(
        options.transport,
        provider_name=None,
        route_name=None,
        browser_cookies=options.browser_cookies,
        seed_urls=options.active_seed_urls,
        headers=options.headers,
        allowed_hosts=None,
    )
    return _AssetRequestContext(
        headers=options.headers,
        user_agent=options.user_agent,
        browser_context_seed=options.browser_context_seed,
        browser_cookies=options.browser_cookies,
        active_seed_urls=options.active_seed_urls,
        cookie_opener_builder=options.cookie_opener_builder,
        opener_requester=options.opener_requester,
        fetch_policy=options.fetch_policy,
        asset_budget=active_budget,
        staging_dir=active_staging_dir,
        session_pool=session_pool,
        use_legacy_requester=options.use_legacy_requester,
    )


@dataclass(frozen=True)
class _CandidateRecoveryResult:
    attempt: _AssetDownloadAttempt | None = None
    resolution: _AssetDownloadResolution | None = None
    conversion_degraded: bool = False
    budget_error: AssetBudgetExceeded | None = None
    budget_response: Mapping[str, Any] | None = None


def _with_conversion_provenance(
    resolution: _AssetDownloadResolution,
    *,
    conversion_degraded: bool,
) -> _AssetDownloadResolution:
    if not conversion_degraded:
        return resolution
    return replace(resolution, provenance=("conversion_degraded",))


def _browser_first_candidate_recovery(
    kind: AssetDownloadKind,
    asset: Mapping[str, Any],
    candidate: _AssetDownloadCandidate,
    *,
    transport: HttpTransport,
    request_context: _AssetRequestContext,
    document_fetcher: ImageDocumentFetcher | FileDocumentFetcher | None,
    preview_url: str,
    full_size_url: str,
) -> _CandidateRecoveryResult:
    response = _fetch_document_fallback(
        kind,
        document_fetcher,
        candidate.url,
        asset,
        transport=transport,
        request_context=request_context,
    )
    if response is None:
        failure = _document_fetch_failure(document_fetcher, candidate.url)
        return _CandidateRecoveryResult(
            attempt=_AssetDownloadAttempt(
                candidate=candidate,
                failure=_asset_failure(
                    _failure_from_document_fetch(kind, asset, candidate.url, failure)
                ),
            )
        )
    try:
        converted, _source_format = _converted_figure_response(
            response,
            source_url=candidate.url,
            asset_budget=request_context.asset_budget,
        )
    except AssetBudgetExceeded as exc:
        return _CandidateRecoveryResult(
            budget_error=exc,
            budget_response=response,
        )
    except ImageConversionFailure as exc:
        return _CandidateRecoveryResult(
            attempt=_conversion_failure_attempt(kind, asset, candidate, response, exc),
            conversion_degraded=True,
        )
    return _CandidateRecoveryResult(
        resolution=_resolution_from_attempt(
            asset=asset,
            attempt=_AssetDownloadAttempt(
                candidate=candidate,
                response=converted,
                source_url=candidate.url,
            ),
            preview_url=preview_url,
            full_size_url=full_size_url,
        )
    )


def _recover_failed_candidate(
    kind: AssetDownloadKind,
    asset: Mapping[str, Any],
    candidate: _AssetDownloadCandidate,
    *,
    transport: HttpTransport,
    request_context: _AssetRequestContext,
    document_fetcher: ImageDocumentFetcher | FileDocumentFetcher | None,
    last_attempt: _AssetDownloadAttempt,
    preview_url: str,
    full_size_url: str,
    recovery_allowed: bool,
) -> _CandidateRecoveryResult:
    retry_attempt, retry_resolution = _retry_seeded_figure_candidate(
        kind,
        transport,
        asset,
        candidate,
        request_context=request_context,
        preview_url=preview_url,
        full_size_url=full_size_url,
        last_attempt=last_attempt,
    )
    if retry_resolution is not None:
        return _CandidateRecoveryResult(
            attempt=retry_attempt,
            resolution=retry_resolution,
        )
    if not recovery_allowed:
        return _CandidateRecoveryResult(attempt=retry_attempt)
    response = _fetch_document_fallback(
        kind,
        document_fetcher,
        candidate.url,
        asset,
        transport=transport,
        request_context=request_context,
    )
    if response is None:
        fetch_failure = _document_fetch_failure(document_fetcher, candidate.url)
        if fetch_failure and retry_attempt.failure is not None:
            retry_attempt.failure.diagnostic.update(fetch_failure)
        return _CandidateRecoveryResult(attempt=retry_attempt)
    response = _with_browser_recovery_diagnostics(response, retry_attempt)
    try:
        converted, _source_format = _converted_figure_response(
            response,
            source_url=candidate.url,
            asset_budget=request_context.asset_budget,
        )
    except AssetBudgetExceeded as exc:
        return _CandidateRecoveryResult(
            attempt=retry_attempt,
            budget_error=exc,
            budget_response=response,
        )
    except ImageConversionFailure as exc:
        return _CandidateRecoveryResult(
            attempt=_conversion_failure_attempt(kind, asset, candidate, response, exc),
            conversion_degraded=True,
        )
    return _CandidateRecoveryResult(
        attempt=retry_attempt,
        resolution=_resolution_from_attempt(
            asset=asset,
            attempt=_AssetDownloadAttempt(
                candidate=candidate,
                response=converted,
                source_url=candidate.url,
            ),
            preview_url=preview_url,
            full_size_url=full_size_url,
        ),
    )


def resolve_asset_download(
    kind: AssetDownloadKind,
    asset: Mapping[str, Any],
    *,
    options: AssetResolutionOptions | None = None,
    **legacy_options: Any,
) -> _AssetDownloadResolution:
    if options is not None and legacy_options:
        raise TypeError(
            "options cannot be combined with legacy asset resolver keywords"
        )
    active_options = options or AssetResolutionOptions(**legacy_options)
    transport = active_options.transport
    request_context = _asset_request_context(kind, asset, active_options)
    active_budget = request_context.asset_budget
    document_fetcher = active_options.document_fetcher
    fetch_policy = active_options.fetch_policy
    conversion_degraded = False
    candidate_urls = (
        active_options.candidate_url_resolver or kind.candidate_url_resolver
    )(asset)
    preview_url, full_size_url = _resolution_preview_fields(kind, asset, candidate_urls)

    def budget_failure_resolution(
        exc: AssetBudgetExceeded,
        candidate: _AssetDownloadCandidate,
        response: Mapping[str, Any] | None = None,
    ) -> _AssetDownloadResolution:
        _rollback_response_reservation(response)
        attempt = _AssetDownloadAttempt(
            candidate=candidate,
            failure=_asset_failure(
                kind.failure_template(
                    asset,
                    candidate.url,
                    reason=exc.reason_code,
                )
            ),
        )
        if attempt.failure is not None:
            attempt.failure.diagnostic.update(exc.diagnostic)
        return _resolution_from_attempt(
            asset=asset,
            attempt=attempt,
            preview_url=preview_url,
            full_size_url=full_size_url,
        )

    if not candidate_urls:
        failure = (
            kind.failure_template(
                asset,
                "",
                reason="Supplementary asset did not include a downloadable URL.",
            )
            if kind.name == "supplementary"
            else None
        )
        return _resolution_from_attempt(
            asset=asset,
            attempt=(
                _AssetDownloadAttempt(
                    candidate=_AssetDownloadCandidate(""),
                    failure=_asset_failure(failure),
                )
                if failure is not None
                else None
            ),
            preview_url=preview_url,
            full_size_url=full_size_url,
        )

    last_attempt: _AssetDownloadAttempt | None = None
    for candidate_url in candidate_urls:
        candidate = _AssetDownloadCandidate(candidate_url)
        parsed = urllib.parse.urlparse(candidate_url)
        if parsed.scheme not in {"http", "https"}:
            last_attempt = _AssetDownloadAttempt(
                candidate=candidate,
                failure=_asset_failure(
                    _unsupported_scheme_failure(kind, asset, candidate_url)
                ),
            )
            continue

        if (
            fetch_policy == "browser_first"
            and _should_use_figure_document_fetcher_for_candidate(
                kind,
                candidate_url,
                document_fetcher,
            )
        ):
            recovery = _browser_first_candidate_recovery(
                kind,
                asset,
                candidate,
                transport=transport,
                request_context=request_context,
                document_fetcher=document_fetcher,
                preview_url=preview_url,
                full_size_url=full_size_url,
            )
            if recovery.budget_error is not None:
                return budget_failure_resolution(
                    recovery.budget_error,
                    candidate,
                    recovery.budget_response,
                )
            conversion_degraded |= recovery.conversion_degraded
            if recovery.resolution is not None:
                return _with_conversion_provenance(
                    recovery.resolution,
                    conversion_degraded=conversion_degraded,
                )
            last_attempt = recovery.attempt
            continue

        try:
            response = _request_asset_candidate(
                kind,
                transport,
                candidate_url,
                request_context=request_context,
            )
        except AssetBudgetExceeded as exc:
            return budget_failure_resolution(exc, candidate)
        except RequestFailure as exc:
            last_attempt = _request_failure_attempt(kind, asset, candidate, exc)
            recovery = _recover_failed_candidate(
                kind,
                asset,
                candidate,
                transport=transport,
                request_context=request_context,
                document_fetcher=document_fetcher,
                last_attempt=last_attempt,
                preview_url=preview_url,
                full_size_url=full_size_url,
                recovery_allowed=browser_asset_recovery_allowed(
                    status=exc.status_code,
                    content_type=header_value(exc.headers, "content-type"),
                    reason=str(exc),
                    error_category=str(getattr(exc, "error_category", "") or ""),
                ),
            )
            if recovery.budget_error is not None:
                return budget_failure_resolution(
                    recovery.budget_error,
                    candidate,
                    recovery.budget_response,
                )
            conversion_degraded |= recovery.conversion_degraded
            if recovery.resolution is not None:
                return _with_conversion_provenance(
                    recovery.resolution,
                    conversion_degraded=conversion_degraded,
                )
            last_attempt = recovery.attempt
            continue

        body = response.get("body", b"")
        if not isinstance(body, (bytes, bytearray)):
            body = b""
        content_type = header_value(response.get("headers"), "content-type")
        block_reason = kind.response_block_reason(content_type, bytes(body))
        if block_reason:
            _rollback_response_reservation(response)
            last_attempt = _blocked_response_attempt(
                kind,
                asset,
                candidate,
                response,
                candidate_url,
                block_reason,
            )
            recovery = _recover_failed_candidate(
                kind,
                asset,
                candidate,
                transport=transport,
                request_context=request_context,
                document_fetcher=document_fetcher,
                last_attempt=last_attempt,
                preview_url=preview_url,
                full_size_url=full_size_url,
                recovery_allowed=browser_asset_recovery_allowed(
                    status=int(response.get("status_code") or 0) or None,
                    content_type=content_type,
                    reason=block_reason,
                ),
            )
            if recovery.budget_error is not None:
                return budget_failure_resolution(
                    recovery.budget_error,
                    candidate,
                    recovery.budget_response,
                )
            conversion_degraded |= recovery.conversion_degraded
            if recovery.resolution is not None:
                return _with_conversion_provenance(
                    recovery.resolution,
                    conversion_degraded=conversion_degraded,
                )
            last_attempt = recovery.attempt
            continue

        if (
            fetch_policy == "browser_first"
            and kind.upgrade_targets is not None
            and document_fetcher is not None
            and _requires_image_payload(asset)
            and _is_preview_candidate(
                candidate_url,
                preview_url=preview_url,
                full_size_url=full_size_url,
            )
        ):
            for upgrade_target in kind.upgrade_targets(candidate_url, asset):
                if upgrade_target == candidate_url:
                    continue
                fallback_response = _fetch_document_fallback(
                    kind,
                    document_fetcher,
                    upgrade_target,
                    asset,
                    transport=transport,
                    request_context=request_context,
                )
                if fallback_response is not None:
                    try:
                        fallback_response, _ = _converted_figure_response(
                            fallback_response,
                            source_url=upgrade_target,
                            asset_budget=active_budget,
                        )
                    except AssetBudgetExceeded as exc:
                        _rollback_response_reservation(response)
                        return budget_failure_resolution(
                            exc,
                            _AssetDownloadCandidate(upgrade_target),
                            fallback_response,
                        )
                    except ImageConversionFailure:
                        conversion_degraded = True
                        continue
                    _rollback_response_reservation(response)
                    return _resolution_from_attempt(
                        asset=asset,
                        attempt=_AssetDownloadAttempt(
                            candidate=_AssetDownloadCandidate(upgrade_target),
                            response=fallback_response,
                            source_url=upgrade_target,
                            download_tier_override="playwright_canvas_fallback",
                        ),
                        preview_url=preview_url,
                        full_size_url=full_size_url,
                        provenance=("conversion_degraded",)
                        if conversion_degraded
                        else (),
                    )

        try:
            if fetch_policy == "direct_then_browser":
                response = {
                    **dict(response),
                    "_paper_fetch_final_fetcher": "direct_http",
                }
            response, _ = (
                _converted_figure_response(
                    response,
                    source_url=candidate_url,
                    asset_budget=active_budget,
                )
                if kind.name == "figure"
                else (dict(response), "")
            )
        except ImageConversionFailure as exc:
            conversion_degraded = True
            last_attempt = _conversion_failure_attempt(
                kind,
                asset,
                candidate,
                response,
                exc,
            )
            continue
        except AssetBudgetExceeded as exc:
            return budget_failure_resolution(exc, candidate, response)

        return _resolution_from_attempt(
            asset=asset,
            attempt=_AssetDownloadAttempt(
                candidate=candidate,
                response=response,
                source_url=candidate_url,
            ),
            preview_url=preview_url,
            full_size_url=full_size_url,
            provenance=("conversion_degraded",) if conversion_degraded else (),
        )

    return _resolution_from_attempt(
        asset=asset,
        attempt=last_attempt,
        preview_url=preview_url,
        full_size_url=full_size_url,
        provenance=("conversion_degraded",) if conversion_degraded else (),
    )


def save_asset_resolution(
    kind: AssetDownloadKind,
    resolved: _AssetDownloadResolution,
    *,
    asset_dir: Path,
    used_names_by_dir: dict[Path, set[str]],
    artifact_store: Any | None = None,
) -> dict[str, Any] | _AssetDownloadFailure:
    asset = resolved.asset
    response = resolved.response or {}
    source_url = normalize_text(resolved.source_url)
    final_url = _response_final_url(response, source_url)
    body = response.get("body", b"")
    staging_value = response.get("staging_path")
    staging_path = Path(staging_value) if isinstance(staging_value, str) else None
    original_staging_value = response.get("_paper_fetch_original_staging_path")
    original_staging_path = (
        Path(original_staging_value)
        if isinstance(original_staging_value, str)
        else None
    )
    original_reservation = response.get("_paper_fetch_original_reservation")
    streamed = bool(response.get("_paper_fetch_streamed"))
    try:
        streamed_size = staging_path.stat().st_size if staging_path is not None else 0
    except OSError:
        streamed_size = 0
    streamed_has_payload = bool(
        streamed
        and staging_path is not None
        and streamed_size > 0
        and int(response.get("downloaded_bytes") or 0) > 0
    )
    if (streamed and not streamed_has_payload) or (
        not streamed and (not isinstance(body, (bytes, bytearray)) or not body)
    ):
        _rollback_response_reservation(response)
        return _AssetDownloadFailure(
            kind.failure_template(
                asset,
                source_url,
                status=response.get("status_code")
                if isinstance(response, Mapping)
                else None,
                content_type=header_value(response.get("headers"), "content-type"),
                final_url=final_url,
                reason="empty_response_body",
            )
        )

    content_type = header_value(response.get("headers"), "content-type")
    output_subdir = kind.output_subdir(asset)
    target_asset_dir = (
        asset_dir / output_subdir if output_subdir is not None else asset_dir
    )
    target_asset_dir.mkdir(parents=True, exist_ok=True)
    output_path = build_asset_output_path(
        target_asset_dir,
        source_url,
        content_type,
        final_url,
        used_names_by_dir.setdefault(target_asset_dir, set()),
        preferred_filename=(
            normalize_text(str(asset.get("filename_hint") or "")) or None
            if kind.name == "supplementary"
            else None
        ),
    )
    reservation = resolved.reservation
    original_saved_path = ""
    if streamed and staging_path is not None:
        from ....artifacts import ArtifactStore

        store = (
            artifact_store
            if isinstance(artifact_store, ArtifactStore)
            else ArtifactStore.from_download_dir(asset_dir.parent)
        )
        if reservation is None:
            with contextlib.suppress(OSError):
                staging_path.unlink(missing_ok=True)
            return _AssetDownloadFailure(
                kind.failure_template(
                    asset,
                    source_url,
                    content_type=content_type,
                    final_url=final_url,
                    reason=ASSET_CANCELLED,
                )
            )
        original_output_path: Path | None = None
        if original_staging_path is not None and isinstance(
            original_reservation, AssetReservation
        ):
            original_output_path = build_asset_output_path(
                target_asset_dir,
                source_url,
                normalize_text(
                    str(response.get("_paper_fetch_original_content_type") or "")
                ),
                final_url,
                used_names_by_dir.setdefault(target_asset_dir, set()),
            )
        published_paths: list[Path] = []
        try:
            with contextlib.ExitStack() as stack:
                stack.enter_context(reservation.commit_critical_section())
                if isinstance(original_reservation, AssetReservation):
                    stack.enter_context(original_reservation.commit_critical_section())
                if (
                    original_output_path is not None
                    and original_staging_path is not None
                ):
                    published_original = store.publish_staged_file(
                        original_staging_path,
                        original_output_path,
                    )
                    published_paths.append(published_original)
                    original_saved_path = str(published_original)
                published = store.publish_staged_file(staging_path, output_path)
                published_paths.append(published)
                saved_path = str(published)
                reservation.unregister_staging(staging_path)
                if (
                    isinstance(original_reservation, AssetReservation)
                    and original_staging_path is not None
                ):
                    original_reservation.unregister_staging(original_staging_path)
                reservation.commit()
                if isinstance(original_reservation, AssetReservation):
                    original_reservation.commit()
        except BaseException:
            for published_path in reversed(published_paths):
                with contextlib.suppress(OSError):
                    published_path.unlink(missing_ok=True)
            reservation.rollback()
            if isinstance(original_reservation, AssetReservation):
                original_reservation.rollback()
            raise
    else:
        saved_path = save_payload(output_path, bytes(body)) or ""
    original_body = response.get("_paper_fetch_original_body")
    original_content_type = normalize_text(
        str(response.get("_paper_fetch_original_content_type") or "")
    )
    original_source_format = normalize_text(
        str(response.get("_paper_fetch_original_source_format") or "")
    )
    conversion_tool = normalize_text(
        str(response.get("_paper_fetch_conversion_tool") or "")
    )
    if isinstance(original_body, (bytes, bytearray)) and original_body:
        original_output_path = build_asset_output_path(
            target_asset_dir,
            source_url,
            original_content_type,
            final_url,
            used_names_by_dir.setdefault(target_asset_dir, set()),
        )
        original_saved_path = (
            save_payload(original_output_path, bytes(original_body)) or ""
        )
    if kind.name == "supplementary":
        download: dict[str, Any] = {
            "kind": "supplementary",
            "heading": asset.get("heading")
            or asset.get("filename_hint")
            or "Supplementary Material",
            "caption": asset.get("caption", ""),
            "download_url": source_url,
            "source_url": final_url,
            "content_type": content_type,
            "path": saved_path,
            "downloaded_bytes": int(response.get("downloaded_bytes") or len(body)),
            "section": "supplementary",
            "download_tier": "supplementary_file",
        }
        for key in (
            "asset_type",
            "source_kind",
            "source_ref",
            "filename_hint",
            "attachment_type",
            "object_type",
            "category",
        ):
            value = asset.get(key)
            if value:
                download[key] = value
        _attach_browser_recovery_diagnostics(download, response)
        return download

    preview_url = normalize_text(resolved.preview_url)
    full_size_url = normalize_text(resolved.full_size_url)
    download_tier_override = normalize_text(resolved.download_tier_override)
    dimensions = _response_dimensions(response) or (0, 0)
    width, height = dimensions
    download_tier = download_tier_override or (
        "preview"
        if preview_url
        and source_url == preview_url
        and source_url != full_size_url
        and not looks_like_full_size_asset_url(source_url.lower())
        else "full_size"
    )
    download = {
        "kind": asset.get("kind", "figure"),
        "heading": asset.get("heading", "Figure"),
        "caption": asset.get("caption", ""),
        "url": asset.get("url", "") or full_size_url or preview_url,
        "original_url": full_size_url
        or normalize_text(str(asset.get("original_url") or ""))
        or source_url,
        "preview_url": preview_url,
        "full_size_url": full_size_url,
        "figure_page_url": asset.get("figure_page_url", ""),
        "download_url": source_url,
        "download_tier": download_tier,
        "source_url": final_url,
        "content_type": content_type,
        "path": saved_path,
        "downloaded_bytes": int(response.get("downloaded_bytes") or len(body)),
        "section": asset.get("section") or "body",
    }
    for key in (
        "asset_type",
        "source_kind",
        "source_ref",
        "filename_hint",
        "attachment_type",
        "object_type",
        "category",
    ):
        value = asset.get(key)
        if value:
            download[key] = value
    _attach_browser_recovery_diagnostics(download, response)
    if resolved.provenance:
        download["provenance"] = list(resolved.provenance)
    if original_saved_path:
        download["original_source_path"] = original_saved_path
        download["original_content_type"] = original_content_type
        download["original_download_url"] = source_url
        download["conversion_source_format"] = original_source_format
        download["conversion_output_format"] = "png"
        download["conversion_tool"] = conversion_tool
        download["download_tier"] = "source_converted"
    if width > 0 and height > 0:
        download["width"] = width
        download["height"] = height
    if download_tier == "preview" and (
        _asset_marks_preview_accepted(asset)
        or preview_dimensions_are_acceptable(width, height)
    ):
        download["preview_accepted"] = True
    return download


def _asset_marks_preview_accepted(asset: Mapping[str, Any]) -> bool:
    value = asset.get("preview_accepted")
    if isinstance(value, bool):
        return value
    return normalize_text(str(value or "")).lower() in {"1", "true", "yes", "accepted"}


def _response_final_url(response: Mapping[str, Any], source_url: str) -> str:
    response_url = normalize_text(str(response.get("url") or ""))
    return urllib.parse.urljoin(source_url, response_url or source_url)


def _asset_items_for_kind(
    kind: AssetDownloadKind,
    assets: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    items = [dict(asset) for asset in assets]
    if kind.name == "supplementary":
        return [asset for asset in items if html_asset_is_supplementary(asset)]
    return items


def download_assets(
    kind: AssetDownloadKind,
    transport: HttpTransport,
    *,
    article_id: str,
    assets: Sequence[Mapping[str, Any]],
    output_dir: Path | None,
    user_agent: str,
    asset_profile: AssetProfile | None = "all",
    options: AssetDownloadOptions | None = None,
    **legacy_options: Any,
) -> dict[str, list[dict[str, Any]]]:
    if output_dir is None or not assets:
        return empty_asset_results()
    active_options = _coerce_asset_download_options(options, legacy_options)
    headers = active_options.headers
    browser_context_seed = active_options.browser_context_seed
    seed_urls = active_options.seed_urls
    figure_page_fetcher = active_options.figure_page_fetcher
    candidate_builder = active_options.candidate_builder
    document_fetcher = active_options.document_fetcher
    image_document_fetcher = active_options.image_document_fetcher
    file_document_fetcher = active_options.file_document_fetcher
    cookie_opener_builder = active_options.cookie_opener_builder
    opener_requester = active_options.opener_requester
    asset_download_concurrency = active_options.asset_download_concurrency
    fetch_policy = active_options.fetch_policy
    asset_budget = active_options.asset_budget
    route_concurrency_cap = active_options.route_concurrency_cap
    allowed_hosts = active_options.allowed_hosts
    provider_name = active_options.provider_name
    artifact_store = active_options.artifact_store
    runtime_context = active_options.runtime_context
    asset_session_pool = active_options.asset_session_pool
    from ....provider_catalog import (
        compile_route_execution_policy_for_kind,
        effective_route_asset_scope,
    )

    asset_execution_policy = None
    if provider_name:
        with contextlib.suppress(ValueError):
            asset_execution_policy = compile_route_execution_policy_for_kind(
                provider_name, "assets"
            )
    asset_route_name = (
        asset_execution_policy.route if asset_execution_policy is not None else None
    )

    active_asset_profile = effective_route_asset_scope(
        asset_profile,
        provider_name=provider_name,
        route_name=asset_route_name,
    )
    if kind.name == "figure" and active_asset_profile == "none":
        return empty_asset_results()
    if kind.name == "supplementary" and active_asset_profile != "all":
        return empty_asset_results()

    asset_items = _asset_items_for_kind(kind, assets)
    if not asset_items:
        return empty_asset_results()

    asset_dir = output_dir / f"{sanitize_filename(article_id)}_assets"
    asset_dir.mkdir(parents=True, exist_ok=True)
    if route_concurrency_cap is None and asset_execution_policy is not None:
        route_concurrency_cap = asset_execution_policy.asset_concurrency_cap
    runtime_budget = (
        getattr(runtime_context, "asset_budget", None)
        if runtime_context is not None
        else None
    )
    active_budget = (
        asset_budget
        or runtime_budget
        or current_asset_budget()
        or AssetBudget(route_concurrency_cap=route_concurrency_cap)
    )
    if artifact_store is None and runtime_context is not None:
        artifact_store = getattr(runtime_context, "artifact_store", None)
    work_keys = [
        "|".join(
            (
                kind.name,
                normalize_text(str(asset.get("source_ref") or "")),
                normalize_text(
                    str(
                        asset.get("original_url")
                        or asset.get("url")
                        or asset.get("link")
                        or asset.get("filename_hint")
                        or ""
                    )
                ),
                normalize_text(str(asset.get("heading") or "")),
            )
        )
        for asset in asset_items
    ]
    admitted = active_budget.admit_work(work_keys)
    rejected_failures = [
        {
            **kind.failure_template(
                asset,
                normalize_text(
                    str(asset.get("original_url") or asset.get("url") or "")
                ),
                reason=ASSET_FILE_LIMIT_EXCEEDED,
            ),
            "max_files": active_budget.max_files,
        }
        for asset, is_admitted in zip(asset_items, admitted, strict=True)
        if not is_admitted
    ]
    asset_items = [
        asset
        for asset, is_admitted in zip(asset_items, admitted, strict=True)
        if is_admitted
    ]
    if not asset_items:
        return {"assets": [], "asset_failures": rejected_failures}
    used_names_by_dir: dict[Path, set[str]] = {}
    active_cookie_opener_builder = cookie_opener_builder or _build_cookie_seeded_opener
    active_opener_requester = opener_requester or _request_with_opener
    browser_cookies = list((browser_context_seed or {}).get("browser_cookies") or [])
    active_seed_urls = _active_seed_urls(seed_urls, browser_context_seed)
    normalized_allowed_hosts = tuple(allowed_hosts or ()) or None
    if normalized_allowed_hosts is None and provider_name:
        from ....http.provider_policy import provider_allowed_hosts

        normalized_allowed_hosts = (
            provider_allowed_hosts(provider_name, asset_route_name) or None
        )
    session_pool = (
        asset_session_pool
        if isinstance(asset_session_pool, _AssetSessionPool)
        else None
    )
    session_cache_key = _asset_session_pool_cache_key(
        transport,
        provider_name=provider_name,
        route_name=asset_route_name,
        browser_cookies=browser_cookies,
        seed_urls=active_seed_urls,
        headers=headers,
        allowed_hosts=normalized_allowed_hosts,
    )
    if session_pool is None and runtime_context is not None:
        cached_pool = runtime_context.get_session_cache(
            session_cache_key,
            copy_value=False,
        )
        if isinstance(cached_pool, _AssetSessionPool):
            session_pool = cached_pool
    if session_pool is None:
        session_pool = _AssetSessionPool(
            transport,
            provider_name=provider_name,
            route_name=asset_route_name,
            browser_cookies=browser_cookies,
            seed_urls=active_seed_urls,
            headers=headers,
            allowed_hosts=normalized_allowed_hosts,
        )
        if runtime_context is not None:
            runtime_context.set_session_cache(
                session_cache_key,
                session_pool,
                copy_value=False,
            )
    active_document_fetcher = document_fetcher
    if active_document_fetcher is None:
        active_document_fetcher = (
            image_document_fetcher
            if kind.file_document_fetcher_kind == "image"
            else file_document_fetcher
        )
    document_fetcher_requires_caller_thread = _requires_caller_thread(
        active_document_fetcher
    )

    active_candidate_builder = candidate_builder or figure_download_candidates

    def candidate_url_resolver(asset: Mapping[str, Any]) -> list[str]:
        if kind.name != "figure":
            return kind.candidate_url_resolver(asset)
        return active_candidate_builder(
            transport,
            asset=asset,
            user_agent=user_agent,
            figure_page_fetcher=figure_page_fetcher,
        )

    collected = _resolve_and_collect_downloads_as_completed(
        asset_items,
        resolver=lambda asset: resolve_asset_download(
            kind,
            asset,
            options=AssetResolutionOptions(
                transport=transport,
                headers=headers,
                user_agent=user_agent,
                browser_context_seed=browser_context_seed,
                browser_cookies=browser_cookies,
                active_seed_urls=active_seed_urls,
                document_fetcher=active_document_fetcher,
                cookie_opener_builder=active_cookie_opener_builder,
                opener_requester=active_opener_requester,
                candidate_url_resolver=candidate_url_resolver,
                fetch_policy=fetch_policy,
                asset_budget=active_budget,
                staging_dir=asset_dir,
                session_pool=session_pool,
                use_legacy_requester=not _transport_supports_pinned_streaming(
                    transport
                ),
            ),
        ),
        asset_download_concurrency=1
        if document_fetcher_requires_caller_thread
        else asset_download_concurrency,
        force_worker_thread=(
            kind.name == "figure"
            and active_document_fetcher is not None
            and not document_fetcher_requires_caller_thread
        ),
        saver=lambda resolved: save_asset_resolution(
            kind,
            resolved,
            asset_dir=asset_dir,
            used_names_by_dir=used_names_by_dir,
            artifact_store=artifact_store,
        ),
        asset_budget=active_budget,
        route_concurrency_cap=route_concurrency_cap,
    )
    collected["asset_failures"].extend(rejected_failures)
    return collected


__all__ = [
    "FIGURE_KIND",
    "SUPPLEMENTARY_BLOCKING_BODY_TOKENS",
    "SUPPLEMENTARY_BLOCKING_TITLE_TOKENS",
    "SUPPLEMENTARY_KIND",
    "_CLOUDFLARE_CHALLENGE_TOKENS",
    "AssetDownloadOptions",
    "AssetFetchPolicy",
    "AssetResolutionOptions",
    "FileDocumentFetcher",
    "ImageDocumentFetcher",
    "_build_cookie_seeded_opener",
    "_request_with_opener",
    "browser_asset_recovery_allowed",
    "download_assets",
    "resolve_asset_download",
    "save_asset_resolution",
]
