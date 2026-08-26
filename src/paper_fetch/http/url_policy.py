"""Shared remote-URL safety policy for HTTP and provider-owned redirects."""

from __future__ import annotations

import ipaddress
import socket
import urllib.parse
from dataclasses import dataclass
from typing import Any, TypeAlias
from collections.abc import Callable, Iterable, Sequence

from .cache import redact_url_for_cache
from .errors import RequestErrorCategory, RequestFailure

AddressInfo: TypeAlias = tuple[Any, ...]
Resolver: TypeAlias = Callable[..., Sequence[AddressInfo]]
DEFAULT_REMOTE_PORTS = frozenset({80, 443})


def _normalized_host(value: str | None) -> str:
    host = (value or "").strip().rstrip(".").lower()
    try:
        return host.encode("idna").decode("ascii")
    except UnicodeError:
        return ""


def _host_allowed(host: str, allowed_hosts: Iterable[str]) -> bool:
    for raw_allowed in allowed_hosts:
        allowed = _normalized_host(raw_allowed)
        if allowed and (host == allowed or host.endswith(f".{allowed}")):
            return True
    return False


def _unsafe_url_failure(url: str, reason: str) -> RequestFailure:
    return RequestFailure(
        None,
        f"Rejected unsafe remote URL ({reason}): {redact_url_for_cache(url)}",
        url=redact_url_for_cache(url),
        error_category=RequestErrorCategory.UNSAFE_REDIRECT,
    )


@dataclass(frozen=True)
class ValidatedRemoteUrl:
    url: str
    scheme: str
    host: str
    port: int
    addresses: tuple[str, ...] = ()


class SafeRemoteUrlPolicy:
    """Fail-closed URL validation shared by all network fetch paths."""

    def __init__(
        self,
        *,
        resolver: Resolver = socket.getaddrinfo,
        allowed_ports: Iterable[int] = DEFAULT_REMOTE_PORTS,
    ) -> None:
        self._resolver = resolver
        self._allowed_ports = frozenset(int(port) for port in allowed_ports)

    def validate(
        self,
        url: str,
        *,
        allowed_hosts: Iterable[str] | None = None,
        previous_url: str | None = None,
        resolve_dns: bool = True,
    ) -> ValidatedRemoteUrl:
        parsed = urllib.parse.urlsplit(str(url or "").strip())
        scheme = parsed.scheme.lower()
        host = _normalized_host(parsed.hostname)
        if scheme not in {"http", "https"} or not host:
            raise _unsafe_url_failure(url, "unsupported scheme or missing host")
        if parsed.username is not None or parsed.password is not None:
            raise _unsafe_url_failure(url, "userinfo is forbidden")
        try:
            port = parsed.port or (443 if scheme == "https" else 80)
        except ValueError as exc:
            raise _unsafe_url_failure(url, "invalid port") from exc
        if port not in self._allowed_ports:
            raise _unsafe_url_failure(url, f"port {port} is not allowed")
        if allowed_hosts is not None and not _host_allowed(host, allowed_hosts):
            raise _unsafe_url_failure(url, "host is outside the route allowlist")

        if previous_url:
            previous = urllib.parse.urlsplit(previous_url)
            if previous.scheme.lower() == "https" and scheme != "https":
                raise _unsafe_url_failure(url, "HTTPS to HTTP redirect downgrade")

        # IP literals never require DNS, so they must remain subject to the
        # public-address checks even in syntax-only validation paths.  This is
        # important for browser guards that perform the DNS lookup in a request
        # interceptor immediately before the browser sends the request.
        try:
            ipaddress.ip_address(host.split("%", 1)[0])
        except ValueError:
            is_ip_literal = False
        else:
            is_ip_literal = True
        addresses = (
            self._resolve_public_addresses(host, port)
            if resolve_dns or is_ip_literal
            else ()
        )
        return ValidatedRemoteUrl(
            url=urllib.parse.urlunsplit(
                (scheme, parsed.netloc, parsed.path or "/", parsed.query, "")
            ),
            scheme=scheme,
            host=host,
            port=port,
            addresses=addresses,
        )

    def _resolve_public_addresses(self, host: str, port: int) -> tuple[str, ...]:
        try:
            literal = ipaddress.ip_address(host.split("%", 1)[0])
        except ValueError:
            try:
                address_info = self._resolver(host, port, type=socket.SOCK_STREAM)
            except OSError as exc:
                raise RequestFailure(
                    None,
                    f"Unable to resolve remote host: {host}",
                    url=host,
                    error_category=RequestErrorCategory.DNS_ERROR,
                ) from exc
            raw_addresses = [
                str(item[4][0]).split("%", 1)[0]
                for item in address_info
                if len(item) >= 5 and item[4]
            ]
            if not raw_addresses:
                raise RequestFailure(
                    None,
                    f"Remote host resolved to no addresses: {host}",
                    url=host,
                    error_category=RequestErrorCategory.DNS_ERROR,
                ) from None
            addresses = tuple(
                dict.fromkeys(ipaddress.ip_address(value) for value in raw_addresses)
            )
        else:
            addresses = (literal,)

        unsafe = [
            str(address)
            for address in addresses
            if (
                not address.is_global
                or address.is_loopback
                or address.is_private
                or address.is_link_local
                or address.is_multicast
                or address.is_reserved
                or address.is_unspecified
            )
        ]
        if unsafe:
            raise _unsafe_url_failure(
                f"https://{host}/",
                f"non-public address {', '.join(unsafe)}",
            )
        return tuple(str(address) for address in addresses)


DEFAULT_SAFE_REMOTE_URL_POLICY = SafeRemoteUrlPolicy()


__all__ = [
    "DEFAULT_REMOTE_PORTS",
    "DEFAULT_SAFE_REMOTE_URL_POLICY",
    "SafeRemoteUrlPolicy",
    "ValidatedRemoteUrl",
]
