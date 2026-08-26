from __future__ import annotations

import socket
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from unittest import mock

import pytest
import urllib3
import paper_fetch.http.browser_policy as browser_policy
import paper_fetch.http.provider_policy as provider_policy_module

from paper_fetch.http import (
    BrowserNetworkGuard,
    HttpRequestPolicy,
    HttpTransportOptions,
    HttpTransport,
    RequestErrorCategory,
    RequestFailure,
    SafeRemoteUrlPolicy,
    _PreparedRequest,
    guarded_browser_request_get,
    provider_request_policy,
)
from paper_fetch.extraction.html.assets.requester import PinnedAssetSession


def _resolver_for(mapping: dict[str, tuple[str, ...]]):
    def resolve(host: str, port: int, *, type: int):
        assert type == socket.SOCK_STREAM
        return [
            (
                socket.AF_INET6 if ":" in address else socket.AF_INET,
                type,
                6,
                "",
                (address, port),
            )
            for address in mapping[host]
        ]

    return resolve


@dataclass
class _Response:
    status: int
    headers: dict[str, str]
    closed: bool = False

    def close(self) -> None:
        self.closed = True


class _Pool:
    def __init__(self, responses: list[_Response]) -> None:
        self.responses = list(responses)
        self.requests: list[tuple[str, str, dict[str, str]]] = []
        self.connections: list[dict[str, object]] = []

    def connection_from_host(self, host, *, port, scheme, pool_kwargs):
        self.connections.append(
            {
                "host": host,
                "port": port,
                "scheme": scheme,
                "pool_kwargs": dict(pool_kwargs),
            }
        )
        return self

    def urlopen(self, method: str, url: str, *, headers, **_kwargs):
        self.requests.append((method, url, dict(headers)))
        return self.responses.pop(0)


class _StreamingResponse(_Response):
    def __init__(
        self,
        status: int,
        headers: object,
        body: bytes = b"",
    ) -> None:
        super().__init__(status, headers)  # type: ignore[arg-type]
        self._stream = BytesIO(body)
        self.released = False

    def read(self, amount: int, **_kwargs: object) -> bytes:
        return self._stream.read(amount)

    def geturl(self) -> str:
        return str(getattr(self, "_paper_fetch_final_url", "") or "")

    def release_conn(self) -> None:
        self.released = True


@pytest.mark.parametrize(
    "address",
    (
        "127.0.0.1",
        "10.0.0.1",
        "169.254.169.254",
        "::1",
        "fc00::1",
        "fe80::1",
        "0.0.0.0",
        "224.0.0.1",
    ),
)
def test_policy_rejects_non_public_addresses(address: str) -> None:
    policy = SafeRemoteUrlPolicy(resolver=_resolver_for({"unsafe.example": (address,)}))

    with pytest.raises(RequestFailure) as raised:
        policy.validate("https://unsafe.example/article")

    assert raised.value.error_category == RequestErrorCategory.UNSAFE_REDIRECT


def test_policy_rejects_dns_answer_when_any_address_is_private() -> None:
    policy = SafeRemoteUrlPolicy(
        resolver=_resolver_for({"mixed.example": ("8.8.8.8", "169.254.169.254")})
    )

    with pytest.raises(RequestFailure):
        policy.validate("https://mixed.example/article")


def test_policy_rejects_empty_dns_answer() -> None:
    policy = SafeRemoteUrlPolicy(resolver=lambda *_args, **_kwargs: [])

    with pytest.raises(RequestFailure) as raised:
        policy.validate("https://empty.example/article")

    assert raised.value.error_category == RequestErrorCategory.DNS_ERROR


def test_policy_enforces_route_hosts_ports_userinfo_and_downgrade() -> None:
    policy = SafeRemoteUrlPolicy(resolver=_resolver_for({"cdn.example": ("8.8.8.8",)}))
    validated = policy.validate(
        "https://images.cdn.example/figure.png",
        allowed_hosts=("cdn.example",),
        resolve_dns=False,
    )
    assert validated.host == "images.cdn.example"

    for url in (
        "https://user:password@cdn.example/article",
        "https://cdn.example:8443/article",
        "https://other.example/article",
    ):
        with pytest.raises(RequestFailure):
            policy.validate(url, allowed_hosts=("cdn.example",), resolve_dns=False)
    with pytest.raises(RequestFailure):
        policy.validate(
            "http://cdn.example/article",
            previous_url="https://cdn.example/start",
            resolve_dns=False,
        )


