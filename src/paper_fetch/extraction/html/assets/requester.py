"""Cookie-aware urllib requester shared by asset and PDF fallback paths."""

from __future__ import annotations

import http.cookiejar
import urllib.error
import urllib.parse
import urllib.request
from typing import Any
from collections.abc import Mapping

from ....http import RequestFailure, classify_network_error
from ....models import normalize_text


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
) -> urllib.request.OpenerDirector | None:
    normalized_seed_urls = [
        normalize_text(url) for url in seed_urls or [] if normalize_text(url)
    ]
    if not normalized_seed_urls and not any(
        isinstance(cookie, dict) for cookie in browser_cookies or []
    ):
        return None

    opener = urllib.request.build_opener(
        urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar())
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
        request_headers = dict(seed_headers)
        cookie_header = cookie_header_for_url(browser_cookies, seed_url)
        if cookie_header:
            request_headers["Cookie"] = cookie_header
        request = urllib.request.Request(seed_url, headers=request_headers)
        try:
            with opener.open(request, timeout=timeout) as response:
                response.read(1024)
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
) -> dict[str, Any]:
    request = urllib.request.Request(url, headers=dict(headers))
    try:
        with opener.open(request, timeout=timeout) as response:
            return {
                "status_code": int(getattr(response, "status", response.getcode())),
                "headers": {
                    str(key).lower(): str(value)
                    for key, value in response.headers.items()
                },
                "body": response.read(),
                "url": str(response.geturl() or url),
            }
    except urllib.error.HTTPError as exc:
        raise RequestFailure(
            exc.code,
            f"HTTP {exc.code} for {url}",
            body=exc.read(),
            headers={
                str(key).lower(): str(value) for key, value in exc.headers.items()
            },
            url=str(exc.geturl() or url),
        ) from exc
    except urllib.error.URLError as exc:
        raise RequestFailure(
            None,
            f"Failed to download {failure_label}: {exc.reason or exc}",
            url=url,
            error_category=classify_network_error(exc),
        ) from exc


__all__ = [
    "build_cookie_seeded_opener",
    "cookie_header_for_url",
    "request_with_opener",
]
