"""Asset download helpers with typed asset kinds."""

from __future__ import annotations

from dataclasses import replace
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any
from collections.abc import Callable, Mapping, Sequence

from ....http import DEFAULT_FULLTEXT_TIMEOUT_SECONDS, HttpTransport, RequestFailure
from ....http.headers import header_value
from ....image_tools import (
    ImageConversionFailure,
    convert_source_image_response_to_png,
    source_image_format_from_payload,
)
from ....models.schema import AssetProfile
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
    collect_downloads_from_resolutions as _collect_downloads_from_resolutions,
    resolution_from_attempt as _resolution_from_attempt,
    resolve_asset_downloads_in_order as _resolve_asset_downloads_in_order,
)

ImageDocumentFetcher = Callable[[str, Mapping[str, Any]], dict[str, Any] | None]
FileDocumentFetcher = Callable[[str, Mapping[str, Any]], dict[str, Any] | None]


def _requires_caller_thread(fetcher: Any) -> bool:
    return bool(getattr(fetcher, "requires_caller_thread", False))


def _fetch_document_fallback(
    kind: AssetDownloadKind,
    fetcher: ImageDocumentFetcher | FileDocumentFetcher | None,
    candidate_url: str,
    asset: Mapping[str, Any],
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
    body = response.get("body", b"")
    if not isinstance(body, (bytes, bytearray)):
        return None
    content_type = header_value(response.get("headers"), "content-type")
    if not kind.accepts_response(content_type, bytes(body)):
        return None
    return dict(response)


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
) -> tuple[dict[str, Any], str]:
    source_format = source_image_format_from_payload(
        response.get("body", b""),
        content_type=header_value(response.get("headers"), "content-type"),
        source_url=source_url,
    )
    if source_format not in {"eps", "tiff"}:
        return dict(response), ""
    conversion = convert_source_image_response_to_png(response, source_url=source_url)
    if conversion is None:
        return dict(response), ""
    converted = dict(response)
    converted_headers = dict(response.get("headers") or {})
    converted_headers["content-type"] = conversion.content_type
    converted["headers"] = converted_headers
    converted["body"] = conversion.body
    converted["_paper_fetch_original_body"] = response.get("body", b"")
    converted["_paper_fetch_original_content_type"] = header_value(
        response.get("headers"),
        "content-type",
    )
    converted["_paper_fetch_original_source_format"] = conversion.source_format
    converted["_paper_fetch_conversion_tool"] = conversion.tool
    return converted, conversion.source_format


def _conversion_failure_attempt(
    kind: AssetDownloadKind,
    asset: Mapping[str, Any],
    candidate: _AssetDownloadCandidate,
    response: Mapping[str, Any],
    exc: ImageConversionFailure,
) -> _AssetDownloadAttempt:
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