def test_transport_validates_every_redirect_and_drops_cross_origin_secrets() -> None:
    policy = SafeRemoteUrlPolicy(
        resolver=_resolver_for(
            {
                "publisher.example": ("8.8.8.8",),
                "cdn.example": ("1.1.1.1",),
            }
        )
    )
    transport = HttpTransport(
        cache_ttl=0,
        cache_capacity=0,
        options=HttpTransportOptions(remote_url_policy=policy),
    )
    pool = _Pool(
        [
            _Response(302, {"location": "https://cdn.example/article.xml"}),
            _Response(200, {"content-type": "application/xml"}),
        ]
    )
    transport._pool = pool

    response = transport._perform_request(
        _PreparedRequest(
            method="GET",
            full_url="https://publisher.example/start",
            headers={"Authorization": "Bearer secret", "Accept": "application/xml"},
        ),
        timeout=1,
    )

    assert response.status == 200
    assert pool.requests[1][1] == "/article.xml"
    assert "Authorization" not in pool.requests[1][2]
    assert pool.requests[1][2]["Accept"] == "application/xml"
    assert pool.requests[0][2]["Host"] == "publisher.example"
    assert pool.connections == [
        {
            "host": "8.8.8.8",
            "port": 443,
            "scheme": "https",
            "pool_kwargs": {
                "server_hostname": "publisher.example",
                "assert_hostname": "publisher.example",
            },
        },
        {
            "host": "1.1.1.1",
            "port": 443,
            "scheme": "https",
            "pool_kwargs": {
                "server_hostname": "cdn.example",
                "assert_hostname": "cdn.example",
            },
        },
    ]


def test_transport_rejects_public_to_private_redirect_before_second_request() -> None:
    policy = SafeRemoteUrlPolicy(
        resolver=_resolver_for(
            {
                "publisher.example": ("8.8.8.8",),
                "metadata.internal": ("169.254.169.254",),
            }
        )
    )
    transport = HttpTransport(
        cache_ttl=0,
        cache_capacity=0,
        options=HttpTransportOptions(remote_url_policy=policy),
    )
    pool = _Pool([_Response(302, {"location": "https://metadata.internal/latest"})])
    transport._pool = pool

    with pytest.raises(RequestFailure) as raised:
        transport._perform_request(
            _PreparedRequest(
                method="GET",
                full_url="https://publisher.example/start",
                headers={},
            ),
            timeout=1,
        )

    assert raised.value.error_category == RequestErrorCategory.UNSAFE_REDIRECT
    assert len(pool.requests) == 1


def test_transport_pins_the_validated_address_without_second_dns_lookup() -> None:
    resolver_calls = 0

    def rebinding_resolver(host: str, port: int, *, type: int):
        nonlocal resolver_calls
        resolver_calls += 1
        address = "8.8.8.8" if resolver_calls == 1 else "127.0.0.1"
        return [(socket.AF_INET, type, 6, "", (address, port))]

    transport = HttpTransport(
        cache_ttl=0,
        cache_capacity=0,
        options=HttpTransportOptions(
            remote_url_policy=SafeRemoteUrlPolicy(resolver=rebinding_resolver)
        ),
    )
    pool = _Pool([_Response(200, {"content-type": "text/plain"})])
    transport._pool = pool

    response = transport._perform_request(
        _PreparedRequest(
            method="GET",
            full_url="https://publisher.example/article",
            headers={},
        ),
        timeout=1,
    )

    assert response.status == 200
    assert resolver_calls == 1
    assert pool.connections[0]["host"] == "8.8.8.8"
    assert pool.requests[0][2]["Host"] == "publisher.example"


