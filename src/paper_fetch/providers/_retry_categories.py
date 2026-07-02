"""Shared provider retryability categories."""

from __future__ import annotations

from ..http import RequestErrorCategory

DEFAULT_RETRYABLE_ASSET_ERROR_CATEGORIES = frozenset(
    {
        RequestErrorCategory.NETWORK_ERROR.value,
        RequestErrorCategory.TIMEOUT.value,
        RequestErrorCategory.TLS_ERROR.value,
        RequestErrorCategory.DNS_ERROR.value,
        RequestErrorCategory.CONNECTION_RESET.value,
        RequestErrorCategory.CONNECTION_CLOSED.value,
    }
)
NETWORK_RETRYABLE_REASON_TOKENS = (
    "network error",
    "timeout",
    "timed out",
    "ssl",
    "eof",
    "connection reset",
    "connection aborted",
    "connection broken",
    "remote end closed",
    "temporary failure",
)


__all__ = [
    "DEFAULT_RETRYABLE_ASSET_ERROR_CATEGORIES",
    "NETWORK_RETRYABLE_REASON_TOKENS",
]
