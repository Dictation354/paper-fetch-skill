"""Asset download helpers with patchable browser-cookie hooks."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
import http.cookiejar
import re
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Callable, Mapping, TypeVar

from ....config import DEFAULT_ASSET_DOWNLOAD_CONCURRENCY
from ....http import DEFAULT_FULLTEXT_TIMEOUT_SECONDS, HttpTransport, RequestFailure
from ....models import AssetProfile, normalize_text
from ....utils import build_asset_output_path, empty_asset_results, sanitize_filename, save_payload
from ..shared import (
    html_text_snippet as _html_text_snippet,
    html_title_snippet as _html_title_snippet,
    image_magic_type as _image_magic_type,
)
from .dom import (
    _response_dimensions,
    _response_header,
    looks_like_full_size_asset_url,
    preview_dimensions_are_acceptable,
    supplementary_response_block_reason,
)
from .figures import FigurePageFetcher, figure_download_candidates
from .identity import html_asset_is_supplementary

_CLOUDFLARE_CHALLENGE_TOKENS = (
    "just a moment",
    "attention required",
    "checking your browser",
)


SUPPLEMENTARY_BLOCKING_TITLE_TOKENS = (
    "just a moment",
    "attention required",
    "checking your browser",
    "sign in",
    "sign-in",
    "login",
    "log in",
    "access denied",
)


SUPPLEMENTARY_BLOCKING_BODY_TOKENS = (
    "checking your browser",
    "enable javascript and cookies",
    "cloudflare",
    "please sign in",
    "institutional login",
    "access denied",
)


ImageDocumentFetcher = Callable[[str, Mapping[str, Any]], dict[str, Any] | None]


FileDocumentFetcher = Callable[[str, Mapping[str, Any]], dict[str, Any] | None]


_AssetWorkItem = TypeVar("_AssetWorkItem")


@dataclass(frozen=True)
class _AssetDownloadCandidate:
    url: str


@dataclass(frozen=True)
class _AssetDownloadFailure:
    diagnostic: dict[str, Any]


@dataclass(frozen=True)
class _AssetDownloadAttempt:
    candidate: _AssetDownloadCandidate
    response: Mapping[str, Any] | None = None
    source_url: str = ""
    failure: _AssetDownloadFailure | None = None
    download_tier_override: str = ""


@dataclass(frozen=True)
class _AssetDownloadResolution:
    asset: dict[str, Any]
    response: Mapping[str, Any] | None = None
    source_url: str = ""
    failure: _AssetDownloadFailure | None = None
    preview_url: str = ""
    full_size_url: str = ""
    download_tier_override: str = ""


def _asset_download_worker_count(total: int, configured_concurrency: int | None) -> int:
    if total <= 0:
        return 0
    try:
        concurrency = int(configured_concurrency or DEFAULT_ASSET_DOWNLOAD_CONCURRENCY)
    except (TypeError, ValueError):
        concurrency = DEFAULT_ASSET_DOWNLOAD_CONCURRENCY
    return min(max(1, concurrency), total)


def _asset_failure(diagnostic: Mapping[str, Any] | None) -> _AssetDownloadFailure | None:
    if not diagnostic:
        return None
    return _AssetDownloadFailure(dict(diagnostic))


def _resolution_from_attempt(
    *,
    asset: Mapping[str, Any],
    attempt: _AssetDownloadAttempt | None,
    preview_url: str = "",
    full_size_url: str = "",
) -> _AssetDownloadResolution:
    if attempt is None:
        return _AssetDownloadResolution(
            asset=dict(asset),
            preview_url=preview_url,
            full_size_url=full_size_url,
        )
    return _AssetDownloadResolution(
        asset=dict(asset),
        response=attempt.response,
        source_url=attempt.source_url or attempt.candidate.url,
        failure=attempt.failure,
        preview_url=preview_url,
        full_size_url=full_size_url,
        download_tier_override=attempt.download_tier_override,
    )


def _resolve_asset_downloads_in_order(
    work_items: list[_AssetWorkItem],
    *,
    resolver: Callable[[_AssetWorkItem], _AssetDownloadResolution | None],
    asset_download_concurrency: int | None,
) -> list[_AssetDownloadResolution | None]:
    if not work_items:
        return []
    max_workers = _asset_download_worker_count(len(work_items), asset_download_concurrency)
    if max_workers <= 1:
        return [resolver(item) for item in work_items]
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [executor.submit(resolver, item) for item in work_items]
        return [future.result() for future in futures]


def _collect_downloads_from_resolutions(
    resolutions: list[_AssetDownloadResolution | None],
    *,
    saver: Callable[[_AssetDownloadResolution], dict[str, Any] | _AssetDownloadFailure | None],
) -> dict[str, list[dict[str, Any]]]:
    downloads: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []
    for resolved in resolutions:
        if resolved is None:
            continue
        if resolved.response is None:
            if resolved.failure is not None:
                failures.append(dict(resolved.failure.diagnostic))
            continue
        saved = saver(resolved)
        if isinstance(saved, _AssetDownloadFailure):
            failures.append(dict(saved.diagnostic))
        elif saved is not None:
            downloads.append(saved)
    return {
        "assets": downloads,
        "asset_failures": failures,
    }


def _looks_like_image_payload(content_type: str | None, body: bytes | bytearray | None, source_url: str | None) -> bool:
    normalized_content_type = normalize_text(content_type).split(";", 1)[0].lower()
    if normalized_content_type.startswith("image/"):
        return True
    if normalized_content_type:
        return False
    if _image_magic_type(body):
        return True
    return bool(re.search(r"\.(?:avif|gif|jpe?g|png|tiff?|webp)(?:[?#]|$)", normalize_text(source_url), re.IGNORECASE))


def _requires_image_payload(asset: Mapping[str, Any]) -> bool:
    kind = normalize_text(str(asset.get("kind") or "")).lower()
    section = normalize_text(str(asset.get("section") or "")).lower()
    return kind in {"figure", "table", "formula"} and section != "supplementary"


def _fetch_image_document_fallback(
    fetcher: ImageDocumentFetcher | None,
    candidate_url: str,
    asset: Mapping[str, Any],
) -> dict[str, Any] | None:
    if fetcher is None or not _requires_image_payload(asset):
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
    content_type = _response_header(response, "content-type")
    final_url = normalize_text(str(response.get("url") or candidate_url))
    if not _looks_like_image_payload(content_type, body, final_url):
        return None
    return dict(response)


def _image_document_fetch_failure(
    fetcher: ImageDocumentFetcher | None,
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


def _figure_asset_failure(
    asset: Mapping[str, Any],
    source_url: str,
    *,
    reason: str,
    status: int | None = None,
    content_type: str | None = None,
    final_url: str | None = None,
    title_snippet: str | None = None,
    body_snippet: str | None = None,
    recovery_attempts: list[dict[str, Any]] | None = None,
    canvas_error: str | None = None,
) -> dict[str, Any]:
    failure: dict[str, Any] = {
        "kind": asset.get("kind", "figure"),
        "heading": asset.get("heading", "Figure"),
        "caption": asset.get("caption", ""),
        "source_url": source_url,
        "reason": reason,
        "section": asset.get("section") or "body",
    }
    if status is not None:
        failure["status"] = status
    if content_type:
        failure["content_type"] = content_type
    if final_url:
        failure["final_url"] = final_url
    if title_snippet:
        failure["title_snippet"] = title_snippet
    if body_snippet:
        failure["body_snippet"] = body_snippet
    if recovery_attempts:
        failure["recovery_attempts"] = list(recovery_attempts)
    if canvas_error:
        failure["canvas_error"] = canvas_error
    return failure


def _is_preview_candidate(candidate_url: str, *, preview_url: str, full_size_url: str) -> bool:
    normalized_candidate = normalize_text(candidate_url)
    if not normalized_candidate or not preview_url:
        return False
    return (
        normalized_candidate == preview_url
        and normalized_candidate != full_size_url
        and not looks_like_full_size_asset_url(normalized_candidate.lower())
    )


def _preview_upgrade_targets(candidate_url: str, asset: Mapping[str, Any]) -> list[str]:
    targets: list[str] = []
    for value in (
        asset.get("figure_page_url"),
        asset.get("full_size_url"),
        asset.get("download_url"),
        candidate_url,
    ):
        normalized = normalize_text(str(value or ""))
        if normalized and normalized not in targets:
            targets.append(normalized)
    return targets


def _resolve_figure_asset_with_image_document_fetcher(
    *,
    transport: HttpTransport,
    asset: Mapping[str, Any],
    user_agent: str,
    candidate_builder: Callable[..., list[str]],
    figure_page_fetcher: FigurePageFetcher | None,
    image_document_fetcher: ImageDocumentFetcher | None,
) -> _AssetDownloadResolution | None:
    if not _requires_image_payload(asset):
        return None

    preview_url = normalize_text(str(asset.get("preview_url") or asset.get("url") or ""))
    full_size_url = normalize_text(str(asset.get("full_size_url") or ""))
    candidate_urls = candidate_builder(
        transport,
        asset=asset,
        user_agent=user_agent,
        figure_page_fetcher=figure_page_fetcher,
    )
    if not candidate_urls:
        return None

    last_attempt: _AssetDownloadAttempt | None = None
    for candidate_url in candidate_urls:
        candidate = _AssetDownloadCandidate(candidate_url)
        parsed = urllib.parse.urlparse(candidate_url)
        if parsed.scheme not in {"http", "https"}:
            last_attempt = _AssetDownloadAttempt(
                candidate=candidate,
                failure=_asset_failure(
                    _figure_asset_failure(
                        asset,
                        candidate_url,
                        reason="unsupported_asset_url_scheme",
                    )
                ),
            )
            continue

        response = _fetch_image_document_fallback(image_document_fetcher, candidate_url, asset)
        if response is not None:
            return _resolution_from_attempt(
                asset=asset,
                attempt=_AssetDownloadAttempt(
                    candidate=candidate,
                    response=response,
                    source_url=candidate_url,
                ),
                preview_url=preview_url,
                full_size_url=full_size_url,
            )
        fetch_failure = _image_document_fetch_failure(image_document_fetcher, candidate_url)
        last_attempt = _AssetDownloadAttempt(
            candidate=candidate,
            failure=_asset_failure(
                _figure_asset_failure(
                    asset,
                    candidate_url,
                    reason=normalize_text(str(fetch_failure.get("reason") or "")) or "image_fetch_error",
                    status=fetch_failure.get("status") if isinstance(fetch_failure.get("status"), int) else None,
                    content_type=normalize_text(str(fetch_failure.get("content_type") or "")),
                    final_url=normalize_text(str(fetch_failure.get("final_url") or "")),
                    title_snippet=normalize_text(str(fetch_failure.get("title_snippet") or "")),
                    body_snippet=normalize_text(str(fetch_failure.get("body_snippet") or "")),
                    recovery_attempts=(
                        list(fetch_failure.get("recovery_attempts"))
                        if isinstance(fetch_failure.get("recovery_attempts"), list)
                        else None
                    ),
                    canvas_error=normalize_text(str(fetch_failure.get("canvas_error") or "")),
                )
            ),
        )

    return _resolution_from_attempt(
        asset=asset,
        attempt=last_attempt,
        preview_url=preview_url,
        full_size_url=full_size_url,
    )


def _build_cookie_seeded_opener(
    seed_urls: list[str] | None,
    *,
    headers: Mapping[str, str],
    timeout: int,
    browser_cookies: list[dict[str, Any]] | None = None,
) -> urllib.request.OpenerDirector | None:
    normalized_seed_urls = [normalize_text(url) for url in seed_urls or [] if normalize_text(url)]
    if not normalized_seed_urls and not any(isinstance(cookie, dict) for cookie in browser_cookies or []):
        return None

    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
    seed_headers = {
        key: value
        for key, value in dict(headers).items()
        if str(key).lower() != "accept"
    }
    seed_headers.setdefault("Accept", "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8")

    for seed_url in normalized_seed_urls:
        request_headers = dict(seed_headers)
        cookie_header = _cookie_header_for_url(browser_cookies, seed_url)
        if cookie_header:
            request_headers["Cookie"] = cookie_header
        request = urllib.request.Request(seed_url, headers=request_headers)
        try:
            with opener.open(request, timeout=timeout) as response:
                response.read(1024)
        except Exception:
            continue

    return opener


def _request_with_opener(
    opener: urllib.request.OpenerDirector,
    url: str,
    *,
    headers: Mapping[str, str],
    timeout: int,
) -> dict[str, Any]:
    request = urllib.request.Request(url, headers=dict(headers))
    try:
        with opener.open(request, timeout=timeout) as response:
            return {
                "status_code": int(getattr(response, "status", response.getcode())),
                "headers": {str(key).lower(): str(value) for key, value in response.headers.items()},
                "body": response.read(),
                "url": str(response.geturl() or url),
            }
    except urllib.error.HTTPError as exc:
        raise RequestFailure(
            exc.code,
            f"HTTP {exc.code} for {url}",
            body=exc.read(),
            headers={str(key).lower(): str(value) for key, value in exc.headers.items()},
            url=str(exc.geturl() or url),
        ) from exc
    except urllib.error.URLError as exc:
        raise RequestFailure(
            None,
            f"Failed to download asset candidate: {exc.reason or exc}",
            url=url,
        ) from exc


def _cookie_header_for_url(browser_cookies: list[dict[str, Any]] | None, url: str) -> str | None:
    parsed_url = urllib.parse.urlparse(normalize_text(url))
    host = normalize_text(parsed_url.hostname).lower()
    path = normalize_text(parsed_url.path) or "/"
    scheme = normalize_text(parsed_url.scheme).lower()
    if not host:
        return None

    matched_pairs: list[str] = []
    for cookie in browser_cookies or []:
        if not isinstance(cookie, dict):
            continue
        name = normalize_text(str(cookie.get("name") or ""))
        value = str(cookie.get("value") or "")
        if not name:
            continue

        cookie_domain = normalize_text(str(cookie.get("domain") or "")).lower().lstrip(".")
        if not cookie_domain:
            cookie_url = normalize_text(str(cookie.get("url") or ""))
            cookie_domain = normalize_text(urllib.parse.urlparse(cookie_url).hostname).lower()
        if cookie_domain and host != cookie_domain and not host.endswith(f".{cookie_domain}"):
            continue

        cookie_path = normalize_text(str(cookie.get("path") or "")) or "/"
        if not path.startswith(cookie_path):
            continue

        if bool(cookie.get("secure")) and scheme != "https":
            continue

        matched_pairs.append(f"{name}={value}")

    return "; ".join(matched_pairs) if matched_pairs else None


def _supplementary_candidate_urls(asset: Mapping[str, Any]) -> list[str]:
    candidates: list[str] = []
    seen: set[str] = set()
    for field in ("download_url", "url", "source_url", "full_size_url", "preview_url"):
        candidate = normalize_text(str(asset.get(field) or ""))
        if candidate and candidate not in seen:
            seen.add(candidate)
            candidates.append(candidate)
    return candidates


def _supplementary_failure(
    asset: Mapping[str, Any],
    source_url: str,
    *,
    reason: str,
    status: int | None = None,
    content_type: str | None = None,
    final_url: str | None = None,
    body: bytes | bytearray | None = None,
    extra: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    failure: dict[str, Any] = {
        "kind": "supplementary",
        "heading": asset.get("heading") or asset.get("filename_hint") or "Supplementary Material",
        "caption": asset.get("caption", ""),
        "source_url": source_url,
        "reason": reason,
        "section": "supplementary",
    }
    if status is not None:
        failure["status"] = status
    normalized_content_type = normalize_text(content_type)
    if normalized_content_type:
        failure["content_type"] = normalized_content_type
    normalized_final_url = normalize_text(final_url)
    if normalized_final_url:
        failure["final_url"] = normalized_final_url
    title_snippet = _html_title_snippet(body)
    if title_snippet:
        failure["title_snippet"] = title_snippet
    body_snippet = _html_text_snippet(body)
    if body_snippet:
        failure["body_snippet"] = body_snippet
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
            failure[key] = value
    if extra:
        for key, value in extra.items():
            if value not in (None, "", [], {}):
                failure[key] = value
    return failure


def _fetch_file_document_fallback(
    fetcher: FileDocumentFetcher | None,
    candidate_url: str,
    asset: Mapping[str, Any],
) -> dict[str, Any] | None:
    if fetcher is None:
        return None
    try:
        response = fetcher(candidate_url, asset)
    except Exception:
        return None
    if not response:
        return None
    body = response.get("body", b"")
    if not isinstance(body, (bytes, bytearray)) or not body:
        return None
    content_type = _response_header(response, "content-type")
    if supplementary_response_block_reason(content_type, body):
        return None
    return dict(response)


def _file_document_fetch_failure(
    fetcher: FileDocumentFetcher | None,
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


def _supplementary_download_headers(
    *,
    headers: Mapping[str, str] | None,
    user_agent: str,
    browser_context_seed: Mapping[str, Any] | None,
) -> dict[str, str]:
    request_headers = {"User-Agent": user_agent, "Accept": "*/*"}
    request_headers.update({str(key): str(value) for key, value in (headers or {}).items() if value is not None})
    active_user_agent = normalize_text(str((browser_context_seed or {}).get("browser_user_agent") or ""))
    if active_user_agent:
        request_headers["User-Agent"] = active_user_agent
    elif not normalize_text(request_headers.get("User-Agent")):
        request_headers.pop("User-Agent", None)
    request_headers.setdefault("Accept", "*/*")
    return request_headers


def _resolve_supplementary_asset_download(
    *,
    asset: Mapping[str, Any],
    headers: Mapping[str, str] | None,
    user_agent: str,
    browser_context_seed: Mapping[str, Any] | None,
    browser_cookies: list[dict[str, Any]],
    active_seed_urls: list[str],
    file_document_fetcher: FileDocumentFetcher | None,
    cookie_opener_builder: Callable[..., urllib.request.OpenerDirector | None],
    opener_requester: Callable[..., dict[str, Any]],
) -> _AssetDownloadResolution:
    candidate_urls = _supplementary_candidate_urls(asset)
    if not candidate_urls:
        return _resolution_from_attempt(
            asset=asset,
            attempt=_AssetDownloadAttempt(
                candidate=_AssetDownloadCandidate(""),
                failure=_asset_failure(
                    _supplementary_failure(
                        asset,
                        "",
                        reason="Supplementary asset did not include a downloadable URL.",
                    )
                ),
            ),
        )

    last_attempt: _AssetDownloadAttempt | None = None
    for candidate_url in candidate_urls:
        candidate = _AssetDownloadCandidate(candidate_url)
        parsed = urllib.parse.urlparse(candidate_url)
        if parsed.scheme not in {"http", "https"}:
            last_attempt = _AssetDownloadAttempt(
                candidate=candidate,
                failure=_asset_failure(
                    _supplementary_failure(
                        asset,
                        candidate_url,
                        reason=f"Unsupported supplementary URL scheme for {candidate_url}",
                    )
                ),
            )
            continue

        request_headers = _supplementary_download_headers(
            headers=headers,
            user_agent=user_agent,
            browser_context_seed=browser_context_seed,
        )
        cookie_header = _cookie_header_for_url(browser_cookies, candidate_url)
        if cookie_header:
            request_headers["Cookie"] = cookie_header

        try:
            opener = cookie_opener_builder(
                active_seed_urls,
                headers=request_headers,
                timeout=DEFAULT_FULLTEXT_TIMEOUT_SECONDS,
                browser_cookies=browser_cookies,
            )
            if opener is None:
                opener = urllib.request.build_opener()
            response = opener_requester(
                opener,
                candidate_url,
                headers=request_headers,
                timeout=DEFAULT_FULLTEXT_TIMEOUT_SECONDS,
            )
        except RequestFailure as exc:
            content_type = _response_header({"headers": exc.headers}, "content-type")
            failure = _supplementary_failure(
                asset,
                candidate_url,
                status=exc.status_code,
                content_type=content_type,
                final_url=exc.url,
                body=exc.body,
                reason=supplementary_response_block_reason(content_type, exc.body) or str(exc),
            )
            fallback_response = _fetch_file_document_fallback(file_document_fetcher, candidate_url, asset)
            if fallback_response is not None:
                return _resolution_from_attempt(
                    asset=asset,
                    attempt=_AssetDownloadAttempt(
                        candidate=candidate,
                        response=fallback_response,
                        source_url=candidate_url,
                    ),
                )
            fetch_failure = _file_document_fetch_failure(file_document_fetcher, candidate_url)
            if fetch_failure:
                failure.update(fetch_failure)
            last_attempt = _AssetDownloadAttempt(candidate=candidate, failure=_asset_failure(failure))
            continue

        body = response.get("body", b"")
        content_type = _response_header(response, "content-type")
        final_url = normalize_text(str(response.get("url") or candidate_url))
        block_reason = supplementary_response_block_reason(content_type, body)
        if block_reason:
            failure = _supplementary_failure(
                asset,
                candidate_url,
                status=response.get("status_code"),
                content_type=content_type,
                final_url=final_url,
                body=body,
                reason=block_reason,
            )
            fallback_response = _fetch_file_document_fallback(file_document_fetcher, candidate_url, asset)
            if fallback_response is not None:
                return _resolution_from_attempt(
                    asset=asset,
                    attempt=_AssetDownloadAttempt(
                        candidate=candidate,
                        response=fallback_response,
                        source_url=candidate_url,
                    ),
                )
            fetch_failure = _file_document_fetch_failure(file_document_fetcher, candidate_url)
            if fetch_failure:
                failure.update(fetch_failure)
            last_attempt = _AssetDownloadAttempt(candidate=candidate, failure=_asset_failure(failure))
            continue

        return _resolution_from_attempt(
            asset=asset,
            attempt=_AssetDownloadAttempt(
                candidate=candidate,
                response=response,
                source_url=candidate_url,
            ),
        )

    return _resolution_from_attempt(asset=asset, attempt=last_attempt)


def _save_supplementary_asset_resolution(
    resolved: _AssetDownloadResolution,
    *,
    asset_dir: Path,
    used_names_by_dir: dict[Path, set[str]],
) -> dict[str, Any] | _AssetDownloadFailure:
    asset = resolved.asset
    response = resolved.response or {}
    source_url = normalize_text(resolved.source_url)
    body = response.get("body", b"")
    if not isinstance(body, (bytes, bytearray)) or not body:
        return _AssetDownloadFailure(
            _supplementary_failure(
                asset,
                source_url,
                status=response.get("status_code") if isinstance(response, Mapping) else None,
                content_type=_response_header(response, "content-type"),
                final_url=normalize_text(str(response.get("url") or source_url)),
                reason="empty_response_body",
            )
        )

    content_type = _response_header(response, "content-type")
    target_asset_dir = asset_dir
    if normalize_text(str(asset.get("asset_kind") or "")).lower() == "source_data":
        target_asset_dir = asset_dir / "source_data"
        target_asset_dir.mkdir(parents=True, exist_ok=True)
    output_path = build_asset_output_path(
        target_asset_dir,
        source_url,
        content_type,
        response.get("url") or source_url,
        used_names_by_dir.setdefault(target_asset_dir, set()),
        preferred_filename=normalize_text(str(asset.get("filename_hint") or "")) or None,
    )
    download = {
        "kind": "supplementary",
        "heading": asset.get("heading") or asset.get("filename_hint") or "Supplementary Material",
        "caption": asset.get("caption", ""),
        "download_url": source_url,
        "source_url": response.get("url") or source_url,
        "content_type": content_type,
        "path": save_payload(output_path, bytes(body)),
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


def download_supplementary_assets(
    transport: HttpTransport,
    *,
    article_id: str,
    assets: list[dict[str, Any]] | list[dict[str, str]],
    output_dir: Path | None,
    user_agent: str,
    asset_profile: AssetProfile = "all",
    headers: Mapping[str, str] | None = None,
    browser_context_seed: Mapping[str, Any] | None = None,
    seed_urls: list[str] | None = None,
    file_document_fetcher: FileDocumentFetcher | None = None,
    cookie_opener_builder: Callable[..., urllib.request.OpenerDirector | None] | None = None,
    opener_requester: Callable[..., dict[str, Any]] | None = None,
    asset_download_concurrency: int | None = None,
) -> dict[str, list[dict[str, Any]]]:
    del transport
    if output_dir is None or asset_profile != "all" or not assets:
        return empty_asset_results()

    supplementary_assets = [dict(asset) for asset in assets if html_asset_is_supplementary(asset)]
    if not supplementary_assets:
        return empty_asset_results()

    asset_dir = output_dir / f"{sanitize_filename(article_id)}_assets"
    asset_dir.mkdir(parents=True, exist_ok=True)
    used_names_by_dir: dict[Path, set[str]] = {}
    active_cookie_opener_builder = cookie_opener_builder or _build_cookie_seeded_opener
    active_opener_requester = opener_requester or _request_with_opener
    browser_cookies = list((browser_context_seed or {}).get("browser_cookies") or [])
    active_seed_urls = [
        normalized
        for normalized in [
            *[normalize_text(item) for item in seed_urls or []],
            normalize_text(str((browser_context_seed or {}).get("browser_final_url") or "")),
        ]
        if normalized
    ]

    resolved_results = _resolve_asset_downloads_in_order(
        supplementary_assets,
        resolver=lambda asset: _resolve_supplementary_asset_download(
            asset=asset,
            headers=headers,
            user_agent=user_agent,
            browser_context_seed=browser_context_seed,
            browser_cookies=browser_cookies,
            active_seed_urls=active_seed_urls,
            file_document_fetcher=file_document_fetcher,
            cookie_opener_builder=active_cookie_opener_builder,
            opener_requester=active_opener_requester,
        ),
        asset_download_concurrency=asset_download_concurrency,
    )

    return _collect_downloads_from_resolutions(
        resolved_results,
        saver=lambda resolved: _save_supplementary_asset_resolution(
            resolved,
            asset_dir=asset_dir,
            used_names_by_dir=used_names_by_dir,
        ),
    )


def _resolve_figure_asset_download(
    *,
    transport: HttpTransport,
    asset: Mapping[str, Any],
    user_agent: str,
    browser_context_seed: Mapping[str, Any] | None,
    seed_urls: list[str] | None,
    figure_page_fetcher: FigurePageFetcher | None,
    candidate_builder: Callable[..., list[str]],
    image_document_fetcher: ImageDocumentFetcher | None,
    cookie_opener_builder: Callable[..., urllib.request.OpenerDirector | None],
    opener_requester: Callable[..., dict[str, Any]],
) -> _AssetDownloadResolution:
    preview_url = normalize_text(str(asset.get("preview_url") or asset.get("url") or ""))
    full_size_url = normalize_text(str(asset.get("full_size_url") or ""))
    candidate_urls = candidate_builder(
        transport,
        asset=asset,
        user_agent=user_agent,
        figure_page_fetcher=figure_page_fetcher,
    )
    if not candidate_urls:
        return _resolution_from_attempt(
            asset=asset,
            attempt=None,
            preview_url=preview_url,
            full_size_url=full_size_url,
        )

    last_attempt: _AssetDownloadAttempt | None = None
    active_user_agent = normalize_text(str((browser_context_seed or {}).get("browser_user_agent") or "")) or user_agent
    browser_cookies = list((browser_context_seed or {}).get("browser_cookies") or [])
    active_seed_urls = [
        normalized
        for normalized in [
            *[normalize_text(item) for item in seed_urls or []],
            normalize_text(str((browser_context_seed or {}).get("browser_final_url") or "")),
        ]
        if normalized
    ]
    for candidate_url in candidate_urls:
        candidate = _AssetDownloadCandidate(candidate_url)
        parsed = urllib.parse.urlparse(candidate_url)
        if parsed.scheme not in {"http", "https"}:
            last_attempt = _AssetDownloadAttempt(
                candidate=candidate,
                failure=_asset_failure(
                    {
                        "kind": asset.get("kind", "figure"),
                        "heading": asset.get("heading", "Figure"),
                        "caption": asset.get("caption", ""),
                        "source_url": candidate_url,
                        "reason": f"Unsupported asset URL scheme for {candidate_url}",
                        "section": asset.get("section") or "body",
                    }
                ),
            )
            continue

        try:
            request_headers = {"User-Agent": active_user_agent, "Accept": "*/*"}
            opener = (
                cookie_opener_builder(
                    active_seed_urls,
                    headers=request_headers,
                    timeout=DEFAULT_FULLTEXT_TIMEOUT_SECONDS,
                    browser_cookies=browser_cookies,
                )
                if browser_cookies
                else None
            )
            cookie_header = _cookie_header_for_url(browser_cookies, candidate_url)
            if cookie_header:
                request_headers["Cookie"] = cookie_header
            response = (
                opener_requester(
                    opener,
                    candidate_url,
                    headers=request_headers,
                    timeout=DEFAULT_FULLTEXT_TIMEOUT_SECONDS,
                )
                if opener is not None
                else transport.request(
                    "GET",
                    candidate_url,
                    headers=request_headers,
                    timeout=DEFAULT_FULLTEXT_TIMEOUT_SECONDS,
                    retry_on_rate_limit=True,
                    retry_on_transient=True,
                )
            )
            body = response.get("body", b"")
            content_type = _response_header(response, "content-type")
            final_url = normalize_text(str(response.get("url") or candidate_url))
            if _requires_image_payload(asset) and not _looks_like_image_payload(content_type, body, final_url):
                last_attempt = _AssetDownloadAttempt(
                    candidate=candidate,
                    failure=_asset_failure(
                        {
                            "kind": asset.get("kind", "figure"),
                            "heading": asset.get("heading", "Figure"),
                            "caption": asset.get("caption", ""),
                            "source_url": candidate_url,
                            "status": response.get("status_code"),
                            "reason": (
                                f"Asset candidate did not return image content "
                                f"(content-type: {content_type or 'unknown'})."
                            ),
                            "section": asset.get("section") or "body",
                        }
                    ),
                )
                fallback_response = _fetch_image_document_fallback(image_document_fetcher, candidate_url, asset)
                if fallback_response is not None:
                    return _resolution_from_attempt(
                        asset=asset,
                        attempt=_AssetDownloadAttempt(
                            candidate=candidate,
                            response=fallback_response,
                            source_url=candidate_url,
                            download_tier_override="playwright_canvas_fallback",
                        ),
                        preview_url=preview_url,
                        full_size_url=full_size_url,
                    )
                continue
            if _requires_image_payload(asset) and _is_preview_candidate(
                candidate_url,
                preview_url=preview_url,
                full_size_url=full_size_url,
            ):
                for upgrade_target in _preview_upgrade_targets(candidate_url, asset):
                    if upgrade_target == candidate_url:
                        continue
                    fallback_response = _fetch_image_document_fallback(image_document_fetcher, upgrade_target, asset)
                    if fallback_response is not None:
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
                        )
            return _resolution_from_attempt(
                asset=asset,
                attempt=_AssetDownloadAttempt(
                    candidate=candidate,
                    response=response,
                    source_url=candidate_url,
                ),
                preview_url=preview_url,
                full_size_url=full_size_url,
            )
        except RequestFailure as exc:
            last_attempt = _AssetDownloadAttempt(
                candidate=candidate,
                failure=_asset_failure(
                    {
                        "kind": asset.get("kind", "figure"),
                        "heading": asset.get("heading", "Figure"),
                        "caption": asset.get("caption", ""),
                        "source_url": candidate_url,
                        "status": exc.status_code,
                        "reason": str(exc),
                        "section": asset.get("section") or "body",
                    }
                ),
            )
            fallback_response = _fetch_image_document_fallback(image_document_fetcher, candidate_url, asset)
            if fallback_response is not None:
                return _resolution_from_attempt(
                    asset=asset,
                    attempt=_AssetDownloadAttempt(
                        candidate=candidate,
                        response=fallback_response,
                        source_url=candidate_url,
                        download_tier_override="playwright_canvas_fallback",
                    ),
                    preview_url=preview_url,
                    full_size_url=full_size_url,
                )
            continue

    return _resolution_from_attempt(
        asset=asset,
        attempt=last_attempt,
        preview_url=preview_url,
        full_size_url=full_size_url,
    )


def _save_figure_asset_resolution(
    resolved: _AssetDownloadResolution,
    *,
    asset_dir: Path,
    used_names: set[str],
) -> dict[str, Any]:
    asset = resolved.asset
    response = resolved.response or {}
    preview_url = normalize_text(resolved.preview_url)
    full_size_url = normalize_text(resolved.full_size_url)
    source_url = normalize_text(resolved.source_url)
    download_tier_override = normalize_text(resolved.download_tier_override)
    content_type = _response_header(response, "content-type")
    dimensions = _response_dimensions(response) or (0, 0)
    width, height = dimensions
    download_tier = (
        download_tier_override
        or (
            "preview"
            if preview_url
            and source_url == preview_url
            and source_url != full_size_url
            and not looks_like_full_size_asset_url(source_url.lower())
            else "full_size"
        )
    )
    final_url = normalize_text(str(response.get("url") or source_url))
    body = bytes(response.get("body") or b"")
    output_path = build_asset_output_path(asset_dir, source_url, content_type, final_url, used_names)
    download = {
        "kind": asset.get("kind", "figure"),
        "heading": asset.get("heading", "Figure"),
        "caption": asset.get("caption", ""),
        "original_url": preview_url,
        "figure_page_url": asset.get("figure_page_url", ""),
        "download_url": source_url,
        "download_tier": download_tier,
        "source_url": final_url,
        "content_type": content_type,
        "path": save_payload(output_path, body),
        "downloaded_bytes": len(body),
        "section": asset.get("section") or "body",
    }
    if width > 0 and height > 0:
        download["width"] = width
        download["height"] = height
    if download_tier == "preview" and preview_dimensions_are_acceptable(width, height):
        download["preview_accepted"] = True
    return download


def download_figure_assets(
    transport: HttpTransport,
    *,
    article_id: str,
    assets: list[dict[str, str]],
    output_dir: Path | None,
    user_agent: str,
    asset_profile: AssetProfile = "all",
    figure_page_fetcher: FigurePageFetcher | None = None,
    browser_context_seed: Mapping[str, Any] | None = None,
    seed_urls: list[str] | None = None,
    candidate_builder: Callable[..., list[str]] | None = None,
    image_document_fetcher: ImageDocumentFetcher | None = None,
    cookie_opener_builder: Callable[..., urllib.request.OpenerDirector | None] | None = None,
    opener_requester: Callable[..., dict[str, Any]] | None = None,
    asset_download_concurrency: int | None = None,
) -> dict[str, list[dict[str, Any]]]:
    if output_dir is None or asset_profile == "none" or not assets:
        return empty_asset_results()

    asset_dir = output_dir / f"{sanitize_filename(article_id)}_assets"
    asset_dir.mkdir(parents=True, exist_ok=True)
    used_names: set[str] = set()
    active_candidate_builder = candidate_builder or figure_download_candidates
    active_cookie_opener_builder = cookie_opener_builder or _build_cookie_seeded_opener
    active_opener_requester = opener_requester or _request_with_opener

    resolved_results = _resolve_asset_downloads_in_order(
        list(assets),
        resolver=lambda asset: _resolve_figure_asset_download(
            transport=transport,
            asset=asset,
            user_agent=user_agent,
            browser_context_seed=browser_context_seed,
            seed_urls=seed_urls,
            figure_page_fetcher=figure_page_fetcher,
            candidate_builder=active_candidate_builder,
            image_document_fetcher=image_document_fetcher,
            cookie_opener_builder=active_cookie_opener_builder,
            opener_requester=active_opener_requester,
        ),
        asset_download_concurrency=asset_download_concurrency,
    )

    return _collect_downloads_from_resolutions(
        resolved_results,
        saver=lambda resolved: _save_figure_asset_resolution(
            resolved,
            asset_dir=asset_dir,
            used_names=used_names,
        ),
    )


def download_figure_assets_with_image_document_fetcher(
    transport: HttpTransport,
    *,
    article_id: str,
    assets: list[dict[str, str]],
    output_dir: Path | None,
    user_agent: str,
    asset_profile: AssetProfile = "all",
    figure_page_fetcher: FigurePageFetcher | None = None,
    candidate_builder: Callable[..., list[str]] | None = None,
    image_document_fetcher: ImageDocumentFetcher | None = None,
    asset_download_concurrency: int | None = None,
) -> dict[str, list[dict[str, Any]]]:
    if output_dir is None or asset_profile == "none" or not assets:
        return empty_asset_results()

    asset_dir = output_dir / f"{sanitize_filename(article_id)}_assets"
    asset_dir.mkdir(parents=True, exist_ok=True)
    used_names: set[str] = set()
    active_candidate_builder = candidate_builder or figure_download_candidates
    work_items = [(index, asset) for index, asset in enumerate(assets) if _requires_image_payload(asset)]
    resolved_work_results = _resolve_asset_downloads_in_order(
        work_items,
        resolver=lambda item: _resolve_figure_asset_with_image_document_fetcher(
            transport=transport,
            asset=item[1],
            user_agent=user_agent,
            candidate_builder=active_candidate_builder,
            figure_page_fetcher=figure_page_fetcher,
            image_document_fetcher=image_document_fetcher,
        ),
        asset_download_concurrency=asset_download_concurrency,
    )
    resolved_by_index: dict[int, _AssetDownloadResolution | None] = {
        index: resolved
        for (index, _asset), resolved in zip(work_items, resolved_work_results)
    }
    resolved_results = [resolved_by_index.get(index) for index in range(len(assets))]

    return _collect_downloads_from_resolutions(
        resolved_results,
        saver=lambda resolved: _save_figure_asset_resolution(
            resolved,
            asset_dir=asset_dir,
            used_names=used_names,
        ),
    )


__all__ = [
    "_CLOUDFLARE_CHALLENGE_TOKENS",
    "SUPPLEMENTARY_BLOCKING_TITLE_TOKENS",
    "SUPPLEMENTARY_BLOCKING_BODY_TOKENS",
    "ImageDocumentFetcher",
    "FileDocumentFetcher",
    "download_supplementary_assets",
    "download_figure_assets",
    "download_figure_assets_with_image_document_fetcher",
    "_build_cookie_seeded_opener",
    "_request_with_opener",
]