@pytest.mark.parametrize("status", (301, 302, 303, 307, 308))
@pytest.mark.parametrize(
    ("provider", "route", "source_host", "credential_header"),
    (
        ("elsevier", "xml_api", "api.elsevier.com", "X-ELS-APIKey"),
        ("wiley", "tdm_pdf", "api.wiley.com", "Wiley-TDM-Client-Token"),
        (
            "crossref",
            "metadata",
            "api.crossref.org",
            "CR-Clickthrough-Client-Token",
        ),
    ),
)
def test_catalog_credentials_are_removed_for_every_cross_origin_redirect_status(
    status: int,
    provider: str,
    route: str,
    source_host: str,
    credential_header: str,
) -> None:
    policy = SafeRemoteUrlPolicy(
        resolver=_resolver_for(
            {
                source_host: ("8.8.8.8",),
                "untrusted.example": ("1.1.1.1",),
            }
        )
    )
    transport = HttpTransport(
        cache_ttl=0,
        cache_capacity=0,
        options=HttpTransportOptions(remote_url_policy=policy),
    )
    pool = _Pool([_Response(status, {"location": "https://untrusted.example/file"})])
    transport._pool = pool
    request_policy = provider_request_policy(provider, route)
    # Explicitly admit the test redirect host so the test can observe header
    # stripping. Production catalog policies do not admit it.
    request_policy = HttpRequestPolicy(
        allowed_hosts=(*tuple(request_policy.allowed_hosts or ()), "untrusted.example"),
        sensitive_headers=request_policy.sensitive_headers,
    )
    pool.responses.append(_Response(200, {"content-type": "text/plain"}))

    transport._perform_request(
        _PreparedRequest(
            method="GET",
            full_url=f"https://{source_host}/start",
            headers={credential_header: "secret", "Accept": "*/*"},
            allowed_hosts=request_policy.allowed_hosts,
            sensitive_headers=request_policy.sensitive_headers,
        ),
        timeout=1,
    )

    assert credential_header not in pool.requests[1][2]
    assert pool.requests[1][2]["Accept"] == "*/*"


def test_catalog_credentials_are_preserved_for_same_origin_redirect() -> None:
    policy = SafeRemoteUrlPolicy(
        resolver=_resolver_for({"api.elsevier.com": ("8.8.8.8",)})
    )
    transport = HttpTransport(
        cache_ttl=0,
        cache_capacity=0,
        options=HttpTransportOptions(remote_url_policy=policy),
    )
    pool = _Pool(
        [
            _Response(302, {"location": "/content/article/final"}),
            _Response(200, {"content-type": "application/xml"}),
        ]
    )
    transport._pool = pool
    request_policy = provider_request_policy("elsevier", "xml_api")

    transport._perform_request(
        _PreparedRequest(
            method="GET",
            full_url="https://api.elsevier.com/content/article/start",
            headers={"X-ELS-APIKey": "secret"},
            allowed_hosts=request_policy.allowed_hosts,
            sensitive_headers=request_policy.sensitive_headers,
        ),
        timeout=1,
    )

    assert pool.requests[1][2]["X-ELS-APIKey"] == "secret"


def test_catalog_policy_rejects_undeclared_redirect_before_second_request() -> None:
    policy = SafeRemoteUrlPolicy(
        resolver=_resolver_for(
            {
                "api.elsevier.com": ("8.8.8.8",),
                "untrusted.example": ("1.1.1.1",),
            }
        )
    )
    transport = HttpTransport(
        cache_ttl=0,
        cache_capacity=0,
        options=HttpTransportOptions(remote_url_policy=policy),
    )
    pool = _Pool([_Response(302, {"location": "https://untrusted.example/steal"})])
    transport._pool = pool
    request_policy = provider_request_policy("elsevier", "xml_api")

    with pytest.raises(RequestFailure):
        transport._perform_request(
            _PreparedRequest(
                method="GET",
                full_url="https://api.elsevier.com/start",
                headers={"X-ELS-APIKey": "secret"},
                allowed_hosts=request_policy.allowed_hosts,
                sensitive_headers=request_policy.sensitive_headers,
            ),
            timeout=1,
        )

    assert len(pool.requests) == 1


