"""Cookie-aware urllib requester shared by asset and PDF fallback paths."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from email.message import Message
import http.cookiejar
import http.client
import time
from typing import Any, cast
import urllib.error
import urllib.parse
import urllib.request

from ....http import (
    DEFAULT_FULLTEXT_TIMEOUT_SECONDS,
    DEFAULT_SAFE_REMOTE_URL_POLICY,
    DEFAULT_MAX_RESPONSE_BYTES,
    DEFAULT_TRANSIENT_BACKOFF_BASE_SECONDS,
    DEFAULT_TRANSIENT_RETRIES,
    HttpRequestPolicy,
    HttpTransport,
    RequestCancelledError,
    RequestErrorCategory,
    RequestFailure,
    SafeRemoteUrlPolicy,
    classify_network_error,
    provider_request_policy,
)
from ....http.cache import redact_url_for_cache
from ....models import normalize_text
from ....pdf_limits import DEFAULT_PDF_MAX_BYTES

DEFAULT_PDF_MAX_RESPONSE_BYTES = DEFAULT_PDF_MAX_BYTES
_READ_CHUNK_BYTES = 64 * 1024
_SENSITIVE_REDIRECT_HEADERS = frozenset({"authorization", "cookie", "referer"})
_ASSET_SEED_MAX_RESPONSE_BYTES = 8192


def _validated_http_url(
    url: str,
    *,
    label: str,
    policy: SafeRemoteUrlPolicy | None = None,
    previous_url: str | None = None,
    resolve_dns: bool = False,
) -> urllib.parse.ParseResult:
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
    (policy or DEFAULT_SAFE_REMOTE_URL_POLICY).validate(
        normalized,
        previous_url=previous_url,
        resolve_dns=resolve_dns,
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
    def __init__(self, policy: SafeRemoteUrlPolicy | None = None) -> None:
        super().__init__()
        self._policy = policy

    def redirect_request(
        self,
        request: urllib.request.Request,
        file_pointer: Any,
        code: int,
        message: str,
        headers: http.client.HTTPMessage,
        new_url: str,
    ) -> urllib.request.Request | None:
        source = _validated_http_url(
            request.full_url,
            label="redirect source URL",
            policy=self._policy,
        )
        target = _validated_http_url(
            new_url,
            label="redirect target URL",
            policy=self._policy,
            previous_url=request.full_url,
            resolve_dns=self._policy is not None,
        )
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
    request = urllib.request.Request(normalize_text(url))
    cookie_jar = browser_cookie_jar(browser_cookies)
    cookie_jar.add_cookie_header(request)
    return request.get_header("Cookie")


def cookie_header_from_jar(
    cookie_jar: http.cookiejar.CookieJar,
    url: str,
) -> str | None:
    request = urllib.request.Request(normalize_text(url))
    cookie_jar.add_cookie_header(request)
    return request.get_header("Cookie")


def _browser_cookie(
    payload: Mapping[str, Any],
) -> http.cookiejar.Cookie | None:
    name = normalize_text(str(payload.get("name") or ""))
    if not name:
        return None
    raw_domain = normalize_text(str(payload.get("domain") or "")).lower()
    cookie_url = normalize_text(str(payload.get("url") or ""))
    fallback_host = normalize_text(urllib.parse.urlsplit(cookie_url).hostname).lower()
    domain = raw_domain or fallback_host
    if not domain:
        return None
    domain_initial_dot = raw_domain.startswith(".")
    # Playwright represents host-only cookies without a leading dot.  Feeding
    # those to CookieJar as domain cookies would incorrectly widen them to
    # subdomains.
    domain_specified = bool(raw_domain and domain_initial_dot)
    path = normalize_text(str(payload.get("path") or "")) or "/"
    expires_value = payload.get("expires")
    try:
        parsed_expires = float(expires_value) if expires_value is not None else 0.0
        expires = int(parsed_expires) if parsed_expires > 0 else None
    except (TypeError, ValueError):
        expires = None
    rest: dict[str, str] = {}
    if payload.get("httpOnly"):
        rest["HttpOnly"] = ""
    same_site = normalize_text(str(payload.get("sameSite") or ""))
    if same_site:
        rest["SameSite"] = same_site
    return http.cookiejar.Cookie(
        version=0,
        name=name,
        value=str(payload.get("value") or ""),
        port=None,
        port_specified=False,
        domain=domain,
        domain_specified=domain_specified,
        domain_initial_dot=domain_initial_dot,
        path=path,
        path_specified=True,
        secure=bool(payload.get("secure")),
        expires=expires,
        discard=expires is None,
        comment=None,
        comment_url=None,
        rest=rest,
        rfc2109=False,
    )


def browser_cookie_jar(
    browser_cookies: list[dict[str, Any]] | None,
) -> http.cookiejar.CookieJar:
    """Convert Playwright cookies without widening their RFC 6265 scope."""

    cookie_jar = http.cookiejar.CookieJar(
        policy=http.cookiejar.DefaultCookiePolicy(
            strict_ns_domain=http.cookiejar.DefaultCookiePolicy.DomainStrictNonDomain
        )
    )
    now = int(time.time())
    for payload in browser_cookies or []:
        if not isinstance(payload, Mapping):
            continue
        cookie = _browser_cookie(payload)
        if cookie is None or (cookie.expires is not None and cookie.expires <= now):
            continue
        cookie_jar.set_cookie(cookie)
    return cookie_jar


class PinnedAssetSession:
    """Per-worker CookieJar and one-shot seed state over pinned HttpTransport."""

    def __init__(
        self,
        transport: HttpTransport,
        *,
        browser_cookies: list[dict[str, Any]] | None,
        seed_urls: list[str] | None,
        headers: Mapping[str, str] | None,
        allowed_hosts: tuple[str, ...] | None = None,
        provider_name: str | None = None,
        route_name: str | None = None,
        timeout: int = DEFAULT_FULLTEXT_TIMEOUT_SECONDS,
    ) -> None:
        self.transport = transport
        self.cookie_jar = browser_cookie_jar(browser_cookies)
        self.seed_urls = [
            normalize_text(url) for url in seed_urls or [] if normalize_text(url)
        ]
        self.headers = dict(headers or {})
        self.allowed_hosts = tuple(allowed_hosts or ()) or None
        self.provider_name = normalize_text(provider_name).lower() or None
        self.route_name = normalize_text(route_name).lower() or None
        self.timeout = max(1, int(timeout))
        self.seed_ready = False
        self.seed_attempts = 0

    def allowed_hosts_for(self, url: str) -> tuple[str, ...]:
        del url
        return tuple(self.allowed_hosts or ())

    def request_headers_for(
        self, url: str, headers: Mapping[str, str]
    ) -> dict[str, str]:
        request_headers = dict(headers)
        cookie_header = cookie_header_from_jar(self.cookie_jar, url)
        if cookie_header:
            request_headers["Cookie"] = cookie_header
        return request_headers

    def prepare_hop_headers(
        self,
        url: str,
        headers: Mapping[str, str],
    ) -> dict[str, str]:
        """Refresh only Cookie from this worker jar for a validated hop."""

        explicit_cookie = next(
            (
                (key, value)
                for key, value in headers.items()
                if str(key).strip().lower() == "cookie"
            ),
            None,
        )
        without_stale_cookie = {
            key: value
            for key, value in headers.items()
            if str(key).strip().lower() != "cookie"
        }
        refreshed = self.request_headers_for(url, without_stale_cookie)
        # Preserve an explicit first-hop Cookie only until redirect handling
        # strips it. A matching jar value takes precedence and cross-origin
        # hops cannot resurrect the removed header.
        if "Cookie" not in refreshed and explicit_cookie is not None:
            refreshed[str(explicit_cookie[0])] = str(explicit_cookie[1])
        return refreshed

    def import_browser_cookies(
        self,
        browser_cookies: list[dict[str, Any]] | None,
    ) -> None:
        for payload in browser_cookies or []:
            if not isinstance(payload, Mapping):
                continue
            cookie = _browser_cookie(payload)
            if cookie is not None:
                self.cookie_jar.set_cookie(cookie)

    def request_policy_for(
        self,
        url: str,
        *,
        max_response_bytes: int,
        max_compressed_response_bytes: int | None = None,
    ) -> HttpRequestPolicy:
        allowed_hosts = self.allowed_hosts_for(url)
        base_policy = HttpRequestPolicy(
            allowed_hosts=allowed_hosts or None,
            sensitive_headers=("cookie",),
            max_response_bytes=max_response_bytes,
            max_compressed_response_bytes=max_compressed_response_bytes,
            timeout_seconds=self.timeout,
            retry_on_rate_limit=True,
            rate_limit_retries=1,
            max_rate_limit_wait_seconds=5,
            retry_on_transient=True,
            transient_retries=DEFAULT_TRANSIENT_RETRIES,
            transient_backoff_base_seconds=DEFAULT_TRANSIENT_BACKOFF_BASE_SECONDS,
        )
        if self.provider_name is None:
            return base_policy
        return provider_request_policy(
            self.provider_name, self.route_name, base=base_policy
        )

    def ensure_seeded(self) -> None:
        if self.seed_ready:
            return
        seed_headers = {
            key: value
            for key, value in self.headers.items()
            if str(key).lower() != "accept"
        }
        seed_headers.setdefault(
            "Accept",
            "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        )
        try:
            for seed_url in self.seed_urls:
                self.seed_attempts += 1
                request_headers = self.request_headers_for(seed_url, seed_headers)
                response_url = seed_url
                try:
                    if callable(getattr(type(self.transport), "request_preview", None)):
                        response = self.transport.request_preview(
                            "GET",
                            seed_url,
                            headers=request_headers,
                            timeout=self.timeout,
                            preview_bytes=_ASSET_SEED_MAX_RESPONSE_BYTES,
                            request_policy=self.request_policy_for(
                                seed_url,
                                max_response_bytes=_ASSET_SEED_MAX_RESPONSE_BYTES,
                            ),
                            on_response_headers=self.observe_response_headers,
                            request_headers_provider=self.prepare_hop_headers,
                        )
                    else:
                        # Compatibility for injected transports. Production
                        # HttpTransport always uses the bounded pinned preview.
                        response = self.transport.request(
                            "GET",
                            seed_url,
                            headers=request_headers,
                            timeout=self.timeout,
                            retry_on_rate_limit=True,
                            retry_on_transient=True,
                            request_policy=self.request_policy_for(
                                seed_url,
                                max_response_bytes=_ASSET_SEED_MAX_RESPONSE_BYTES,
                            ),
                        )
                    response_url = (
                        normalize_text(str(response.get("url") or "")) or seed_url
                    )
                    header_values = response.get("_paper_fetch_header_values")
                    set_cookie_values = (
                        list(header_values.get("set-cookie") or [])
                        if isinstance(header_values, Mapping)
                        else []
                    )
                except RequestFailure as exc:
                    set_cookie_values = [
                        str(value)
                        for key, value in exc.headers.items()
                        if str(key).lower() == "set-cookie"
                    ]
                except Exception:
                    set_cookie_values = []
                # Production already observed each hop. Re-importing only the
                # final values is idempotent and keeps injected transports that
                # bypass the observer compatible without assigning a redirect
                # cookie to the original host.
                self._store_response_cookies(response_url, set_cookie_values)
        finally:
            # A failed warmup is still terminal for this worker. Candidate
            # requests retain the initial browser CookieJar and must not create
            # an N-assets x M-seeds retry fanout.
            self.seed_ready = True

    def _store_response_cookies(
        self,
        request_url: str,
        set_cookie_values: list[str],
    ) -> None:
        if not set_cookie_values:
            return
        message = Message()
        for value in set_cookie_values:
            message.add_header("Set-Cookie", str(value))

        class _CookieResponse:
            def info(self) -> Message:
                return message

        try:
            self.cookie_jar.extract_cookies(
                _CookieResponse(),  # type: ignore[arg-type]
                urllib.request.Request(request_url),
            )
        except Exception:
            return

    def observe_response_headers(self, response_url: str, headers: Any) -> None:
        """Import Set-Cookie from every validated redirect/final response."""

        getter = getattr(headers, "getlist", None)
        if callable(getter):
            try:
                set_cookie_values = [
                    str(value) for value in getter("set-cookie") if str(value)
                ]
            except Exception:
                set_cookie_values = []
        else:
            set_cookie_values = [
                str(value)
                for key, value in getattr(headers, "items", lambda: ())()
                if str(key).lower() == "set-cookie" and str(value)
            ]
        self._store_response_cookies(response_url, set_cookie_values)


def build_cookie_seeded_opener(
    seed_urls: list[str] | None,
    *,
    headers: Mapping[str, str],
    timeout: int,
    timeout_provider: Callable[[], int] | None = None,
    browser_cookies: list[dict[str, Any]] | None = None,
    cancel_check: Callable[[], bool] | None = None,
    force: bool = False,
    remote_url_policy: SafeRemoteUrlPolicy | None = None,
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

    policy = remote_url_policy or DEFAULT_SAFE_REMOTE_URL_POLICY
    cookie_jar = browser_cookie_jar(browser_cookies)
    opener = urllib.request.build_opener(
        urllib.request.HTTPCookieProcessor(cookie_jar),
        _SafeRedirectHandler(policy),
    )
    cast(Any, opener)._paper_fetch_remote_url_policy = policy
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
        _validated_http_url(
            seed_url,
            label="cookie seed URL",
            policy=policy,
            resolve_dns=True,
        )
        request_headers = dict(seed_headers)
        request = urllib.request.Request(seed_url, headers=request_headers)
        try:
            active_timeout = (
                max(1, int(timeout_provider()))
                if timeout_provider is not None
                else timeout
            )
            with opener.open(request, timeout=active_timeout) as response:
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
    policy = getattr(opener, "_paper_fetch_remote_url_policy", None)
    _validated_http_url(
        url,
        label=failure_label,
        policy=policy,
        resolve_dns=policy is not None,
    )
    request = urllib.request.Request(url, headers=dict(headers))
    try:
        with opener.open(request, timeout=timeout) as response:
            final_url = str(response.geturl() or url)
            _validated_http_url(
                final_url,
                label="redirect result URL",
                policy=policy,
                previous_url=url,
                resolve_dns=policy is not None,
            )
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
        _validated_http_url(
            final_url,
            label="HTTP error URL",
            policy=policy,
            previous_url=url,
            resolve_dns=policy is not None,
        )
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
    "PinnedAssetSession",
    "browser_cookie_jar",
    "build_cookie_seeded_opener",
    "cookie_header_for_url",
    "cookie_header_from_jar",
    "request_with_opener",
]