def _request_asset_candidate(
    kind: AssetDownloadKind,
    transport: HttpTransport,
    candidate_url: str,
    *,
    headers: Mapping[str, str] | None,
    user_agent: str,
    browser_context_seed: Mapping[str, Any] | None,
    browser_cookies: list[dict[str, Any]],
    active_seed_urls: list[str],
    cookie_opener_builder: Callable[..., urllib.request.OpenerDirector | None],
    opener_requester: Callable[..., dict[str, Any]],
) -> dict[str, Any]:
    request_headers = kind.request_headers(headers, user_agent, browser_context_seed)
    cookie_header = _cookie_header_for_url(browser_cookies, candidate_url)
    if cookie_header:
        request_headers["Cookie"] = cookie_header

    opener = (
        cookie_opener_builder(
            active_seed_urls,
            headers=request_headers,
            timeout=DEFAULT_FULLTEXT_TIMEOUT_SECONDS,
            browser_cookies=browser_cookies,
        )
        if browser_cookies or active_seed_urls or kind.name == "supplementary"
        else None
    )
    if opener is None and kind.name == "supplementary":
        opener = urllib.request.build_opener()
    if opener is not None:
        return opener_requester(
            opener,
            candidate_url,
            headers=request_headers,
            timeout=DEFAULT_FULLTEXT_TIMEOUT_SECONDS,
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
                reason=kind.response_block_reason(content_type, bytes(body))
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
    headers: Mapping[str, str] | None,
    user_agent: str,
    browser_context_seed: Mapping[str, Any] | None,
    browser_cookies: list[dict[str, Any]],
    active_seed_urls: list[str],
    cookie_opener_builder: Callable[..., urllib.request.OpenerDirector | None],
    opener_requester: Callable[..., dict[str, Any]],
    preview_url: str,
    full_size_url: str,
    last_attempt: _AssetDownloadAttempt,
) -> tuple[_AssetDownloadAttempt, _AssetDownloadResolution | None]:
    if kind.name != "figure" or not _should_retry_seeded_full_size_candidate(
        candidate.url,
        preview_url=preview_url,
        full_size_url=full_size_url,
        active_seed_urls=active_seed_urls,
        browser_cookies=browser_cookies,
    ):
        return last_attempt, None
    try:
        response = _request_asset_candidate(
            kind,
            transport,
            candidate.url,
            headers=headers,
            user_agent=user_agent,
            browser_context_seed=browser_context_seed,
            browser_cookies=browser_cookies,
            active_seed_urls=active_seed_urls,
            cookie_opener_builder=cookie_opener_builder,
            opener_requester=opener_requester,
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


def resolve_asset_download(
    kind: AssetDownloadKind,
    asset: Mapping[str, Any],
    *,
    transport: HttpTransport,
    headers: Mapping[str, str] | None,
    user_agent: str,
    browser_context_seed: Mapping[str, Any] | None,
    browser_cookies: list[dict[str, Any]],
    active_seed_urls: list[str],
    document_fetcher: ImageDocumentFetcher | FileDocumentFetcher | None,
    cookie_opener_builder: Callable[..., urllib.request.OpenerDirector | None],
    opener_requester: Callable[..., dict[str, Any]],
    candidate_url_resolver: Callable[[Mapping[str, Any]], list[str]] | None = None,
) -> _AssetDownloadResolution:
    conversion_degraded = False
    candidate_urls = (candidate_url_resolver or kind.candidate_url_resolver)(asset)
    preview_url, full_size_url = _resolution_preview_fields(kind, asset, candidate_urls)
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

        if _should_use_figure_document_fetcher_for_candidate(
            kind,
            candidate_url,
            document_fetcher,
        ):
            fallback_response = _fetch_document_fallback(
                kind,
                document_fetcher,
                candidate_url,
                asset,
            )
            if fallback_response is not None:
                try:
                    fallback_response, _ = _converted_figure_response(
                        fallback_response,
                        source_url=candidate_url,
                    )
                except ImageConversionFailure as exc:
                    conversion_degraded = True
                    last_attempt = _conversion_failure_attempt(
                        kind,
                        asset,
                        candidate,
                        fallback_response,
                        exc,
                    )
                    continue
                return _resolution_from_attempt(
                    asset=asset,
                    attempt=_AssetDownloadAttempt(
                        candidate=candidate,
                        response=fallback_response,
                        source_url=candidate_url,
                    ),
                    preview_url=preview_url,
                    full_size_url=full_size_url,
                    provenance=("conversion_degraded",) if conversion_degraded else (),
                )
            fetch_failure = _document_fetch_failure(document_fetcher, candidate_url)
            last_attempt = _AssetDownloadAttempt(
                candidate=candidate,
                failure=_asset_failure(
                    _failure_from_document_fetch(
                        kind,
                        asset,
                        candidate_url,
                        fetch_failure,
                    )
                ),
            )
            continue

        try:
            response = _request_asset_candidate(
                kind,
                transport,
                candidate_url,
                headers=headers,
                user_agent=user_agent,
                browser_context_seed=browser_context_seed,
                browser_cookies=browser_cookies,
                active_seed_urls=active_seed_urls,
                cookie_opener_builder=cookie_opener_builder,
                opener_requester=opener_requester,
            )
        except RequestFailure as exc:
            last_attempt = _request_failure_attempt(kind, asset, candidate, exc)
            last_attempt, retry_resolution = _retry_seeded_figure_candidate(
                kind,
                transport,
                asset,
                candidate,
                headers=headers,
                user_agent=user_agent,
                browser_context_seed=browser_context_seed,
                browser_cookies=browser_cookies,
                active_seed_urls=active_seed_urls,
                cookie_opener_builder=cookie_opener_builder,
                opener_requester=opener_requester,
                preview_url=preview_url,
                full_size_url=full_size_url,
                last_attempt=last_attempt,
            )
            if retry_resolution is not None:
                if conversion_degraded:
                    retry_resolution = replace(
                        retry_resolution, provenance=("conversion_degraded",)
                    )
                return retry_resolution
            fallback_response = _fetch_document_fallback(
                kind,
                document_fetcher,
                candidate_url,
                asset,
            )
            if fallback_response is not None:
                try:
                    fallback_response, _ = _converted_figure_response(
                        fallback_response,
                        source_url=candidate_url,
                    )
                except ImageConversionFailure as exc:
                    conversion_degraded = True
                    last_attempt = _conversion_failure_attempt(
                        kind,
                        asset,
                        candidate,
                        fallback_response,
                        exc,
                    )
                    continue
                return _resolution_from_attempt(
                    asset=asset,
                    attempt=_AssetDownloadAttempt(
                        candidate=candidate,
                        response=fallback_response,
                        source_url=candidate_url,
                    ),
                    preview_url=preview_url,
                    full_size_url=full_size_url,
                    provenance=("conversion_degraded",) if conversion_degraded else (),
                )
            fetch_failure = _document_fetch_failure(document_fetcher, candidate_url)
            if fetch_failure and last_attempt.failure is not None:
                last_attempt.failure.diagnostic.update(fetch_failure)
            continue

        body = response.get("body", b"")
        if not isinstance(body, (bytes, bytearray)):
            body = b""
        content_type = header_value(response.get("headers"), "content-type")
        block_reason = kind.response_block_reason(content_type, bytes(body))
        if block_reason:
            last_attempt = _blocked_response_attempt(
                kind,
                asset,
                candidate,
                response,
                candidate_url,
                block_reason,
            )
            last_attempt, retry_resolution = _retry_seeded_figure_candidate(
                kind,
                transport,
                asset,
                candidate,
                headers=headers,
                user_agent=user_agent,
                browser_context_seed=browser_context_seed,
                browser_cookies=browser_cookies,
                active_seed_urls=active_seed_urls,
                cookie_opener_builder=cookie_opener_builder,
                opener_requester=opener_requester,
                preview_url=preview_url,
                full_size_url=full_size_url,
                last_attempt=last_attempt,
            )
            if retry_resolution is not None:
                if conversion_degraded:
                    retry_resolution = replace(
                        retry_resolution, provenance=("conversion_degraded",)
                    )
                return retry_resolution
            fallback_response = _fetch_document_fallback(
                kind,
                document_fetcher,
                candidate_url,
                asset,
            )
            if fallback_response is not None:
                try:
                    fallback_response, _ = _converted_figure_response(
                        fallback_response,
                        source_url=candidate_url,
                    )
                except ImageConversionFailure as exc:
                    conversion_degraded = True
                    last_attempt = _conversion_failure_attempt(
                        kind,
                        asset,
                        candidate,
                        fallback_response,
                        exc,
                    )
                    continue
                return _resolution_from_attempt(
                    asset=asset,
                    attempt=_AssetDownloadAttempt(
                        candidate=candidate,
                        response=fallback_response,
                        source_url=candidate_url,
                    ),
                    preview_url=preview_url,
                    full_size_url=full_size_url,
                    provenance=("conversion_degraded",) if conversion_degraded else (),
                )
            fetch_failure = _document_fetch_failure(document_fetcher, candidate_url)
            if fetch_failure and last_attempt.failure is not None:
                last_attempt.failure.diagnostic.update(fetch_failure)
            continue

        if (
            kind.upgrade_targets is not None
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
                )
                if fallback_response is not None:
                    try:
                        fallback_response, _ = _converted_figure_response(
                            fallback_response,
                            source_url=upgrade_target,
                        )
                    except ImageConversionFailure:
                        conversion_degraded = True
                        continue
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
            response, _ = (
                _converted_figure_response(response, source_url=candidate_url)
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
) -> dict[str, Any] | _AssetDownloadFailure:
    asset = resolved.asset
    response = resolved.response or {}
    source_url = normalize_text(resolved.source_url)
    final_url = _response_final_url(response, source_url)
    body = response.get("body", b"")
    if not isinstance(body, (bytes, bytearray)) or not body:
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
    saved_path = save_payload(output_path, bytes(body))
    original_body = response.get("_paper_fetch_original_body")
    original_saved_path = ""
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
            "downloaded_bytes": len(body),
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
        "downloaded_bytes": len(body),
        "section": asset.get("section") or "body",
    }
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
    asset_profile: AssetProfile = "all",
    headers: Mapping[str, str] | None = None,
    browser_context_seed: Mapping[str, Any] | None = None,
    seed_urls: Sequence[str] | None = None,
    figure_page_fetcher: FigurePageFetcher | None = None,
    candidate_builder: Callable[..., list[str]] | None = None,
    document_fetcher: ImageDocumentFetcher | FileDocumentFetcher | None = None,
    image_document_fetcher: ImageDocumentFetcher | None = None,
    file_document_fetcher: FileDocumentFetcher | None = None,
    cookie_opener_builder: Callable[..., urllib.request.OpenerDirector | None]
    | None = None,
    opener_requester: Callable[..., dict[str, Any]] | None = None,
    asset_download_concurrency: int | None = None,
) -> dict[str, list[dict[str, Any]]]:
    if output_dir is None or not assets:
        return empty_asset_results()
    if kind.name == "figure" and asset_profile == "none":
        return empty_asset_results()
    if kind.name == "supplementary" and asset_profile != "all":
        return empty_asset_results()

    asset_items = _asset_items_for_kind(kind, assets)
    if not asset_items:
        return empty_asset_results()

    asset_dir = output_dir / f"{sanitize_filename(article_id)}_assets"
    asset_dir.mkdir(parents=True, exist_ok=True)
    used_names_by_dir: dict[Path, set[str]] = {}
    active_cookie_opener_builder = cookie_opener_builder or _build_cookie_seeded_opener
    active_opener_requester = opener_requester or _request_with_opener
    browser_cookies = list((browser_context_seed or {}).get("browser_cookies") or [])
    active_seed_urls = _active_seed_urls(seed_urls, browser_context_seed)
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

    resolved_results = _resolve_asset_downloads_in_order(
        asset_items,
        resolver=lambda asset: resolve_asset_download(
            kind,
            asset,
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
        ),
        asset_download_concurrency=1
        if document_fetcher_requires_caller_thread
        else asset_download_concurrency,
        force_worker_thread=(
            kind.name == "figure"
            and active_document_fetcher is not None
            and not document_fetcher_requires_caller_thread
        ),
    )
    return _collect_downloads_from_resolutions(
        resolved_results,
        saver=lambda resolved: save_asset_resolution(
            kind,
            resolved,
            asset_dir=asset_dir,
            used_names_by_dir=used_names_by_dir,
        ),
    )


__all__ = [
    "FIGURE_KIND",
    "SUPPLEMENTARY_BLOCKING_BODY_TOKENS",
    "SUPPLEMENTARY_BLOCKING_TITLE_TOKENS",
    "SUPPLEMENTARY_KIND",
    "_CLOUDFLARE_CHALLENGE_TOKENS",
    "FileDocumentFetcher",
    "ImageDocumentFetcher",
    "_build_cookie_seeded_opener",
    "_request_with_opener",
    "download_assets",
    "resolve_asset_download",
    "save_asset_resolution",
]