def test_credentialed_request_policy_requires_host_allowlist() -> None:
    transport = HttpTransport(cache_ttl=0, cache_capacity=0)

    with pytest.raises(RequestFailure) as raised:
        transport.request(
            "GET",
            "https://api.elsevier.com/content/article",
            headers={"X-ELS-APIKey": "secret"},
            request_policy=HttpRequestPolicy(sensitive_headers=("x-els-apikey",)),
        )

    assert raised.value.error_category == RequestErrorCategory.UNSAFE_REDIRECT


def test_browser_guard_rejects_mixed_dns_and_public_to_private_redirect() -> None:
    policy = SafeRemoteUrlPolicy(
        resolver=_resolver_for(
            {
                "mixed.example": ("8.8.8.8", "127.0.0.1"),
                "publisher.example": ("8.8.8.8",),
                "metadata.internal": ("169.254.169.254",),
            }
        )
    )
    guard = BrowserNetworkGuard(
        allowed_hosts=("mixed.example", "publisher.example", "metadata.internal"),
        policy=policy,
    )

    mixed_route = mock.Mock()
    mixed_route.request.url = "https://mixed.example/article"
    mixed_route.request.redirected_from = None
    guard.route_handler(mixed_route)
    mixed_route.abort.assert_called_once()
    mixed_route.continue_.assert_not_called()

    redirect_route = mock.Mock()
    redirect_route.request.url = "https://metadata.internal/latest"
    redirect_route.request.redirected_from.url = "https://publisher.example/article"
    guard.route_handler(redirect_route)
    redirect_route.abort.assert_called_once()
    redirect_route.continue_.assert_not_called()


def test_browser_guard_rejects_allowlisted_cross_origin_request_with_credentials() -> (
    None
):
    guard = BrowserNetworkGuard(
        allowed_hosts=("publisher.example", "cdn.example"),
        policy=SafeRemoteUrlPolicy(
            resolver=_resolver_for(
                {
                    "publisher.example": ("8.8.8.8",),
                    "cdn.example": ("1.1.1.1",),
                }
            )
        ),
    )
    guard.set_credential_origin("https://publisher.example/article")
    route = mock.Mock()
    route.request.url = "https://cdn.example/figure.png"
    route.request.redirected_from = None

    guard.route_handler(route)

    route.abort.assert_called_once()
    route.continue_.assert_not_called()


def test_provider_request_policy_merges_base_and_catalog_allowed_hosts() -> None:
    policy = provider_request_policy(
        "elsevier",
        "xml_api",
        base=HttpRequestPolicy(
            allowed_hosts=("proxy.example",),
            sensitive_headers=("x-private-proxy-token",),
        ),
    )

    assert policy.allowed_hosts is not None
    assert "proxy.example" in policy.allowed_hosts
    assert "elsevier.com" in policy.allowed_hosts
    assert "x-private-proxy-token" in policy.sensitive_headers
    assert "x-els-apikey" in policy.sensitive_headers


def test_provider_request_policy_rejects_sensitive_route_without_hosts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    compiled = mock.Mock(
        provider="example",
        sensitive_headers=("Authorization",),
        hosts=(),
    )
    monkeypatch.setattr(
        provider_policy_module,
        "compile_route_execution_policy",
        lambda _provider, _route: compiled,
    )

    with pytest.raises(ValueError, match="no declared hosts"):
        provider_policy_module.provider_request_policy("example", "api")


