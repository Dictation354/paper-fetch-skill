from __future__ import annotations

import socket
from dataclasses import dataclass

import pytest

from paper_fetch.http import (
    HttpTransportOptions,
    HttpTransport,
    RequestErrorCategory,
    RequestFailure,
    SafeRemoteUrlPolicy,
    _PreparedRequest,
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

    def request(self, method: str, url: str, *, headers, **_kwargs):
        self.requests.append((method, url, dict(headers)))
        return self.responses.pop(0)


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
