"""Cookie-aware urllib requester shared by asset and PDF fallback paths."""

from __future__ import annotations

import http.cookiejar
import http.client
import urllib.error
import urllib.parse
import urllib.request
from typing import Any
from collections.abc import Callable, Mapping

from ....http import (
    DEFAULT_MAX_RESPONSE_BYTES,
    RequestCancelledError,
    RequestErrorCategory,
    RequestFailure,
    classify_network_error,
)
from ....http.cache import redact_url_for_cache
from ....models import normalize_text

DEFAULT_PDF_MAX_RESPONSE_BYTES = 128 * 1024 * 1024
_READ_CHUNK_BYTES = 64 * 1024
_SENSITIVE_REDIRECT_HEADERS = frozenset({"authorization", "cookie", "referer"})


def _validated_http_url(url: str, *, label: str) -> urllib.parse.ParseResult:
    normalized = normalize_text(url)
    parsed = urllib.parse.urlparse(normalized)
    if (
        parsed.scheme.lower() not in {"http", "https"}
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
    ):
        raise RequestFailure(
            None,
            f"Rejected {label}: {redact_url_for_cache(normalized)}",
            url=normalized,
            error_category=RequestErrorCategory.UNSUPPORTED_SCHEME,
        )
    return parsed


def _origin(parsed: urllib.parse.ParseResult) -> tuple[str, str, int | None]:
    default_port = 443 if parsed.scheme.lower() == "https" else 80
    return (
        parsed.scheme.lower(),
        normalize_text(parsed.hostname).lower(),
        parsed.port or default_port,
    )


class _SafeRedirectHandler(urllib.request.HTTPRedirectHandler):
    def redirect_request(
        self,
        request: urllib.request.Request,
        file_pointer: Any,
        code: int,
        message: str,
        headers: http.client.HTTPMessage,
        new_url: str,
    ) -> urllib.request.Request | None:
        source = _validated_http_url(request.full_url, label="redirect source URL")
        target = _validated_http_url(new_url, label="redirect target URL")
        redirected = super().redirect_request(
            request, file_pointer, code, message, headers, new_url
        )
        if redirected is None:
            return None
        if _origin(source) != _origin(target):
            for key in tuple(redirected.headers):
                if key.lower() in _SENSITIVE_REDIRECT_HEADERS:
                    redirected.remove_header(key)
            for key in tuple(redirected.unredirected_hdrs):
                if key.lower() in _SENSITIVE_REDIRECT_HEADERS:
                    redirected.remove_header(key)
        return redirected


def _content_length(headers: Mapping[str, Any] | None) -> int | None:
    value = next(
        (
            raw
            for key, raw in (headers or {}).items()
            if str(key).lower() == "content-length"
        ),
        None,
    )
    try:
        parsed = int(str(value))
    except (TypeError, ValueError):
        return None
    return parsed if parsed >= 0 else None


def _read_bounded(
    response: Any,
    *,
    max_response_bytes: int,
    url: str,
    cancel_check: Callable[[], bool] | None,
) -> bytes:
    declared = _content_length(getattr(response, "headers", None))
    if declared is not None and declared > max_response_bytes:
        raise RequestFailure(
            None,
            (
                f"Response body exceeded {max_response_bytes} bytes for "
                f"{redact_url_for_cache(url)}"
            ),
            url=url,
            error_category=RequestErrorCategory.RESPONSE_TOO_LARGE,
        )

    chunks: list[bytes] = []
    total = 0
    while True:
        if cancel_check is not None and cancel_check():
            raise RequestCancelledError("Request cancelled.")
        requested = min(_READ_CHUNK_BYTES, max_response_bytes - total + 1)
        chunk = response.read(requested)
        if not chunk:
            break
        chunks.append(chunk)
        total += len(chunk)
        if total > max_response_bytes:
            raise RequestFailure(
                None,
                (
                    f"Response body exceeded {max_response_bytes} bytes for "
                    f"{redact_url_for_cache(url)}"
                ),
                body=b"".join(chunks)[:max_response_bytes],
                url=url,
                error_category=RequestErrorCategory.RESPONSE_TOO_LARGE,
            )
        if len(chunk) < requested:
            break
    return b"".join(chunks)