def test_asset_stream_uses_catalog_sensitive_headers_on_redirect(
    tmp_path: Path,
) -> None:
    policy = SafeRemoteUrlPolicy(
        resolver=_resolver_for(
            {
                "api.elsevier.com": ("8.8.8.8",),
                "untrusted.example": ("1.1.1.1",),
            }
        )
    )
    transport = HttpTransport(
        cache_ttl=0,
        cache_capacity=0,
        options=HttpTransportOptions(remote_url_policy=policy),
    )
    pool = _Pool(
        [
            _StreamingResponse(
                302,
                {"location": "https://untrusted.example/file.bin"},
            ),
            _StreamingResponse(
                200,
                {
                    "content-type": "application/octet-stream",
                    "set-cookie": "candidate=ready; Path=/next; Secure",
                },
                b"asset",
            ),
        ]
    )
    transport._pool = pool
    session = PinnedAssetSession(
        transport,
        browser_cookies=None,
        seed_urls=None,
        headers={},
        allowed_hosts=("api.elsevier.com", "untrusted.example"),
        provider_name="elsevier",
    )
    destination = tmp_path / "asset.part"

    transport.stream_to_file(
        "GET",
        "https://api.elsevier.com/start",
        destination,
        headers={
            "X-ELS-APIKey": "secret",
            "Cookie": "manual=source-only",
            "Accept": "*/*",
        },
        request_policy=session.request_policy_for(
            "https://api.elsevier.com/start",
            max_response_bytes=16,
        ),
        on_response_headers=session.observe_response_headers,
        request_headers_provider=session.prepare_hop_headers,
    )

    assert destination.read_bytes() == b"asset"
    assert pool.requests[0][2]["Cookie"] == "manual=source-only"
    assert "X-ELS-APIKey" not in pool.requests[1][2]
    assert "Cookie" not in pool.requests[1][2]
    assert pool.requests[1][2]["Accept"] == "*/*"
    assert (
        session.request_headers_for("https://untrusted.example/next/asset", {})[
            "Cookie"
        ]
        == "candidate=ready"
    )


def test_seed_redirect_preserves_multiple_cookies_and_refreshes_next_hop() -> None:
    policy = SafeRemoteUrlPolicy(
        resolver=_resolver_for({"publisher.example": ("8.8.8.8",)})
    )
    transport = HttpTransport(
        cache_ttl=0,
        cache_capacity=0,
        options=HttpTransportOptions(remote_url_policy=policy),
    )
    redirect_headers = urllib3._collections.HTTPHeaderDict()
    redirect_headers.add("location", "/article/final")
    redirect_headers.add("set-cookie", "root=one; Path=/; Secure")
    redirect_headers.add("set-cookie", "article=two; Path=/article; Secure")
    pool = _Pool(
        [
            _StreamingResponse(302, redirect_headers),
            _StreamingResponse(200, {"content-type": "text/html"}, b"ready"),
        ]
    )
    transport._pool = pool
    session = PinnedAssetSession(
        transport,
        browser_cookies=None,
        seed_urls=["https://publisher.example/start"],
        headers={},
        allowed_hosts=("publisher.example",),
    )

    session.ensure_seeded()

    assert pool.requests[0][2].get("Cookie") is None
    assert pool.requests[1][2]["Cookie"] == "article=two; root=one"
    assert (
        session.request_headers_for("https://publisher.example/article/asset", {})[
            "Cookie"
        ]
        == "article=two; root=one"
    )


def test_seed_redirect_drops_catalog_secret_without_leaking_source_cookie() -> None:
    policy = SafeRemoteUrlPolicy(
        resolver=_resolver_for(
            {
                "api.elsevier.com": ("8.8.8.8",),
                "untrusted.example": ("1.1.1.1",),
            }
        )
    )
    transport = HttpTransport(
        cache_ttl=0,
        cache_capacity=0,
        options=HttpTransportOptions(remote_url_policy=policy),
    )
    pool = _Pool(
        [
            _StreamingResponse(
                302,
                {
                    "location": "https://untrusted.example/final",
                    "set-cookie": "source=only; Path=/; Secure",
                },
            ),
            _StreamingResponse(200, {"content-type": "text/html"}, b"ready"),
        ]
    )
    transport._pool = pool
    session = PinnedAssetSession(
        transport,
        browser_cookies=None,
        seed_urls=["https://api.elsevier.com/start"],
        headers={"X-ELS-APIKey": "secret"},
        allowed_hosts=("api.elsevier.com", "untrusted.example"),
        provider_name="elsevier",
    )

    session.ensure_seeded()

    assert "X-ELS-APIKey" not in pool.requests[1][2]
    assert "Cookie" not in pool.requests[1][2]
    assert (
        session.request_headers_for("https://api.elsevier.com/next", {})["Cookie"]
        == "source=only"
    )


