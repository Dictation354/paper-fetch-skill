"""Synchronous network guard shared by Playwright and Camoufox call sites."""

from __future__ import annotations

import urllib.parse
import contextlib
from dataclasses import dataclass
from typing import Any
from collections.abc import Callable, Iterable, Mapping

from .errors import RequestFailure
from .url_policy import DEFAULT_SAFE_REMOTE_URL_POLICY, SafeRemoteUrlPolicy

_BROWSER_REDIRECT_STATUS_CODES = frozenset({301, 302, 303, 307, 308})
_CROSS_ORIGIN_SENSITIVE_HEADERS = frozenset(
    {"authorization", "cookie", "proxy-authorization", "referer"}
)


def url_origin(url: str) -> tuple[str, str, int] | None:
    parsed = urllib.parse.urlsplit(str(url or "").strip())
    scheme = parsed.scheme.lower()
    host = str(parsed.hostname or "").strip().lower().rstrip(".")
    if scheme not in {"http", "https"} or not host:
        return None
    try:
        port = parsed.port or (443 if scheme == "https" else 80)
    except ValueError:
        return None
    return scheme, host, port


@dataclass
class BrowserNetworkGuard:
    """Validate every browser request immediately before it is continued."""

    allowed_hosts: tuple[str, ...]
    policy: SafeRemoteUrlPolicy = DEFAULT_SAFE_REMOTE_URL_POLICY
    credential_origin: tuple[str, str, int] | None = None

    def set_credential_origin(self, url: str | None) -> None:
        self.credential_origin = url_origin(url or "")

    def credentials_may_reach(self, url: str) -> bool:
        return (
            self.credential_origin is None or url_origin(url) == self.credential_origin
        )

    def validate(
        self,
        url: str,
        *,
        previous_url: str | None = None,
        resolve_dns: bool = True,
        enforce_credential_origin: bool = True,
    ) -> str:
        validated = self.policy.validate(
            url,
            allowed_hosts=self.allowed_hosts,
            previous_url=previous_url,
            resolve_dns=resolve_dns,
        )
        if enforce_credential_origin and not self.credentials_may_reach(validated.url):
            raise RequestFailure(
                None,
                "Credentialed browser context may only request its authenticated origin.",
                url=validated.url,
                error_category="unsafe_redirect",
            )
        return validated.url

    def validate_route_request(self, request: Any) -> str:
        request_url = str(getattr(request, "url", "") or "")
        redirected_from = getattr(request, "redirected_from", None)
        previous_url = (
            str(getattr(redirected_from, "url", "") or "")
            if redirected_from is not None
            else None
        )
        return self.validate(
            request_url,
            previous_url=previous_url,
            resolve_dns=True,
        )

    def route_handler(self, route: Any) -> None:
        try:
            self.validate_route_request(route.request)
        except Exception:
            route.abort()
            return
        route.continue_()

    def install_on_context(
        self,
        browser_context: Any,
        *,
        after_validation: Callable[[Any], None] | None = None,
    ) -> Callable[[Any], None]:
        """Install a fail-closed context-wide route before any page is created."""

        diagnostics = getattr(
            browser_context, "_paper_fetch_external_cdp_diagnostics", {}
        )
        if isinstance(diagnostics, Mapping) and diagnostics.get(
            "borrowed_existing_context"
        ):
            raise RequestFailure(
                None,
                "Cannot secure a borrowed browser context against service-worker bypass.",
                error_category="unsafe_redirect",
            )
        route_method = getattr(browser_context, "route", None)
        if not callable(route_method):
            raise RequestFailure(
                None,
                "Browser context does not support a context-wide network interceptor.",
                error_category="unsafe_redirect",
            )

        def guarded_route_handler(route: Any) -> None:
            try:
                self.validate_route_request(route.request)
                if after_validation is None:
                    route.continue_()
                else:
                    after_validation(route)
            except Exception:
                with contextlib.suppress(Exception):
                    route.abort()

        try:
            route_method("**/*", guarded_route_handler)
        except Exception as exc:
            raise RequestFailure(
                None,
                "Unable to install the browser context network interceptor.",
                error_category="unsafe_redirect",
            ) from exc
        return guarded_route_handler


def _browser_response_headers(response: Any) -> dict[str, str]:
    headers = getattr(response, "headers", {}) or {}
    if callable(headers):
        headers = headers()
    if not isinstance(headers, Mapping):
        all_headers = getattr(response, "all_headers", None)
        headers = all_headers() if callable(all_headers) else {}
    return {
        str(key).strip().lower(): str(value) for key, value in dict(headers).items()
    }


def _browser_response_status(response: Any) -> int:
    try:
        return int(getattr(response, "status", 0) or 0)
    except (TypeError, ValueError):
        return 0


def guarded_browser_request_get(
    request_context: Any,
    url: str,
    *,
    guard: BrowserNetworkGuard,
    headers: Mapping[str, str] | None = None,
    timeout_ms: int,
    max_redirects: int = 5,
) -> Any:
    """Issue a Playwright request-context GET with manual, validated redirects."""

    current_url = guard.validate(url, resolve_dns=True)
    previous_url: str | None = None
    active_headers = dict(headers or {})
    for redirect_count in range(max(0, int(max_redirects)) + 1):
        current_url = guard.validate(
            current_url,
            previous_url=previous_url,
            resolve_dns=True,
        )
        response = request_context.get(
            current_url,
            headers=active_headers or None,
            timeout=timeout_ms,
            max_redirects=0,
        )
        response_url = str(getattr(response, "url", "") or current_url)
        guard.validate(
            response_url,
            previous_url=current_url,
            resolve_dns=True,
        )
        response_headers = _browser_response_headers(response)
        location = response_headers.get("location", "").strip()
        if _browser_response_status(response) not in _BROWSER_REDIRECT_STATUS_CODES:
            return response
        if not location:
            return response
        if redirect_count >= max_redirects:
            raise RequestFailure(
                None,
                f"Browser request exceeded {max_redirects} redirects.",
                url=current_url,
                error_category="unsafe_redirect",
            )
        next_url = urllib.parse.urljoin(response_url, location)
        next_url = guard.validate(
            next_url,
            previous_url=response_url,
            resolve_dns=True,
        )
        if url_origin(next_url) != url_origin(response_url):
            active_headers = {
                key: value
                for key, value in active_headers.items()
                if key.strip().lower() not in _CROSS_ORIGIN_SENSITIVE_HEADERS
            }
        dispose = getattr(response, "dispose", None)
        if callable(dispose):
            dispose()
        previous_url, current_url = response_url, next_url

    raise AssertionError("redirect loop must return or raise")


def hosts_from_urls(urls: Iterable[str]) -> tuple[str, ...]:
    return tuple(
        dict.fromkeys(
            host
            for value in urls
            if (
                host := str(
                    urllib.parse.urlsplit(str(value or "")).hostname or ""
                ).lower()
            )
        )
    )


__all__ = [
    "BrowserNetworkGuard",
    "guarded_browser_request_get",
    "hosts_from_urls",
    "url_origin",
]
