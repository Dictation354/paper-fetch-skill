from __future__ import annotations

import socket
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path

import pytest

from paper_fetch.http import (
    HttpRequestPolicy,
    HttpStreamOptions,
    HttpTransportOptions,
    HttpTransport,
    RequestErrorCategory,
    RequestFailure,
    SafeRemoteUrlPolicy,
    _PreparedRequest,
    provider_request_policy,
)


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

    def request(self, method: str, url: str, *, headers, **_kwargs):
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
    assert pool.requests[1][1] == "https://cdn.example/article.xml"
    assert "Authorization" not in pool.requests[1][2]
    assert pool.requests[1][2]["Accept"] == "application/xml"
    assert "Host" not in pool.requests[0][2]
    assert pool.connections == []


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


def test_transport_validates_dns_then_uses_the_shared_hostname_pool() -> None:
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
    assert pool.connections == []
    assert pool.requests[0][1] == "https://publisher.example/article"
    assert "Host" not in pool.requests[0][2]


@pytest.mark.parametrize("status", (301, 302, 303, 307, 308))
def test_standard_sensitive_headers_are_removed_on_cross_origin_redirect(
    status: int,
) -> None:
    policy = SafeRemoteUrlPolicy(
        resolver=_resolver_for(
            {
                "publisher.example": ("8.8.8.8",),
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
    pool.responses.append(_Response(200, {"content-type": "text/plain"}))

    transport._perform_request(
        _PreparedRequest(
            method="GET",
            full_url="https://publisher.example/start",
            headers={
                "Authorization": "Bearer secret",
                "Cookie": "session=secret",
                "Accept": "*/*",
            },
        ),
        timeout=1,
    )

    assert "Authorization" not in pool.requests[1][2]
    assert "Cookie" not in pool.requests[1][2]
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


def test_provider_catalog_does_not_implicitly_restrict_public_redirect_hosts() -> None:
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
            _Response(302, {"location": "https://untrusted.example/file"}),
            _Response(200, {"content-type": "application/xml"}),
        ]
    )
    transport._pool = pool
    request_policy = provider_request_policy("elsevier", "xml_api")

    response = transport._perform_request(
        _PreparedRequest(
            method="GET",
            full_url="https://api.elsevier.com/start",
            headers={"Authorization": "Bearer secret"},
            allowed_hosts=request_policy.allowed_hosts,
            sensitive_headers=request_policy.sensitive_headers,
        ),
        timeout=1,
    )

    assert response.status == 200
    assert request_policy.allowed_hosts is None
    assert len(pool.requests) == 2
    assert "Authorization" not in pool.requests[1][2]


def test_credentialed_request_does_not_require_an_allowlist() -> None:
    policy = SafeRemoteUrlPolicy(
        resolver=_resolver_for({"api.elsevier.com": ("8.8.8.8",)})
    )
    transport = HttpTransport(
        cache_ttl=0,
        cache_capacity=0,
        options=HttpTransportOptions(remote_url_policy=policy),
    )
    transport._pool = _Pool([_StreamingResponse(200, {}, b"ok")])

    response = transport.request(
        "GET",
        "https://api.elsevier.com/content/article",
        headers={"X-ELS-APIKey": "secret"},
        request_policy=HttpRequestPolicy(sensitive_headers=("x-els-apikey",)),
    )

    assert response["status_code"] == 200


def test_provider_request_policy_preserves_only_explicit_host_and_header_limits() -> (
    None
):
    policy = provider_request_policy(
        "elsevier",
        "xml_api",
        base=HttpRequestPolicy(
            allowed_hosts=("proxy.example",),
            sensitive_headers=("x-private-proxy-token",),
        ),
    )

    assert policy.allowed_hosts == ("proxy.example",)
    assert policy.sensitive_headers == ("x-private-proxy-token",)


def test_stream_honors_an_explicit_allowlist_and_standard_header_stripping(
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
    destination = tmp_path / "asset.part"

    transport.stream_to_file(
        "GET",
        "https://api.elsevier.com/start",
        destination,
        headers={
            "Authorization": "Bearer secret",
            "Cookie": "manual=source-only",
            "Accept": "*/*",
        },
        options=HttpStreamOptions(
            request_policy=HttpRequestPolicy(
                allowed_hosts=("api.elsevier.com", "untrusted.example"),
                max_response_bytes=16,
                max_compressed_response_bytes=16,
            ),
        ),
    )

    assert destination.read_bytes() == b"asset"
    assert pool.requests[0][2]["Cookie"] == "manual=source-only"
    assert "Authorization" not in pool.requests[1][2]
    assert "Cookie" not in pool.requests[1][2]
    assert pool.requests[1][2]["Accept"] == "*/*"