def test_context_guard_rejects_borrowed_context_before_route_install() -> None:
    context = mock.Mock()
    context._paper_fetch_external_cdp_diagnostics = {
        "borrowed_existing_context": True,
    }
    guard = BrowserNetworkGuard(
        allowed_hosts=("publisher.example",),
        policy=SafeRemoteUrlPolicy(
            resolver=_resolver_for({"publisher.example": ("8.8.8.8",)})
        ),
    )

    with pytest.raises(RequestFailure):
        guard.install_on_context(context)

    context.route.assert_not_called()


def test_guarded_browser_request_redirect_rejects_private_hop_before_second_get() -> (
    None
):
    response = mock.Mock(
        status=302,
        url="https://publisher.example/start",
        headers={"location": "http://169.254.169.254/latest/meta-data"},
    )
    request_context = mock.Mock()
    request_context.get.return_value = response
    guard = BrowserNetworkGuard(
        allowed_hosts=("publisher.example", "169.254.169.254"),
        policy=SafeRemoteUrlPolicy(
            resolver=_resolver_for({"publisher.example": ("8.8.8.8",)})
        ),
    )

    with pytest.raises(RequestFailure):
        guarded_browser_request_get(
            request_context,
            "https://publisher.example/start",
            guard=guard,
            timeout_ms=1000,
        )

    request_context.get.assert_called_once()


def test_browser_origin_and_context_interceptor_fail_closed_contract() -> None:
    assert browser_policy.url_origin("ftp://publisher.example/file") is None
    assert browser_policy.url_origin("https://publisher.example:invalid/file") is None

    guard = BrowserNetworkGuard(
        allowed_hosts=("publisher.example",),
        policy=SafeRemoteUrlPolicy(
            resolver=_resolver_for({"publisher.example": ("8.8.8.8",)})
        ),
    )
    context = mock.Mock()
    installed: dict[str, object] = {}

    def install(pattern: str, handler: object) -> None:
        installed[pattern] = handler

    context.route.side_effect = install
    after_validation = mock.Mock()
    handler = guard.install_on_context(
        context,
        after_validation=after_validation,
    )

    assert installed == {"**/*": handler}
    safe_route = mock.Mock()
    safe_route.request.url = "https://publisher.example/article"
    safe_route.request.redirected_from = None
    handler(safe_route)
    after_validation.assert_called_once_with(safe_route)

    unsafe_route = mock.Mock()
    unsafe_route.request.url = "https://127.0.0.1/private"
    unsafe_route.request.redirected_from = None
    handler(unsafe_route)
    unsafe_route.abort.assert_called_once()

    default_context = mock.Mock()
    default_context.route.side_effect = install
    default_handler = guard.install_on_context(default_context)
    default_route = mock.Mock()
    default_route.request.url = "https://publisher.example/default"
    default_route.request.redirected_from = None
    default_handler(default_route)
    default_route.continue_.assert_called_once_with()

    unsupported = mock.Mock(route=None)
    with pytest.raises(RequestFailure, match="context-wide network interceptor"):
        guard.install_on_context(unsupported)

    broken = mock.Mock()
    broken.route.side_effect = RuntimeError("interceptor unavailable")
    with pytest.raises(RequestFailure, match="Unable to install"):
        guard.install_on_context(broken)


def test_browser_route_handler_continues_a_valid_request() -> None:
    guard = BrowserNetworkGuard(
        allowed_hosts=("publisher.example",),
        policy=SafeRemoteUrlPolicy(
            resolver=_resolver_for({"publisher.example": ("8.8.8.8",)})
        ),
    )
    route = mock.Mock()
    route.request.url = "https://publisher.example/article"
    route.request.redirected_from = None

    guard.route_handler(route)

    route.continue_.assert_called_once_with()
    route.abort.assert_not_called()