def cookie_header_for_url(
    browser_cookies: list[dict[str, Any]] | None, url: str
) -> str | None:
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

        cookie_domain = (
            normalize_text(str(cookie.get("domain") or "")).lower().lstrip(".")
        )
        if not cookie_domain:
            cookie_url = normalize_text(str(cookie.get("url") or ""))
            cookie_domain = normalize_text(
                urllib.parse.urlparse(cookie_url).hostname
            ).lower()
        if (
            cookie_domain
            and host != cookie_domain
            and not host.endswith(f".{cookie_domain}")
        ):
            continue

        cookie_path = normalize_text(str(cookie.get("path") or "")) or "/"
        if not path.startswith(cookie_path):
            continue

        if bool(cookie.get("secure")) and scheme != "https":
            continue

        matched_pairs.append(f"{name}={value}")

    return "; ".join(matched_pairs) if matched_pairs else None


def build_cookie_seeded_opener(
    seed_urls: list[str] | None,
    *,
    headers: Mapping[str, str],
    timeout: int,
    browser_cookies: list[dict[str, Any]] | None = None,
    cancel_check: Callable[[], bool] | None = None,
    force: bool = False,
) -> urllib.request.OpenerDirector | None:
    normalized_seed_urls = [
        normalize_text(url) for url in seed_urls or [] if normalize_text(url)
    ]
    if (
        not force
        and not normalized_seed_urls
        and not any(isinstance(cookie, dict) for cookie in browser_cookies or [])
    ):
        return None

    opener = urllib.request.build_opener(
        urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()),
        _SafeRedirectHandler(),
    )
    seed_headers = {
        key: value
        for key, value in dict(headers).items()
        if str(key).lower() != "accept"
    }
    seed_headers.setdefault(
        "Accept", "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
    )

    for seed_url in normalized_seed_urls:
        if cancel_check is not None and cancel_check():
            raise RequestCancelledError("Request cancelled.")
        _validated_http_url(seed_url, label="cookie seed URL")
        request_headers = dict(seed_headers)
        cookie_header = cookie_header_for_url(browser_cookies, seed_url)
        if cookie_header:
            request_headers["Cookie"] = cookie_header
        request = urllib.request.Request(seed_url, headers=request_headers)
        try:
            with opener.open(request, timeout=timeout) as response:
                response.read(1024)
                if cancel_check is not None and cancel_check():
                    raise RequestCancelledError("Request cancelled.")
        except RequestCancelledError:
            raise
        except Exception:
            continue

    return opener


def request_with_opener(
    opener: urllib.request.OpenerDirector,
    url: str,
    *,
    headers: Mapping[str, str],
    timeout: int,
    failure_label: str = "asset candidate",
    max_response_bytes: int = DEFAULT_MAX_RESPONSE_BYTES,
    cancel_check: Callable[[], bool] | None = None,
) -> dict[str, Any]:
    _validated_http_url(url, label=failure_label)
    request = urllib.request.Request(url, headers=dict(headers))
    try:
        with opener.open(request, timeout=timeout) as response:
            final_url = str(response.geturl() or url)
            _validated_http_url(final_url, label="redirect result URL")
            return {
                "status_code": int(getattr(response, "status", response.getcode())),
                "headers": {
                    str(key).lower(): str(value)
                    for key, value in response.headers.items()
                },
                "body": _read_bounded(
                    response,
                    max_response_bytes=max_response_bytes,
                    url=final_url,
                    cancel_check=cancel_check,
                ),
                "url": final_url,
            }
    except (RequestFailure, RequestCancelledError):
        raise
    except urllib.error.HTTPError as exc:
        final_url = str(exc.geturl() or url)
        _validated_http_url(final_url, label="HTTP error URL")
        raise RequestFailure(
            exc.code,
            f"HTTP {exc.code} for {redact_url_for_cache(final_url)}",
            body=_read_bounded(
                exc,
                max_response_bytes=max_response_bytes,
                url=final_url,
                cancel_check=cancel_check,
            ),
            headers={
                str(key).lower(): str(value) for key, value in exc.headers.items()
            },
            url=final_url,
        ) from exc
    except urllib.error.URLError as exc:
        raise RequestFailure(
            None,
            f"Failed to download {failure_label}: {exc.reason or exc}",
            url=redact_url_for_cache(url),
            error_category=classify_network_error(exc),
        ) from exc


__all__ = [
    "DEFAULT_PDF_MAX_RESPONSE_BYTES",
    "build_cookie_seeded_opener",
    "cookie_header_for_url",
    "request_with_opener",
]