class _BrowserResponse:
    def __init__(
        self,
        *,
        status: object,
        url: str,
        headers: object,
        all_headers: object | None = None,
    ) -> None:
        self.status = status
        self.url = url
        self.headers = headers
        self._all_headers = all_headers
        self.disposed = False

    def all_headers(self) -> object:
        return self._all_headers

    def dispose(self) -> None:
        self.disposed = True


def test_guarded_browser_redirect_strips_cross_origin_sensitive_headers() -> None:
    first = _BrowserResponse(
        status=302,
        url="https://publisher.example/start",
        headers=lambda: {"Location": "https://cdn.example/article.xml"},
    )
    final = _BrowserResponse(
        status="not-an-integer",
        url="https://cdn.example/article.xml",
        headers=["not-a-mapping"],
        all_headers={"Content-Type": "application/xml"},
    )
    request_context = mock.Mock()
    request_context.get.side_effect = [first, final]
    guard = BrowserNetworkGuard(
        allowed_hosts=("publisher.example", "cdn.example"),
        policy=SafeRemoteUrlPolicy(
            resolver=_resolver_for(
                {
                    "publisher.example": ("8.8.8.8",),
                    "cdn.example": ("1.1.1.1",),
                }
            )
        ),
    )

    result = guarded_browser_request_get(
        request_context,
        "https://publisher.example/start",
        guard=guard,
        headers={
            "Authorization": "secret",
            "Cookie": "session=secret",
            "Proxy-Authorization": "secret",
            "Referer": "https://publisher.example/start",
            "Accept": "application/xml",
        },
        timeout_ms=1000,
    )

    assert result is final
    assert first.disposed
    redirected_headers = request_context.get.call_args_list[1].kwargs["headers"]
    assert redirected_headers == {"Accept": "application/xml"}


def test_guarded_browser_same_origin_redirect_keeps_headers_without_dispose() -> None:
    class ResponseWithoutDispose:
        status = 302
        url = "https://publisher.example/start"
        headers = {"location": "/final"}

    final = _BrowserResponse(
        status=200,
        url="https://publisher.example/final",
        headers={"content-type": "application/xml"},
    )
    request_context = mock.Mock()
    request_context.get.side_effect = [ResponseWithoutDispose(), final]
    guard = BrowserNetworkGuard(
        allowed_hosts=("publisher.example",),
        policy=SafeRemoteUrlPolicy(
            resolver=_resolver_for({"publisher.example": ("8.8.8.8",)})
        ),
    )

    result = guarded_browser_request_get(
        request_context,
        "https://publisher.example/start",
        guard=guard,
        headers={"Authorization": "secret", "Accept": "application/xml"},
        timeout_ms=1000,
    )

    assert result is final
    assert request_context.get.call_args_list[1].kwargs["headers"] == {
        "Authorization": "secret",
        "Accept": "application/xml",
    }


def test_guarded_browser_redirect_handles_missing_location_and_limit() -> None:
    missing_location = _BrowserResponse(
        status=302,
        url="https://publisher.example/start",
        headers={},
    )
    request_context = mock.Mock()
    request_context.get.return_value = missing_location
    guard = BrowserNetworkGuard(
        allowed_hosts=("publisher.example",),
        policy=SafeRemoteUrlPolicy(
            resolver=_resolver_for({"publisher.example": ("8.8.8.8",)})
        ),
    )

    assert (
        guarded_browser_request_get(
            request_context,
            "https://publisher.example/start",
            guard=guard,
            timeout_ms=1000,
        )
        is missing_location
    )

    limited = _BrowserResponse(
        status=307,
        url="https://publisher.example/start",
        headers={"location": "/again"},
    )
    request_context.get.return_value = limited
    with pytest.raises(RequestFailure, match="exceeded 0 redirects"):
        guarded_browser_request_get(
            request_context,
            "https://publisher.example/start",
            guard=guard,
            timeout_ms=1000,
            max_redirects=0,
        )


def test_hosts_from_urls_deduplicates_hosts_and_ignores_relative_urls() -> None:
    assert browser_policy.hosts_from_urls(
        (
            "https://Publisher.Example/a",
            "https://publisher.example/b",
            "/relative",
            "https://cdn.example/image.png",
        )
    ) == ("publisher.example", "cdn.example")
